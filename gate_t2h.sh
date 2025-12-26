#!/bin/bash
# gate_t2h.sh - T+2h SKELETON GATE
# RUN THIS OR KILL PROJECT

set -e

echo "=== IllinoisProof T+2h Gate Check ==="

# Check spec.md exists
[ -f spec.md ] || { echo "FAIL: no spec.md"; exit 1; }
echo "PASS: spec.md exists"

# Check ledger_schema.json exists
[ -f ledger_schema.json ] || { echo "FAIL: no ledger_schema.json"; exit 1; }
echo "PASS: ledger_schema.json exists"

# Check cli.py exists
[ -f cli.py ] || { echo "FAIL: no cli.py"; exit 1; }
echo "PASS: cli.py exists"

# Check cli.py emits valid receipt JSON
python cli.py --test 2>&1 | grep -q '"receipt_type"' || { echo "FAIL: cli.py doesn't emit receipt"; exit 1; }
echo "PASS: cli.py emits valid receipt"

# Check core.py exists with required functions
[ -f src/core.py ] || { echo "FAIL: no src/core.py"; exit 1; }
grep -q "def dual_hash" src/core.py || { echo "FAIL: no dual_hash in core.py"; exit 1; }
grep -q "def emit_receipt" src/core.py || { echo "FAIL: no emit_receipt in core.py"; exit 1; }
grep -q "def merkle" src/core.py || { echo "FAIL: no merkle in core.py"; exit 1; }
grep -q "class StopRule" src/core.py || { echo "FAIL: no StopRule in core.py"; exit 1; }
echo "PASS: core.py has required functions"

# Check directory structure
[ -d src/ingest ] || { echo "FAIL: no src/ingest directory"; exit 1; }
[ -d src/detect ] || { echo "FAIL: no src/detect directory"; exit 1; }
[ -d src/tier1_dolton ] || { echo "FAIL: no src/tier1_dolton directory"; exit 1; }
[ -d src/tier2_ides ] || { echo "FAIL: no src/tier2_ides directory"; exit 1; }
[ -d src/tier3_madigan ] || { echo "FAIL: no src/tier3_madigan directory"; exit 1; }
[ -d src/output ] || { echo "FAIL: no src/output directory"; exit 1; }
echo "PASS: directory structure correct"

echo ""
echo "=== PASS: T+2h gate ==="
echo "Proceed to T+24h implementation"
