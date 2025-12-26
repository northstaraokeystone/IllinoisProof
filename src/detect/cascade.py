"""
Cross-Tier Cascade Detection Module

Purpose: Detect patterns that span multiple tiers of corruption.

Examples:
- Dolton credit card anomalies → vendor concentration → O.A.K.K. bribery
- IDES cross-match gaps → identity theft → unrecoverable funds
- ComEd PAC contributions → Madigan allies → veto override votes
"""

from dataclasses import dataclass, field
from typing import Optional
import sys
sys.path.insert(0, "..")
from src.core import emit_receipt, TENANT_ID, stoprule_alert


@dataclass
class CascadePattern:
    """Represents a detected cascade pattern across tiers."""
    pattern_id: str
    tiers: list[str]
    findings: list[dict]
    confidence: float
    dollar_value: float = 0.0
    entities: list[str] = field(default_factory=list)
    description: str = ""


def detect_tier1_to_tier3(tier1_findings: list[dict],
                          tier3_findings: list[dict]) -> list[CascadePattern]:
    """
    Detect cascades from local (Dolton) to institutional (Madigan).

    Pattern: Local vendor gets contracts → PAC contributions → favorable legislation

    Args:
        tier1_findings: Tier 1 vendor/contract findings
        tier3_findings: Tier 3 PAC/legislation findings

    Returns:
        List of detected cascade patterns
    """
    cascades = []
    pattern_count = 0

    # Extract entities from tier1 vendor findings
    tier1_vendors = set()
    tier1_officials = set()
    tier1_contracts = []

    for f in tier1_findings:
        if f.get("finding_type") == "vendor_concentration":
            tier1_vendors.update(f.get("vendors", []))
        if f.get("finding_type") == "contract_anomaly":
            tier1_contracts.append(f)
            tier1_vendors.add(f.get("vendor", ""))
        if f.get("official"):
            tier1_officials.add(f["official"])

    # Extract entities from tier3 PAC findings
    tier3_contributors = set()
    tier3_recipients = set()

    for f in tier3_findings:
        if f.get("finding_type") == "pac_contribution":
            tier3_contributors.add(f.get("contributor", ""))
            tier3_recipients.add(f.get("recipient", ""))
        if f.get("finding_type") == "legislation_correlation":
            tier3_recipients.update(f.get("legislators", []))

    # Look for overlaps
    vendor_pac_overlap = tier1_vendors & tier3_contributors
    official_pac_overlap = tier1_officials & tier3_recipients

    if vendor_pac_overlap or official_pac_overlap:
        pattern_count += 1
        entities = list(vendor_pac_overlap | official_pac_overlap)

        # Sum dollar values
        dollar_value = sum(f.get("dollar_value", 0) for f in tier1_contracts
                          if f.get("vendor") in vendor_pac_overlap)

        cascades.append(CascadePattern(
            pattern_id=f"CASCADE-T1T3-{pattern_count:04d}",
            tiers=["tier1_dolton", "tier3_madigan"],
            findings=tier1_findings + tier3_findings,
            confidence=0.75 if len(entities) > 1 else 0.5,
            dollar_value=dollar_value,
            entities=entities,
            description="Local vendor contracts correlate with PAC contributions"
        ))

    return cascades


def detect_tier2_cascade(tier2_findings: list[dict]) -> list[CascadePattern]:
    """
    Detect cascades within IDES pandemic fraud tier.

    Pattern: Cross-match gap → identity theft → unrecoverable overpayment

    Args:
        tier2_findings: Tier 2 IDES findings

    Returns:
        List of detected cascade patterns
    """
    cascades = []
    pattern_count = 0

    # Group findings by type
    crossmatch_gaps = [f for f in tier2_findings
                       if f.get("finding_type") == "crossmatch_gap"]
    identity_theft = [f for f in tier2_findings
                      if f.get("finding_type") == "identity_theft"]
    unrecoverable = [f for f in tier2_findings
                     if f.get("finding_type") == "unrecoverable_overpayment"]

    # Look for temporal correlations
    gap_periods = set()
    for f in crossmatch_gaps:
        gap_periods.add((f.get("gap_start"), f.get("gap_end")))

    for f in identity_theft:
        claim_date = f.get("claim_date")
        for gap_start, gap_end in gap_periods:
            if gap_start and gap_end and claim_date:
                if gap_start <= claim_date <= gap_end:
                    pattern_count += 1
                    cascades.append(CascadePattern(
                        pattern_id=f"CASCADE-T2-{pattern_count:04d}",
                        tiers=["tier2_ides"],
                        findings=[f] + [g for g in crossmatch_gaps
                                       if g.get("gap_start") == gap_start],
                        confidence=0.85,
                        dollar_value=f.get("dollar_value", 0),
                        entities=[f.get("claimant_id", "unknown")],
                        description="Identity theft during cross-match suspension"
                    ))
                    break

    return cascades


