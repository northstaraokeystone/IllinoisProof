"""
Tier 2 IDES: Overpayment Recovery Tracking

Recovery Statistics from spec:
- Total overpayments: $5.24B
- Recovered: $511.7M (10%)
- Non-recoverable (identity theft): $2.8B
- Overpayment letters sent: 174,685
- Waiver requests: 67,678
- Waivers denied: 62%
- Average overpayment: $5,505
"""

from dataclasses import dataclass
from typing import Optional
import sys
sys.path.insert(0, "../..")
from src.core import emit_receipt, TENANT_ID, stoprule_alert


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


@dataclass
class RecoveryMetrics:
    """Overpayment recovery metrics."""
    total_overpayments: float
    recovered: float
    pending: float
    non_recoverable: float
    recovery_rate: float
    avg_recovery_time_days: float = 0


def compute_recovery_rate(overpayments: list[dict],
                           recoveries: list[dict]) -> float:
    """
    Compute percentage of overpayments recovered.

    Args:
        overpayments: Overpayment records with overpayment_id, amount
        recoveries: Recovery records with overpayment_id, amount_recovered

    Returns:
        Recovery rate as float (0.0-1.0)
    """
    if not overpayments:
        return 0.0

    total_overpaid = sum(o.get("amount", 0) for o in overpayments)

    # Match recoveries to overpayments
    recovery_by_id = {}
    for r in recoveries:
        op_id = r.get("overpayment_id")
        if op_id:
            if op_id not in recovery_by_id:
                recovery_by_id[op_id] = 0
            recovery_by_id[op_id] += r.get("amount_recovered", 0)

    total_recovered = sum(recovery_by_id.values())

    return total_recovered / total_overpaid if total_overpaid > 0 else 0.0


def segment_by_recoverability(overpayments: list[dict]) -> dict:
    """
    Segment overpayments by recoverability category.

    Categories:
    - identity_theft: Non-recoverable (victim didn't receive funds)
    - fraud: Potentially recoverable via prosecution
    - error: Recoverable via repayment
    - unknown: Needs investigation

    Args:
        overpayments: Overpayment records with category field

    Returns:
        Dict with segments and totals
    """
    segments = {
        "identity_theft": {"count": 0, "amount": 0, "recoverable": False},
        "fraud": {"count": 0, "amount": 0, "recoverable": True},
        "error": {"count": 0, "amount": 0, "recoverable": True},
        "unknown": {"count": 0, "amount": 0, "recoverable": None}
    }

    for op in overpayments:
        category = op.get("category", "unknown")
        if category not in segments:
            category = "unknown"

        segments[category]["count"] += 1
        segments[category]["amount"] += op.get("amount", 0)

    # Compute totals
    total = sum(s["amount"] for s in segments.values())
    recoverable = sum(s["amount"] for s in segments.values() if s["recoverable"])
    non_recoverable = sum(s["amount"] for s in segments.values() if s["recoverable"] is False)

    return {
        "segments": segments,
        "total_amount": total,
        "recoverable_amount": recoverable,
        "non_recoverable_amount": non_recoverable,
        "unknown_amount": segments["unknown"]["amount"]
    }


def recovery_trend(recoveries: list[dict], period: str = "month") -> list[dict]:
    """
    Compute recovery rate over time.

    Args:
        recoveries: Recovery records with date, amount
        period: Aggregation period (month, quarter, year)

    Returns:
        List of period recovery dicts
    """
    # Group by period
    by_period = {}
    for r in recoveries:
        date = r.get("date", "")[:7] if period == "month" else r.get("date", "")[:4]
        if date not in by_period:
            by_period[date] = {"recovered": 0, "count": 0}
        by_period[date]["recovered"] += r.get("amount_recovered", 0)
        by_period[date]["count"] += 1

    # Convert to list
    trend = []
    for period_key, data in sorted(by_period.items()):
        trend.append({
            "period": period_key,
            "recovered_amount": data["recovered"],
            "recovery_count": data["count"],
            "average_recovery": data["recovered"] / data["count"] if data["count"] > 0 else 0
        })

    return trend


def analyze_recovery_performance(overpayments: list[dict],
                                   recoveries: list[dict]) -> dict:
    """
    Comprehensive recovery performance analysis.

    Args:
        overpayments: Overpayment records
        recoveries: Recovery records

    Returns:
        Performance analysis dict
    """
    recovery_rate = compute_recovery_rate(overpayments, recoveries)
    segments = segment_by_recoverability(overpayments)
    trend = recovery_trend(recoveries)

    # Compare to known benchmarks
    benchmark_rate = KNOWN_STATS["recovered"] / KNOWN_STATS["total_overpayments"]
    rate_vs_benchmark = recovery_rate - benchmark_rate

    return {
        "recovery_rate": recovery_rate,
        "benchmark_rate": benchmark_rate,
        "rate_vs_benchmark": rate_vs_benchmark,
        "total_overpayments": sum(o.get("amount", 0) for o in overpayments),
        "total_recovered": sum(r.get("amount_recovered", 0) for r in recoveries),
        "segments": segments,
        "trend": trend,
        "avg_overpayment": (
            sum(o.get("amount", 0) for o in overpayments) / len(overpayments)
            if overpayments else 0
        )
    }


def recovery_receipt(overpayments: list[dict],
                      recoveries: list[dict]) -> dict:
    """
    Emit receipt for recovery analysis.

    Args:
        overpayments: Overpayment records
        recoveries: Recovery records

    Returns:
        Receipt dict
    """
    analysis = analyze_recovery_performance(overpayments, recoveries)

    receipt = emit_receipt("tier2", {
        "tenant_id": TENANT_ID,
        "finding_type": "recovery_analysis",
        "dollar_value": analysis["total_overpayments"],
        "recovery_status": "analyzed",
        "recovery_rate": analysis["recovery_rate"],
        "benchmark_rate": analysis["benchmark_rate"],
        "rate_vs_benchmark": analysis["rate_vs_benchmark"],
        "total_recovered": analysis["total_recovered"],
        "segments": {
            k: {"count": v["count"], "amount": v["amount"]}
            for k, v in analysis["segments"]["segments"].items()
        },
        "recoverable_amount": analysis["segments"]["recoverable_amount"],
        "non_recoverable_amount": analysis["segments"]["non_recoverable_amount"],
        "avg_overpayment": analysis["avg_overpayment"]
    })

    # Alert if recovery rate significantly below benchmark
    if analysis["rate_vs_benchmark"] < -0.05:  # 5% below benchmark
        stoprule_alert(
            metric="recovery_rate",
            message=f"Recovery rate {analysis['recovery_rate']:.1%} below benchmark {analysis['benchmark_rate']:.1%}",
            baseline=analysis["benchmark_rate"],
            delta=analysis["rate_vs_benchmark"]
        )

    return receipt
