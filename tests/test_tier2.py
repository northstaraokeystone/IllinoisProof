"""
Tests for Tier 2 (IDES) detection modules.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tier2_ides.crossmatch import (
    simulate_crossmatch_gap,
    detect_deceased_during_gap,
    detect_incarcerated_during_gap,
    analyze_crossmatch_impact,
    CROSSMATCH_GAPS
)
from src.tier2_ides.recovery import (
    compute_recovery_rate,
    segment_by_recoverability,
    recovery_trend,
    analyze_recovery_performance,
    KNOWN_STATS
)
from src.tier2_ides.waiver import (
    waiver_pattern_analysis,
    detect_waiver_gaming,
    analyze_waiver_timing
)


class TestCrossmatch:
    """Tests for crossmatch gap analysis."""

    def test_known_gaps_defined(self):
        """Test that known gaps are properly defined."""
        assert "prison_registry" in CROSSMATCH_GAPS
        assert "death_master" in CROSSMATCH_GAPS
        assert CROSSMATCH_GAPS["prison_registry"]["gap_start"] == "2020-03-01"

    def test_simulate_crossmatch_gap(self, sample_claims):
        """Test gap simulation."""
        result = simulate_crossmatch_gap(
            sample_claims,
            gap_start="2020-03-01",
            gap_end="2021-09-30"
        )
        assert "claims_during_gap" in result
        assert "gap_total_amount" in result

    def test_detect_deceased_during_gap(self):
        """Test deceased claimant detection."""
        claims = [
            {"ssn": "111-11-1111", "claim_date": "2020-06-15", "amount": 5000}
        ]
        deaths = [
            {"ssn": "111-11-1111", "death_date": "2019-01-01"}
        ]
        flags = detect_deceased_during_gap(
            claims, deaths,
            gap_start="2020-03-01",
            gap_end="2021-09-30"
        )
        assert len(flags) == 1
        assert flags[0]["finding_type"] == "deceased_during_gap"

    def test_detect_incarcerated_during_gap(self):
        """Test incarcerated claimant detection."""
        claims = [
            {"ssn": "222-22-2222", "claim_date": "2020-07-15", "amount": 4500}
        ]
        prison = [
            {"ssn": "222-22-2222", "start_date": "2020-01-01", "end_date": "2021-12-31", "facility": "State Prison"}
        ]
        flags = detect_incarcerated_during_gap(
            claims, prison,
            gap_start="2020-03-01",
            gap_end="2021-09-30"
        )
        assert len(flags) == 1
        assert flags[0]["finding_type"] == "incarcerated_during_gap"

    def test_analyze_crossmatch_impact(self, sample_claims, ides_calibration):
        """Test comprehensive crossmatch analysis."""
        result = analyze_crossmatch_impact(sample_claims)
        assert "gaps_analyzed" in result
        assert "deceased_flags" in result
        assert "incarcerated_flags" in result


class TestRecovery:
    """Tests for recovery analysis."""

    def test_known_stats(self):
        """Test known statistics are defined."""
        assert KNOWN_STATS["total_overpayments"] == 5_240_000_000
        assert KNOWN_STATS["recovered"] == 511_700_000

    def test_compute_recovery_rate(self):
        """Test recovery rate calculation."""
        overpayments = [
            {"overpayment_id": "OP-001", "amount": 10000},
            {"overpayment_id": "OP-002", "amount": 5000}
        ]
        recoveries = [
            {"overpayment_id": "OP-001", "amount_recovered": 5000}
        ]
        rate = compute_recovery_rate(overpayments, recoveries)
        assert rate == pytest.approx(5000 / 15000)

    def test_segment_by_recoverability(self):
        """Test recoverability segmentation."""
        overpayments = [
            {"category": "identity_theft", "amount": 100000},
            {"category": "error", "amount": 50000},
            {"category": "fraud", "amount": 25000}
        ]
        result = segment_by_recoverability(overpayments)

        assert result["segments"]["identity_theft"]["amount"] == 100000
        assert result["non_recoverable_amount"] == 100000
        assert result["recoverable_amount"] == 75000

    def test_recovery_trend(self):
        """Test recovery trend analysis."""
        recoveries = [
            {"date": "2024-01-15", "amount_recovered": 1000},
            {"date": "2024-01-20", "amount_recovered": 1500},
            {"date": "2024-02-10", "amount_recovered": 2000}
        ]
        trend = recovery_trend(recoveries, period="month")

        assert len(trend) == 2  # Jan and Feb
        assert trend[0]["period"] == "2024-01"

    def test_analyze_recovery_performance(self):
        """Test comprehensive recovery analysis."""
        overpayments = [{"overpayment_id": "OP-001", "amount": 10000}]
        recoveries = [{"overpayment_id": "OP-001", "amount_recovered": 1000}]

        result = analyze_recovery_performance(overpayments, recoveries)

        assert result["recovery_rate"] == 0.1
        assert result["total_recovered"] == 1000


class TestWaiver:
    """Tests for waiver analysis."""

    def test_waiver_pattern_analysis(self):
        """Test waiver pattern analysis."""
        waivers = [
            {"claimant_id": "C-001", "status": "approved", "amount": 1000},
            {"claimant_id": "C-002", "status": "denied", "amount": 2000},
            {"claimant_id": "C-003", "status": "denied", "amount": 1500}
        ]
        result = waiver_pattern_analysis(waivers)

        assert result["total_waivers"] == 3
        assert result["approved"] == 1
        assert result["denied"] == 2
        assert result["denial_rate"] == pytest.approx(2/3)

    def test_detect_waiver_gaming_multiple_requests(self):
        """Test detection of multiple waiver requests."""
        waivers = [
            {"claimant_id": "C-001", "overpayment_id": "OP-001", "status": "denied", "date": "2024-01-01", "amount": 1000},
            {"claimant_id": "C-001", "overpayment_id": "OP-002", "status": "denied", "date": "2024-02-01", "amount": 1000},
            {"claimant_id": "C-001", "overpayment_id": "OP-003", "status": "denied", "date": "2024-03-01", "amount": 1000},
            {"claimant_id": "C-001", "overpayment_id": "OP-004", "status": "pending", "date": "2024-04-01", "amount": 1000}
        ]
        flags = detect_waiver_gaming(waivers, [])

        assert any(f["flag_type"] == "multiple_waiver_requests" for f in flags)

    def test_analyze_waiver_timing(self):
        """Test waiver timing analysis."""
        waivers = [
            {"date": "2024-01-15", "amount": 1000},
            {"date": "2024-01-20", "amount": 1500},
            {"date": "2024-02-10", "amount": 2000}
        ]
        result = analyze_waiver_timing(waivers)

        assert "trend" in result
        assert "peak_month" in result