def detect_full_cascade(tier1_findings: list[dict],
                         tier2_findings: list[dict],
                         tier3_findings: list[dict]) -> list[CascadePattern]:
    """
    Detect cascades spanning all three tiers.

    Pattern: Local contracts → state agency fraud → institutional pay-to-play

    Args:
        tier1_findings: Tier 1 findings
        tier2_findings: Tier 2 findings
        tier3_findings: Tier 3 findings

    Returns:
        List of detected cascade patterns
    """
    cascades = []

    # Collect from sub-cascade detections
    t1_t3 = detect_tier1_to_tier3(tier1_findings, tier3_findings)
    t2 = detect_tier2_cascade(tier2_findings)

    cascades.extend(t1_t3)
    cascades.extend(t2)

    # Look for full three-tier patterns
    # This would involve more complex entity resolution in production
    all_entities = set()
    for f in tier1_findings + tier2_findings + tier3_findings:
        for key in ["vendor", "official", "contributor", "recipient", "claimant"]:
            if f.get(key):
                all_entities.add(f[key])

    # Check for entities appearing in multiple tiers
    entity_tiers = {}
    for entity in all_entities:
        tiers = []
        if any(f.get("vendor") == entity or f.get("official") == entity
               for f in tier1_findings):
            tiers.append("tier1")
        if any(f.get("claimant") == entity for f in tier2_findings):
            tiers.append("tier2")
        if any(f.get("contributor") == entity or f.get("recipient") == entity
               for f in tier3_findings):
            tiers.append("tier3")

        if len(tiers) >= 2:
            entity_tiers[entity] = tiers

    # Create cascade patterns for multi-tier entities
    for entity, tiers in entity_tiers.items():
        if len(tiers) >= 3:
            cascades.append(CascadePattern(
                pattern_id=f"CASCADE-FULL-{entity[:8]}",
                tiers=tiers,
                findings=tier1_findings + tier2_findings + tier3_findings,
                confidence=0.90,
                entities=[entity],
                description=f"Entity {entity} appears across all three tiers"
            ))

    return cascades


def cross_tier_cascade(tier1: list[dict], tier2: list[dict],
                       tier3: list[dict]) -> list[dict]:
    """
    Main entry point for cascade detection.

    Args:
        tier1: Tier 1 findings
        tier2: Tier 2 findings
        tier3: Tier 3 findings

    Returns:
        List of cascade pattern dicts
    """
    cascades = detect_full_cascade(tier1, tier2, tier3)

    results = []
    for cascade in cascades:
        results.append({
            "pattern_id": cascade.pattern_id,
            "tiers": cascade.tiers,
            "confidence": cascade.confidence,
            "dollar_value": cascade.dollar_value,
            "entities": cascade.entities,
            "description": cascade.description,
            "findings_count": len(cascade.findings)
        })

    return results


def cascade_receipt(tier1: list[dict], tier2: list[dict],
                    tier3: list[dict]) -> dict:
    """
    Emit receipt for cascade detection analysis.

    Args:
        tier1: Tier 1 findings
        tier2: Tier 2 findings
        tier3: Tier 3 findings

    Returns:
        Receipt dict
    """
    cascades = cross_tier_cascade(tier1, tier2, tier3)

    total_value = sum(c.get("dollar_value", 0) for c in cascades)
    high_confidence = [c for c in cascades if c.get("confidence", 0) >= 0.75]

    receipt = emit_receipt("cascade", {
        "tenant_id": TENANT_ID,
        "patterns_detected": len(cascades),
        "high_confidence_patterns": len(high_confidence),
        "total_dollar_value": total_value,
        "tiers_analyzed": ["tier1_dolton", "tier2_ides", "tier3_madigan"],
        "findings_counts": {
            "tier1": len(tier1),
            "tier2": len(tier2),
            "tier3": len(tier3)
        },
        "patterns": cascades
    })

    # Alert on high-confidence cascades
    if high_confidence:
        stoprule_alert(
            metric="cascade_detection",
            message=f"Detected {len(high_confidence)} high-confidence cascade patterns",
            baseline=0,
            delta=len(high_confidence)
        )

    return receipt
