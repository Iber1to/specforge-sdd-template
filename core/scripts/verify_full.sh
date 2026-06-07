#!/usr/bin/env bash
# Verificación completa Linux previa a revisión o finalización.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

export PATH="$HOME/.local/bin:$PATH"

if command -v uv >/dev/null 2>&1; then
  sync_command=(uv sync --locked)
  run_python=(uv run python)
  run_ruff=(uv run python -m ruff)
  run_pytest=(uv run python -m pytest)
else
  sync_command=()
  run_python=(.venv/bin/python)
  run_ruff=(.venv/bin/ruff)
  run_pytest=(.venv/bin/python -m pytest)
fi

if [ "${#sync_command[@]}" -gt 0 ]; then
  echo "── Lockfile ───────────────────────────────────────────"
  "${sync_command[@]}"
  echo
fi

if [ -d .venv ]; then
  find .venv -type f \( \
    -path "*/bin/ruff" -o \
    -path "*/bin/pytest" -o \
    -path "*/site-packages/ruff/ruff" \
  \) -exec chmod +x {} + 2>/dev/null || true
fi

echo "── Política de agentes ─────────────────────────────────"
"${run_python[@]}" scripts/validate_agent_budgets.py
echo
echo "── Compilación Python ─────────────────────────────────"
PYTHONDONTWRITEBYTECODE=1 "${run_python[@]}" -m compileall -q scripts src tests

echo
echo "── Ruff lint ──────────────────────────────────────────"
"${run_ruff[@]}" check .

echo
echo "── Ruff format ────────────────────────────────────────"
"${run_ruff[@]}" format --check .

echo
echo "── Suite completa de tests ────────────────────────────"
PYTHONDONTWRITEBYTECODE=1 "${run_pytest[@]}" -q -p no:cacheprovider

echo
echo "── Integridad Git ─────────────────────────────────────"
git diff --check

echo
echo "[OK] Verificación completa Linux completada."
