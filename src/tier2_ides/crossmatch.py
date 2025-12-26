"""
Tier 2 IDES: Cross-Match Gap Analysis

Detection Focus: Identify fraud enabled by verification system suspension.

Cross-Match Gap Data (from Auditor General):
- State Prison Registry: Real-time → suspended Mar 2020 - Sept 2021 ($40.5M)
- County Jail Registries: Real-time → suspended ($unknown)
- SSA Death Master File: Real-time → suspended ($6M)
- NDNH (New Hires): Real-time → suspended ($600K+)
"""

from dataclasses import dataclass
from typing import Optional
import sys
sys.path.insert(0, "../..")
from src.core import emit_receipt, dual_hash, TENANT_ID, stoprule_alert


# Known gap periods from Auditor General
CROSSMATCH_GAPS = {
    "prison_registry": {
        "gap_start": "2020-03-01",
        "gap_end": "2021-09-30",
        "estimated_fraud": 40500000
    },
    "death_master": {
        "gap_start": "2020-03-01",
        "gap_end": "2021-09-30",
        "estimated_fraud": 6000000
    },
    "ndnh": {
        "gap_start": "2020-03-01",
        "gap_end": "2021-09-30",
        "estimated_fraud": 600000
    }
}


@dataclass
class CrossmatchGap:
    """Represents a verification gap period."""
    database: str
    gap_start: str
    gap_end: str
    claims_during_gap: int = 0
    estimated_fraud: float = 0.0


def simulate_crossmatch_gap(claims: list[dict],
                             gap_start: str,
                             gap_end: str) -> dict:
    """
    Model claims during verification gap periods.

    Args:
        claims: Unemployment claims with claim_date, amount
        gap_start: Gap period start (ISO date)
        gap_end: Gap period end (ISO date)

    Returns:
        Dict with gap analysis results
    """
    gap_claims = []
    pre_gap_claims = []
    post_gap_claims = []

    for claim in claims:
        claim_date = claim.get("claim_date", "")

        if gap_start <= claim_date <= gap_end:
            gap_claims.append(claim)
        elif claim_date < gap_start:
            pre_gap_claims.append(claim)
        else:
            post_gap_claims.append(claim)

    gap_total = sum(c.get("amount", 0) for c in gap_claims)
    pre_gap_total = sum(c.get("amount", 0) for c in pre_gap_claims)
    post_gap_total = sum(c.get("amount", 0) for c in post_gap_claims)

    # Compute average claim rate before gap
    pre_gap_avg = len(pre_gap_claims) / max(1, 1)  # Simplified

    # Check for spike during gap
    gap_spike = len(gap_claims) > pre_gap_avg * 2 if pre_gap_avg > 0 else False

    return {
        "gap_start": gap_start,
        "gap_end": gap_end,
        "claims_during_gap": len(gap_claims),
        "gap_total_amount": gap_total,
        "pre_gap_claims": len(pre_gap_claims),
        "post_gap_claims": len(post_gap_claims),
        "gap_spike_detected": gap_spike,
        "average_claim_pre_gap": pre_gap_total / max(1, len(pre_gap_claims)),
        "average_claim_during_gap": gap_total / max(1, len(gap_claims))
    }


def detect_deceased_during_gap(claims: list[dict],
                                 death_records: list[dict],
                                 gap_start: str,
                                 gap_end: str) -> list[dict]:
    """
    Find claims from deceased during crossmatch gap.

    Args:
        claims: UI claims
        death_records: Death master file records
        gap_start: Gap start
        gap_end: Gap end

    Returns:
        List of flagged claims
    """
    flags = []

    # Build death lookup
    deaths = {}
    for record in death_records:
        ssn = record.get("ssn")
        if ssn:
            deaths[ssn] = record.get("death_date")

    for claim in claims:
        claim_date = claim.get("claim_date", "")
        ssn = claim.get("ssn")

        # Check if during gap
        if not (gap_start <= claim_date <= gap_end):
            continue

        # Check if deceased before claim
        if ssn in deaths:
            death_date = deaths[ssn]
            if death_date and death_date < claim_date:
                flags.append({
                    "finding_type": "deceased_during_gap",
                    "claimant_id": ssn,
                    "claim_date": claim_date,
                    "death_date": death_date,
                    "amount": claim.get("amount", 0),
                    "confidence": 0.95,
                    "note": "Claim would have been blocked if crossmatch active"
                })

    return flags


