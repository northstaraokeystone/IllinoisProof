"""
Tier 1 Dolton: Credit Card Expenditure Analysis

Detection Focus: Credit card anomalies indicating misuse or fraud.

Red Flags from Dolton calibration:
- $779K credit card expenditures missing receipts
- $33,027 Amazon purchase (single transaction)
- Round number transactions
- Same-day multiple transactions just under approval threshold
"""

from typing import Optional
import sys
sys.path.insert(0, "../..")
from src.core import emit_receipt, dual_hash, TENANT_ID, stoprule_alert
from src.detect.benford import benford_receipt, detect_round_numbers


# Known thresholds from Dolton case
SINGLE_TRANSACTION_THRESHOLD = 25000  # Flag single purchases above this
ROUND_NUMBER_THRESHOLDS = [10000, 25000, 33000, 50000]  # Suspicious round amounts
APPROVAL_THRESHOLD = 10000  # Typical approval threshold for splitting detection


def parse_credit_card_transactions(source: str) -> list[dict]:
    """
    Ingest credit card transaction data.

    Args:
        source: Source identifier (file path or API endpoint)

    Returns:
        List of transaction dicts
    """
    # Placeholder - would read from actual source
    # Returns sample structure
    return []


def detect_round_number_transactions(transactions: list[dict]) -> list[dict]:
    """
    Flag transactions with suspiciously round amounts.

    Args:
        transactions: List of transactions with amount field

    Returns:
        List of flagged transactions with flag details
    """
    amounts = [t.get("amount", 0) for t in transactions]
    flags = detect_round_numbers(amounts, ROUND_NUMBER_THRESHOLDS)

    flagged = []
    for flag in flags:
        idx = flag["index"]
        if idx < len(transactions):
            flagged.append({
                **transactions[idx],
                "flag_type": "round_number",
                "flag_threshold": flag["threshold"],
                "flag_value": flag["value"]
            })

    return flagged


def detect_missing_receipts(transactions: list[dict],
                             receipt_log: list[dict]) -> list[dict]:
    """
    Match transactions to supporting documentation.

    Args:
        transactions: Credit card transactions
        receipt_log: Log of receipts/documentation

    Returns:
        List of transactions missing receipts
    """
    # Build receipt lookup by transaction ID or amount+date
    receipted = set()
    for receipt in receipt_log:
        tx_id = receipt.get("transaction_id")
        if tx_id:
            receipted.add(tx_id)

    missing = []
    for tx in transactions:
        tx_id = tx.get("transaction_id")
        if tx_id and tx_id not in receipted:
            missing.append({
                **tx,
                "flag_type": "missing_receipt",
                "severity": "high" if tx.get("amount", 0) > 1000 else "medium"
            })

    return missing


def single_transaction_outliers(transactions: list[dict],
                                  threshold: float = None) -> list[dict]:
    """
    Flag unusually large single purchases.

    Args:
        transactions: List of transactions
        threshold: Dollar threshold for flagging (default: $25,000)

    Returns:
        List of flagged transactions
    """
    if threshold is None:
        threshold = SINGLE_TRANSACTION_THRESHOLD

    flagged = []
    for tx in transactions:
        amount = abs(tx.get("amount", 0))
        if amount >= threshold:
            flagged.append({
                **tx,
                "flag_type": "large_single_transaction",
                "threshold": threshold,
                "excess": amount - threshold
            })

    return flagged


def detect_split_transactions(transactions: list[dict],
                                approval_limit: float = None,
                                time_window_hours: int = 24) -> list[dict]:
    """
    Detect transaction splitting to avoid approval thresholds.

    Pattern: Multiple transactions same day just under limit.

    Args:
        transactions: List of transactions with date, amount
        approval_limit: Threshold for splitting detection
        time_window_hours: Window to look for splits

    Returns:
        List of potential split transaction groups
    """
    if approval_limit is None:
        approval_limit = APPROVAL_THRESHOLD

    # Group by date and vendor
    groups = {}
    for tx in transactions:
        date = tx.get("date", "")[:10]  # YYYY-MM-DD
        vendor = tx.get("vendor", "unknown")
        key = f"{date}:{vendor}"

        if key not in groups:
            groups[key] = []
        groups[key].append(tx)

    splits = []
    for key, group_txs in groups.items():
        # Check for multiple transactions just under limit
        under_limit = [t for t in group_txs
                       if 0.8 * approval_limit <= t.get("amount", 0) < approval_limit]

        if len(under_limit) >= 2:
            total = sum(t.get("amount", 0) for t in under_limit)
            if total > approval_limit:
                splits.append({
                    "flag_type": "split_transaction",
                    "date": key.split(":")[0],
                    "vendor": key.split(":")[1],
                    "transaction_count": len(under_limit),
                    "total_amount": total,
                    "approval_limit": approval_limit,
                    "transactions": under_limit
                })

    return splits


