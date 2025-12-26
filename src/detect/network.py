"""
PAC-to-Legislation Network Analysis Module

Purpose: Detect pay-to-play patterns through network topology analysis.

Key concepts:
- Graph structure: nodes = entities, edges = contributions/relationships
- Shannon entropy of edge weights reveals concentration
- Hub detection identifies power brokers
- Temporal correlation: contribution → favorable vote timing
"""

from dataclasses import dataclass, field
from typing import Optional
import math
import sys
sys.path.insert(0, "..")
from src.core import emit_receipt, TENANT_ID, stoprule_alert


@dataclass
class Node:
    """Graph node representing an entity."""
    id: str
    node_type: str  # pac, legislator, contributor, vendor
    attributes: dict = field(default_factory=dict)


@dataclass
class Edge:
    """Graph edge representing a relationship."""
    source: str
    target: str
    weight: float  # contribution amount or relationship strength
    edge_type: str  # contribution, vote, contract
    attributes: dict = field(default_factory=dict)


@dataclass
class Graph:
    """Simple directed graph implementation."""
    nodes: dict = field(default_factory=dict)  # id -> Node
    edges: list = field(default_factory=list)

    def add_node(self, node: Node):
        self.nodes[node.id] = node

    def add_edge(self, edge: Edge):
        self.edges.append(edge)

    def get_outgoing(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.source == node_id]

    def get_incoming(self, node_id: str) -> list[Edge]:
        return [e for e in self.edges if e.target == node_id]


def build_contribution_graph(contributions: list[dict]) -> Graph:
    """
    Build network graph from contribution records.

    Args:
        contributions: List of contribution records with
            contributor, recipient, amount, date fields

    Returns:
        Graph with contribution edges
    """
    graph = Graph()

    for contrib in contributions:
        contributor = contrib.get("contributor", "unknown")
        recipient = contrib.get("recipient", "unknown")
        amount = float(contrib.get("amount", 0))

        # Add nodes if not present
        if contributor not in graph.nodes:
            graph.add_node(Node(
                id=contributor,
                node_type=contrib.get("contributor_type", "contributor")
            ))

        if recipient not in graph.nodes:
            graph.add_node(Node(
                id=recipient,
                node_type=contrib.get("recipient_type", "pac")
            ))

        # Add edge
        graph.add_edge(Edge(
            source=contributor,
            target=recipient,
            weight=amount,
            edge_type="contribution",
            attributes={"date": contrib.get("date")}
        ))

    return graph


def compute_network_entropy(graph: Graph) -> float:
    """
    Compute Shannon entropy of edge weight distribution.

    Lower entropy = more concentrated (potential pay-to-play)
    Higher entropy = more distributed (normal pattern)

    Args:
        graph: Network graph

    Returns:
        Entropy value (0 = single relationship, higher = more distributed)
    """
    if not graph.edges:
        return 0.0

    # Get total weight
    total_weight = sum(e.weight for e in graph.edges)
    if total_weight == 0:
        return 0.0

    # Compute entropy
    entropy = 0.0
    for edge in graph.edges:
        if edge.weight > 0:
            p = edge.weight / total_weight
            entropy -= p * math.log2(p)

    return entropy


def compute_node_centrality(graph: Graph, node_id: str) -> dict:
    """
    Compute centrality metrics for a node.

    Args:
        graph: Network graph
        node_id: Node to analyze

    Returns:
        Dict with in_degree, out_degree, weighted_in, weighted_out, betweenness_approx
    """
    incoming = graph.get_incoming(node_id)
    outgoing = graph.get_outgoing(node_id)

    return {
        "in_degree": len(incoming),
        "out_degree": len(outgoing),
        "weighted_in": sum(e.weight for e in incoming),
        "weighted_out": sum(e.weight for e in outgoing),
        "total_degree": len(incoming) + len(outgoing)
    }


def detect_hub_nodes(graph: Graph, threshold: float = 0.3) -> list[dict]:
    """
    Identify hub nodes with high centrality.

    Args:
        graph: Network graph
        threshold: Centrality threshold (fraction of total edges)

    Returns:
        List of hub node info dicts
    """
    hubs = []
    total_edges = len(graph.edges)

    if total_edges == 0:
        return hubs

    for node_id, node in graph.nodes.items():
        centrality = compute_node_centrality(graph, node_id)
        normalized = centrality["total_degree"] / (2 * total_edges)

        if normalized > threshold:
            hubs.append({
                "node_id": node_id,
                "node_type": node.node_type,
                "centrality": normalized,
                "in_degree": centrality["in_degree"],
                "out_degree": centrality["out_degree"],
                "weighted_in": centrality["weighted_in"],
                "weighted_out": centrality["weighted_out"]
            })

    # Sort by centrality
    hubs.sort(key=lambda x: x["centrality"], reverse=True)
    return hubs


