"""
Auditor General Output Module

Purpose: Format compatible with Illinois Auditor General methodology.

Materiality thresholds and recommendation formats.
"""

from typing import Optional
from dataclasses import dataclass
import sys
sys.path.insert(0, "../..")
from src.core import emit_receipt, TENANT_ID


# Materiality thresholds
MATERIALITY_THRESHOLDS = {
    "material": 0.05,      # 5% of budget = material
    "significant": 0.01,   # 1% of budget = significant
    "minor": 0.001         # 0.1% of budget = minor
}


@dataclass
class AuditorFinding:
    """Finding in Auditor General format."""
    finding_id: str
    finding_number: str  # e.g., "2024-001"
    condition: str       # What we found
    criteria: str        # What should have happened
    cause: str           # Why the condition occurred
    effect: str          # Potential or actual impact
    recommendation: str  # What should be done
    view_of_responsible_officials: str = ""
    auditor_comment: str = ""
    materiality: str = "significant"
    dollar_value: float = 0.0


def compute_materiality(finding: dict, entity_budget: float) -> str:
    """
    Compute materiality classification.

    Args:
        finding: Finding dict with dollar_value
        entity_budget: Entity's total budget

    Returns:
        Materiality classification string
    """
    if entity_budget <= 0:
        return "undetermined"

    dollar_value = finding.get("dollar_value", 0)
    ratio = dollar_value / entity_budget

    if ratio >= MATERIALITY_THRESHOLDS["material"]:
        return "material"
    elif ratio >= MATERIALITY_THRESHOLDS["significant"]:
        return "significant"
    elif ratio >= MATERIALITY_THRESHOLDS["minor"]:
        return "minor"
    else:
        return "immaterial"


def format_compliance_finding(finding: dict,
                                finding_number: str,
                                entity_budget: float = 0) -> dict:
    """
    Format finding in OAG compliance report format.

    Args:
        finding: Raw finding dict
        finding_number: Report finding number (e.g., "2024-001")
        entity_budget: Entity budget for materiality

    Returns:
        OAG-formatted finding dict
    """
    materiality = compute_materiality(finding, entity_budget)
    finding_type = finding.get("finding_type", "")

    # Generate condition statement
    condition = _generate_condition(finding)

    # Generate criteria
    criteria = _generate_criteria(finding_type)

    # Generate cause
    cause = _generate_cause(finding)

    # Generate effect
    effect = _generate_effect(finding)

    # Generate recommendation
    recommendation = generate_recommendation(finding)

    return {
        "finding_id": finding.get("finding_id", finding_number),
        "finding_number": finding_number,
        "entity": finding.get("entity", "Unknown Entity"),
        "condition": condition,
        "criteria": criteria,
        "cause": cause,
        "effect": effect,
        "recommendation": recommendation,
        "materiality": materiality,
        "dollar_value": finding.get("dollar_value", 0),
        "tier": finding.get("tier", ""),
        "severity": finding.get("severity", "medium")
    }


def _generate_condition(finding: dict) -> str:
    """Generate condition statement from finding."""
    finding_type = finding.get("finding_type", "")
    entity = finding.get("entity", "the entity")
    dollar_value = finding.get("dollar_value", 0)

    conditions = {
        "credit_card_analysis": f"During our examination, we noted that {entity} had credit card expenditures totaling ${dollar_value:,.0f} with documentation deficiencies.",
        "vendor_analysis": f"We found that {entity} exhibited vendor concentration patterns exceeding normal thresholds.",
        "overtime_analysis": f"Payroll records for {entity} contained overtime entries that exceeded possible working hours.",
        "crossmatch_gap_analysis": f"During the crossmatch verification suspension period, claims totaling ${dollar_value:,.0f} were paid without standard verification.",
        "recovery_analysis": f"Overpayment recovery rates fell below established benchmarks.",
        "waiver_analysis": f"Waiver request patterns showed anomalies suggesting potential gaming of the system.",
        "pac_network_analysis": f"Campaign contribution patterns showed concentrated network structures.",
        "legislation_correlation": f"Temporal correlation was detected between campaign contributions and legislative votes.",
        "nowork_contract_analysis": f"Contract payments totaling ${dollar_value:,.0f} lacked documented deliverables."
    }

    return conditions.get(finding_type, f"An anomaly was detected affecting {entity}.")


def _generate_criteria(finding_type: str) -> str:
    """Generate criteria statement."""
    criteria = {
        "credit_card_analysis": "The Illinois Local Government Travel Expense Control Act and sound internal controls require documented receipts and business purpose for all credit card expenditures.",
        "vendor_analysis": "Prudent fiscal practices and competitive bidding requirements call for vendor diversification to ensure competitive pricing and reduce fraud risk.",
        "overtime_analysis": "State personnel regulations and basic arithmetic require that recorded work hours not exceed the number of hours in a pay period.",
        "crossmatch_gap_analysis": "Federal regulations require verification of claimant eligibility through crossmatch databases prior to payment authorization.",
        "recovery_analysis": "IDES recovery policies require reasonable efforts to recoup overpayments within established timeframes.",
        "waiver_analysis": "Waiver policies are intended for legitimate hardship cases, not repeated use by the same claimants.",
        "pac_network_analysis": "Campaign finance laws require transparent reporting of contributions and prohibit quid pro quo arrangements.",
        "legislation_correlation": "Federal and state bribery statutes prohibit payments in exchange for official actions.",
        "nowork_contract_analysis": "Sound fiscal practices require documented deliverables and work product for all contract payments."
    }

    return criteria.get(finding_type, "Applicable laws, regulations, and sound fiscal practices require proper controls and documentation.")


