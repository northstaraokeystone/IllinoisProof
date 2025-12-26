"""
Tests for simulation scenarios.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.sim import (
    run_simulation, run_scenario, run_calibration_check,
    generate_synthetic_transactions, inject_fraud_pattern,
    run_detection_cycle, validate_detection,
    SimConfig, CALIBRATION_DATA
)
from src.core import SimResult


class TestSimulation:
    """Tests for simulation harness."""

    def test_simconfig_defaults(self):
        """Test default simulation configuration."""
        config = SimConfig()
        assert config.n_cycles == 1000
        assert config.fraud_injection_rate == 0.05

    def test_generate_synthetic_transactions(self):
        """Test synthetic transaction generation."""
        transactions = generate_synthetic_transactions(100, distribution="normal", seed=42)

        assert len(transactions) == 100
        assert all("amount" in t for t in transactions)
        assert all("vendor" in t for t in transactions)

    def test_generate_benford_transactions(self):
        """Test Benford-compliant transaction generation."""
        transactions = generate_synthetic_transactions(1000, distribution="benford", seed=42)

        # Check first digit distribution roughly follows Benford
        first_digits = []
        for t in transactions:
            amount = t["amount"]
            while amount >= 10:
                amount /= 10
            first_digits.append(int(amount))

        digit_1_count = first_digits.count(1)
        # Benford expects ~30% ones
        assert digit_1_count / len(transactions) > 0.2

    def test_inject_fraud_round_numbers(self):
        """Test round number fraud injection."""
        transactions = generate_synthetic_transactions(100, seed=42)
        modified = inject_fraud_pattern(transactions, "round_numbers", rate=0.1)

        injected = [t for t in modified if t.get("_fraud_injected")]
        assert len(injected) >= 5  # At least some injected

    def test_inject_fraud_vendor_concentration(self):
        """Test vendor concentration fraud injection."""
        transactions = generate_synthetic_transactions(100, seed=42)
        modified = inject_fraud_pattern(transactions, "vendor_concentration", rate=0.1)

        # Check vendor concentration
        vendors = [t.get("vendor") for t in modified]
        concentrated = vendors.count("Vendor-CONCENTRATED")
        assert concentrated > 10

    def test_run_detection_cycle(self):
        """Test single detection cycle."""
        transactions = generate_synthetic_transactions(100, seed=42)
        result = run_detection_cycle(transactions, ["benford", "entropy"])

        assert "findings" in result
        assert "methods_applied" in result

    def test_validate_detection(self):
        """Test detection validation."""
        predictions = [{"id": "TX-001", "flagged": True}]
        ground_truth = [{"id": "TX-001", "_fraud_injected": True}]

        metrics = validate_detection(predictions, ground_truth)

        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1_score" in metrics

    def test_run_simulation_basic(self):
        """Test basic simulation run."""
        config = SimConfig(n_cycles=10, fraud_injection_rate=0.05)
        result = run_simulation(config)

        assert isinstance(result, SimResult)
        assert result.config.n_cycles == 10


class TestScenarios:
    """Tests for specific simulation scenarios."""

    def test_baseline_scenario(self):
        """Test BASELINE scenario."""
        result = run_scenario("BASELINE")

        assert isinstance(result, SimResult)
        assert len(result.state.violations) == 0

    def test_dolton_calibration_scenario(self):
        """Test DOLTON_CALIBRATION scenario."""
        result = run_scenario("DOLTON_CALIBRATION")

        assert isinstance(result, SimResult)
        assert result.detection_rate >= 0

    def test_ides_calibration_scenario(self):
        """Test IDES_CALIBRATION scenario."""
        result = run_scenario("IDES_CALIBRATION")

        assert isinstance(result, SimResult)
        assert result.detection_rate >= 0

    def test_madigan_calibration_scenario(self):
        """Test MADIGAN_CALIBRATION scenario."""
        result = run_scenario("MADIGAN_CALIBRATION")

        assert isinstance(result, SimResult)
        assert result.detection_rate >= 0

    def test_cascade_scenario(self):
        """Test CASCADE scenario."""
        result = run_scenario("CASCADE")

        assert isinstance(result, SimResult)

    def test_godel_scenario(self):
        """Test GODEL edge case scenario."""
        result = run_scenario("GODEL")

        assert isinstance(result, SimResult)
        # GODEL tests graceful degradation
        assert result.detection_rate >= 0

    def test_unknown_scenario_raises(self):
        """Test that unknown scenario raises error."""
        with pytest.raises(ValueError):
            run_scenario("UNKNOWN_SCENARIO")


class TestCalibration:
    """Tests for calibration data."""

    def test_calibration_data_structure(self):
        """Test calibration data is properly structured."""
        assert "dolton" in CALIBRATION_DATA
        assert "ides" in CALIBRATION_DATA
        assert "madigan" in CALIBRATION_DATA

    def test_dolton_calibration_values(self):
        """Test Dolton calibration values."""
        dolton = CALIBRATION_DATA["dolton"]

        assert dolton["credit_card_missing_receipts"] == 779000
        assert dolton["amazon_single_purchase"] == 33027
        assert dolton["overtime_332_hours"] is True

    def test_ides_calibration_values(self):
        """Test IDES calibration values."""
        ides = CALIBRATION_DATA["ides"]

        assert ides["total_overpayments"] == 5240000000
        assert ides["recovered"] == 511700000
        assert ides["non_recoverable"] == 2800000000

    def test_madigan_calibration_values(self):
        """Test Madigan calibration values."""
        madigan = CALIBRATION_DATA["madigan"]

        assert madigan["dpa_fine"] == 200000000
        assert madigan["sb1652_bribery"] is True

    def test_run_calibration_check(self):
        """Test calibration check function."""
        match_rate = run_calibration_check()

        assert 0 <= match_rate <= 1
        assert match_rate >= 0.5  # Should match at least half
