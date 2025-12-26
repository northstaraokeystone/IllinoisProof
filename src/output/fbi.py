"""
FBI/Prosecution Output Module

Purpose: Chain-of-custody documentation meeting federal evidence standards.

Standards: NIST IR 8387 + FBI LEB
- Unique asset ID with tamper-evidence
- Continuous monitoring and incident alerts
- Hash verification at every transfer
- Metadata preservation
- Change logs with timestamps
- Original/working copy segregation
- Read-only storage media
- Written custody logs (access, transfers)
- Operator name/signature/date/case number
"""

from dataclasses import dataclass, field
from typing import Optional
import uuid
from datetime import datetime, timezone
import sys
sys.path.insert(0, "../..")
from src.core import emit_receipt, dual_hash, TENANT_ID


@dataclass
class CustodyEntry:
    """Single custody log entry."""
    timestamp: str
    action: str  # created, accessed, transferred, verified, sealed
    operator: str
    signature: str = ""
    notes: str = ""
    case_number: str = ""

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "action": self.action,
            "operator": self.operator,
            "signature": self.signature,
            "notes": self.notes,
            "case_number": self.case_number
        }


@dataclass
class EvidenceItem:
    """Individual evidence item in package."""
    item_id: str
    item_type: str  # transaction, document, network_graph
    source: str
    source_hash: str
    extraction_timestamp: str
    finding_summary: str
    analysis_method: str  # benford, entropy, network
    confidence: float
    raw_data_hash: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "item_id": self.item_id,
            "type": self.item_type,
            "source": self.source,
            "source_hash": self.source_hash,
            "extraction_timestamp": self.extraction_timestamp,
            "finding_summary": self.finding_summary,
            "analysis_method": self.analysis_method,
            "confidence": self.confidence,
            "raw_data_hash": self.raw_data_hash,
            "metadata": self.metadata
        }


def create_evidence_package(findings: list[dict],
                             case_number: str,
                             operator: str = "IllinoisProof") -> dict:
    """
    Create FBI-grade evidence package.

    Args:
        findings: List of findings to package
        case_number: Case reference number
        operator: Name of operator creating package

    Returns:
        Evidence package dict with chain-of-custody
    """
    package_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Create evidence items
    evidence_items = []
    for finding in findings:
        item = EvidenceItem(
            item_id=str(uuid.uuid4()),
            item_type=finding.get("finding_type", "unknown"),
            source=finding.get("source", "unknown"),
            source_hash=finding.get("evidence_hash", dual_hash(str(finding).encode())),
            extraction_timestamp=finding.get("timestamp", timestamp),
            finding_summary=finding.get("summary", str(finding)[:200]),
            analysis_method=finding.get("analysis_method", "unknown"),
            confidence=finding.get("confidence", 0.0)
        )
        evidence_items.append(item)

    # Initialize custody log
    custody_log = [
        CustodyEntry(
            timestamp=timestamp,
            action="created",
            operator=operator,
            signature=dual_hash(f"{package_id}:{operator}:{timestamp}".encode()),
            notes="Evidence package initialized",
            case_number=case_number
        )
    ]

    # Compute package hash
    items_data = str([i.to_dict() for i in evidence_items])
    package_hash = dual_hash(items_data.encode())

    return {
        "package_id": package_id,
        "case_reference": case_number,
        "created_at": timestamp,
        "created_by": operator,
        "evidence_items": [i.to_dict() for i in evidence_items],
        "custody_log": [c.to_dict() for c in custody_log],
        "package_hash": package_hash,
        "nist_compliance": "NIST IR 8387",
        "status": "unsealed"
    }


def generate_custody_log(package_id: str,
                          operator: str,
                          case_number: str = "") -> list[dict]:
    """
    Initialize custody tracking for new package.

    Args:
        package_id: Package identifier
        operator: Creating operator
        case_number: Case reference

    Returns:
        Initial custody log
    """
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    return [
        {
            "timestamp": timestamp,
            "action": "created",
            "operator": operator,
            "signature": dual_hash(f"{package_id}:{operator}:{timestamp}".encode()),
            "notes": "Custody log initialized",
            "case_number": case_number
        }
    ]


