"""
Compression-Based Anomaly Detection Module

Purpose: Legitimate data compresses efficiently; fraud introduces entropy.

Mathematical Basis:
- Kolmogorov complexity approximation via compression ratio
- NCD (Normalized Compression Distance) for pattern comparison
- Higher entropy = more anomalous
"""

import gzip
import json
import math
from typing import Optional
import sys
sys.path.insert(0, "..")
from src.core import (
    emit_receipt, TENANT_ID, stoprule_alert,
    compute_compression_ratio, compute_ncd
)


# Baseline statistics cache
_baseline_cache: dict = {}


def entropy_baseline(entity_type: str, period: str) -> dict:
    """
    Load or compute baseline entropy statistics for entity type.

    Args:
        entity_type: Type of entity (municipality, state_agency, pac)
        period: Time period (fiscal_year, quarter, month)

    Returns:
        Dict with mean, std, sample_size for baseline
    """
    cache_key = f"{entity_type}:{period}"

    if cache_key in _baseline_cache:
        return _baseline_cache[cache_key]

    # Default baselines based on entity type
    # These would be computed from historical data in production
    defaults = {
        "municipality": {"mean": 0.45, "std": 0.08, "sample_size": 100},
        "state_agency": {"mean": 0.42, "std": 0.06, "sample_size": 200},
        "pac": {"mean": 0.55, "std": 0.10, "sample_size": 150},
        "contractor": {"mean": 0.50, "std": 0.09, "sample_size": 80},
        "default": {"mean": 0.48, "std": 0.10, "sample_size": 50}
    }

    baseline = defaults.get(entity_type, defaults["default"])
    _baseline_cache[cache_key] = baseline
    return baseline


def set_baseline(entity_type: str, period: str, mean: float, std: float, sample_size: int):
    """
    Set baseline statistics for an entity type.

    Args:
        entity_type: Type of entity
        period: Time period
        mean: Mean compression ratio
        std: Standard deviation
        sample_size: Number of samples in baseline
    """
    cache_key = f"{entity_type}:{period}"
    _baseline_cache[cache_key] = {
        "mean": mean,
        "std": std,
        "sample_size": sample_size
    }


def compute_z_score(ratio: float, baseline: dict) -> float:
    """
    Compute z-score for compression ratio vs baseline.

    Args:
        ratio: Observed compression ratio
        baseline: Baseline statistics dict

    Returns:
        Z-score (positive = higher entropy than expected)
    """
    if baseline["std"] == 0:
        return 0.0

    return (ratio - baseline["mean"]) / baseline["std"]


def entropy_anomaly_check(current: float, baseline: dict) -> dict:
    """
    Check if current entropy is anomalous vs baseline.

    Args:
        current: Current compression ratio
        baseline: Baseline statistics

    Returns:
        Dict with z_score, is_anomaly, severity
    """
    z_score = compute_z_score(current, baseline)

    # Thresholds from spec
    if abs(z_score) > 3.0:
        is_anomaly = True
        severity = "critical"
    elif abs(z_score) > 2.0:
        is_anomaly = True
        severity = "high"
    elif abs(z_score) > 1.5:
        is_anomaly = True
        severity = "medium"
    else:
        is_anomaly = False
        severity = "normal"

    return {
        "z_score": z_score,
        "is_anomaly": is_anomaly,
        "severity": severity,
        "baseline_mean": baseline["mean"],
        "baseline_std": baseline["std"]
    }


def shannon_entropy(data: bytes) -> float:
    """
    Compute Shannon entropy of byte sequence.

    Args:
        data: Byte sequence

    Returns:
        Entropy in bits per byte (0-8)
    """
    if not data:
        return 0.0

    # Count byte frequencies
    freq = [0] * 256
    for byte in data:
        freq[byte] += 1

    # Compute entropy
    length = len(data)
    entropy = 0.0
    for count in freq:
        if count > 0:
            p = count / length
            entropy -= p * math.log2(p)

    return entropy