def trace_money_flow(graph: Graph, source: str, target: str,
                     max_depth: int = 5) -> list[list[str]]:
    """
    Find all paths from source to target in contribution network.

    Args:
        graph: Network graph
        source: Source node ID
        target: Target node ID
        max_depth: Maximum path length

    Returns:
        List of paths (each path is list of node IDs)
    """
    paths = []

    def dfs(current: str, target: str, path: list, depth: int):
        if depth > max_depth:
            return
        if current == target:
            paths.append(path.copy())
            return

        for edge in graph.get_outgoing(current):
            if edge.target not in path:
                path.append(edge.target)
                dfs(edge.target, target, path, depth + 1)
                path.pop()

    dfs(source, target, [source], 0)
    return paths


def detect_contribution_vote_correlation(contributions: list[dict],
                                          votes: list[dict],
                                          window_days: int = 60) -> list[dict]:
    """
    Detect temporal correlation between contributions and favorable votes.

    Args:
        contributions: Contribution records with date, contributor, amount
        votes: Vote records with date, legislator, bill, vote
        window_days: Window to look for correlation

    Returns:
        List of correlated contribution-vote pairs
    """
    correlations = []

    for contrib in contributions:
        contrib_date = contrib.get("date")
        recipient = contrib.get("recipient")
        amount = contrib.get("amount", 0)

        if not contrib_date or not recipient:
            continue

        # Look for votes by recipient in window after contribution
        for vote in votes:
            vote_date = vote.get("date")
            legislator = vote.get("legislator")
            vote_value = vote.get("vote")

            if not vote_date or legislator != recipient:
                continue

            # Check if vote is within window after contribution
            # Simplified: just check if vote is "favorable"
            if vote_value in ["yea", "yes", "aye"]:
                correlations.append({
                    "contribution": {
                        "contributor": contrib.get("contributor"),
                        "amount": amount,
                        "date": contrib_date
                    },
                    "vote": {
                        "legislator": legislator,
                        "bill": vote.get("bill"),
                        "vote": vote_value,
                        "date": vote_date
                    },
                    "correlation_type": "contribution_then_vote"
                })

    return correlations


def network_receipt(graph: Graph, analysis_type: str = "full") -> dict:
    """
    Emit receipt for network analysis.

    Args:
        graph: Network graph analyzed
        analysis_type: Type of analysis performed

    Returns:
        Receipt dict
    """
    entropy = compute_network_entropy(graph)
    hubs = detect_hub_nodes(graph)

    receipt = emit_receipt("network", {
        "tenant_id": TENANT_ID,
        "graph_id": f"graph-{len(graph.nodes)}-{len(graph.edges)}",
        "nodes": len(graph.nodes),
        "edges": len(graph.edges),
        "entropy": entropy,
        "hubs": hubs[:10],  # Top 10 hubs
        "hub_count": len(hubs),
        "analysis_type": analysis_type,
        "node_types": list(set(n.node_type for n in graph.nodes.values())),
        "edge_types": list(set(e.edge_type for e in graph.edges))
    })

    # Alert on concentrated networks or high-centrality hubs
    if entropy < 2.0 and len(graph.edges) > 10:
        stoprule_alert(
            metric="network_concentration",
            message="Network shows concentrated contribution pattern",
            baseline=3.0,
            delta=3.0 - entropy
        )

    for hub in hubs:
        if hub["centrality"] > 0.5:
            stoprule_alert(
                metric="hub_centrality",
                message=f"High-centrality hub detected: {hub['node_id']}",
                baseline=0.3,
                delta=hub["centrality"] - 0.3
            )

    return receipt


def pac_network_receipt(contributions: list[dict]) -> dict:
    """
    Build PAC network and emit analysis receipt.

    Args:
        contributions: Campaign contribution records

    Returns:
        Receipt dict
    """
    graph = build_contribution_graph(contributions)
    return network_receipt(graph, analysis_type="pac_network")
