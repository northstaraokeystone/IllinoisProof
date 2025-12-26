"""
Tier 3 Madigan: Legislation Correlation Analysis

Calibration case:
- SB 1652 (PA 97-0616): Energy Infrastructure Modernization Act
- Passed: Oct 2011 (veto override)
- Obtained via: Bribery (per conviction)
- Value to ComEd: Rate increases enabled
"""

from typing import Optional
from dataclasses import dataclass
import sys
sys.path.insert(0, "../..")
from src.core import emit_receipt, TENANT_ID, stoprule_alert


# Known legislation from case
KNOWN_LEGISLATION = {
    "SB1652": {
        "bill_number": "SB1652",
        "public_act": "PA 97-0616",
        "title": "Energy Infrastructure Modernization Act",
        "passed": "2011-10",
        "method": "veto_override",
        "beneficiary": "ComEd",
        "proven_bribery": True
    }
}


@dataclass
class VoteRecord:
    """Represents a legislative vote."""
    bill_number: str
    legislator: str
    vote: str  # yea, nay, present, absent
    vote_date: str


@dataclass
class ContributionVoteLink:
    """Links contributions to votes."""
    contributor: str
    legislator: str
    contribution_amount: float
    contribution_date: str
    bill_number: str
    vote: str
    vote_date: str
    days_between: int
    correlation_strength: float


def correlation_contribution_vote(contributions: list[dict],
                                    votes: list[dict],
                                    window_days: int = 90) -> dict:
    """
    Analyze temporal correlation between contributions and votes.

    Args:
        contributions: Contribution records
        votes: Vote records
        window_days: Window to look for correlation

    Returns:
        Correlation analysis dict
    """
    correlations = []

    for contrib in contributions:
        contrib_date = contrib.get("date", "")
        recipient = contrib.get("recipient")
        contributor = contrib.get("contributor")
        amount = contrib.get("amount", 0)

        if not contrib_date or not recipient:
            continue

        # Look for votes by recipient within window
        for vote in votes:
            legislator = vote.get("legislator")
            vote_date = vote.get("vote_date", vote.get("date", ""))

            if legislator != recipient:
                continue

            # Check if vote is within window after contribution
            # Simplified date comparison
            if contrib_date <= vote_date:
                correlations.append({
                    "contributor": contributor,
                    "legislator": legislator,
                    "contribution_amount": amount,
                    "contribution_date": contrib_date,
                    "bill_number": vote.get("bill_number"),
                    "vote": vote.get("vote"),
                    "vote_date": vote_date
                })

    # Group by contributor-legislator pairs
    pairs = {}
    for c in correlations:
        key = f"{c['contributor']}:{c['legislator']}"
        if key not in pairs:
            pairs[key] = {"correlations": [], "total_amount": 0}
        pairs[key]["correlations"].append(c)
        pairs[key]["total_amount"] += c["contribution_amount"]

    return {
        "total_correlations": len(correlations),
        "unique_pairs": len(pairs),
        "top_pairs": sorted(
            [{"pair": k, **v} for k, v in pairs.items()],
            key=lambda x: x["total_amount"],
            reverse=True
        )[:10],
        "correlations": correlations[:100]  # Limit for receipt
    }


def detect_vote_buying(contributions: list[dict],
                        votes: list[dict],
                        bills: list[dict]) -> list[dict]:
    """
    Detect patterns suggesting vote buying.

    Pattern: Contribution → favorable vote → bill passage

    Args:
        contributions: Contribution records
        votes: Vote records
        bills: Bill records with beneficiary info

    Returns:
        List of vote buying patterns
    """
    patterns = []

    # Build bill lookup
    bill_info = {b.get("bill_number"): b for b in bills}

    # Get correlation data
    correlation_data = correlation_contribution_vote(contributions, votes)

    # Look for correlated votes on bills with known beneficiaries
    for corr in correlation_data["correlations"]:
        bill_number = corr.get("bill_number")
        if not bill_number:
            continue

        bill = bill_info.get(bill_number, {})
        beneficiary = bill.get("beneficiary")

        # Check if contributor is related to beneficiary
        contributor = corr.get("contributor", "")
        if beneficiary and (
            beneficiary.lower() in contributor.lower() or
            contributor.lower() in beneficiary.lower()
        ):
            patterns.append({
                "pattern_type": "contribution_vote_beneficiary",
                "contributor": contributor,
                "beneficiary": beneficiary,
                "legislator": corr["legislator"],
                "bill_number": bill_number,
                "vote": corr["vote"],
                "contribution_amount": corr["contribution_amount"],
                "confidence": 0.75
            })

        # Check against known bribery cases
        if bill_number in KNOWN_LEGISLATION:
            known = KNOWN_LEGISLATION[bill_number]
            if known.get("proven_bribery"):
                patterns.append({
                    "pattern_type": "known_bribery_case",
                    "contributor": contributor,
                    "legislator": corr["legislator"],
                    "bill_number": bill_number,
                    "bill_title": known.get("title"),
                    "vote": corr["vote"],
                    "contribution_amount": corr["contribution_amount"],
                    "confidence": 0.95,
                    "note": "Matches convicted bribery pattern"
                })

    return patterns


