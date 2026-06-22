#!/usr/bin/env bash
# Wrapper de hooks de Claude Code.
# Resuelve el interprete Python del proyecto y falla cerrado si no existe,
# evitando que un PATH incompleto deje el Role Guard sin aplicar.
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR no definido}"

HOOK_NAME="${1:?hook name requerido}"
shift || true

resolve_python() {
    if [ -x ".venv/bin/python" ]; then
        echo ".venv/bin/python"
        return 0
    fi

    if command -v python3 >/dev/null 2>&1; then
        command -v python3
        return 0
    fi

    if command -v python >/dev/null 2>&1; then
        command -v python
        return 0
    fi

    return 1
}

PYTHON_BIN="$(resolve_python || true)"

if [ -z "${PYTHON_BIN:-}" ]; then
    echo "[HOOK_FATAL] No se encontro interprete Python" >&2
    exit 2
fi

case "$HOOK_NAME" in
    role_guard)
        exec "$PYTHON_BIN" scripts/role_guard.py "$@"
        ;;
    agent_budget_observer)
        exec "$PYTHON_BIN" scripts/agent_budget_observer.py "$@"
        ;;
    notify)
        # Capability opcional remote-notifications: si no esta instalada,
        # el hook es un no-op (no debe romper proyectos sin la capability).
        if [ ! -f scripts/notify_hook.py ]; then
            exit 0
        fi
        exec "$PYTHON_BIN" scripts/notify_hook.py "$@"
        ;;
    tool_telemetry)
        # Capability opcional tool-telemetry: si no esta instalada,
        # el hook es un no-op (no debe romper proyectos sin la capability).
        if [ ! -f scripts/tool_telemetry_hook.py ]; then
            exit 0
        fi
        exec "$PYTHON_BIN" scripts/tool_telemetry_hook.py "$@"
        ;;
    *)
        echo "[HOOK_FATAL] Hook desconocido: $HOOK_NAME" >&2
        exit 2
        ;;
esac
