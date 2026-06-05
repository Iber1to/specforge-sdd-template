#!/usr/bin/env bash
# Verificación rápida para el ciclo habitual de desarrollo.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

export PATH="$HOME/.local/bin:$PATH"

if command -v uv >/dev/null 2>&1; then
  run_python=(uv run python)
  run_ruff=(uv run ruff)
  run_pytest=(uv run pytest)
else
  run_python=(.venv/bin/python)
  run_ruff=(.venv/bin/ruff)
  run_pytest=(.venv/bin/python -m pytest)
fi

echo "── Ruff lint ──────────────────────────────────────────"
"${run_ruff[@]}" check scripts tests/unit

echo
echo "── Ruff format ────────────────────────────────────────"
"${run_ruff[@]}" format --check scripts tests/unit

echo
echo "── Tests unitarios ────────────────────────────────────"
PYTHONDONTWRITEBYTECODE=1 "${run_pytest[@]}" -q tests/unit -p no:cacheprovider

echo
echo "[OK] Verificación rápida completada."
