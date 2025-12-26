"""
Tier 1 Dolton: Vendor Concentration Detection

Detection Focus: Identify vendor concentration and related party transactions.

Key patterns:
- O.A.K.K. Construction: $200K+ before owner's bribery guilty plea
- Vendor concentration > 25% of total spend
- Related party transactions (ownership/address crossmatch)
- Contract timing correlation with political events
"""

from typing import Optional
from dataclasses import dataclass
import sys
sys.path.insert(0, "../..")
from src.core import emit_receipt, dual_hash, TENANT_ID, stoprule_alert


# Concentration thresholds
CONCENTRATION_WARNING = 0.15  # 15% of spend
CONCENTRATION_FLAG = 0.25    # 25% of spend
CONCENTRATION_CRITICAL = 0.40  # 40% of spend


@dataclass
class VendorProfile:
    """Profile of a vendor for analysis."""
    vendor_id: str
    name: str
    total_amount: float = 0.0
    contract_count: int = 0
    first_contract_date: str = ""
    last_contract_date: str = ""
    address: str = ""
    owners: list = None
    related_entities: list = None

    def __post_init__(self):
        if self.owners is None:
            self.owners = []
        if self.related_entities is None:
            self.related_entities = []


def compute_vendor_concentration(expenditures: list[dict]) -> dict:
    """
    Compute HHI-style vendor concentration metric.

    Args:
        expenditures: List of expenditure records with vendor, amount

    Returns:
        Dict with concentration metrics per vendor and overall HHI
    """
    # Aggregate by vendor
    vendor_totals = {}
    for exp in expenditures:
        vendor = exp.get("vendor", "unknown")
        amount = exp.get("amount", 0)

        if vendor not in vendor_totals:
            vendor_totals[vendor] = 0
        vendor_totals[vendor] += amount

    total_spend = sum(vendor_totals.values())

    if total_spend == 0:
        return {
            "vendors": {},
            "hhi": 0,
            "top_vendor": None,
            "top_concentration": 0,
            "total_spend": 0
        }

    # Compute shares and HHI
    vendor_shares = {}
    hhi = 0
    for vendor, amount in vendor_totals.items():
        share = amount / total_spend
        vendor_shares[vendor] = {
            "amount": amount,
            "share": share,
            "is_concentrated": share >= CONCENTRATION_FLAG
        }
        hhi += share ** 2

    # Find top vendor
    top_vendor = max(vendor_totals.items(), key=lambda x: x[1])

    return {
        "vendors": vendor_shares,
        "hhi": hhi,
        "top_vendor": top_vendor[0],
        "top_concentration": top_vendor[1] / total_spend,
        "total_spend": total_spend,
        "vendor_count": len(vendor_totals)
    }


def detect_related_parties(vendors: list[dict],
                            board_members: list[dict]) -> list[dict]:
    """
    Cross-reference vendor ownership with board/official relationships.

    Args:
        vendors: Vendor records with owners, address fields
        board_members: Board member records with name, address, related_entities

    Returns:
        List of related party matches
    """
    matches = []

    # Build lookup sets
    board_names = set()
    board_addresses = set()
    board_entities = set()

    for member in board_members:
        name = member.get("name", "").lower().strip()
        if name:
            board_names.add(name)
            # Add variations
            parts = name.split()
            if len(parts) >= 2:
                board_names.add(f"{parts[-1]}, {parts[0]}")  # Last, First

        addr = member.get("address", "").lower().strip()
        if addr:
            board_addresses.add(addr)

        for entity in member.get("related_entities", []):
            board_entities.add(entity.lower().strip())

    # Check vendors
    for vendor in vendors:
        vendor_id = vendor.get("vendor_id", vendor.get("name", ""))

        # Check owner names
        for owner in vendor.get("owners", []):
            owner_lower = owner.lower().strip()
            if owner_lower in board_names:
                matches.append({
                    "vendor": vendor_id,
                    "match_type": "owner_is_board_member",
                    "matched_value": owner,
                    "confidence": 0.95
                })

        # Check addresses
        vendor_addr = vendor.get("address", "").lower().strip()
        if vendor_addr and vendor_addr in board_addresses:
            matches.append({
                "vendor": vendor_id,
                "match_type": "shared_address",
                "matched_value": vendor_addr,
                "confidence": 0.85
            })

        # Check entity names
        vendor_name = vendor.get("name", "").lower().strip()
        if vendor_name in board_entities:
            matches.append({
                "vendor": vendor_id,
                "match_type": "related_entity",
                "matched_value": vendor_name,
                "confidence": 0.90
            })

    return matches


