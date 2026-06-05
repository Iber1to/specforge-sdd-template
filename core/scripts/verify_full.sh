#!/usr/bin/env bash
# Verificación completa Linux previa a revisión o finalización.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "── Lockfile ───────────────────────────────────────────"
uv sync --locked

echo
echo "── Política de agentes ─────────────────────────────────"
uv run python scripts/validate_agent_budgets.py
echo
echo "── Compilación Python ─────────────────────────────────"
uv run python -m compileall -q scripts src tests

echo
echo "── Ruff lint ──────────────────────────────────────────"
uv run ruff check .

echo
echo "── Ruff format ────────────────────────────────────────"
uv run ruff format --check .

echo
echo "── Suite completa de tests ────────────────────────────"
uv run pytest -q

echo
echo "── Integridad Git ─────────────────────────────────────"
git diff --check

echo
echo "[OK] Verificación completa Linux completada."
