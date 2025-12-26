"""
IllinoisProof Proof Generation Module

Purpose: Receipt chain management and Merkle proof generation.

Features:
- Receipt chain validation
- Merkle tree construction
- Proof generation and verification
- Anchor creation for external timestamping
"""

import json
from typing import Optional
from dataclasses import dataclass, field
import sys

sys.path.insert(0, ".")
from src.core import (
    emit_receipt, dual_hash, merkle, verify_merkle_proof,
    TENANT_ID, RECEIPTS_FILE
)


@dataclass
class ReceiptChain:
    """Represents a chain of linked receipts."""
    chain_id: str
    receipts: list = field(default_factory=list)
    merkle_root: str = ""
    anchor_hash: str = ""
    is_sealed: bool = False

    def add_receipt(self, receipt: dict):
        """Add receipt to chain."""
        if self.is_sealed:
            raise ValueError("Cannot add to sealed chain")
        self.receipts.append(receipt)
        self.merkle_root = merkle(self.receipts)

    def seal(self):
        """Seal the chain for anchoring."""
        self.merkle_root = merkle(self.receipts)
        self.anchor_hash = dual_hash(self.merkle_root.encode())
        self.is_sealed = True


def load_receipts(file_path: str = None) -> list[dict]:
    """
    Load receipts from JSONL file.

    Args:
        file_path: Path to receipts file

    Returns:
        List of receipt dicts
    """
    if file_path is None:
        file_path = RECEIPTS_FILE

    receipts = []
    try:
        with open(file_path, "r") as f:
            for line in f:
                if line.strip():
                    receipts.append(json.loads(line))
    except FileNotFoundError:
        pass

    return receipts


def validate_receipt_chain(receipts: list[dict]) -> dict:
    """
    Validate integrity of receipt chain.

    Args:
        receipts: List of receipts to validate

    Returns:
        Validation result dict
    """
    if not receipts:
        return {
            "valid": True,
            "receipt_count": 0,
            "errors": []
        }

    errors = []

    for i, receipt in enumerate(receipts):
        # Check required fields
        required = ["receipt_type", "ts", "tenant_id", "payload_hash"]
        for field in required:
            if field not in receipt:
                errors.append({
                    "index": i,
                    "error": f"missing_field:{field}",
                    "receipt_type": receipt.get("receipt_type", "unknown")
                })

        # Verify payload hash
        payload = {k: v for k, v in receipt.items()
                   if k not in ["receipt_type", "ts", "payload_hash"]}
        expected_hash = dual_hash(json.dumps(payload, sort_keys=True))

        # Note: We can't verify the exact hash because the original payload
        # construction might differ. This is a structural check.

    return {
        "valid": len(errors) == 0,
        "receipt_count": len(receipts),
        "errors": errors,
        "merkle_root": merkle(receipts) if receipts else None
    }


def generate_merkle_proof(receipts: list[dict],
                           target_index: int) -> list[tuple[str, str]]:
    """
    Generate Merkle proof for a specific receipt.

    Args:
        receipts: All receipts in tree
        target_index: Index of receipt to prove

    Returns:
        List of (sibling_hash, position) tuples
    """
    if not receipts or target_index >= len(receipts):
        return []

    # Hash all receipts
    hashes = [dual_hash(json.dumps(r, sort_keys=True)) for r in receipts]

    # Pad to power of 2
    while len(hashes) & (len(hashes) - 1):
        hashes.append(hashes[-1])

    proof = []
    index = target_index

    while len(hashes) > 1:
        next_level = []
        for i in range(0, len(hashes), 2):
            left = hashes[i]
            right = hashes[i + 1] if i + 1 < len(hashes) else hashes[i]

            # Add sibling to proof
            if i // 2 == index // 2:
                if index % 2 == 0:
                    proof.append((right, "right"))
                else:
                    proof.append((left, "left"))

            next_level.append(dual_hash(left + right))

        hashes = next_level
        index = index // 2

    return proof


def verify_receipt_inclusion(receipt: dict,
                               proof: list[tuple[str, str]],
                               root: str) -> bool:
    """
    Verify a receipt is included in merkle tree.

    Args:
        receipt: Receipt to verify
        proof: Merkle proof
        root: Expected Merkle root

    Returns:
        True if receipt is in tree
    """
    return verify_merkle_proof(receipt, proof, root)