def timeline_correlation(contract_awards: list[dict],
                          political_events: list[dict]) -> list[dict]:
    """
    Detect suspicious timing between contracts and political events.

    Args:
        contract_awards: Contract records with award_date, vendor, amount
        political_events: Political events with date, type, participants

    Returns:
        List of suspicious timing correlations
    """
    correlations = []

    for contract in contract_awards:
        award_date = contract.get("award_date")
        vendor = contract.get("vendor")
        amount = contract.get("amount", 0)

        if not award_date:
            continue

        for event in political_events:
            event_date = event.get("date")
            event_type = event.get("type")

            if not event_date:
                continue

            # Look for contracts awarded shortly after elections/appointments
            # or shortly before elections
            # Simplified: just check if dates are within 90 days

            # Check if event is election, appointment, or vote
            if event_type in ["election", "appointment", "vote", "endorsement"]:
                # Would compute actual date difference here
                correlations.append({
                    "contract_vendor": vendor,
                    "contract_amount": amount,
                    "contract_date": award_date,
                    "event_type": event_type,
                    "event_date": event_date,
                    "event_participants": event.get("participants", []),
                    "correlation_type": "temporal_proximity"
                })

    return correlations


def detect_contract_anomalies(contracts: list[dict]) -> list[dict]:
    """
    Detect anomalies in contract patterns.

    Args:
        contracts: Contract records

    Returns:
        List of anomaly flags
    """
    anomalies = []

    for contract in contracts:
        amount = contract.get("amount", 0)
        vendor = contract.get("vendor", "")

        # Check for no-bid contracts
        if contract.get("bid_type") == "sole_source" and amount > 10000:
            anomalies.append({
                "vendor": vendor,
                "anomaly_type": "large_sole_source",
                "amount": amount,
                "severity": "high" if amount > 50000 else "medium"
            })

        # Check for contract modifications that increase value significantly
        original = contract.get("original_amount", amount)
        if amount > original * 1.5 and original > 10000:
            anomalies.append({
                "vendor": vendor,
                "anomaly_type": "significant_modification",
                "original_amount": original,
                "current_amount": amount,
                "increase_ratio": amount / original,
                "severity": "high"
            })

        # Check for rapid succession of contracts to same vendor
        # Would need to track dates here

    return anomalies


def vendor_receipt(expenditures: list[dict],
                    vendors: list[dict] = None,
                    board_members: list[dict] = None,
                    entity: str = "dolton") -> dict:
    """
    Emit receipt with vendor analysis results.

    Args:
        expenditures: Expenditure records
        vendors: Optional vendor detail records
        board_members: Optional board member records
        entity: Entity name

    Returns:
        Receipt dict
    """
    if vendors is None:
        vendors = []
    if board_members is None:
        board_members = []

    concentration = compute_vendor_concentration(expenditures)
    related = detect_related_parties(vendors, board_members)
    anomalies = detect_contract_anomalies(expenditures)

    # Identify high-concentration vendors
    concentrated_vendors = [
        v for v, data in concentration["vendors"].items()
        if data["share"] >= CONCENTRATION_FLAG
    ]

    # Compute severity
    if concentration["top_concentration"] >= CONCENTRATION_CRITICAL:
        severity = "critical"
    elif concentration["top_concentration"] >= CONCENTRATION_FLAG or related:
        severity = "high"
    elif concentration["top_concentration"] >= CONCENTRATION_WARNING:
        severity = "medium"
    else:
        severity = "low"

    receipt = emit_receipt("tier1", {
        "tenant_id": TENANT_ID,
        "finding_type": "vendor_analysis",
        "entity": entity,
        "severity": severity,
        "evidence_hash": dual_hash(str(concentration).encode()),
        "dollar_value": concentration["total_spend"],
        "vendor_flags": {
            "concentrated_vendors": concentrated_vendors,
            "related_party_matches": len(related),
            "contract_anomalies": len(anomalies)
        },
        "hhi": concentration["hhi"],
        "top_vendor": concentration["top_vendor"],
        "top_concentration": concentration["top_concentration"],
        "vendor_count": concentration["vendor_count"]
    })

    # Alert on high concentration
    if concentration["top_concentration"] >= CONCENTRATION_FLAG:
        stoprule_alert(
            metric="vendor_concentration",
            message=f"Vendor concentration {concentration['top_concentration']:.1%} for {entity}",
            baseline=CONCENTRATION_FLAG,
            delta=concentration["top_concentration"] - CONCENTRATION_FLAG
        )

    # Alert on related parties
    if related:
        stoprule_alert(
            metric="related_parties",
            message=f"Found {len(related)} related party matches for {entity}",
            baseline=0,
            delta=len(related)
        )

    return receipt
