"""
Tier 3 Madigan: No-Work Contract Detection

ComEd No-Work Contracts (from case):
- Doherty firm: Unknown amount, 2011-2019, "Legal consulting"
- Shaw Decremer: Unknown, 2011-2019, Various
- Olivo: $4,000/month, multi-year
- Nice: $5,000/month, multi-year
- Acevedo: $5,000/month, multi-year
"""

from typing import Optional
from dataclasses import dataclass
import sys
sys.path.insert(0, "../..")
from src.core import emit_receipt, TENANT_ID, stoprule_alert


# Known no-work contracts from case
KNOWN_NOWORK = {
    "olivo": {"monthly": 4000, "duration_years": 8, "role": "no_work_consultant"},
    "nice": {"monthly": 5000, "duration_years": 8, "role": "no_work_consultant"},
    "acevedo": {"monthly": 5000, "duration_years": 8, "role": "no_work_consultant"},
    "doherty": {"monthly": None, "duration_years": 8, "role": "legal_consulting"},
    "shaw_decremer": {"monthly": None, "duration_years": 8, "role": "various"}
}


@dataclass
class ContractAnalysis:
    """Analysis result for a potential no-work contract."""
    contractor: str
    total_paid: float
    duration_months: int
    monthly_average: float
    deliverables_count: int
    deliverables_value: float
    work_ratio: float  # deliverables_value / total_paid
    is_suspicious: bool
    confidence: float


def detect_nowork_contracts(contracts: list[dict],
                             deliverables: list[dict]) -> list[dict]:
    """
    Detect contracts with payments but no work product.

    Args:
        contracts: Contract records with contractor, amount, period
        deliverables: Deliverable records with contract_id, description, value

    Returns:
        List of potential no-work contract flags
    """
    flags = []

    # Build deliverable lookup by contract
    deliverable_by_contract = {}
    for d in deliverables:
        contract_id = d.get("contract_id")
        if contract_id not in deliverable_by_contract:
            deliverable_by_contract[contract_id] = []
        deliverable_by_contract[contract_id].append(d)

    for contract in contracts:
        contract_id = contract.get("contract_id")
        contractor = contract.get("contractor", "unknown")
        total_paid = contract.get("amount", 0)
        duration_months = contract.get("duration_months", 12)

        # Get deliverables for this contract
        contract_deliverables = deliverable_by_contract.get(contract_id, [])
        deliverable_count = len(contract_deliverables)
        deliverable_value = sum(d.get("value", 0) for d in contract_deliverables)

        # Calculate work ratio
        work_ratio = deliverable_value / total_paid if total_paid > 0 else 0
        monthly_avg = total_paid / duration_months if duration_months > 0 else 0

        # Flag suspicious contracts
        is_suspicious = False
        confidence = 0.0

        # No deliverables at all
        if deliverable_count == 0 and total_paid > 10000:
            is_suspicious = True
            confidence = 0.9

        # Very low work ratio
        elif work_ratio < 0.1 and total_paid > 25000:
            is_suspicious = True
            confidence = 0.75

        # High monthly payment with minimal deliverables
        elif monthly_avg > 3000 and deliverable_count < 3:
            is_suspicious = True
            confidence = 0.6

        # Check against known no-work patterns
        contractor_lower = contractor.lower()
        for known, info in KNOWN_NOWORK.items():
            if known in contractor_lower:
                is_suspicious = True
                confidence = 0.95
                break

        if is_suspicious:
            flags.append({
                "finding_type": "potential_nowork_contract",
                "contract_id": contract_id,
                "contractor": contractor,
                "total_paid": total_paid,
                "duration_months": duration_months,
                "monthly_average": monthly_avg,
                "deliverables_count": deliverable_count,
                "deliverables_value": deliverable_value,
                "work_ratio": work_ratio,
                "confidence": confidence,
                "severity": "critical" if confidence > 0.8 else "high"
            })

    return flags


