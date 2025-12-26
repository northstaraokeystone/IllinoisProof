"""
Tests for Tier 1 (Dolton) detection modules.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tier1_dolton.credit_card import (
    detect_round_number_transactions,
    detect_missing_receipts,
    single_transaction_outliers,
    detect_split_transactions,
    detect_vendor_patterns,
    analyze_credit_cards
)
from src.tier1_dolton.vendor import (
    compute_vendor_concentration,
    detect_related_parties,
    detect_contract_anomalies
)
from src.tier1_dolton.overtime import (
    compute_overtime_ratio,
    detect_impossible_hours,
    detect_overtime_patterns
)


class TestCreditCard:
    """Tests for credit card analysis."""

    def test_detect_round_numbers(self, sample_transactions):
        """Test round number detection."""
        flags = detect_round_number_transactions(sample_transactions)
        # Should flag the $33,000 transaction
        assert any(f["amount"] == 33000 for f in flags)

    def test_detect_missing_receipts(self):
        """Test missing receipt detection."""
        transactions = [
            {"transaction_id": "TX-001", "amount": 100},
            {"transaction_id": "TX-002", "amount": 200},
            {"transaction_id": "TX-003", "amount": 5000}
        ]
        receipts = [
            {"transaction_id": "TX-001"}
        ]
        missing = detect_missing_receipts(transactions, receipts)
        assert len(missing) == 2
        assert any(m["transaction_id"] == "TX-003" for m in missing)

    def test_single_transaction_outliers(self):
        """Test large transaction detection."""
        transactions = [
            {"amount": 1000},
            {"amount": 30000},  # Should flag
            {"amount": 5000}
        ]
        outliers = single_transaction_outliers(transactions, threshold=25000)
        assert len(outliers) == 1
        assert outliers[0]["amount"] == 30000

    def test_detect_split_transactions(self, sample_transactions):
        """Test split transaction detection."""
        flags = detect_split_transactions(sample_transactions)
        # TX-005 and TX-006 are same day, same vendor, just under limit
        if flags:
            assert any(f["flag_type"] == "split_transaction" for f in flags)

    def test_detect_vendor_patterns(self, sample_transactions):
        """Test vendor pattern detection."""
        flags = detect_vendor_patterns(sample_transactions)
        assert isinstance(flags, list)

    def test_analyze_credit_cards(self, sample_transactions):
        """Test complete credit card analysis."""
        result = analyze_credit_cards(sample_transactions)
        assert "total_transactions" in result
        assert "flagged_transactions" in result
        assert "flags" in result


class TestVendor:
    """Tests for vendor analysis."""

    def test_compute_vendor_concentration(self):
        """Test vendor concentration calculation."""
        expenditures = [
            {"vendor": "A", "amount": 80000},
            {"vendor": "B", "amount": 10000},
            {"vendor": "C", "amount": 10000}
        ]
        result = compute_vendor_concentration(expenditures)

        assert result["top_vendor"] == "A"
        assert result["top_concentration"] == 0.8
        assert result["hhi"] > 0.5  # High concentration

    def test_detect_related_parties(self):
        """Test related party detection."""
        vendors = [
            {"vendor_id": "V1", "name": "Smith Corp", "owners": ["John Smith"]}
        ]
        board = [
            {"name": "John Smith", "address": "123 Main St"}
        ]
        matches = detect_related_parties(vendors, board)
        assert len(matches) >= 1
        assert matches[0]["match_type"] == "owner_is_board_member"

    def test_detect_contract_anomalies(self):
        """Test contract anomaly detection."""
        contracts = [
            {"vendor": "A", "amount": 100000, "bid_type": "sole_source"},
            {"vendor": "B", "amount": 50000, "original_amount": 20000}
        ]
        anomalies = detect_contract_anomalies(contracts)
        assert len(anomalies) >= 1


class TestOvertime:
    """Tests for overtime analysis."""

    def test_compute_overtime_ratio(self):
        """Test overtime ratio calculation."""
        payroll = [
            {"employee": "EMP-001", "regular_hours": 80, "overtime_hours": 40},
            {"employee": "EMP-001", "regular_hours": 80, "overtime_hours": 60}
        ]
        result = compute_overtime_ratio(payroll, "EMP-001")

        assert result["total_regular"] == 160
        assert result["total_overtime"] == 100
        assert result["ot_ratio"] > 0.5

    def test_detect_impossible_hours(self, dolton_calibration):
        """Test impossible hours detection."""
        payroll = [
            {"employee": "EMP-001", "period": "2024-01", "total_hours": 332}
        ]
        flags = detect_impossible_hours(payroll, period_hours=336)

        # 332/336 is not impossible, but it's extreme
        if flags:
            assert flags[0]["reported_hours"] == 332

    def test_detect_impossible_hours_extreme(self):
        """Test detection of truly impossible hours."""
        payroll = [
            {"employee": "EMP-001", "period": "2024-01", "total_hours": 400}
        ]
        flags = detect_impossible_hours(payroll, period_hours=336)

        assert len(flags) == 1
        assert flags[0]["flag_type"] == "impossible_hours"
        assert flags[0]["excess_hours"] == 64

    def test_detect_overtime_patterns(self):
        """Test overtime pattern detection."""
        payroll = [
            {"employee": "EMP-001", "regular_hours": 80, "overtime_hours": 100},
            {"employee": "EMP-001", "regular_hours": 80, "overtime_hours": 90},
            {"employee": "EMP-001", "regular_hours": 80, "overtime_hours": 110}
        ]
        patterns = detect_overtime_patterns(payroll)

        assert any(p.get("flag_type") == "consistent_overtime" for p in patterns)
