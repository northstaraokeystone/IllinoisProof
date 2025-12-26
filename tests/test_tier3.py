"""
Tests for Tier 3 (Madigan) detection modules.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.tier3_madigan.pac_network import (
    build_pac_network,
    compute_pac_entropy,
    detect_pac_clusters,
    trace_comed_flow,
    KNOWN_ENTITIES
)
from src.tier3_madigan.legislation import (
    correlation_contribution_vote,
    detect_vote_buying,
    analyze_veto_override,
    KNOWN_LEGISLATION
)
from src.tier3_madigan.nowork import (
    detect_nowork_contracts,
    compensation_anomaly,
    detect_connected_recipients,
    KNOWN_NOWORK
)


class TestPACNetwork:
    """Tests for PAC network analysis."""

    def test_known_entities(self):
        """Test known entities are defined."""
        assert "pacs" in KNOWN_ENTITIES
        assert "friends_of_madigan" in KNOWN_ENTITIES["pacs"]
        assert KNOWN_ENTITIES["pacs"]["friends_of_madigan"]["cash_on_hand"] == 6_100_000

    def test_build_pac_network(self, sample_contributions):
        """Test PAC network construction."""
        graph = build_pac_network(sample_contributions)
        assert len(graph.nodes) > 0
        assert len(graph.edges) > 0

    def test_compute_pac_entropy(self, sample_contributions):
        """Test PAC entropy calculation."""
        result = compute_pac_entropy(sample_contributions)

        assert "entropy" in result
        assert "classification" in result
        assert "severity" in result
        assert result["entropy"] >= 0

    def test_detect_pac_clusters(self, sample_contributions):
        """Test PAC cluster detection."""
        clusters = detect_pac_clusters(sample_contributions)
        assert isinstance(clusters, list)

    def test_trace_comed_flow(self, sample_contributions):
        """Test ComEd flow tracing."""
        flows = trace_comed_flow(sample_contributions)
        assert isinstance(flows, list)


class TestLegislation:
    """Tests for legislation correlation analysis."""

    def test_known_legislation(self):
        """Test known legislation is defined."""
        assert "SB1652" in KNOWN_LEGISLATION
        assert KNOWN_LEGISLATION["SB1652"]["proven_bribery"] is True

    def test_correlation_contribution_vote(self, sample_contributions, sample_votes):
        """Test contribution-vote correlation."""
        result = correlation_contribution_vote(sample_contributions, sample_votes)

        assert "total_correlations" in result
        assert "unique_pairs" in result
        assert "correlations" in result

    def test_detect_vote_buying(self, sample_contributions, sample_votes):
        """Test vote buying pattern detection."""
        bills = [
            {"bill_number": "SB1652", "beneficiary": "ComEd"}
        ]
        patterns = detect_vote_buying(sample_contributions, sample_votes, bills)
        assert isinstance(patterns, list)

    def test_analyze_veto_override(self, sample_votes):
        """Test veto override analysis."""
        votes = [
            {"bill_number": "SB1652", "vote": "yea", "vote_type": "veto_override"}
        ]
        bills = [
            {"bill_number": "SB1652", "beneficiary": "ComEd"}
        ]
        patterns = analyze_veto_override(votes, bills)

        # Should find known bribery override
        assert any(p.get("pattern_type") == "known_bribery_override" for p in patterns)


class TestNoWork:
    """Tests for no-work contract detection."""

    def test_known_nowork(self):
        """Test known no-work patterns are defined."""
        assert "olivo" in KNOWN_NOWORK
        assert "nice" in KNOWN_NOWORK
        assert "acevedo" in KNOWN_NOWORK
        assert KNOWN_NOWORK["olivo"]["monthly"] == 4000

    def test_detect_nowork_contracts(self):
        """Test no-work contract detection."""
        contracts = [
            {
                "contract_id": "C-001",
                "contractor": "Olivo Consulting",
                "amount": 48000,  # 12 months at $4K
                "duration_months": 12
            }
        ]
        deliverables = []  # No deliverables

        flags = detect_nowork_contracts(contracts, deliverables)

        assert len(flags) >= 1
        assert flags[0]["confidence"] > 0.8  # Should match known pattern

    def test_detect_nowork_with_deliverables(self):
        """Test that contracts with good deliverables have lower confidence."""
        contracts = [
            {"contract_id": "C-002", "contractor": "Real Work LLC", "amount": 50000, "duration_months": 12}
        ]
        deliverables = [
            {"contract_id": "C-002", "description": "Monthly reports", "value": 45000}
        ]
        flags = detect_nowork_contracts(contracts, deliverables)

        # Contract with 90% deliverable ratio should not be flagged as suspicious
        c002_flags = [f for f in flags if f.get("contract_id") == "C-002"]
        # If flagged at all, confidence should be very low
        for f in c002_flags:
            assert f.get("confidence", 0) < 0.75

    def test_compensation_anomaly(self):
        """Test compensation anomaly detection."""
        payments = [
            {"recipient": "Consultant A", "amount": 15000, "role": "consultant"},
            {"recipient": "Consultant A", "amount": 15000, "role": "consultant"}
        ]
        flags = compensation_anomaly(payments)

        # $30K over 2 months = $15K/month, way above $5K baseline
        assert any(f["finding_type"] == "above_market_compensation" for f in flags)

    def test_detect_connected_recipients(self, madigan_calibration):
        """Test politically connected recipient detection."""
        contracts = [
            {"contractor": "Olivo LLC", "contract_id": "C-001", "amount": 50000}
        ]
        connections = [
            {"entity": "Olivo", "connected_to": "Madigan"}
        ]
        flags = detect_connected_recipients(contracts, connections)

        assert len(flags) >= 1
