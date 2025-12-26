"""
IDES Dashboard Data Ingestion

Source: IDES UI Dashboard
Access: Web scraping (limited public data)
Data: Aggregate claims, payments (no individual-level data)
Fields: weekly_claims, payments_total
"""

from typing import Optional
import sys
sys.path.insert(0, "../..")
from src.core import emit_receipt, dual_hash, TENANT_ID


# IDES public data sources
IDES_DASHBOARD_URL = "https://ides.illinois.gov/resources/labor-market-information.html"
DOL_ETA_227_URL = "https://oui.doleta.gov/unemploy/DataDashboard.asp"

# Known statistics from Auditor General
KNOWN_STATS = {
    "total_overpayments": 5_240_000_000,
    "recovered": 511_700_000,
    "non_recoverable": 2_800_000_000,
    "letters_sent": 174_685,
    "waiver_requests": 67_678,
    "waiver_denial_rate": 0.62,
    "average_overpayment": 5_505
}


def fetch_weekly_claims(start_date: str = None,
                         end_date: str = None) -> list[dict]:
    """
    Fetch weekly initial claims data.

    Args:
        start_date: Start of date range
        end_date: End of date range

    Returns:
        List of weekly claims records
    """
    # Stub implementation - would scrape dashboard
    return []


def fetch_payments_total(period: str = "weekly") -> list[dict]:
    """
    Fetch aggregate payment totals.

    Args:
        period: Aggregation period (weekly, monthly)

    Returns:
        List of payment records
    """
    # Stub implementation
    return []


def fetch_dol_eta_227(state: str = "IL",
                       quarters: list[str] = None) -> list[dict]:
    """
    Fetch DOL ETA 227 quarterly reports.

    Args:
        state: State code
        quarters: List of quarters (e.g., ["2020Q2", "2020Q3"])

    Returns:
        List of quarterly report records
    """
    # Stub implementation - would fetch from DOL
    return []


def fetch_auditor_findings() -> dict:
    """
    Get Auditor General findings (from PDF extraction).

    Returns:
        Structured findings data
    """
    # Return known statistics
    return {
        "source": "auditor_general_report",
        "findings": KNOWN_STATS,
        "crossmatch_gaps": {
            "prison_registry": {
                "gap_start": "2020-03-01",
                "gap_end": "2021-09-30",
                "estimated_fraud": 40_500_000
            },
            "death_master": {
                "gap_start": "2020-03-01",
                "gap_end": "2021-09-30",
                "estimated_fraud": 6_000_000
            },
            "ndnh": {
                "gap_start": "2020-03-01",
                "gap_end": "2021-09-30",
                "estimated_fraud": 600_000
            }
        },
        "methodology": {
            "sample_size": "174,685 overpayment letters",
            "error_rate": "estimated 54% identity theft"
        }
    }


def fetch_trust_fund_reports(fiscal_years: list[int] = None) -> list[dict]:
    """
    Fetch UI Trust Fund reports.

    Args:
        fiscal_years: Years to fetch

    Returns:
        Trust fund status records
    """
    # Stub implementation
    return []


def ingest_ides(data_types: list[str] = None) -> dict:
    """
    Main ingestion function for IDES data.

    Args:
        data_types: Types of data to fetch
            ("claims", "payments", "eta227", "auditor", "trust_fund")

    Returns:
        Ingestion result with receipt
    """
    if data_types is None:
        data_types = ["claims", "payments", "auditor"]

    all_records = {}

    if "claims" in data_types:
        all_records["weekly_claims"] = fetch_weekly_claims()

    if "payments" in data_types:
        all_records["payments"] = fetch_payments_total()

    if "eta227" in data_types:
        all_records["eta227"] = fetch_dol_eta_227()

    if "auditor" in data_types:
        all_records["auditor_findings"] = fetch_auditor_findings()

    if "trust_fund" in data_types:
        all_records["trust_fund"] = fetch_trust_fund_reports()

    total_count = sum(len(v) if isinstance(v, list) else 1
                      for v in all_records.values())

    # Compute hash
    data_hash = dual_hash(str(all_records).encode())

    receipt = emit_receipt("ingest", {
        "tenant_id": TENANT_ID,
        "source": "ides_public_data",
        "source_type": "web_scraping",
        "records_count": total_count,
        "payload_hash": data_hash,
        "data_types": data_types,
        "constraints": "aggregate_only_no_individual_data",
        "fields": ["weekly_claims", "payments_total", "overpayments", "recovery_rate"]
    })

    return {
        "receipt": receipt,
        "records": all_records,
        "count": total_count
    }
