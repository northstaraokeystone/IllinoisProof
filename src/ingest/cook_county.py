"""
Cook County Open Data (Socrata) Ingestion

Source: Cook County Open Data Portal
Access: Socrata REST API
Data: Property, budget, court records
Rate Limit: 1000/query with pagination
"""

from typing import Optional
import sys
sys.path.insert(0, "../..")
from src.core import emit_receipt, dual_hash, TENANT_ID


# Socrata API configuration
SOCRATA_BASE = "https://datacatalog.cookcountyil.gov/resource"
SOCRATA_DATASETS = {
    "property": "u553-pqmu",
    "budget": "8a4c-ht6n",
    "court_cases": "5cd7-aqxn",
    "vendor_payments": "pdpd-t9rp"
}
DEFAULT_LIMIT = 1000


def build_query(dataset_id: str,
                select: list[str] = None,
                where: str = None,
                limit: int = None,
                offset: int = None) -> str:
    """
    Build Socrata API query URL.

    Args:
        dataset_id: Socrata dataset identifier
        select: Fields to select
        where: Filter condition (SoQL)
        limit: Max records to return
        offset: Pagination offset

    Returns:
        Query URL string
    """
    url = f"{SOCRATA_BASE}/{dataset_id}.json?"

    params = []
    if select:
        params.append(f"$select={','.join(select)}")
    if where:
        params.append(f"$where={where}")
    if limit:
        params.append(f"$limit={limit}")
    if offset:
        params.append(f"$offset={offset}")

    return url + "&".join(params)


def fetch_dataset(dataset_id: str,
                   where: str = None,
                   limit: int = None) -> list[dict]:
    """
    Fetch data from Socrata dataset.

    Args:
        dataset_id: Dataset identifier
        where: Filter condition
        limit: Max records

    Returns:
        List of records
    """
    # Stub implementation - would make HTTP request
    url = build_query(dataset_id, where=where, limit=limit or DEFAULT_LIMIT)
    return []


def fetch_dolton_property(limit: int = None) -> list[dict]:
    """
    Fetch Dolton property records.

    Args:
        limit: Max records

    Returns:
        Property records for Dolton
    """
    return fetch_dataset(
        SOCRATA_DATASETS["property"],
        where="municipality='DOLTON'",
        limit=limit
    )


def fetch_dolton_court_cases(limit: int = None) -> list[dict]:
    """
    Fetch court cases related to Dolton.

    Args:
        limit: Max records

    Returns:
        Court case records
    """
    return fetch_dataset(
        SOCRATA_DATASETS["court_cases"],
        where="municipality='DOLTON' OR defendant LIKE '%Dolton%'",
        limit=limit
    )


def fetch_vendor_payments(municipality: str = None,
                           limit: int = None) -> list[dict]:
    """
    Fetch vendor payment records.

    Args:
        municipality: Optional municipality filter
        limit: Max records

    Returns:
        Vendor payment records
    """
    where = f"municipality='{municipality}'" if municipality else None
    return fetch_dataset(
        SOCRATA_DATASETS["vendor_payments"],
        where=where,
        limit=limit
    )


def ingest_cook_county(datasets: list[str] = None,
                        municipality: str = None,
                        limit: int = None) -> dict:
    """
    Main ingestion function for Cook County Open Data.

    Args:
        datasets: List of dataset names to fetch
        municipality: Optional municipality filter
        limit: Max records per dataset

    Returns:
        Ingestion result with receipt
    """
    if datasets is None:
        datasets = list(SOCRATA_DATASETS.keys())

    all_records = {}
    total_count = 0

    for dataset_name in datasets:
        if dataset_name not in SOCRATA_DATASETS:
            continue

        dataset_id = SOCRATA_DATASETS[dataset_name]

        if municipality:
            where = f"municipality='{municipality}'"
        else:
            where = None

        records = fetch_dataset(dataset_id, where=where, limit=limit)
        all_records[dataset_name] = records
        total_count += len(records)

    # Compute hash
    data_hash = dual_hash(str(all_records).encode())

    receipt = emit_receipt("ingest", {
        "tenant_id": TENANT_ID,
        "source": "cook_county_open_data",
        "source_type": "socrata_api",
        "records_count": total_count,
        "payload_hash": data_hash,
        "datasets": datasets,
        "municipality_filter": municipality,
        "rate_limit": "1000/query"
    })

    return {
        "receipt": receipt,
        "records": all_records,
        "count": total_count
    }