def compensation_anomaly(payments: list[dict],
                          industry_baseline: dict = None) -> list[dict]:
    """
    Detect above-market payments for undefined work.

    Args:
        payments: Payment records with recipient, amount, description
        industry_baseline: Optional baseline compensation by role

    Returns:
        List of compensation anomaly flags
    """
    if industry_baseline is None:
        # Default baselines for consulting roles
        industry_baseline = {
            "legal_consulting": {"monthly_max": 10000, "hourly_max": 500},
            "lobbyist": {"monthly_max": 8000, "hourly_max": 300},
            "consultant": {"monthly_max": 5000, "hourly_max": 200},
            "default": {"monthly_max": 3000, "hourly_max": 150}
        }

    flags = []

    # Group payments by recipient
    by_recipient = {}
    for p in payments:
        recipient = p.get("recipient", "unknown")
        if recipient not in by_recipient:
            by_recipient[recipient] = []
        by_recipient[recipient].append(p)

    for recipient, recipient_payments in by_recipient.items():
        total = sum(p.get("amount", 0) for p in recipient_payments)
        months = len(set(p.get("date", "")[:7] for p in recipient_payments))

        if months == 0:
            months = 1

        monthly_avg = total / months

        # Determine role
        roles = set(p.get("role", "default") for p in recipient_payments)
        role = list(roles)[0] if roles else "default"
        baseline = industry_baseline.get(role, industry_baseline["default"])

        # Check against baseline
        if monthly_avg > baseline["monthly_max"] * 1.5:
            flags.append({
                "finding_type": "above_market_compensation",
                "recipient": recipient,
                "total_paid": total,
                "months": months,
                "monthly_average": monthly_avg,
                "baseline_max": baseline["monthly_max"],
                "excess_ratio": monthly_avg / baseline["monthly_max"],
                "role": role,
                "severity": "high" if monthly_avg > baseline["monthly_max"] * 2 else "medium"
            })

        # Check for vague descriptions
        vague_count = sum(1 for p in recipient_payments
                          if not p.get("description") or
                          len(p.get("description", "")) < 10)

        if vague_count > len(recipient_payments) * 0.5 and total > 10000:
            flags.append({
                "finding_type": "vague_payment_descriptions",
                "recipient": recipient,
                "total_paid": total,
                "vague_payment_count": vague_count,
                "total_payments": len(recipient_payments),
                "vague_ratio": vague_count / len(recipient_payments),
                "severity": "medium"
            })

    return flags


def detect_connected_recipients(contracts: list[dict],
                                  connections: list[dict]) -> list[dict]:
    """
    Detect no-work contractors with political connections.

    Args:
        contracts: Contract records
        connections: Political connection records

    Returns:
        List of connected recipient flags
    """
    flags = []

    # Build connection lookup
    connected_entities = set()
    for conn in connections:
        entity = conn.get("entity", "").lower()
        connected_to = conn.get("connected_to", "").lower()
        if entity:
            connected_entities.add(entity)
        if connected_to:
            connected_entities.add(connected_to)

    for contract in contracts:
        contractor = contract.get("contractor", "").lower()

        # Check if contractor appears in connections
        is_connected = any(
            contractor in entity or entity in contractor
            for entity in connected_entities
        )

        if is_connected and contract.get("amount", 0) > 10000:
            flags.append({
                "finding_type": "politically_connected_contractor",
                "contractor": contract.get("contractor"),
                "contract_id": contract.get("contract_id"),
                "amount": contract.get("amount"),
                "severity": "high"
            })

    return flags


def nowork_receipt(contracts: list[dict],
                    deliverables: list[dict] = None,
                    payments: list[dict] = None) -> dict:
    """
    Emit receipt for no-work contract analysis.

    Args:
        contracts: Contract records
        deliverables: Optional deliverable records
        payments: Optional payment records

    Returns:
        Receipt dict
    """
    if deliverables is None:
        deliverables = []
    if payments is None:
        payments = []

    nowork_flags = detect_nowork_contracts(contracts, deliverables)
    compensation_flags = compensation_anomaly(payments)

    total_flagged = sum(f.get("total_paid", 0) for f in nowork_flags)

    # Determine severity
    critical_flags = [f for f in nowork_flags if f.get("confidence", 0) > 0.8]
    if critical_flags:
        severity = "critical"
        confidence = max(f.get("confidence", 0) for f in critical_flags)
    elif nowork_flags:
        severity = "high"
        confidence = max(f.get("confidence", 0) for f in nowork_flags)
    elif compensation_flags:
        severity = "medium"
        confidence = 0.5
    else:
        severity = "low"
        confidence = 0.25

    receipt = emit_receipt("tier3", {
        "tenant_id": TENANT_ID,
        "finding_type": "nowork_contract_analysis",
        "network_path": "contract_deliverable_graph",
        "confidence": confidence,
        "nowork_flags": {
            "total_flags": len(nowork_flags),
            "critical_flags": len(critical_flags),
            "total_flagged_amount": total_flagged,
            "top_contractors": [f["contractor"] for f in nowork_flags[:5]]
        },
        "compensation_flags": {
            "above_market": len([f for f in compensation_flags
                                 if f.get("finding_type") == "above_market_compensation"]),
            "vague_descriptions": len([f for f in compensation_flags
                                       if f.get("finding_type") == "vague_payment_descriptions"])
        },
        "known_pattern_matches": len([f for f in nowork_flags
                                      if f.get("confidence", 0) > 0.9]),
        "severity": severity
    })

    # Alert on known pattern matches
    known_matches = [f for f in nowork_flags if f.get("confidence", 0) > 0.9]
    if known_matches:
        stoprule_alert(
            metric="known_nowork_pattern",
            message=f"Detected {len(known_matches)} matches to known no-work patterns",
            baseline=0,
            delta=len(known_matches)
        )

    # Alert on high total
    if total_flagged > 100000:
        stoprule_alert(
            metric="nowork_total",
            message=f"No-work contract flags total ${total_flagged:,.0f}",
            baseline=50000,
            delta=total_flagged - 50000
        )

    return receipt