def _generate_cause(finding: dict) -> str:
    """Generate cause statement."""
    finding_type = finding.get("finding_type", "")

    causes = {
        "credit_card_analysis": "Inadequate internal controls over credit card usage and insufficient supervisory review of expenditures.",
        "vendor_analysis": "Lack of competitive bidding enforcement and insufficient oversight of procurement decisions.",
        "overtime_analysis": "Inadequate timekeeping controls and supervisory review of payroll data.",
        "crossmatch_gap_analysis": "Federal guidance to suspend verification requirements during the pandemic emergency.",
        "recovery_analysis": "Resource constraints and challenges in locating claimants responsible for overpayments.",
        "waiver_analysis": "Insufficient controls to identify repeated waiver requests from the same claimants.",
        "pac_network_analysis": "The legal structure of campaign finance permits concentrated contribution patterns.",
        "legislation_correlation": "Lack of transparency requirements linking contributions to specific legislative actions.",
        "nowork_contract_analysis": "Inadequate contract management and deliverable tracking procedures."
    }

    return causes.get(finding_type, "Insufficient internal controls and oversight procedures.")


def _generate_effect(finding: dict) -> str:
    """Generate effect statement."""
    dollar_value = finding.get("dollar_value", 0)

    if dollar_value > 0:
        return f"This condition resulted in potential fiscal impact of ${dollar_value:,.0f} and undermines public trust in government operations."
    else:
        return "This condition undermines internal controls, increases fraud risk, and reduces public confidence in government accountability."


def generate_recommendation(finding: dict) -> str:
    """
    Generate remediation recommendation.

    Args:
        finding: Finding dict

    Returns:
        Recommendation text
    """
    finding_type = finding.get("finding_type", "")

    recommendations = {
        "credit_card_analysis": "We recommend the entity strengthen internal controls over credit card usage, require documented receipts and business purposes for all transactions, and implement regular supervisory review of credit card statements.",
        "vendor_analysis": "We recommend the entity enforce competitive bidding requirements, diversify vendor relationships, and implement conflict of interest disclosures for contract awards.",
        "overtime_analysis": "We recommend the entity implement automated timekeeping controls that prevent entry of hours exceeding available time in the pay period, and require supervisory approval for overtime.",
        "crossmatch_gap_analysis": "We recommend IDES restore all crossmatch verifications, implement enhanced identity verification for high-risk claims, and pursue recovery of payments made to ineligible claimants.",
        "recovery_analysis": "We recommend IDES dedicate additional resources to overpayment recovery, implement skip-tracing for unlocatable claimants, and establish performance metrics for recovery activities.",
        "waiver_analysis": "We recommend IDES implement controls to identify and flag repeated waiver requests and conduct enhanced review of claims with prior denied waivers.",
        "pac_network_analysis": "We recommend enhanced disclosure requirements for bundled contributions and transparency in relationships between contributors and legislative beneficiaries.",
        "legislation_correlation": "We recommend investigation by appropriate authorities and enhanced ethics training for elected officials.",
        "nowork_contract_analysis": "We recommend the entity terminate contracts lacking documented deliverables, pursue recovery of payments without work product, and implement milestone-based payment controls."
    }

    return recommendations.get(finding_type, "We recommend the entity review and strengthen internal controls related to this finding.")


def auditor_receipt(findings: list[dict],
                     entity_budget: float = 0) -> dict:
    """
    Emit receipt for auditor-format output.

    Args:
        findings: Findings to format
        entity_budget: Entity budget for materiality calculation

    Returns:
        Receipt dict
    """
    formatted = []
    for i, finding in enumerate(findings):
        finding_number = f"2024-{i+1:03d}"
        formatted.append(format_compliance_finding(finding, finding_number, entity_budget))

    # Count by materiality
    by_materiality = {}
    for f in formatted:
        mat = f["materiality"]
        if mat not in by_materiality:
            by_materiality[mat] = 0
        by_materiality[mat] += 1

    receipt = emit_receipt("auditor", {
        "tenant_id": TENANT_ID,
        "findings_count": len(formatted),
        "by_materiality": by_materiality,
        "total_dollar_value": sum(f["dollar_value"] for f in formatted),
        "entity_budget": entity_budget,
        "format": "illinois_auditor_general",
        "finding_ids": [f["finding_number"] for f in formatted[:10]]
    })

    return receipt
