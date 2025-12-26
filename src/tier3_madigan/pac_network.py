"""
Tier 3 Madigan: PAC Network Analysis

Key entities from case:
- Friends of Michael J Madigan #665: $6.1M cash on hand
- ComEd (via executives): contributor
- Doherty, Shaw Decremer: intermediaries
- No-work recipients: Olivo, Nice, Acevedo
"""

from typing import Optional
from dataclasses import dataclass, field
import sys
sys.path.insert(0, "../..")
from src.core import emit_receipt, TENANT_ID, stoprule_alert
from src.detect.network import (
    Graph, Node, Edge, build_contribution_graph,
    compute_network_entropy, detect_hub_nodes, trace_money_flow
)


# Known entities from Madigan case
KNOWN_ENTITIES = {
    "pacs": {
        "friends_of_madigan": {
            "committee_id": "665",
            "name": "Friends of Michael J Madigan",
            "cash_on_hand": 6_100_000,
            "role": "target"
        }
    },
    "contributors": {
        "comed": {
            "name": "ComEd/Exelon executives",
            "role": "contributor",
            "dpa_fine": 200_000_000
        }
    },
    "intermediaries": {
        "doherty": {
            "name": "Doherty firm",
            "role": "intermediary",
            "contract_type": "legal_consulting"
        },
        "shaw_decremer": {
            "name": "Shaw Decremer",
            "role": "intermediary"
        }
    },
    "recipients": {
        "olivo": {"name": "Olivo", "monthly": 4000, "role": "no_work"},
        "nice": {"name": "Nice", "monthly": 5000, "role": "no_work"},
        "acevedo": {"name": "Acevedo", "monthly": 5000, "role": "no_work"}
    }
}


def build_pac_network(contributions: list[dict],
                       include_known: bool = True) -> Graph:
    """
    Build PAC contribution network.

    Args:
        contributions: Contribution records
        include_known: Whether to seed with known Madigan entities

    Returns:
        Network graph
    """
    graph = build_contribution_graph(contributions)

    if include_known:
        # Add known entities as nodes if not present
        for category, entities in KNOWN_ENTITIES.items():
            for entity_id, info in entities.items():
                if entity_id not in graph.nodes:
                    graph.add_node(Node(
                        id=entity_id,
                        node_type=info.get("role", category),
                        attributes=info
                    ))

    return graph


def compute_pac_entropy(contributions: list[dict]) -> dict:
    """
    Compute PAC network entropy metrics.

    Args:
        contributions: Contribution records

    Returns:
        Entropy analysis dict
    """
    graph = build_pac_network(contributions)
    entropy = compute_network_entropy(graph)
    hubs = detect_hub_nodes(graph, threshold=0.2)

    # Classify entropy level
    if entropy < 2.0:
        classification = "highly_concentrated"
        severity = "critical"
    elif entropy < 3.0:
        classification = "moderately_concentrated"
        severity = "high"
    elif entropy < 4.0:
        classification = "normal_concentration"
        severity = "medium"
    else:
        classification = "well_distributed"
        severity = "low"

    return {
        "entropy": entropy,
        "classification": classification,
        "severity": severity,
        "hub_count": len(hubs),
        "top_hubs": hubs[:5],
        "node_count": len(graph.nodes),
        "edge_count": len(graph.edges)
    }