def analyze_veto_override(votes: list[dict], bills: list[dict]) -> list[dict]:
    """
    Analyze veto override votes for suspicious patterns.

    Args:
        votes: Vote records
        bills: Bill records

    Returns:
        List of suspicious override patterns
    """
    patterns = []

    # Get override votes
    override_votes = [v for v in votes if v.get("vote_type") == "veto_override"]

    # Group by bill
    by_bill = {}
    for v in override_votes:
        bill = v.get("bill_number")
        if bill not in by_bill:
            by_bill[bill] = []
        by_bill[bill].append(v)

    for bill_number, bill_votes in by_bill.items():
        # Check if bill is in known cases
        if bill_number in KNOWN_LEGISLATION:
            known = KNOWN_LEGISLATION[bill_number]
            patterns.append({
                "pattern_type": "known_bribery_override",
                "bill_number": bill_number,
                "bill_title": known.get("title"),
                "vote_count": len(bill_votes),
                "beneficiary": known.get("beneficiary"),
                "confidence": 0.95
            })

        # Analyze vote margins
        yea_votes = len([v for v in bill_votes if v.get("vote") in ["yea", "yes"]])
        nay_votes = len([v for v in bill_votes if v.get("vote") in ["nay", "no"]])

        if yea_votes > 0 and nay_votes > 0:
            margin = yea_votes - nay_votes
            total = yea_votes + nay_votes

            patterns.append({
                "pattern_type": "veto_override_margin",
                "bill_number": bill_number,
                "yea_votes": yea_votes,
                "nay_votes": nay_votes,
                "margin": margin,
                "margin_percentage": margin / total if total > 0 else 0
            })

    return patterns


def legislation_receipt(contributions: list[dict],
                         votes: list[dict],
                         bills: list[dict] = None) -> dict:
    """
    Emit receipt for legislation correlation analysis.

    Args:
        contributions: Contribution records
        votes: Vote records
        bills: Optional bill records

    Returns:
        Receipt dict
    """
    if bills is None:
        bills = []

    correlation = correlation_contribution_vote(contributions, votes)
    vote_buying = detect_vote_buying(contributions, votes, bills)
    overrides = analyze_veto_override(votes, bills)

    # Determine severity
    known_bribery = [p for p in vote_buying if p.get("pattern_type") == "known_bribery_case"]
    if known_bribery:
        severity = "critical"
        confidence = 0.95
    elif vote_buying:
        severity = "high"
        confidence = 0.75
    elif correlation["total_correlations"] > 10:
        severity = "medium"
        confidence = 0.5
    else:
        severity = "low"
        confidence = 0.25

    receipt = emit_receipt("tier3", {
        "tenant_id": TENANT_ID,
        "finding_type": "legislation_correlation",
        "network_path": "contribution_vote_graph",
        "confidence": confidence,
        "legislation_correlation": {
            "total_correlations": correlation["total_correlations"],
            "unique_pairs": correlation["unique_pairs"],
            "top_pairs": [p["pair"] for p in correlation["top_pairs"][:5]]
        },
        "vote_buying_patterns": len(vote_buying),
        "known_bribery_matches": len(known_bribery),
        "veto_override_patterns": len(overrides),
        "severity": severity,
        "known_legislation_matches": list(KNOWN_LEGISLATION.keys())
    })

    # Alert on known bribery matches
    if known_bribery:
        stoprule_alert(
            metric="known_bribery_match",
            message=f"Detected {len(known_bribery)} matches to known bribery patterns",
            baseline=0,
            delta=len(known_bribery)
        )

    return receipt
