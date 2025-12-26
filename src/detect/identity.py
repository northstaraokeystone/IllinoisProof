"""
Identity Theft Pattern Detection Module

Purpose: Detect identity theft patterns in unemployment claims.

Key patterns:
- Claims from deceased individuals (SSN in death master file)
- Claims from incarcerated individuals (SSN in prison registry)
- Geographic anomalies (multiple claims from same address)
- Temporal clustering (claims during cross-match suspension)
"""

from dataclasses import dataclass
from typing import Optional
import sys
sys.path.insert(0, "..")
from src.core import emit_receipt, TENANT_ID, stoprule_alert


@dataclass
class IdentityFlag:
    """Represents an identity theft flag."""
    flag_type: str
    claimant_id: str
    confidence: float
    dollar_value: float = 0.0
    details: dict = None

    def __post_init__(self):
        if self.details is None:
            self.details = {}


def detect_deceased_claimant(claims: list[dict],
                              death_records: list[dict]) -> list[IdentityFlag]:
    """
    Match claims against death master file.

    Args:
        claims: Unemployment claims with ssn, claim_date, amount
        death_records: Death records with ssn, death_date

    Returns:
        List of identity flags for deceased claimants
    """
    flags = []

    # Build death record lookup
    death_lookup = {}
    for record in death_records:
        ssn = record.get("ssn")
        if ssn:
            death_lookup[ssn] = record.get("death_date")

    for claim in claims:
        ssn = claim.get("ssn")
        claim_date = claim.get("claim_date")

        if ssn in death_lookup:
            death_date = death_lookup[ssn]
            # Check if claim was after death
            if claim_date and death_date and claim_date > death_date:
                flags.append(IdentityFlag(
                    flag_type="deceased_claimant",
                    claimant_id=ssn,
                    confidence=0.95,
                    dollar_value=claim.get("amount", 0),
                    details={
                        "claim_date": claim_date,
                        "death_date": death_date,
                        "days_after_death": _date_diff(death_date, claim_date)
                    }
                ))

    return flags


def detect_incarcerated_claimant(claims: list[dict],
                                   prison_records: list[dict]) -> list[IdentityFlag]:
    """
    Match claims against prison registry.

    Args:
        claims: Unemployment claims
        prison_records: Incarceration records with ssn, start_date, end_date

    Returns:
        List of identity flags for incarcerated claimants
    """
    flags = []

    for claim in claims:
        ssn = claim.get("ssn")
        claim_date = claim.get("claim_date")

        for record in prison_records:
            if record.get("ssn") == ssn:
                start_date = record.get("start_date")
                end_date = record.get("end_date")

                # Check if claim was during incarceration
                if start_date and claim_date:
                    if start_date <= claim_date:
                        if not end_date or claim_date <= end_date:
                            flags.append(IdentityFlag(
                                flag_type="incarcerated_claimant",
                                claimant_id=ssn,
                                confidence=0.90,
                                dollar_value=claim.get("amount", 0),
                                details={
                                    "claim_date": claim_date,
                                    "incarceration_start": start_date,
                                    "incarceration_end": end_date,
                                    "facility": record.get("facility")
                                }
                            ))
                            break

    return flags


def detect_geographic_anomaly(claims: list[dict]) -> list[IdentityFlag]:
    """
    Detect multiple claims from the same address.

    Args:
        claims: Unemployment claims with address field

    Returns:
        List of geographic anomaly flags
    """
    flags = []

    # Group claims by address
    address_claims = {}
    for claim in claims:
        addr = claim.get("address", "").lower().strip()
        if addr:
            if addr not in address_claims:
                address_claims[addr] = []
            address_claims[addr].append(claim)

    # Flag addresses with multiple claims
    for addr, addr_claims in address_claims.items():
        if len(addr_claims) > 3:  # Threshold for suspicion
            total_value = sum(c.get("amount", 0) for c in addr_claims)

            # Get unique SSNs at this address
            unique_ssns = set(c.get("ssn") for c in addr_claims if c.get("ssn"))

            flags.append(IdentityFlag(
                flag_type="geographic_clustering",
                claimant_id=f"ADDR:{addr[:50]}",
                confidence=min(0.5 + len(addr_claims) * 0.1, 0.95),
                dollar_value=total_value,
                details={
                    "address": addr,
                    "claim_count": len(addr_claims),
                    "unique_ssns": len(unique_ssns),
                    "ssn_list": list(unique_ssns)[:10]  # First 10
                }
            ))

    return flags