def detect_vendor_patterns(transactions: list[dict]) -> list[dict]:
    """
    Detect suspicious vendor patterns in credit card spending.

    Args:
        transactions: List of transactions with vendor field

    Returns:
        List of vendor pattern flags
    """
    # Group by vendor
    vendor_totals = {}
    for tx in transactions:
        vendor = tx.get("vendor", "unknown")
        if vendor not in vendor_totals:
            vendor_totals[vendor] = {"count": 0, "total": 0, "transactions": []}
        vendor_totals[vendor]["count"] += 1
        vendor_totals[vendor]["total"] += tx.get("amount", 0)
        vendor_totals[vendor]["transactions"].append(tx)

    total_spend = sum(v["total"] for v in vendor_totals.values())

    flags = []
    for vendor, stats in vendor_totals.items():
        if total_spend > 0:
            concentration = stats["total"] / total_spend

            # Flag high concentration vendors
            if concentration > 0.25:
                flags.append({
                    "flag_type": "vendor_concentration",
                    "vendor": vendor,
                    "concentration": concentration,
                    "total_amount": stats["total"],
                    "transaction_count": stats["count"],
                    "severity": "critical" if concentration > 0.5 else "high"
                })

    return flags


def analyze_credit_cards(transactions: list[dict],
                          receipt_log: list[dict] = None) -> dict:
    """
    Perform complete credit card analysis.

    Args:
        transactions: Credit card transactions
        receipt_log: Optional receipt log for matching

    Returns:
        Complete analysis result
    """
    if receipt_log is None:
        receipt_log = []

    # Run all detection methods
    round_flags = detect_round_number_transactions(transactions)
    missing_flags = detect_missing_receipts(transactions, receipt_log)
    large_flags = single_transaction_outliers(transactions)
    split_flags = detect_split_transactions(transactions)
    vendor_flags = detect_vendor_patterns(transactions)

    all_flags = round_flags + missing_flags + large_flags + vendor_flags
    split_count = len(split_flags)

    # Calculate totals
    total_transactions = len(transactions)
    total_amount = sum(t.get("amount", 0) for t in transactions)
    flagged_amount = sum(t.get("amount", 0) for t in all_flags)

    return {
        "total_transactions": total_transactions,
        "total_amount": total_amount,
        "flagged_transactions": len(all_flags),
        "flagged_amount": flagged_amount,
        "flag_rate": len(all_flags) / total_transactions if total_transactions > 0 else 0,
        "round_number_flags": len(round_flags),
        "missing_receipt_flags": len(missing_flags),
        "large_transaction_flags": len(large_flags),
        "split_transaction_groups": split_count,
        "vendor_concentration_flags": len(vendor_flags),
        "flags": all_flags,
        "splits": split_flags
    }


def credit_card_receipt(transactions: list[dict],
                         receipt_log: list[dict] = None,
                         entity: str = "dolton") -> dict:
    """
    Emit receipt with credit card analysis results.

    Args:
        transactions: Credit card transactions
        receipt_log: Optional receipt documentation
        entity: Entity name

    Returns:
        Receipt dict
    """
    analysis = analyze_credit_cards(transactions, receipt_log)

    # Compute evidence hash
    evidence_data = {
        "transactions_hash": dual_hash(str(transactions).encode()),
        "analysis_summary": {k: v for k, v in analysis.items() if k != "flags"}
    }

    receipt = emit_receipt("tier1", {
        "tenant_id": TENANT_ID,
        "finding_type": "credit_card_analysis",
        "entity": entity,
        "severity": _compute_severity(analysis),
        "evidence_hash": dual_hash(str(evidence_data).encode()),
        "dollar_value": analysis["flagged_amount"],
        "credit_card_flags": {
            "round_numbers": analysis["round_number_flags"],
            "missing_receipts": analysis["missing_receipt_flags"],
            "large_transactions": analysis["large_transaction_flags"],
            "split_transactions": analysis["split_transaction_groups"],
            "vendor_concentration": analysis["vendor_concentration_flags"]
        },
        "total_transactions": analysis["total_transactions"],
        "flagged_transactions": analysis["flagged_transactions"],
        "flag_rate": analysis["flag_rate"]
    })

    # Alert on high flag rates
    if analysis["flag_rate"] > 0.1:
        stoprule_alert(
            metric="credit_card_flag_rate",
            message=f"High credit card flag rate for {entity}: {analysis['flag_rate']:.1%}",
            baseline=0.05,
            delta=analysis["flag_rate"] - 0.05
        )

    return receipt


def _compute_severity(analysis: dict) -> str:
    """Compute overall severity from analysis results."""
    if analysis["flagged_amount"] > 100000:
        return "critical"
    if analysis["flag_rate"] > 0.2:
        return "critical"
    if analysis["flagged_amount"] > 25000:
        return "high"
    if analysis["flag_rate"] > 0.1:
        return "high"
    if analysis["flagged_transactions"] > 0:
        return "medium"
    return "low"