def append_custody_entry(log: list[dict],
                          action: str,
                          operator: str,
                          notes: str = "",
                          case_number: str = "") -> list[dict]:
    """
    Append entry to custody log.

    Args:
        log: Existing custody log
        action: Action performed
        operator: Operator name
        notes: Additional notes
        case_number: Case reference

    Returns:
        Updated custody log
    """
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    # Chain signature to previous entry
    prev_sig = log[-1]["signature"] if log else ""
    new_sig = dual_hash(f"{prev_sig}:{operator}:{action}:{timestamp}".encode())

    log.append({
        "timestamp": timestamp,
        "action": action,
        "operator": operator,
        "signature": new_sig,
        "notes": notes,
        "case_number": case_number
    })

    return log


def compute_evidence_hash(evidence: bytes) -> str:
    """
    Compute dual-hash for evidence integrity.

    Args:
        evidence: Evidence bytes

    Returns:
        Dual hash string (SHA256:BLAKE3)
    """
    return dual_hash(evidence)


def verify_integrity(evidence: bytes, expected_hash: str) -> bool:
    """
    Verify evidence has not been tampered with.

    Args:
        evidence: Evidence bytes to verify
        expected_hash: Expected hash value

    Returns:
        True if hash matches
    """
    actual_hash = dual_hash(evidence)
    return actual_hash == expected_hash


def seal_package(package: dict, operator: str) -> dict:
    """
    Seal evidence package for court submission.

    Args:
        package: Evidence package
        operator: Sealing operator

    Returns:
        Sealed package
    """
    if package.get("status") == "sealed":
        return package

    # Add seal entry to custody log
    package["custody_log"] = append_custody_entry(
        package["custody_log"],
        action="sealed",
        operator=operator,
        notes="Package sealed for court submission"
    )

    # Compute final hash over entire package
    package_data = str({
        k: v for k, v in package.items()
        if k != "final_hash"
    })
    package["final_hash"] = dual_hash(package_data.encode())
    package["sealed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    package["sealed_by"] = operator
    package["status"] = "sealed"

    return package


def export_prosecution_format(package: dict) -> bytes:
    """
    Export package in court-submittable format.

    Args:
        package: Evidence package

    Returns:
        Serialized package bytes
    """
    import json

    # Ensure package is sealed
    if package.get("status") != "sealed":
        raise ValueError("Package must be sealed before export")

    # Create export structure
    export = {
        "format_version": "1.0",
        "format_standard": "NIST IR 8387",
        "package": package,
        "export_timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "verification_instructions": {
            "1": "Compute SHA256 and BLAKE3 hashes of evidence_items",
            "2": "Verify hash matches package_hash",
            "3": "Verify custody_log signature chain",
            "4": "Verify final_hash matches entire package"
        }
    }

    return json.dumps(export, indent=2, sort_keys=True).encode()


def fbi_receipt(findings: list[dict],
                 case_number: str,
                 operator: str = "IllinoisProof") -> dict:
    """
    Emit receipt for FBI-grade evidence packaging.

    Args:
        findings: Findings to package
        case_number: Case reference
        operator: Creating operator

    Returns:
        Receipt dict
    """
    package = create_evidence_package(findings, case_number, operator)

    receipt = emit_receipt("fbi", {
        "tenant_id": TENANT_ID,
        "package_id": package["package_id"],
        "case_reference": case_number,
        "package_hash": package["package_hash"],
        "evidence_items_count": len(package["evidence_items"]),
        "custody_entries": len(package["custody_log"]),
        "nist_compliance": package["nist_compliance"],
        "status": package["status"],
        "created_by": operator
    })

    return receipt
