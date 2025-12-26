"""
Pytest configuration and fixtures for IllinoisProof tests.
"""

import pytest
import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


@pytest.fixture
def sample_transactions():
    """Sample transactions for testing."""
    return [
        {"id": "TX-001", "amount": 1234.56, "vendor": "Vendor-A", "date": "2024-01-15"},
        {"id": "TX-002", "amount": 5678.90, "vendor": "Vendor-B", "date": "2024-01-16"},
        {"id": "TX-003", "amount": 2345.67, "vendor": "Vendor-A", "date": "2024-01-17"},
        {"id": "TX-004", "amount": 33000.00, "vendor": "Vendor-C", "date": "2024-01-18"},
        {"id": "TX-005", "amount": 9500.00, "vendor": "Vendor-D", "date": "2024-01-19"},
        {"id": "TX-006", "amount": 9500.00, "vendor": "Vendor-D", "date": "2024-01-19"},
    ]


@pytest.fixture
def dolton_calibration():
    """Dolton calibration data from known case."""
    return {
        "credit_card_missing_receipts": 779000,
        "amazon_single_purchase": 33027,
        "oakk_contracts": 200000,
        "overtime_332_hours": True,
        "deficit": 3650000,
        "expected_flags": ["credit_card", "vendor_concentration", "overtime"]
    }


@pytest.fixture
def ides_calibration():
    """IDES calibration data from Auditor General."""
    return {
        "total_overpayments": 5240000000,
        "recovered": 511700000,
        "non_recoverable": 2800000000,
        "deceased_payments": 6000000,
        "incarcerated_payments": 40500000,
        "crossmatch_gap_start": "2020-03-01",
        "crossmatch_gap_end": "2021-09-30"
    }


@pytest.fixture
def madigan_calibration():
    """Madigan calibration data from trial exhibits."""
    return {
        "dpa_fine": 200000000,
        "nowork_contracts_total": 1300000,
        "committee_cash": 6100000,
        "sb1652_bribery": True,
        "known_nowork_recipients": ["olivo", "nice", "acevedo"]
    }


@pytest.fixture
def sample_claims():
    """Sample UI claims for IDES testing."""
    return [
        {"ssn": "123-45-6789", "claim_date": "2020-05-15", "amount": 5000},
        {"ssn": "234-56-7890", "claim_date": "2020-06-20", "amount": 4500},
        {"ssn": "345-67-8901", "claim_date": "2020-07-10", "amount": 6000},
    ]


@pytest.fixture
def sample_contributions():
    """Sample campaign contributions for Madigan testing."""
    return [
        {"contributor": "ComEd-Exec-1", "recipient": "Madigan-PAC", "amount": 50000, "date": "2011-01-15"},
        {"contributor": "ComEd-Exec-2", "recipient": "Madigan-PAC", "amount": 25000, "date": "2011-02-20"},
        {"contributor": "Exelon-Corp", "recipient": "Madigan-PAC", "amount": 100000, "date": "2011-03-10"},
    ]


@pytest.fixture
def sample_votes():
    """Sample legislative votes for correlation testing."""
    return [
        {"legislator": "Madigan-PAC", "bill_number": "SB1652", "vote": "yea", "date": "2011-10-15"},
        {"legislator": "Other-Rep", "bill_number": "SB1652", "vote": "yea", "date": "2011-10-15"},
    ]