def detect_pac_clusters(contributions: list[dict]) -> list[dict]:
    """
    Detect clusters of related PAC activity.

    Args:
        contributions: Contribution records

    Returns:
        List of detected clusters
    """
    clusters = []

    # Group by contributor
    by_contributor = {}
    for c in contributions:
        contrib = c.get("contributor", "")
        if contrib not in by_contributor:
            by_contributor[contrib] = []
        by_contributor[contrib].append(c)

    # Find contributors giving to multiple PACs
    for contributor, contribs in by_contributor.items():
        recipients = set(c.get("recipient") for c in contribs)
        if len(recipients) > 3:
            total = sum(c.get("amount", 0) for c in contribs)
            clusters.append({
                "cluster_type": "multi_pac_contributor",
                "contributor": contributor,
                "recipient_count": len(recipients),
                "total_amount": total,
                "recipients": list(recipients)
            })

    # Group by recipient
    by_recipient = {}
    for c in contributions:
        recip = c.get("recipient", "")
        if recip not in by_recipient:
            by_recipient[recip] = []
        by_recipient[recip].append(c)

    # Find PACs with many contributors
    for recipient, contribs in by_recipient.items():
        contributors = set(c.get("contributor") for c in contribs)
        if len(contributors) > 10:
            total = sum(c.get("amount", 0) for c in contribs)
            clusters.append({
                "cluster_type": "multi_contributor_pac",
                "recipient": recipient,
                "contributor_count": len(contributors),
                "total_amount": total,
                "top_contributors": sorted(
                    contributors,
                    key=lambda x: sum(c.get("amount", 0) for c in contribs
                                      if c.get("contributor") == x),
                    reverse=True
                )[:5]
            })

    return clusters


def trace_comed_flow(contributions: list[dict]) -> list[dict]:
    """
    Trace money flow from ComEd-related entities.

    Args:
        contributions: Contribution records

    Returns:
        List of traced flows
    """
    graph = build_pac_network(contributions, include_known=True)

    flows = []

    # Look for paths from ComEd to Madigan
    comed_ids = [k for k, v in KNOWN_ENTITIES["contributors"].items()]
    madigan_ids = [k for k, v in KNOWN_ENTITIES["pacs"].items()]

    for source in comed_ids:
        for target in madigan_ids:
            paths = trace_money_flow(graph, source, target)
            for path in paths:
                path_edges = []
                for i in range(len(path) - 1):
                    edges = [e for e in graph.edges
                             if e.source == path[i] and e.target == path[i+1]]
                    if edges:
                        path_edges.append({
                            "from": path[i],
                            "to": path[i+1],
                            "amount": edges[0].weight
                        })

                if path_edges:
                    flows.append({
                        "source": source,
                        "target": target,
                        "path": path,
                        "path_length": len(path),
                        "edges": path_edges,
                        "total_flow": sum(e.get("amount", 0) for e in path_edges)
                    })

    return flows


def pac_network_receipt(contributions: list[dict]) -> dict:
    """
    Emit receipt for PAC network analysis.

    Args:
        contributions: Contribution records

    Returns:
        Receipt dict
    """
    entropy_analysis = compute_pac_entropy(contributions)
    clusters = detect_pac_clusters(contributions)
    flows = trace_comed_flow(contributions)

    total_amount = sum(c.get("amount", 0) for c in contributions)

    receipt = emit_receipt("tier3", {
        "tenant_id": TENANT_ID,
        "finding_type": "pac_network_analysis",
        "network_path": "pac_contribution_graph",
        "confidence": 0.85 if entropy_analysis["severity"] in ["critical", "high"] else 0.5,
        "pac_connections": {
            "entropy": entropy_analysis["entropy"],
            "classification": entropy_analysis["classification"],
            "hub_count": entropy_analysis["hub_count"],
            "top_hubs": [h["node_id"] for h in entropy_analysis["top_hubs"]]
        },
        "clusters_detected": len(clusters),
        "comed_flows_traced": len(flows),
        "total_contribution_amount": total_amount,
        "node_count": entropy_analysis["node_count"],
        "edge_count": entropy_analysis["edge_count"],
        "severity": entropy_analysis["severity"]
    })

    # Alert on concentrated networks
    if entropy_analysis["severity"] in ["critical", "high"]:
        stoprule_alert(
            metric="pac_concentration",
            message=f"PAC network {entropy_analysis['classification']}: entropy={entropy_analysis['entropy']:.2f}",
            baseline=3.0,
            delta=3.0 - entropy_analysis["entropy"]
        )

    # Alert on ComEd flow detection
    if flows:
        stoprule_alert(
            metric="comed_flow",
            message=f"Detected {len(flows)} money flow paths from ComEd entities",
            baseline=0,
            delta=len(flows)
        )

    return receipt
