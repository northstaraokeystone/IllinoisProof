"""
Citizen Output Module

Purpose: Accessible, tweet-ready findings for public accountability.

Output formats:
- Tweet-ready summaries (280 char max)
- Dashboard-friendly JSON
- Plain language explanations
"""

from typing import Optional
import sys
sys.path.insert(0, "../..")
from src.core import emit_receipt, dual_hash, TENANT_ID


# Tier emoji mapping
TIER_EMOJI = {
    "tier1": "🏛️",
    "tier2": "💸",
    "tier3": "⚖️",
    "local": "🏛️",
    "systemic": "💸",
    "institutional": "⚖️"
}

# Severity emoji
SEVERITY_EMOJI = {
    "critical": "🚨",
    "high": "⚠️",
    "medium": "📊",
    "low": "📝"
}


def format_tweet(finding: dict, max_chars: int = 280) -> str:
    """
    Compress finding to tweet-ready format.

    Args:
        finding: Finding dict with tier, entity, metric, value
        max_chars: Maximum characters (default 280)

    Returns:
        Tweet-ready string
    """
    tier = finding.get("tier", "")
    tier_emoji = TIER_EMOJI.get(tier, "📌")
    severity = finding.get("severity", "medium")
    severity_emoji = SEVERITY_EMOJI.get(severity, "📊")

    entity = finding.get("entity", "Unknown")
    metric = finding.get("metric", "")
    value = finding.get("value", "")
    comparison = finding.get("comparison", "")

    # Build one-liner
    one_liner = finding.get("summary", f"{metric}: {value}")

    # Get receipt hash (shortened)
    receipt_hash = finding.get("receipt_hash", "")
    short_hash = receipt_hash[:12] if receipt_hash else ""

    # Template
    template = f"""{severity_emoji} {tier.upper()} ALERT: {entity}
{metric}: {value} ({comparison})
{one_liner}
Proof: {short_hash}"""

    # Truncate if needed
    if len(template) > max_chars:
        # Shorten one_liner
        available = max_chars - len(template) + len(one_liner)
        if available > 20:
            one_liner = one_liner[:available-3] + "..."
            template = f"""{severity_emoji} {tier.upper()} ALERT: {entity}
{metric}: {value}
{one_liner}
Proof: {short_hash}"""
        else:
            # Minimal format
            template = f"{severity_emoji} {entity}: {metric}={value} [{short_hash}]"

    return template[:max_chars]


def generate_infographic_data(findings: list[dict]) -> dict:
    """
    Generate data structure for visualizations.

    Args:
        findings: List of findings

    Returns:
        Infographic-ready data structure
    """
    # Aggregate by tier
    by_tier = {}
    for f in findings:
        tier = f.get("tier", "unknown")
        if tier not in by_tier:
            by_tier[tier] = {"count": 0, "total_value": 0, "findings": []}
        by_tier[tier]["count"] += 1
        by_tier[tier]["total_value"] += f.get("dollar_value", 0)
        by_tier[tier]["findings"].append(f)

    # Aggregate by severity
    by_severity = {}
    for f in findings:
        sev = f.get("severity", "unknown")
        if sev not in by_severity:
            by_severity[sev] = 0
        by_severity[sev] += 1

    # Top entities
    entity_values = {}
    for f in findings:
        entity = f.get("entity", "unknown")
        if entity not in entity_values:
            entity_values[entity] = 0
        entity_values[entity] += f.get("dollar_value", 0)

    top_entities = sorted(entity_values.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "donut_chart": {
            "title": "Findings by Tier",
            "data": [
                {"tier": t, "count": d["count"], "value": d["total_value"]}
                for t, d in by_tier.items()
            ]
        },
        "severity_chart": {
            "title": "Findings by Severity",
            "data": [{"severity": s, "count": c} for s, c in by_severity.items()]
        },
        "top_entities": {
            "title": "Top 10 Flagged Entities",
            "data": [{"entity": e, "total_value": v} for e, v in top_entities]
        },
        "summary": {
            "total_findings": len(findings),
            "total_dollar_value": sum(f.get("dollar_value", 0) for f in findings),
            "critical_count": by_severity.get("critical", 0),
            "tiers_affected": len(by_tier)
        }
    }


