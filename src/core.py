"""
IllinoisProof Core Module

Contains foundational functions required by all modules:
- dual_hash: SHA256:BLAKE3 dual hashing
- emit_receipt: Receipt emission for all operations
- StopRule: Exception for stoprule violations
- merkle: Merkle tree root computation
"""

import hashlib
import json
import gzip
import sys
from datetime import datetime, timezone
from typing import Any
from dataclasses import dataclass, field, asdict

try:
    import blake3
    HAS_BLAKE3 = True
except ImportError:
    HAS_BLAKE3 = False

# Tenant ID for all receipts
TENANT_ID = "illinoisproof"

# Receipt ledger file path
RECEIPTS_FILE = "receipts.jsonl"


class StopRule(Exception):
    """Raised when a stoprule triggers. Never catch silently."""

    def __init__(self, message: str, metric: str = "unknown", action: str = "halt"):
        self.message = message
        self.metric = metric
        self.action = action
        super().__init__(message)


def dual_hash(data: bytes | str) -> str:
    """
    SHA256:BLAKE3 - ALWAYS use this, never single hash.

    Args:
        data: Bytes or string to hash

    Returns:
        String in format "sha256_hex:blake3_hex"
    """
    if isinstance(data, str):
        data = data.encode('utf-8')

    sha = hashlib.sha256(data).hexdigest()

    if HAS_BLAKE3:
        b3 = blake3.blake3(data).hexdigest()
    else:
        # Fallback: use SHA256 for both if blake3 not available
        b3 = sha

    return f"{sha}:{b3}"


def emit_receipt(receipt_type: str, data: dict, to_file: bool = False) -> dict:
    """
    Every function calls this. No exceptions.

    Args:
        receipt_type: Type of receipt (ingest, benford, entropy, etc.)
        data: Receipt payload data
        to_file: If True, also append to receipts.jsonl

    Returns:
        Complete receipt dict with metadata
    """
    # Ensure tenant_id is present
    if "tenant_id" not in data:
        data["tenant_id"] = TENANT_ID

    receipt = {
        "receipt_type": receipt_type,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "tenant_id": data.get("tenant_id", TENANT_ID),
        "payload_hash": dual_hash(json.dumps(data, sort_keys=True)),
        **data
    }

    receipt_json = json.dumps(receipt, sort_keys=True)

    # Output to stdout for pipeline consumption
    print(receipt_json, flush=True)

    # Optionally append to ledger file
    if to_file:
        try:
            with open(RECEIPTS_FILE, "a") as f:
                f.write(receipt_json + "\n")
        except IOError:
            pass  # Don't fail on file write issues in non-critical path

    return receipt


def merkle(items: list) -> str:
    """
    Compute Merkle root of items using BLAKE3.

    Args:
        items: List of items (will be JSON serialized)

    Returns:
        Dual hash of merkle root
    """
    if not items:
        return dual_hash(b"empty")

    # Hash each item
    hashes = [dual_hash(json.dumps(i, sort_keys=True)) for i in items]

    # Build tree
    while len(hashes) > 1:
        # Pad with last element if odd
        if len(hashes) % 2:
            hashes.append(hashes[-1])
        # Combine pairs
        hashes = [dual_hash(hashes[i] + hashes[i + 1])
                  for i in range(0, len(hashes), 2)]

    return hashes[0]


def verify_merkle_proof(item: dict, proof: list[tuple[str, str]], root: str) -> bool:
    """
    Verify a Merkle proof for an item.

    Args:
        item: The item to verify
        proof: List of (sibling_hash, position) tuples
        root: Expected Merkle root

    Returns:
        True if proof is valid
    """
    current_hash = dual_hash(json.dumps(item, sort_keys=True))

    for sibling_hash, position in proof:
        if position == "left":
            current_hash = dual_hash(sibling_hash + current_hash)
        else:
            current_hash = dual_hash(current_hash + sibling_hash)

    return current_hash == root


@dataclass
class SimConfig:
    """Configuration for Monte Carlo simulation."""
    n_cycles: int = 1000
    tiers: list = field(default_factory=lambda: ["dolton", "ides", "madigan"])
    fraud_injection_rate: float = 0.05
    detection_methods: list = field(default_factory=lambda: ["benford", "entropy", "network"])
    random_seed: int = 42
    use_calibration_data: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SimState:
    """State tracking for simulation runs."""
    findings: list = field(default_factory=list)
    receipts: list = field(default_factory=list)
    violations: list = field(default_factory=list)
    detection_accuracy: dict = field(default_factory=dict)
    cycle: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SimResult:
    """Result of a simulation run."""
    config: SimConfig
    state: SimState
    detection_rate: float = 0.0
    precision: float = 0.0
    recall: float = 0.0
    f1_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "config": self.config.to_dict(),
            "state": self.state.to_dict(),
            "detection_rate": self.detection_rate,
            "precision": self.precision,
            "recall": self.recall,
            "f1_score": self.f1_score
        }


def compute_compression_ratio(data: bytes) -> float:
    """
    Compute compression ratio for anomaly detection.

    Args:
        data: Bytes to compress

    Returns:
        Ratio of compressed size to original size
    """
    if not data:
        return 1.0

    compressed = gzip.compress(data, compresslevel=9)
    return len(compressed) / len(data)


def compute_ncd(data1: bytes, data2: bytes) -> float:
    """
    Compute Normalized Compression Distance between two byte sequences.

    NCD(x,y) = (C(xy) - min(C(x), C(y))) / max(C(x), C(y))

    Args:
        data1: First byte sequence
        data2: Second byte sequence

    Returns:
        NCD value between 0 (identical) and ~1 (unrelated)
    """
    if not data1 or not data2:
        return 1.0

    c1 = len(gzip.compress(data1, compresslevel=9))
    c2 = len(gzip.compress(data2, compresslevel=9))
    c12 = len(gzip.compress(data1 + data2, compresslevel=9))

    return (c12 - min(c1, c2)) / max(c1, c2)


def stoprule_halt(metric: str, message: str, baseline: float = 0.0, delta: float = 0.0):
    """
    Emit anomaly receipt and halt execution.

    Args:
        metric: Name of the metric that triggered
        message: Error message
        baseline: Expected baseline value
        delta: Deviation from baseline
    """
    emit_receipt("anomaly", {
        "metric": metric,
        "baseline": baseline,
        "delta": delta,
        "classification": "violation",
        "action": "halt",
        "tenant_id": TENANT_ID
    })
    raise StopRule(message, metric=metric, action="halt")


def stoprule_escalate(metric: str, message: str, baseline: float = 0.0, delta: float = 0.0):
    """
    Emit anomaly receipt and escalate for human review.

    Args:
        metric: Name of the metric that triggered
        message: Error message
        baseline: Expected baseline value
        delta: Deviation from baseline
    """
    emit_receipt("anomaly", {
        "metric": metric,
        "baseline": baseline,
        "delta": delta,
        "classification": "degradation",
        "action": "escalate",
        "tenant_id": TENANT_ID
    })
    raise StopRule(message, metric=metric, action="escalate")


def stoprule_alert(metric: str, message: str, baseline: float = 0.0, delta: float = 0.0) -> dict:
    """
    Emit anomaly receipt and continue with alert.

    Args:
        metric: Name of the metric that triggered
        message: Alert message
        baseline: Expected baseline value
        delta: Deviation from baseline

    Returns:
        The anomaly receipt
    """
    return emit_receipt("anomaly", {
        "metric": metric,
        "baseline": baseline,
        "delta": delta,
        "classification": "drift",
        "action": "alert",
        "tenant_id": TENANT_ID
    })
