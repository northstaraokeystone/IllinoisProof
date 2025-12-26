"""
Benford's Law Analysis Module

Purpose: First-digit distribution testing reveals manufactured vs organic financial data.

Mathematical Basis:
- Natural financial data follows: P(d) = log10(1 + 1/d)
- Expected first-digit frequencies: 1=30.1%, 2=17.6%, 3=12.5%, ...
- Chi-squared test for conformity
- 2BL-test (second-leading digit) is most sensitive for fraud detection
"""

import math
from typing import Optional
import sys
sys.path.insert(0, "..")
from src.core import emit_receipt, TENANT_ID, stoprule_alert


def benford_expected(digit_position: int = 1) -> dict:
    """
    Return expected Benford's Law frequencies.

    Args:
        digit_position: 1 for first digit, 2 for second digit

    Returns:
        Dict mapping digit (1-9 or 0-9) to expected frequency
    """
    if digit_position == 1:
        # First digit: P(d) = log10(1 + 1/d) for d in 1-9
        return {d: math.log10(1 + 1/d) for d in range(1, 10)}
    else:
        # Second digit distribution
        expected = {}
        for d in range(0, 10):
            prob = sum(math.log10(1 + 1/(10*k + d)) for k in range(1, 10))
            expected[d] = prob
        return expected


def extract_first_digit(values: list[float]) -> list[int]:
    """
    Extract leading digit from each value.

    Args:
        values: List of financial values

    Returns:
        List of first digits (1-9)
    """
    digits = []
    for v in values:
        if v == 0:
            continue
        v = abs(v)
        # Get first digit by repeatedly dividing/multiplying by 10
        while v >= 10:
            v /= 10
        while v < 1:
            v *= 10
        digits.append(int(v))
    return digits


def extract_second_digit(values: list[float]) -> list[int]:
    """
    Extract second digit from each value.

    Args:
        values: List of financial values

    Returns:
        List of second digits (0-9)
    """
    digits = []
    for v in values:
        if v == 0:
            continue
        v = abs(v)
        # Get to two significant digits
        while v >= 100:
            v /= 10
        while v < 10:
            v *= 10
        # Second digit is the ones place
        digits.append(int(v) % 10)
    return digits


def compute_observed_frequencies(digits: list[int], digit_position: int = 1) -> dict:
    """
    Compute observed frequency distribution.

    Args:
        digits: List of extracted digits
        digit_position: 1 for first digit (1-9), 2 for second (0-9)

    Returns:
        Dict mapping digit to observed frequency
    """
    if not digits:
        if digit_position == 1:
            return {d: 0.0 for d in range(1, 10)}
        else:
            return {d: 0.0 for d in range(0, 10)}

    counts = {}
    digit_range = range(1, 10) if digit_position == 1 else range(0, 10)

    for d in digit_range:
        counts[d] = 0

    for digit in digits:
        if digit in counts:
            counts[digit] += 1

    total = len(digits)
    return {d: count / total for d, count in counts.items()}


def chi_squared_test(observed: dict, expected: dict, n: int) -> dict:
    """
    Perform chi-squared test for Benford conformity.

    Args:
        observed: Observed frequency dict
        expected: Expected frequency dict
        n: Sample size

    Returns:
        Dict with chi_squared, p_value, pass_fail, degrees_of_freedom
    """
    if n == 0:
        return {
            "chi_squared": 0.0,
            "p_value": 1.0,
            "pass_fail": "insufficient_data",
            "degrees_of_freedom": len(expected) - 1
        }

    chi_sq = 0.0
    for d in expected:
        obs = observed.get(d, 0) * n
        exp = expected[d] * n
        if exp > 0:
            chi_sq += ((obs - exp) ** 2) / exp

    df = len(expected) - 1

    # Chi-squared p-value approximation
    # Using Wilson-Hilferty approximation for simplicity
    # For exact values, would need scipy.stats.chi2.sf
    p_value = _chi2_pvalue_approx(chi_sq, df)

    # Flag thresholds from spec
    if p_value < 0.01:
        pass_fail = "high_priority_anomaly"
    elif p_value < 0.05:
        pass_fail = "flag_for_investigation"
    else:
        pass_fail = "pass"

    return {
        "chi_squared": chi_sq,
        "p_value": p_value,
        "pass_fail": pass_fail,
        "degrees_of_freedom": df
    }


