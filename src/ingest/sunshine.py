"""
Illinois Sunshine Campaign Finance Ingestion

Source: Illinois Sunshine (State Board of Elections)
Access: REST API
Data: 2.3M+ contributions since 1994
Key Committee: Friends of Michael J Madigan #665 ($6.1M cash)
"""

from typing import Optional
import sys
sys.path.insert(0, "../..")
from src.core import emit_receipt, dual_hash, TENANT_ID


# Illinois Sunshine API configuration
SUNSHINE_BASE = "https://illinoissunshine.org/api"
SUNSHINE_ENDPOINTS = {
    "committees": "/committees/",
    "contributions": "/contributions/",
    "expenditures": "/expenditures/",
    "receipts": "/receipts/"
}

# Key committees from case
KNOWN_COMMITTEES = {
    "665": {
        "name": "Friends of Michael J Madigan",
        "cash_on_hand": 6_100_000,
        "role": "target"
    }
}


def fetch_committee(committee_id: str) -> dict:
    """
    Fetch committee details.

    Args:
        committee_id: Committee ID number

    Returns:
        Committee record
    """
    # Stub implementation
    if committee_id in KNOWN_COMMITTEES:
        return {
            "committee_id": committee_id,
            **KNOWN_COMMITTEES[committee_id]
        }
    return {}


def fetch_contributions(committee_id: str = None,
                         contributor: str = None,
                         min_amount: float = None,
                         max_amount: float = None,
                         date_from: str = None,
                         date_to: str = None,
                         limit: int = 1000) -> list[dict]:
    """
    Fetch contribution records.

    Args:
        committee_id: Filter by recipient committee
        contributor: Filter by contributor name
        min_amount: Minimum contribution amount
        max_amount: Maximum contribution amount
        date_from: Start date filter
        date_to: End date filter
        limit: Max records

    Returns:
        List of contribution records
    """
    # Stub implementation
    return []


def fetch_expenditures(committee_id: str = None,
                        payee: str = None,
                        limit: int = 1000) -> list[dict]:
    """
    Fetch expenditure records.

    Args:
        committee_id: Filter by committee
        payee: Filter by payee name
        limit: Max records

    Returns:
        List of expenditure records
    """
    # Stub implementation
    return []


def fetch_madigan_contributions(limit: int = None) -> list[dict]:
    """
    Fetch contributions to Madigan committee.

    Args:
        limit: Max records

    Returns:
        Contribution records
    """
    return fetch_contributions(committee_id="665", limit=limit)


def search_comed_contributions(limit: int = None) -> list[dict]:
    """
    Search for ComEd-related contributions.

    Args:
        limit: Max records

    Returns:
        Contribution records
    """
    # Search by various ComEd-related entities
    searches = [
        "ComEd",
        "Commonwealth Edison",
        "Exelon"
    ]

    all_contributions = []
    for search_term in searches:
        contribs = fetch_contributions(contributor=search_term, limit=limit)
        all_contributions.extend(contribs)

    return all_contributions


def build_contribution_network(committee_ids: list[str]) -> dict:
    """
    Build network of contributions between committees.

    Args:
        committee_ids: List of committee IDs to analyze

    Returns:
        Network structure dict
    """
    nodes = {}
    edges = []

    for cid in committee_ids:
        committee = fetch_committee(cid)
        if committee:
            nodes[cid] = committee

        contributions = fetch_contributions(committee_id=cid)
        for contrib in contributions:
            edges.append({
                "source": contrib.get("contributor"),
                "target": cid,
                "amount": contrib.get("amount"),
                "date": contrib.get("date")
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges)
    }


def ingest_sunshine(committee_ids: list[str] = None,
                     include_comed: bool = True,
                     limit: int = None) -> dict:
    """
    Main ingestion function for Illinois Sunshine.

    Args:
        committee_ids: List of committee IDs to fetch
        include_comed: Whether to include ComEd search
        limit: Max records per query

    Returns:
        Ingestion result with receipt
    """
    if committee_ids is None:
        committee_ids = list(KNOWN_COMMITTEES.keys())

    all_records = {
        "committees": [],
        "contributions": [],
        "expenditures": []
    }

    for cid in committee_ids:
        committee = fetch_committee(cid)
        if committee:
            all_records["committees"].append(committee)

        contribs = fetch_contributions(committee_id=cid, limit=limit)
        all_records["contributions"].extend(contribs)

        expends = fetch_expenditures(committee_id=cid, limit=limit)
        all_records["expenditures"].extend(expends)

    if include_comed:
        comed_contribs = search_comed_contributions(limit=limit)
        all_records["contributions"].extend(comed_contribs)

    total_count = (len(all_records["committees"]) +
                   len(all_records["contributions"]) +
                   len(all_records["expenditures"]))

    # Compute hash
    data_hash = dual_hash(str(all_records).encode())

    receipt = emit_receipt("ingest", {
        "tenant_id": TENANT_ID,
        "source": "illinois_sunshine",
        "source_type": "rest_api",
        "records_count": total_count,
        "payload_hash": data_hash,
        "committee_ids": committee_ids,
        "include_comed_search": include_comed,
        "fields": ["committee_id", "contributor", "amount", "date"]
    })

    return {
        "receipt": receipt,
        "records": all_records,
        "count": total_count
    }