def analyze_entropy(data: bytes, entity: str, entity_type: str,
                    period: str = "default") -> dict:
    """
    Perform complete entropy analysis on data.

    Args:
        data: Byte sequence to analyze
        entity: Entity name
        entity_type: Type of entity for baseline
        period: Time period for baseline

    Returns:
        Analysis result dict
    """
    ratio = compute_compression_ratio(data)
    shannon = shannon_entropy(data)
    baseline = entropy_baseline(entity_type, period)
    anomaly = entropy_anomaly_check(ratio, baseline)

    return {
        "entity": entity,
        "entity_type": entity_type,
        "compression_ratio": ratio,
        "shannon_entropy": shannon,
        "raw_size": len(data),
        "compressed_size": int(len(data) * ratio),
        **anomaly
    }


def entropy_receipt(entity: str, data: bytes, entity_type: str,
                    period: str = "default") -> dict:
    """
    Emit receipt with entropy analysis results.

    Args:
        entity: Entity name
        data: Data to analyze
        entity_type: Type of entity
        period: Time period

    Returns:
        Receipt dict with analysis results
    """
    analysis = analyze_entropy(data, entity, entity_type, period)

    receipt = emit_receipt("entropy", {
        "tenant_id": TENANT_ID,
        "entity": entity,
        "entity_type": entity_type,
        "compression_ratio": analysis["compression_ratio"],
        "z_score": analysis["z_score"],
        "is_anomaly": analysis["is_anomaly"],
        "severity": analysis["severity"],
        "baseline_mean": analysis["baseline_mean"],
        "baseline_std": analysis["baseline_std"],
        "raw_size": analysis["raw_size"],
        "compressed_size": analysis["compressed_size"],
        "shannon_entropy": analysis["shannon_entropy"]
    })

    # Emit alert if anomalous
    if analysis["is_anomaly"]:
        stoprule_alert(
            metric="entropy_deviation",
            message=f"Entropy anomaly detected for {entity}",
            baseline=analysis["baseline_mean"],
            delta=analysis["compression_ratio"] - analysis["baseline_mean"]
        )

    return receipt


def compare_entities(entity1_data: bytes, entity2_data: bytes,
                     entity1_name: str, entity2_name: str) -> dict:
    """
    Compare entropy patterns between two entities using NCD.

    Args:
        entity1_data: First entity's data
        entity2_data: Second entity's data
        entity1_name: First entity name
        entity2_name: Second entity name

    Returns:
        Comparison result dict
    """
    ncd = compute_ncd(entity1_data, entity2_data)

    # NCD interpretation
    if ncd < 0.3:
        similarity = "highly_similar"
    elif ncd < 0.5:
        similarity = "moderately_similar"
    elif ncd < 0.7:
        similarity = "moderately_different"
    else:
        similarity = "highly_different"

    return {
        "entity1": entity1_name,
        "entity2": entity2_name,
        "ncd": ncd,
        "similarity": similarity,
        "entity1_ratio": compute_compression_ratio(entity1_data),
        "entity2_ratio": compute_compression_ratio(entity2_data)
    }


def detect_pattern_deviation(transactions: list[dict], entity: str,
                              window_size: int = 10) -> list[dict]:
    """
    Detect pattern deviations in transaction stream using rolling entropy.

    Args:
        transactions: List of transaction dicts
        entity: Entity name
        window_size: Rolling window size

    Returns:
        List of deviation flags
    """
    if len(transactions) < window_size * 2:
        return []

    deviations = []
    baseline_ratios = []

    # Compute baseline from first half
    for i in range(len(transactions) // 2 - window_size + 1):
        window = transactions[i:i + window_size]
        data = json.dumps(window, sort_keys=True).encode()
        baseline_ratios.append(compute_compression_ratio(data))

    if not baseline_ratios:
        return []

    baseline_mean = sum(baseline_ratios) / len(baseline_ratios)
    baseline_std = (sum((r - baseline_mean) ** 2 for r in baseline_ratios) / len(baseline_ratios)) ** 0.5

    if baseline_std == 0:
        baseline_std = 0.01  # Prevent division by zero

    # Check second half for deviations
    for i in range(len(transactions) // 2, len(transactions) - window_size + 1):
        window = transactions[i:i + window_size]
        data = json.dumps(window, sort_keys=True).encode()
        ratio = compute_compression_ratio(data)
        z_score = (ratio - baseline_mean) / baseline_std

        if abs(z_score) > 2.0:
            deviations.append({
                "window_start": i,
                "window_end": i + window_size,
                "compression_ratio": ratio,
                "z_score": z_score,
                "entity": entity,
                "flag_type": "pattern_deviation"
            })

    return deviations
