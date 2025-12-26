"""
Tests for detection modules.
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.detect.benford import (
    benford_expected, extract_first_digit, extract_second_digit,
    compute_observed_frequencies, chi_squared_test, analyze_benford,
    detect_round_numbers
)
from src.detect.entropy import (
    entropy_baseline, compute_z_score, entropy_anomaly_check,
    analyze_entropy, shannon_entropy
)
from src.detect.cascade import (
    cross_tier_cascade, CascadePattern
)
from src.detect.network import (
    Graph, Node, Edge, build_contribution_graph,
    compute_network_entropy, detect_hub_nodes
)


class TestBenford:
    """Tests for Benford's Law analysis."""

    def test_benford_expected_first_digit(self):
        """Test expected first digit frequencies."""
        expected = benford_expected(1)
        assert len(expected) == 9  # Digits 1-9
        assert expected[1] > expected[9]  # 1 more common than 9
        assert abs(sum(expected.values()) - 1.0) < 0.01  # Sum to ~1

    def test_benford_expected_second_digit(self):
        """Test expected second digit frequencies."""
        expected = benford_expected(2)
        assert len(expected) == 10  # Digits 0-9

    def test_extract_first_digit(self):
        """Test first digit extraction."""
        values = [123.45, 5678, 0.0042, 987654]
        digits = extract_first_digit(values)
        assert digits == [1, 5, 4, 9]

    def test_extract_first_digit_handles_zero(self):
        """Test that zero values are skipped."""
        values = [0, 100, 0, 200]
        digits = extract_first_digit(values)
        assert digits == [1, 2]

    def test_extract_second_digit(self):
        """Test second digit extraction."""
        values = [123, 456, 789]
        digits = extract_second_digit(values)
        assert digits == [2, 5, 8]

    def test_chi_squared_test(self):
        """Test chi-squared calculation."""
        # Benford-compliant observed
        expected = benford_expected(1)
        result = chi_squared_test(expected, expected, 1000)
        assert result["chi_squared"] < 1  # Should be very low
        assert result["pass_fail"] == "pass"

    def test_analyze_benford(self):
        """Test complete Benford analysis."""
        # Generate Benford-compliant values
        values = []
        for d in range(1, 10):
            count = int(1000 * benford_expected(1)[d])
            values.extend([d * 100 + i for i in range(count)])

        result = analyze_benford(values, "test")
        assert "chi_squared" in result
        assert "p_value" in result

    def test_detect_round_numbers(self):
        """Test round number detection."""
        values = [1234, 10000, 5678, 25000, 33000]
        flags = detect_round_numbers(values)
        assert len(flags) >= 2  # Should catch 10K, 25K, 33K


class TestEntropy:
    """Tests for entropy-based detection."""

    def test_entropy_baseline(self):
        """Test baseline retrieval."""
        baseline = entropy_baseline("municipality", "fiscal_year")
        assert "mean" in baseline
        assert "std" in baseline
        assert baseline["std"] > 0

    def test_compute_z_score(self):
        """Test z-score calculation."""
        baseline = {"mean": 0.5, "std": 0.1, "sample_size": 100}

        z = compute_z_score(0.5, baseline)
        assert z == 0

        z = compute_z_score(0.6, baseline)
        assert z == pytest.approx(1.0)

        z = compute_z_score(0.7, baseline)
        assert z == pytest.approx(2.0)

    def test_entropy_anomaly_check(self):
        """Test anomaly detection."""
        baseline = {"mean": 0.5, "std": 0.1, "sample_size": 100}

        # Normal case
        result = entropy_anomaly_check(0.55, baseline)
        assert not result["is_anomaly"]

        # Anomaly case
        result = entropy_anomaly_check(0.75, baseline)
        assert result["is_anomaly"]

    def test_shannon_entropy(self):
        """Test Shannon entropy calculation."""
        # All same bytes = 0 entropy
        data = b"\x00" * 100
        entropy = shannon_entropy(data)
        assert entropy == 0

        # Uniform distribution = max entropy
        data = bytes(range(256))
        entropy = shannon_entropy(data)
        assert entropy > 7  # Close to 8 bits

    def test_analyze_entropy(self):
        """Test complete entropy analysis."""
        data = b"some test data for entropy analysis"
        result = analyze_entropy(data, "test", "municipality")
        assert "compression_ratio" in result
        assert "z_score" in result
        assert "is_anomaly" in result


class TestCascade:
    """Tests for cascade detection."""

    def test_cross_tier_cascade_empty(self):
        """Test cascade with empty inputs."""
        result = cross_tier_cascade([], [], [])
        assert isinstance(result, list)

    def test_cascade_pattern_dataclass(self):
        """Test CascadePattern creation."""
        pattern = CascadePattern(
            pattern_id="TEST-001",
            tiers=["tier1", "tier3"],
            findings=[],
            confidence=0.75
        )
        assert pattern.pattern_id == "TEST-001"
        assert pattern.confidence == 0.75


class TestNetwork:
    """Tests for network analysis."""

    def test_graph_operations(self):
        """Test basic graph operations."""
        graph = Graph()

        node1 = Node(id="A", node_type="contributor")
        node2 = Node(id="B", node_type="pac")
        graph.add_node(node1)
        graph.add_node(node2)

        edge = Edge(source="A", target="B", weight=1000, edge_type="contribution")
        graph.add_edge(edge)

        assert len(graph.nodes) == 2
        assert len(graph.edges) == 1
        assert len(graph.get_outgoing("A")) == 1
        assert len(graph.get_incoming("B")) == 1

    def test_build_contribution_graph(self):
        """Test graph building from contributions."""
        contributions = [
            {"contributor": "A", "recipient": "B", "amount": 1000},
            {"contributor": "A", "recipient": "C", "amount": 2000},
            {"contributor": "B", "recipient": "C", "amount": 500}
        ]
        graph = build_contribution_graph(contributions)

        assert len(graph.nodes) == 3
        assert len(graph.edges) == 3

    def test_compute_network_entropy(self):
        """Test network entropy calculation."""
        contributions = [
            {"contributor": "A", "recipient": "B", "amount": 1000},
            {"contributor": "C", "recipient": "B", "amount": 1000}
        ]
        graph = build_contribution_graph(contributions)
        entropy = compute_network_entropy(graph)

        assert entropy >= 0

    def test_detect_hub_nodes(self, sample_contributions):
        """Test hub detection."""
        graph = build_contribution_graph(sample_contributions)
        hubs = detect_hub_nodes(graph, threshold=0.1)

        assert isinstance(hubs, list)