def detect_temporal_clustering(claims: list[dict],
                                 gap_start: str,
                                 gap_end: str) -> list[IdentityFlag]:
    """
    Detect claims clustered during cross-match suspension period.

    Args:
        claims: Unemployment claims
        gap_start: Start of verification gap (ISO date string)
        gap_end: End of verification gap (ISO date string)

    Returns:
        List of temporal clustering flags
    """
    flags = []

    gap_claims = []
    for claim in claims:
        claim_date = claim.get("claim_date")
        if claim_date and gap_start <= claim_date <= gap_end:
            gap_claims.append(claim)

    if len(gap_claims) > len(claims) * 0.4:  # >40% during gap is suspicious
        total_value = sum(c.get("amount", 0) for c in gap_claims)

        flags.append(IdentityFlag(
            flag_type="temporal_clustering",
            claimant_id="AGGREGATE",
            confidence=0.70,
            dollar_value=total_value,
            details={
                "gap_start": gap_start,
                "gap_end": gap_end,
                "gap_claims": len(gap_claims),
                "total_claims": len(claims),
                "gap_percentage": len(gap_claims) / len(claims) if claims else 0
            }
        ))

    return flags


def _date_diff(date1: str, date2: str) -> int:
    """Simple date difference in days (placeholder)."""
    # In production, would use proper date parsing
    return 0


def detect_all_identity_patterns(claims: list[dict],
                                   death_records: list[dict] = None,
                                   prison_records: list[dict] = None,
                                   gap_start: str = None,
                                   gap_end: str = None) -> list[IdentityFlag]:
    """
    Run all identity theft detection patterns.

    Args:
        claims: Unemployment claims
        death_records: Death master file records
        prison_records: Incarceration records
        gap_start: Cross-match gap start
        gap_end: Cross-match gap end

    Returns:
        Combined list of all identity flags
    """
    flags = []

    if death_records:
        flags.extend(detect_deceased_claimant(claims, death_records))

    if prison_records:
        flags.extend(detect_incarcerated_claimant(claims, prison_records))

    flags.extend(detect_geographic_anomaly(claims))

    if gap_start and gap_end:
        flags.extend(detect_temporal_clustering(claims, gap_start, gap_end))

    return flags


def identity_receipt(claims: list[dict],
                      death_records: list[dict] = None,
                      prison_records: list[dict] = None,
                      gap_start: str = None,
                      gap_end: str = None) -> dict:
    """
    Emit receipt for identity theft detection.

    Args:
        claims: Claims analyzed
        death_records: Death records
        prison_records: Prison records
        gap_start: Gap period start
        gap_end: Gap period end

    Returns:
        Receipt dict
    """
    flags = detect_all_identity_patterns(
        claims, death_records, prison_records, gap_start, gap_end
    )

    # Aggregate by type
    by_type = {}
    for flag in flags:
        if flag.flag_type not in by_type:
            by_type[flag.flag_type] = {"count": 0, "dollar_value": 0}
        by_type[flag.flag_type]["count"] += 1
        by_type[flag.flag_type]["dollar_value"] += flag.dollar_value

    total_value = sum(f.dollar_value for f in flags)

    receipt = emit_receipt("identity", {
        "tenant_id": TENANT_ID,
        "claims_analyzed": len(claims),
        "flags_detected": len(flags),
        "total_flagged_value": total_value,
        "flags_by_type": by_type,
        "high_confidence_flags": len([f for f in flags if f.confidence >= 0.8]),
        "gap_period": {"start": gap_start, "end": gap_end} if gap_start else None
    })

    # Alert on high-value flags
    if total_value > 1000000:  # $1M threshold
        stoprule_alert(
            metric="identity_theft_value",
            message=f"Identity theft flags total ${total_value:,.0f}",
            baseline=100000,
            delta=total_value - 100000
        )

    return receipt
