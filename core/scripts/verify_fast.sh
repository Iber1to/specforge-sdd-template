#!/usr/bin/env bash
# Verificación rápida para el ciclo habitual de desarrollo.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

echo "── Ruff lint ──────────────────────────────────────────"
uv run ruff check scripts tests/unit

echo
echo "── Ruff format ────────────────────────────────────────"
uv run ruff format --check scripts tests/unit

echo
echo "── Tests unitarios ────────────────────────────────────"
uv run pytest -q tests/unit

echo
echo "[OK] Verificación rápida completada."
