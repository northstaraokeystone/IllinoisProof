"""
Tier 2 IDES: Waiver Request Pattern Analysis

Waiver statistics:
- Waiver requests: 67,678
- Waivers denied: 62%
- Patterns indicating gaming or abuse
"""

from typing import Optional
import sys
sys.path.insert(0, "../..")
from src.core import emit_receipt, TENANT_ID, stoprule_alert


# Known statistics
KNOWN_WAIVER_DENIAL_RATE = 0.62


def waiver_pattern_analysis(waivers: list[dict]) -> dict:
    """
    Analyze waiver request patterns for anomalies.

    Args:
        waivers: Waiver records with claimant_id, status, amount, date

    Returns:
        Analysis result dict
    """
    total = len(waivers)
    if total == 0:
        return {
            "total_waivers": 0,
            "approved": 0,
            "denied": 0,
            "pending": 0,
            "approval_rate": 0,
            "denial_rate": 0
        }

    # Count by status
    by_status = {}
    for w in waivers:
        status = w.get("status", "unknown")
        if status not in by_status:
            by_status[status] = {"count": 0, "amount": 0}
        by_status[status]["count"] += 1
        by_status[status]["amount"] += w.get("amount", 0)

    approved = by_status.get("approved", {"count": 0})["count"]
    denied = by_status.get("denied", {"count": 0})["count"]
    pending = by_status.get("pending", {"count": 0})["count"]

    total_decided = approved + denied

    return {
        "total_waivers": total,
        "approved": approved,
        "denied": denied,
        "pending": pending,
        "approval_rate": approved / total_decided if total_decided > 0 else 0,
        "denial_rate": denied / total_decided if total_decided > 0 else 0,
        "by_status": by_status,
        "total_waived_amount": by_status.get("approved", {"amount": 0})["amount"],
        "total_denied_amount": by_status.get("denied", {"amount": 0})["amount"]
    }


def detect_waiver_gaming(waivers: list[dict], claims: list[dict]) -> list[dict]:
    """
    Detect patterns suggesting waiver system gaming.

    Patterns:
    - Multiple waiver requests for same overpayment
    - Rapid succession of waiver requests
    - Waivers requested immediately after denial
    - Claimants with high waiver request rates

    Args:
        waivers: Waiver records
        claims: Related claim records

    Returns:
        List of gaming flags
    """
    flags = []

    # Group waivers by claimant
    by_claimant = {}
    for w in waivers:
        claimant = w.get("claimant_id")
        if claimant:
            if claimant not in by_claimant:
                by_claimant[claimant] = []
            by_claimant[claimant].append(w)

    # Check for multiple requests
    for claimant, claimant_waivers in by_claimant.items():
        if len(claimant_waivers) > 3:
            total_amount = sum(w.get("amount", 0) for w in claimant_waivers)
            flags.append({
                "flag_type": "multiple_waiver_requests",
                "claimant_id": claimant,
                "waiver_count": len(claimant_waivers),
                "total_amount": total_amount,
                "severity": "high" if len(claimant_waivers) > 5 else "medium"
            })

        # Check for resubmission after denial
        denied = [w for w in claimant_waivers if w.get("status") == "denied"]
        subsequent = [w for w in claimant_waivers
                      if w.get("status") in ["pending", "approved"]]

        for d in denied:
            # Look for submissions after this denial
            denial_date = d.get("date", "")
            resubmits = [s for s in subsequent
                         if s.get("date", "") > denial_date
                         and s.get("overpayment_id") == d.get("overpayment_id")]

            if resubmits:
                flags.append({
                    "flag_type": "resubmission_after_denial",
                    "claimant_id": claimant,
                    "original_denial_date": denial_date,
                    "resubmit_count": len(resubmits),
                    "overpayment_id": d.get("overpayment_id"),
                    "severity": "medium"
                })

    # Group waivers by overpayment
    by_overpayment = {}
    for w in waivers:
        op_id = w.get("overpayment_id")
        if op_id:
            if op_id not in by_overpayment:
                by_overpayment[op_id] = []
            by_overpayment[op_id].append(w)

    # Check for multiple requests on same overpayment
    for op_id, op_waivers in by_overpayment.items():
        if len(op_waivers) > 1:
            flags.append({
                "flag_type": "multiple_requests_same_overpayment",
                "overpayment_id": op_id,
                "request_count": len(op_waivers),
                "claimants": list(set(w.get("claimant_id") for w in op_waivers)),
                "severity": "high" if len(op_waivers) > 2 else "medium"
            })

    return flags


def analyze_waiver_timing(waivers: list[dict]) -> dict:
    """
    Analyze timing patterns in waiver requests.

    Args:
        waivers: Waiver records with date

    Returns:
        Timing analysis dict
    """
    # Group by month
    by_month = {}
    for w in waivers:
        date = w.get("date", "")[:7]  # YYYY-MM
        if date:
            if date not in by_month:
                by_month[date] = {"count": 0, "amount": 0}
            by_month[date]["count"] += 1
            by_month[date]["amount"] += w.get("amount", 0)

    # Find peaks
    if not by_month:
        return {"trend": [], "peak_month": None, "peak_count": 0}

    peak_month = max(by_month.items(), key=lambda x: x[1]["count"])

    return {
        "trend": [{"month": k, **v} for k, v in sorted(by_month.items())],
        "peak_month": peak_month[0],
        "peak_count": peak_month[1]["count"],
        "peak_amount": peak_month[1]["amount"],
        "total_months": len(by_month),
        "avg_per_month": sum(v["count"] for v in by_month.values()) / len(by_month)
    }


def waiver_receipt(waivers: list[dict], claims: list[dict] = None) -> dict:
    """
    Emit receipt for waiver analysis.

    Args:
        waivers: Waiver records
        claims: Optional related claims

    Returns:
        Receipt dict
    """
    if claims is None:
        claims = []

    patterns = waiver_pattern_analysis(waivers)
    gaming_flags = detect_waiver_gaming(waivers, claims)
    timing = analyze_waiver_timing(waivers)

    receipt = emit_receipt("tier2", {
        "tenant_id": TENANT_ID,
        "finding_type": "waiver_analysis",
        "dollar_value": patterns["total_waived_amount"] + patterns["total_denied_amount"],
        "recovery_status": "waiver_analyzed",
        "waiver_patterns": {
            "total_waivers": patterns["total_waivers"],
            "approved": patterns["approved"],
            "denied": patterns["denied"],
            "pending": patterns["pending"],
            "approval_rate": patterns["approval_rate"],
            "denial_rate": patterns["denial_rate"]
        },
        "gaming_flags": {
            "multiple_requests": len([f for f in gaming_flags
                                      if f["flag_type"] == "multiple_waiver_requests"]),
            "resubmissions": len([f for f in gaming_flags
                                  if f["flag_type"] == "resubmission_after_denial"]),
            "same_overpayment": len([f for f in gaming_flags
                                     if f["flag_type"] == "multiple_requests_same_overpayment"]),
            "total_flags": len(gaming_flags)
        },
        "timing": {
            "peak_month": timing["peak_month"],
            "peak_count": timing["peak_count"],
            "avg_per_month": timing["avg_per_month"]
        },
        "total_waived_amount": patterns["total_waived_amount"]
    })

    # Alert on high gaming activity
    if len(gaming_flags) > 10:
        stoprule_alert(
            metric="waiver_gaming",
            message=f"Detected {len(gaming_flags)} waiver gaming patterns",
            baseline=5,
            delta=len(gaming_flags) - 5
        )

    return receipt