def detect_incarcerated_during_gap(claims: list[dict],
                                     prison_records: list[dict],
                                     gap_start: str,
                                     gap_end: str) -> list[dict]:
    """
    Find claims from incarcerated during crossmatch gap.

    Args:
        claims: UI claims
        prison_records: DOC records
        gap_start: Gap start
        gap_end: Gap end

    Returns:
        List of flagged claims
    """
    flags = []

    for claim in claims:
        claim_date = claim.get("claim_date", "")
        ssn = claim.get("ssn")

        # Check if during gap
        if not (gap_start <= claim_date <= gap_end):
            continue

        # Check prison records
        for record in prison_records:
            if record.get("ssn") == ssn:
                incarceration_start = record.get("start_date")
                incarceration_end = record.get("end_date")

                # Check if incarcerated at time of claim
                if incarceration_start and incarceration_start <= claim_date:
                    if not incarceration_end or claim_date <= incarceration_end:
                        flags.append({
                            "finding_type": "incarcerated_during_gap",
                            "claimant_id": ssn,
                            "claim_date": claim_date,
                            "incarceration_start": incarceration_start,
                            "incarceration_end": incarceration_end,
                            "facility": record.get("facility"),
                            "amount": claim.get("amount", 0),
                            "confidence": 0.90,
                            "note": "Claim would have been blocked if crossmatch active"
                        })
                        break

    return flags


def analyze_crossmatch_impact(claims: list[dict],
                                death_records: list[dict] = None,
                                prison_records: list[dict] = None) -> dict:
    """
    Comprehensive analysis of crossmatch gap impact.

    Args:
        claims: UI claims
        death_records: Optional death records
        prison_records: Optional prison records

    Returns:
        Analysis result dict
    """
    if death_records is None:
        death_records = []
    if prison_records is None:
        prison_records = []

    results = {
        "gaps_analyzed": [],
        "deceased_flags": [],
        "incarcerated_flags": [],
        "total_flagged_amount": 0
    }

    # Analyze each known gap
    for database, gap_info in CROSSMATCH_GAPS.items():
        gap_analysis = simulate_crossmatch_gap(
            claims,
            gap_info["gap_start"],
            gap_info["gap_end"]
        )
        gap_analysis["database"] = database
        results["gaps_analyzed"].append(gap_analysis)

    # Run detection for primary gap period
    primary_gap = CROSSMATCH_GAPS["prison_registry"]

    deceased_flags = detect_deceased_during_gap(
        claims, death_records,
        primary_gap["gap_start"], primary_gap["gap_end"]
    )
    results["deceased_flags"] = deceased_flags

    incarcerated_flags = detect_incarcerated_during_gap(
        claims, prison_records,
        primary_gap["gap_start"], primary_gap["gap_end"]
    )
    results["incarcerated_flags"] = incarcerated_flags

    # Sum flagged amounts
    results["total_flagged_amount"] = (
        sum(f.get("amount", 0) for f in deceased_flags) +
        sum(f.get("amount", 0) for f in incarcerated_flags)
    )

    return results


def crossmatch_receipt(claims: list[dict],
                        death_records: list[dict] = None,
                        prison_records: list[dict] = None) -> dict:
    """
    Emit receipt for crossmatch gap analysis.

    Args:
        claims: UI claims
        death_records: Death master records
        prison_records: DOC records

    Returns:
        Receipt dict
    """
    analysis = analyze_crossmatch_impact(claims, death_records, prison_records)

    receipt = emit_receipt("tier2", {
        "tenant_id": TENANT_ID,
        "finding_type": "crossmatch_gap_analysis",
        "dollar_value": analysis["total_flagged_amount"],
        "recovery_status": "pending",
        "crossmatch_gaps": {
            database: {
                "gap_start": info["gap_start"],
                "gap_end": info["gap_end"],
                "estimated_fraud": info["estimated_fraud"]
            }
            for database, info in CROSSMATCH_GAPS.items()
        },
        "flags": {
            "deceased_count": len(analysis["deceased_flags"]),
            "incarcerated_count": len(analysis["incarcerated_flags"]),
            "total_flags": len(analysis["deceased_flags"]) + len(analysis["incarcerated_flags"])
        },
        "claims_analyzed": len(claims)
    })

    # Alert on significant findings
    if analysis["total_flagged_amount"] > 100000:
        stoprule_alert(
            metric="crossmatch_fraud",
            message=f"Crossmatch gap fraud: ${analysis['total_flagged_amount']:,.0f}",
            baseline=10000,
            delta=analysis["total_flagged_amount"] - 10000
        )

    return receipt
