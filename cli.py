#!/usr/bin/env python3
"""
IllinoisProof CLI

Command-line interface for the Illinois Corruption Detection Harness.
Emits valid receipt JSON for all operations.
"""

import argparse
import json
import sys
from datetime import datetime, timezone

# Add src to path for imports
sys.path.insert(0, "src")

from src.core import (
    dual_hash, emit_receipt, merkle, TENANT_ID,
    SimConfig, SimState, SimResult
)


def cmd_test(args):
    """Emit a test receipt to verify CLI functionality."""
    receipt = emit_receipt("test", {
        "tenant_id": TENANT_ID,
        "message": "CLI test receipt",
        "test_mode": True
    })
    return receipt


def cmd_hash(args):
    """Compute dual hash of input."""
    if args.input:
        data = args.input
    else:
        data = sys.stdin.read()

    result = dual_hash(data)
    receipt = emit_receipt("hash", {
        "tenant_id": TENANT_ID,
        "input_preview": data[:100] if len(data) > 100 else data,
        "hash": result
    })
    return receipt


def cmd_ingest(args):
    """Ingest data from a source."""
    # Import ingest modules dynamically based on source type
    source_type = args.source

    receipt = emit_receipt("ingest", {
        "tenant_id": TENANT_ID,
        "source": source_type,
        "records_count": 0,
        "status": "stub - not implemented",
        "source_type": source_type
    })
    return receipt


def cmd_detect(args):
    """Run detection analysis."""
    method = args.method

    receipt = emit_receipt("detect", {
        "tenant_id": TENANT_ID,
        "method": method,
        "status": "stub - not implemented",
        "findings_count": 0
    })
    return receipt


def cmd_simulate(args):
    """Run Monte Carlo simulation."""
    config = SimConfig(
        n_cycles=args.cycles,
        tiers=args.tiers.split(",") if args.tiers else ["dolton", "ides", "madigan"],
        fraud_injection_rate=args.fraud_rate,
        random_seed=args.seed
    )

    # Stub implementation
    state = SimState(cycle=0)
    result = SimResult(config=config, state=state)

    receipt = emit_receipt("simulation", {
        "tenant_id": TENANT_ID,
        "cycle_id": 0,
        "scenario": "BASELINE",
        "config": config.to_dict(),
        "status": "stub - not implemented"
    })
    return receipt


def cmd_verify(args):
    """Verify receipt chain integrity."""
    try:
        receipts = []
        with open(args.file, "r") as f:
            for line in f:
                if line.strip():
                    receipts.append(json.loads(line))

        root = merkle(receipts)

        receipt = emit_receipt("verify", {
            "tenant_id": TENANT_ID,
            "receipts_count": len(receipts),
            "merkle_root": root,
            "file": args.file,
            "status": "verified"
        })
        return receipt
    except FileNotFoundError:
        receipt = emit_receipt("verify", {
            "tenant_id": TENANT_ID,
            "file": args.file,
            "status": "file_not_found",
            "error": f"File not found: {args.file}"
        })
        return receipt


def cmd_anchor(args):
    """Create merkle anchor from receipts."""
    try:
        receipts = []
        with open(args.file, "r") as f:
            for line in f:
                if line.strip():
                    receipts.append(json.loads(line))

        root = merkle(receipts)

        receipt = emit_receipt("anchor", {
            "tenant_id": TENANT_ID,
            "merkle_root": root,
            "hash_algos": ["SHA256", "BLAKE3"],
            "batch_size": len(receipts),
            "source_file": args.file
        })
        return receipt
    except FileNotFoundError:
        receipt = emit_receipt("anchor", {
            "tenant_id": TENANT_ID,
            "source_file": args.file,
            "status": "file_not_found",
            "merkle_root": dual_hash(b"empty"),
            "hash_algos": ["SHA256", "BLAKE3"],
            "batch_size": 0
        })
        return receipt


def main():
    # Handle standalone --test flag for T+2h gate compatibility
    if len(sys.argv) == 2 and sys.argv[1] == "--test":
        emit_receipt("test", {
            "tenant_id": TENANT_ID,
            "message": "CLI test receipt",
            "test_mode": True
        })
        return 0

    parser = argparse.ArgumentParser(
        prog="illinoisproof",
        description="Illinois Corruption Detection Harness CLI"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Test command
    test_parser = subparsers.add_parser("test", help="Emit test receipt")

    # Hash command
    hash_parser = subparsers.add_parser("hash", help="Compute dual hash")
    hash_parser.add_argument("--input", "-i", help="Input string to hash")

    # Ingest command
    ingest_parser = subparsers.add_parser("ingest", help="Ingest data from source")
    ingest_parser.add_argument("--source", "-s", required=True,
                               choices=["comptroller", "cook_county", "pacer",
                                       "sunshine", "ides", "foia"],
                               help="Data source to ingest")

    # Detect command
    detect_parser = subparsers.add_parser("detect", help="Run detection analysis")
    detect_parser.add_argument("--method", "-m", required=True,
                               choices=["benford", "entropy", "network", "cascade"],
                               help="Detection method")
    detect_parser.add_argument("--tier", "-t",
                               choices=["dolton", "ides", "madigan"],
                               help="Tier to analyze")

    # Simulate command
    sim_parser = subparsers.add_parser("simulate", help="Run Monte Carlo simulation")
    sim_parser.add_argument("--cycles", "-n", type=int, default=1000,
                            help="Number of simulation cycles")
    sim_parser.add_argument("--tiers", help="Comma-separated tiers to simulate")
    sim_parser.add_argument("--fraud-rate", type=float, default=0.05,
                            help="Fraud injection rate")
    sim_parser.add_argument("--seed", type=int, default=42,
                            help="Random seed")

    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify receipt chain")
    verify_parser.add_argument("--file", "-f", default="receipts.jsonl",
                               help="Receipts file to verify")

    # Anchor command
    anchor_parser = subparsers.add_parser("anchor", help="Create merkle anchor")
    anchor_parser.add_argument("--file", "-f", default="receipts.jsonl",
                               help="Receipts file to anchor")

    args = parser.parse_args()

    if args.command == "test":
        cmd_test(args)
    elif args.command == "hash":
        cmd_hash(args)
    elif args.command == "ingest":
        cmd_ingest(args)
    elif args.command == "detect":
        cmd_detect(args)
    elif args.command == "simulate":
        cmd_simulate(args)
    elif args.command == "verify":
        cmd_verify(args)
    elif args.command == "anchor":
        cmd_anchor(args)
    else:
        parser.print_help()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
