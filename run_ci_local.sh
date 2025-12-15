#!/bin/bash
# Local CI validation script - run before pushing to verify everything works

set -e

echo "=== AniFlow CI Validation ==="
echo ""

echo "[1/5] Setting test environment..."
export FLASK_ENV=test
export TESTING=true
export KAFKA_ENABLED=false
echo "✓ Environment set"
echo ""

echo "[2/5] Installing dependencies..."
pip install -q -r requirements.txt
echo "✓ Dependencies installed"
echo ""

echo "[3/5] Running syntax check..."
python -m compileall . > /dev/null 2>&1
echo "✓ Syntax check passed"
echo ""

echo "[4/5] Running health check..."
python ci_healthcheck.py
echo ""

echo "[5/5] Running tests..."
pytest -v --disable-warnings --tb=short
echo ""

echo "=== All CI checks passed! ==="
