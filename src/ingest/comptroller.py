"""
Illinois Comptroller Warehouse Ingestion

Source: Illinois Comptroller Warehouse
Access: Bulk download (Access/Excel)
Data: 9,200+ annual financial reports FY2000-2024
Fields: revenues, expenditures, fund_balances, debt
"""

from typing import Optional
import sys
sys.path.insert(0, "../..")
from src.core import emit_receipt, dual_hash, TENANT_ID


# Warehouse base URLs and configurations
COMPTROLLER_BASE = "https://illinoiscomptroller.gov/financial-data"
WAREHOUSE_FORMATS = ["xlsx", "csv", "access"]


def fetch_annual_reports(fiscal_year: int,
                          entity_type: str = "municipality") -> dict:
    """
    Fetch annual financial report data.

    Args:
        fiscal_year: Fiscal year (e.g., 2024)
        entity_type: Type of government entity

    Returns:
        Dict with fetched data and metadata
    """
    # Stub implementation - would make actual HTTP request
    return {
        "fiscal_year": fiscal_year,
        "entity_type": entity_type,
        "records": [],
        "source_url": f"{COMPTROLLER_BASE}/afr/{fiscal_year}",
        "format": "xlsx"
    }


def parse_financial_report(data: bytes, format: str = "xlsx") -> list[dict]:
    """
    Parse financial report data.

    Args:
        data: Raw report data
        format: Data format (xlsx, csv, access)

    Returns:
        List of parsed records
    """
    # Stub - would parse actual Excel/CSV data
    return []


def extract_dolton_financials(reports: list[dict]) -> dict:
    """
    Extract Dolton-specific financial data.

    Args:
        reports: Annual financial reports

    Returns:
        Dolton financial summary
    """
    dolton_reports = [r for r in reports
                      if r.get("entity", "").lower() == "dolton"]

    if not dolton_reports:
        return {
            "entity": "dolton",
            "found": False,
            "reports": []
        }

    # Extract key metrics
    revenues = sum(r.get("revenues", 0) for r in dolton_reports)
    expenditures = sum(r.get("expenditures", 0) for r in dolton_reports)
    fund_balance = dolton_reports[-1].get("fund_balance", 0) if dolton_reports else 0

    return {
        "entity": "dolton",
        "found": True,
        "reports": dolton_reports,
        "total_revenues": revenues,
        "total_expenditures": expenditures,
        "current_fund_balance": fund_balance,
        "deficit": expenditures - revenues if expenditures > revenues else 0
    }


def ingest_comptroller(fiscal_years: list[int] = None,
                        entity_filter: str = None) -> dict:
    """
    Main ingestion function for Comptroller Warehouse.

    Args:
        fiscal_years: List of years to fetch (default: last 5)
        entity_filter: Optional entity name filter

    Returns:
        Ingestion result with receipt
    """
    if fiscal_years is None:
        fiscal_years = list(range(2020, 2025))

    all_records = []
    for year in fiscal_years:
        result = fetch_annual_reports(year)
        all_records.extend(result.get("records", []))

    # Apply filter
    if entity_filter:
        all_records = [r for r in all_records
                       if entity_filter.lower() in r.get("entity", "").lower()]

    # Compute hash of ingested data
    data_hash = dual_hash(str(all_records).encode())

    receipt = emit_receipt("ingest", {
        "tenant_id": TENANT_ID,
        "source": "illinois_comptroller_warehouse",
        "source_type": "bulk_download",
        "records_count": len(all_records),
        "payload_hash": data_hash,
        "fiscal_years": fiscal_years,
        "entity_filter": entity_filter,
        "fields": ["revenues", "expenditures", "fund_balances", "debt"]
    })

    return {
        "receipt": receipt,
        "records": all_records,
        "count": len(all_records)
    }
