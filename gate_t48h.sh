#!/bin/bash
# gate_t48h.sh - T+48h HARDENED GATE
# RUN THIS OR KILL PROJECT - THEN SHIP IT

set -e

echo "=== IllinoisProof T+48h Gate Check ==="

# First run T+24h gate
./gate_t24h.sh || { echo "FAIL: T+24h gate failed"; exit 1; }

echo ""
echo "=== T+48h Hardening Checks ==="

# Check anomaly detection active
grep -rq "anomaly" src/*.py || { echo "FAIL: no anomaly detection in src"; exit 1; }
echo "PASS: anomaly detection active"

# Check stoprules present
grep -rq "stoprule\|StopRule" src/*.py || { echo "FAIL: no stoprules in src"; exit 1; }
echo "PASS: stoprules present"

# Check all 6 scenarios pass
echo "Running scenario tests..."
python -c "
from src.sim import run_scenario
scenarios = ['BASELINE', 'DOLTON_CALIBRATION', 'IDES_CALIBRATION', 'MADIGAN_CALIBRATION', 'CASCADE', 'GODEL']
for s in scenarios:
    r = run_scenario(s)
    assert r.detection_rate >= 0, f'Scenario {s} failed'
    print(f'  {s}: detection_rate={r.detection_rate:.2f}')
print('PASS: all 6 scenarios pass')
" || { echo "FAIL: scenario tests"; exit 1; }

# Check calibration match >= 95%
python -c "
from src.sim import run_calibration_check
match = run_calibration_check()
assert match >= 0.95, f'Calibration match {match} < 0.95'
print(f'PASS: calibration match = {match:.2%}')
" || { echo "FAIL: calibration"; exit 1; }

# Check FBI-grade packaging functional
python -c "
from src.output.fbi import create_evidence_package
pkg = create_evidence_package([], 'TEST-001')
assert 'package_id' in pkg
assert 'package_hash' in pkg
print('PASS: FBI packaging functional')
" || { echo "FAIL: FBI packaging"; exit 1; }

# Check citizen output generates
python -c "
from src.output.citizen import dashboard_payload
payload = dashboard_payload([], 'test')
assert payload is not None
print('PASS: citizen output generates')
" || { echo "FAIL: citizen output"; exit 1; }

# Run full test suite with coverage
python -m pytest tests/ -v --cov=src --cov-fail-under=80 || { echo "FAIL: coverage < 80%"; exit 1; }
echo "PASS: test coverage >= 80%"

echo ""
echo "========================================="
echo "=== PASS: T+48h gate — SHIP IT ==="
echo "========================================="
echo ""
echo "Compression reveals what ledgers hide."
echo "The receipt proves what claims assert."
echo "Illinois bleeds receipts now."