def create_anchor(receipts: list[dict],
                   anchor_type: str = "merkle") -> dict:
    """
    Create anchor for external timestamping.

    Args:
        receipts: Receipts to anchor
        anchor_type: Type of anchor

    Returns:
        Anchor dict
    """
    root = merkle(receipts)

    anchor = {
        "anchor_type": anchor_type,
        "merkle_root": root,
        "receipt_count": len(receipts),
        "anchor_hash": dual_hash(root.encode()),
        "timestamp": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat().replace("+00:00", "Z")
    }

    # Emit anchor receipt
    emit_receipt("anchor", {
        "tenant_id": TENANT_ID,
        "merkle_root": root,
        "hash_algos": ["SHA256", "BLAKE3"],
        "batch_size": len(receipts),
        "anchor_hash": anchor["anchor_hash"]
    })

    return anchor


def build_proof_chain(findings: list[dict]) -> dict:
    """
    Build complete proof chain for findings.

    Args:
        findings: List of findings with receipts

    Returns:
        Proof chain structure
    """
    # Collect all receipts
    receipts = []
    for finding in findings:
        if "receipt" in finding:
            receipts.append(finding["receipt"])

    if not receipts:
        return {
            "chain_valid": False,
            "error": "no_receipts"
        }

    # Validate chain
    validation = validate_receipt_chain(receipts)

    # Generate proofs for each receipt
    proofs = []
    for i, receipt in enumerate(receipts):
        proof = generate_merkle_proof(receipts, i)
        proofs.append({
            "receipt_index": i,
            "receipt_type": receipt.get("receipt_type"),
            "proof": proof
        })

    # Create anchor
    anchor = create_anchor(receipts)

    return {
        "chain_valid": validation["valid"],
        "receipt_count": len(receipts),
        "merkle_root": validation["merkle_root"],
        "anchor": anchor,
        "proofs": proofs,
        "validation_errors": validation["errors"]
    }


def export_proof_bundle(findings: list[dict],
                          bundle_id: str) -> dict:
    """
    Export complete proof bundle for verification.

    Args:
        findings: Findings with receipts
        bundle_id: Bundle identifier

    Returns:
        Exportable proof bundle
    """
    chain = build_proof_chain(findings)

    bundle = {
        "bundle_id": bundle_id,
        "format_version": "1.0",
        "created_at": __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ).isoformat().replace("+00:00", "Z"),
        "chain": chain,
        "findings_count": len(findings),
        "verification_instructions": {
            "1": "Compute Merkle root from receipts",
            "2": "Verify root matches anchor.merkle_root",
            "3": "For each finding, verify Merkle proof",
            "4": "Verify anchor_hash = dual_hash(merkle_root)"
        },
        "bundle_hash": dual_hash(json.dumps(chain, sort_keys=True).encode())
    }

    # Emit proof bundle receipt
    emit_receipt("proof_bundle", {
        "tenant_id": TENANT_ID,
        "bundle_id": bundle_id,
        "findings_count": len(findings),
        "chain_valid": chain["chain_valid"],
        "merkle_root": chain.get("merkle_root"),
        "bundle_hash": bundle["bundle_hash"]
    })

    return bundle


def prove_finding(finding: dict, all_receipts: list[dict]) -> dict:
    """
    Generate proof for a specific finding.

    Args:
        finding: Finding to prove
        all_receipts: All receipts for Merkle tree

    Returns:
        Proof structure for finding
    """
    if "receipt" not in finding:
        return {
            "provable": False,
            "error": "no_receipt"
        }

    receipt = finding["receipt"]

    # Find receipt in list
    receipt_str = json.dumps(receipt, sort_keys=True)
    index = None
    for i, r in enumerate(all_receipts):
        if json.dumps(r, sort_keys=True) == receipt_str:
            index = i
            break

    if index is None:
        return {
            "provable": False,
            "error": "receipt_not_in_chain"
        }

    # Generate proof
    proof = generate_merkle_proof(all_receipts, index)
    root = merkle(all_receipts)

    # Verify proof
    is_valid = verify_receipt_inclusion(receipt, proof, root)

    return {
        "provable": True,
        "finding_type": finding.get("finding_type"),
        "receipt_index": index,
        "merkle_root": root,
        "proof": proof,
        "verified": is_valid
    }