def _chi2_pvalue_approx(chi_sq: float, df: int) -> float:
    """
    Approximate chi-squared p-value using Wilson-Hilferty transformation.

    This is a reasonable approximation; for production use scipy.stats.chi2.sf
    """
    if df <= 0:
        return 1.0
    if chi_sq <= 0:
        return 1.0

    # Wilson-Hilferty approximation
    z = ((chi_sq / df) ** (1/3) - (1 - 2/(9*df))) / math.sqrt(2/(9*df))

    # Standard normal CDF approximation (Abramowitz and Stegun)
    if z > 6:
        return 0.0
    if z < -6:
        return 1.0

    # Error function approximation
    t = 1.0 / (1.0 + 0.2316419 * abs(z))
    d = 0.3989422804014327  # 1/sqrt(2*pi)
    p = d * math.exp(-z * z / 2.0) * (
        t * (0.319381530 +
             t * (-0.356563782 +
                  t * (1.781477937 +
                       t * (-1.821255978 +
                            t * 1.330274429))))
    )

    return p if z > 0 else 1 - p


def analyze_benford(values: list[float], entity: str, digit_position: int = 1) -> dict:
    """
    Perform complete Benford's Law analysis on a dataset.

    Args:
        values: List of financial values
        entity: Name of entity being analyzed
        digit_position: 1 or 2 for first/second digit test

    Returns:
        Analysis result dict
    """
    if digit_position == 1:
        digits = extract_first_digit(values)
    else:
        digits = extract_second_digit(values)

    observed = compute_observed_frequencies(digits, digit_position)
    expected = benford_expected(digit_position)
    test_result = chi_squared_test(observed, expected, len(digits))

    result = {
        "entity": entity,
        "digit_position": digit_position,
        "sample_size": len(digits),
        "observed_frequencies": observed,
        "expected_frequencies": expected,
        **test_result
    }

    return result


def benford_receipt(data: list[float], source: str, entity: str,
                    digit_position: int = 1) -> dict:
    """
    Emit receipt with Benford's Law analysis results.

    Args:
        data: Financial values to analyze
        source: Data source identifier
        entity: Entity being analyzed
        digit_position: 1 or 2 for first/second digit

    Returns:
        Receipt dict with analysis results
    """
    analysis = analyze_benford(data, entity, digit_position)

    receipt = emit_receipt("benford", {
        "tenant_id": TENANT_ID,
        "entity": entity,
        "source": source,
        "chi_squared": analysis["chi_squared"],
        "p_value": analysis["p_value"],
        "pass_fail": analysis["pass_fail"],
        "digit_position": digit_position,
        "sample_size": analysis["sample_size"],
        "observed_frequencies": analysis["observed_frequencies"],
        "expected_frequencies": analysis["expected_frequencies"]
    })

    # Emit alert if flagged
    if analysis["pass_fail"] in ["flag_for_investigation", "high_priority_anomaly"]:
        stoprule_alert(
            metric="benford_conformity",
            message=f"Benford anomaly detected for {entity}",
            baseline=0.05,
            delta=0.05 - analysis["p_value"]
        )

    return receipt


def detect_round_numbers(values: list[float], thresholds: Optional[list[float]] = None) -> list[dict]:
    """
    Detect suspiciously round numbers in financial data.

    Round numbers are more likely in fraudulent data.

    Args:
        values: Financial values
        thresholds: Round number thresholds to check (default: common amounts)

    Returns:
        List of flagged transactions with round number flags
    """
    if thresholds is None:
        thresholds = [1000, 5000, 10000, 25000, 33000, 50000, 100000]

    flags = []
    for i, v in enumerate(values):
        v = abs(v)
        # Check if value is within 5% of any threshold
        for thresh in thresholds:
            if abs(v - thresh) / thresh < 0.05:
                flags.append({
                    "index": i,
                    "value": v,
                    "threshold": thresh,
                    "flag_type": "round_number"
                })
                break

        # Also flag exact round thousands
        if v >= 1000 and v % 1000 == 0:
            flags.append({
                "index": i,
                "value": v,
                "threshold": v,
                "flag_type": "exact_thousands"
            })

    return flags