def simplify_finding(finding: dict, reading_level: int = 8) -> str:
    """
    Create plain language explanation of finding.

    Args:
        finding: Finding dict
        reading_level: Target reading level (grade)

    Returns:
        Plain language explanation
    """
    tier = finding.get("tier", "")
    entity = finding.get("entity", "an entity")
    finding_type = finding.get("finding_type", "an issue")
    dollar_value = finding.get("dollar_value", 0)
    severity = finding.get("severity", "medium")

    # Tier descriptions
    tier_desc = {
        "tier1": "local government",
        "tier2": "state unemployment agency",
        "tier3": "campaign finance"
    }

    # Finding type descriptions
    type_desc = {
        "credit_card_analysis": "credit card spending patterns",
        "vendor_analysis": "payments to contractors",
        "overtime_analysis": "employee overtime payments",
        "crossmatch_gap_analysis": "identity verification problems",
        "recovery_analysis": "getting money back from overpayments",
        "waiver_analysis": "requests to forgive overpayments",
        "pac_network_analysis": "campaign donations",
        "legislation_correlation": "links between donations and votes",
        "nowork_contract_analysis": "contracts without actual work"
    }

    tier_text = tier_desc.get(tier, "government operations")
    type_text = type_desc.get(finding_type, finding_type)

    # Build explanation
    if dollar_value > 0:
        value_text = f"${dollar_value:,.0f}"
    else:
        value_text = "an undetermined amount"

    if severity == "critical":
        severity_text = "This is a serious concern that needs immediate attention."
    elif severity == "high":
        severity_text = "This is an important issue that should be investigated."
    else:
        severity_text = "This may need further review."

    return f"""We found unusual activity in {entity}'s {tier_text} {type_text}.

The issue involves {value_text}.

{severity_text}

This finding was detected by analyzing public records and looking for patterns that don't match normal operations."""


def dashboard_payload(findings: list[dict], period: str = "current") -> dict:
    """
    Generate JSON payload for web dashboard.

    Args:
        findings: List of findings
        period: Time period for dashboard

    Returns:
        Dashboard-ready JSON structure
    """
    infographic = generate_infographic_data(findings)

    # Generate individual cards
    cards = []
    for f in findings[:20]:  # Top 20 for dashboard
        cards.append({
            "id": f.get("finding_id", f.get("receipt_hash", "")),
            "tier": f.get("tier"),
            "entity": f.get("entity"),
            "title": f.get("finding_type", "").replace("_", " ").title(),
            "severity": f.get("severity"),
            "value": f.get("dollar_value", 0),
            "summary": simplify_finding(f)[:200],
            "tweet": format_tweet(f),
            "receipt_hash": f.get("receipt_hash", "")[:12]
        })

    return {
        "period": period,
        "generated_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat(),
        "summary": infographic["summary"],
        "charts": infographic,
        "cards": cards,
        "export_formats": ["csv", "json", "pdf"]
    }


def citizen_receipt(findings: list[dict], period: str = "current") -> dict:
    """
    Emit receipt for citizen output generation.

    Args:
        findings: Findings to format
        period: Time period

    Returns:
        Receipt dict
    """
    payload = dashboard_payload(findings, period)
    tweets = [format_tweet(f) for f in findings[:10]]

    receipt = emit_receipt("citizen", {
        "tenant_id": TENANT_ID,
        "output_type": "dashboard_and_tweets",
        "content": {
            "total_findings": len(findings),
            "tweets_generated": len(tweets),
            "dashboard_cards": len(payload["cards"])
        },
        "period": period,
        "reading_level": 8,
        "formats": ["tweet", "dashboard", "plain_language"]
    })

    return receipt
