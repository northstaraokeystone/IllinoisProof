#!/bin/bash
# gate_t24h.sh - T+24h MVP GATE
# RUN THIS OR KILL PROJECT

set -e

echo "=== IllinoisProof T+24h Gate Check ==="

# First run T+2h gate
./gate_t2h.sh || { echo "FAIL: T+2h gate failed"; exit 1; }

echo ""
echo "=== T+24h Additional Checks ==="

# Check tests exist and pass
python -m pytest tests/ -q || { echo "FAIL: tests failed"; exit 1; }
echo "PASS: tests pass"

# Check emit_receipt in src files
grep -rq "emit_receipt" src/*.py || { echo "FAIL: no emit_receipt in src"; exit 1; }
echo "PASS: emit_receipt used in src"

# Check assertions in tests
grep -rq "assert" tests/*.py || { echo "FAIL: no assertions in tests"; exit 1; }
echo "PASS: assertions in tests"

# Check detection modules exist
[ -f src/detect/benford.py ] || { echo "FAIL: no benford.py"; exit 1; }
[ -f src/detect/entropy.py ] || { echo "FAIL: no entropy.py"; exit 1; }
echo "PASS: detection modules exist"

# Run 10-cycle smoke test
python -c "from src.sim import run_simulation, SimConfig; r = run_simulation(SimConfig(n_cycles=10)); assert len(r.violations) == 0; print('PASS: 10-cycle smoke test')" || { echo "FAIL: smoke test"; exit 1; }

echo ""
echo "=== PASS: T+24h gate ==="
echo "Proceed to T+48h hardening"
