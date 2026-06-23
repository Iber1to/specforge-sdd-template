#!/usr/bin/env bash
# Fast verification for the regular development cycle.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

export PATH="$HOME/.local/bin:$PATH"

if command -v uv >/dev/null 2>&1; then
  run_python=(uv run python)
  run_ruff=(uv run python -m ruff)
  run_pytest=(uv run python -m pytest)
else
  run_python=(.venv/bin/python)
  run_ruff=(.venv/bin/ruff)
  run_pytest=(.venv/bin/python -m pytest)
fi

if [ -d .venv ]; then
  find .venv -type f \( \
    -path "*/bin/ruff" -o \
    -path "*/bin/pytest" -o \
    -path "*/site-packages/ruff/ruff" \
  \) -exec chmod +x {} + 2>/dev/null || true
fi

echo "── Ruff lint ──────────────────────────────────────────"
"${run_ruff[@]}" check scripts tests/unit

echo
echo "── Ruff format ────────────────────────────────────────"
"${run_ruff[@]}" format --check scripts tests/unit

echo
echo "── Unit tests ─────────────────────────────────────────"
PYTHONDONTWRITEBYTECODE=1 "${run_pytest[@]}" -q tests/unit -p no:cacheprovider

echo
echo "[OK] Fast verification complete."
