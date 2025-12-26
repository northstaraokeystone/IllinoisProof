"""
Tests for core module functions.
"""

import pytest
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.core import (
    dual_hash, emit_receipt, merkle, verify_merkle_proof,
    StopRule, SimConfig, SimState, SimResult,
    compute_compression_ratio, compute_ncd,
    TENANT_ID
)


class TestDualHash:
    """Tests for dual_hash function."""

    def test_dual_hash_string(self):
        """Test hashing a string."""
        result = dual_hash("test")
        assert ":" in result
        parts = result.split(":")
        assert len(parts) == 2
        assert len(parts[0]) == 64  # SHA256 hex

    def test_dual_hash_bytes(self):
        """Test hashing bytes."""
        result = dual_hash(b"test bytes")
        assert ":" in result

    def test_dual_hash_deterministic(self):
        """Test that same input gives same output."""
        result1 = dual_hash("same input")
        result2 = dual_hash("same input")
        assert result1 == result2

    def test_dual_hash_different_inputs(self):
        """Test that different inputs give different outputs."""
        result1 = dual_hash("input one")
        result2 = dual_hash("input two")
        assert result1 != result2


class TestEmitReceipt:
    """Tests for emit_receipt function."""

    def test_emit_receipt_basic(self, capsys):
        """Test basic receipt emission."""
        receipt = emit_receipt("test", {"message": "hello"})

        assert receipt["receipt_type"] == "test"
        assert receipt["tenant_id"] == TENANT_ID
        assert "ts" in receipt
        assert "payload_hash" in receipt

        # Check stdout
        captured = capsys.readouterr()
        assert "receipt_type" in captured.out

    def test_emit_receipt_with_tenant(self, capsys):
        """Test receipt with custom tenant."""
        receipt = emit_receipt("test", {"tenant_id": "custom", "data": 123})
        assert receipt["tenant_id"] == "custom"

    def test_emit_receipt_payload_hash(self, capsys):
        """Test that payload hash is computed correctly."""
        receipt = emit_receipt("test", {"key": "value"})
        assert ":" in receipt["payload_hash"]


class TestMerkle:
    """Tests for merkle tree functions."""

    def test_merkle_empty(self):
        """Test merkle of empty list."""
        result = merkle([])
        assert ":" in result

    def test_merkle_single(self):
        """Test merkle of single item."""
        result = merkle([{"a": 1}])
        assert ":" in result

    def test_merkle_multiple(self):
        """Test merkle of multiple items."""
        items = [{"a": 1}, {"b": 2}, {"c": 3}]
        result = merkle(items)
        assert ":" in result

    def test_merkle_deterministic(self):
        """Test merkle is deterministic."""
        items = [{"x": 1}, {"y": 2}]
        result1 = merkle(items)
        result2 = merkle(items)
        assert result1 == result2

    def test_merkle_order_matters(self):
        """Test that item order affects result."""
        items1 = [{"a": 1}, {"b": 2}]
        items2 = [{"b": 2}, {"a": 1}]
        result1 = merkle(items1)
        result2 = merkle(items2)
        assert result1 != result2


class TestStopRule:
    """Tests for StopRule exception."""

    def test_stoprule_raise(self):
        """Test StopRule can be raised."""
        with pytest.raises(StopRule) as exc_info:
            raise StopRule("test error", metric="test", action="halt")

        assert "test error" in str(exc_info.value)
        assert exc_info.value.metric == "test"
        assert exc_info.value.action == "halt"


class TestSimConfig:
    """Tests for SimConfig dataclass."""

    def test_simconfig_defaults(self):
        """Test default values."""
        config = SimConfig()
        assert config.n_cycles == 1000
        assert config.fraud_injection_rate == 0.05
        assert "dolton" in config.tiers

    def test_simconfig_custom(self):
        """Test custom values."""
        config = SimConfig(n_cycles=100, fraud_injection_rate=0.1)
        assert config.n_cycles == 100
        assert config.fraud_injection_rate == 0.1

    def test_simconfig_to_dict(self):
        """Test conversion to dict."""
        config = SimConfig(n_cycles=50)
        d = config.to_dict()
        assert d["n_cycles"] == 50


class TestCompressionRatio:
    """Tests for compression-based functions."""

    def test_compression_ratio_basic(self):
        """Test compression ratio calculation."""
        # Need enough data for gzip overhead to be worth it
        data = b"a" * 1000  # Highly compressible
        ratio = compute_compression_ratio(data)
        assert 0 < ratio < 0.5  # Should compress very well with enough data

    def test_compression_ratio_random(self):
        """Test compression of random data."""
        import random
        random.seed(42)
        data = bytes([random.randint(0, 255) for _ in range(1000)])
        ratio = compute_compression_ratio(data)
        assert ratio > 0

    def test_ncd_similar(self):
        """Test NCD of similar data."""
        data1 = b"hello world hello world"
        data2 = b"hello world hello world hello"
        ncd = compute_ncd(data1, data2)
        assert 0 <= ncd <= 1
        assert ncd < 0.5  # Should be similar

    def test_ncd_different(self):
        """Test NCD of different data."""
        data1 = b"aaaaaaaaaaaaa"
        data2 = b"zzzzzzzzzzzzz"
        ncd = compute_ncd(data1, data2)
        assert 0 <= ncd <= 1
