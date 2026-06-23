#!/usr/bin/env bash
# Claude Code hooks wrapper.
# Resolves the project's Python interpreter and fails closed if it is missing,
# preventing an incomplete PATH from leaving the Role Guard unenforced.
set -euo pipefail

cd "${CLAUDE_PROJECT_DIR:?CLAUDE_PROJECT_DIR not defined}"

HOOK_NAME="${1:?hook name required}"
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
    echo "[HOOK_FATAL] No Python interpreter found" >&2
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
        # Optional remote-notifications capability: if not installed,
        # the hook is a no-op (must not break projects without the capability).
        if [ ! -f scripts/notify_hook.py ]; then
            exit 0
        fi
        exec "$PYTHON_BIN" scripts/notify_hook.py "$@"
        ;;
    tool_telemetry)
        # Optional tool-telemetry capability: if not installed,
        # the hook is a no-op (must not break projects without the capability).
        if [ ! -f scripts/tool_telemetry_hook.py ]; then
            exit 0
        fi
        exec "$PYTHON_BIN" scripts/tool_telemetry_hook.py "$@"
        ;;
    *)
        echo "[HOOK_FATAL] Unknown hook: $HOOK_NAME" >&2
        exit 2
        ;;
esac
