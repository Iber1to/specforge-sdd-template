#!/usr/bin/env bash
# Launches the harness Telegram gateway in a persistent tmux session.
#
# The session survives SSH disconnections. Reconnect by running this script
# again, or with:  tmux attach -t notify-gateway
#
# Optional variables:
#   GATEWAY_TMUX_SESSION   tmux session name (default: notify-gateway)
set -euo pipefail

SESSION="${GATEWAY_TMUX_SESSION:-notify-gateway}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v tmux >/dev/null 2>&1; then
    echo "[ERROR] tmux is not installed; install it for persistent sessions." >&2
    exit 2
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "[OK] The gateway is already running in the session: $SESSION"
    exit 0
fi

echo "[OK] Creating tmux session '$SESSION' in $PROJECT_DIR"
tmux new-session -d -s "$SESSION" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION" 'export PATH="$HOME/.local/bin:$PATH"' C-m
tmux send-keys -t "$SESSION" 'python3 scripts/telegram_gateway.py' C-m

echo "[OK] Gateway launched. Logs: tmux attach -t $SESSION (detach: Ctrl-b d)"
