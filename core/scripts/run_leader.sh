#!/usr/bin/env bash
# Launches the harness leader in a persistent tmux session.
#
# The session survives SSH disconnects and workstation shutdown
# (it keeps running on the server). Reconnect by running this script
# again, or with:  tmux attach -t leader
#
# Optional variables:
#   LEADER_TMUX_SESSION   tmux session name (default: leader)
#   CLAUDE_HARNESS_ROLE   role of the main session (default: leader)
set -euo pipefail

SESSION="${LEADER_TMUX_SESSION:-leader}"
ROLE="${CLAUDE_HARNESS_ROLE:-leader}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v tmux >/dev/null 2>&1; then
    echo "[ERROR] tmux is not installed; install it for persistent sessions." >&2
    exit 2
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "[OK] Reconnecting to existing session: $SESSION"
    exec tmux attach -t "$SESSION"
fi

echo "[OK] Creating tmux session '$SESSION' (role: $ROLE) in $PROJECT_DIR"
tmux new-session -d -s "$SESSION" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION" 'export PATH="$HOME/.local/bin:$PATH"' C-m
tmux send-keys -t "$SESSION" "export CLAUDE_HARNESS_ROLE=$ROLE" C-m
tmux send-keys -t "$SESSION" "claude --agent leader --permission-mode bypassPermissions" C-m

echo "[OK] Leader launched. Detach: Ctrl-b d. Reconnect: tmux attach -t $SESSION"
exec tmux attach -t "$SESSION"
