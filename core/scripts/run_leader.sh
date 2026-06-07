#!/usr/bin/env bash
# Lanza el leader del harness en una sesion tmux persistente.
#
# La sesion sobrevive a desconexiones SSH y al apagado de la workstation
# (sigue corriendo en el servidor). Reconecta volviendo a ejecutar este
# script, o con:  tmux attach -t leader
#
# Variables opcionales:
#   LEADER_TMUX_SESSION   nombre de la sesion tmux (por defecto: leader)
#   CLAUDE_HARNESS_ROLE   rol de la sesion principal (por defecto: leader)
set -euo pipefail

SESSION="${LEADER_TMUX_SESSION:-leader}"
ROLE="${CLAUDE_HARNESS_ROLE:-leader}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v tmux >/dev/null 2>&1; then
    echo "[ERROR] tmux no esta instalado; instalalo para sesiones persistentes." >&2
    exit 2
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "[OK] Reconectando a la sesion existente: $SESSION"
    exec tmux attach -t "$SESSION"
fi

echo "[OK] Creando sesion tmux '$SESSION' (rol: $ROLE) en $PROJECT_DIR"
tmux new-session -d -s "$SESSION" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION" 'export PATH="$HOME/.local/bin:$PATH"' C-m
tmux send-keys -t "$SESSION" "export CLAUDE_HARNESS_ROLE=$ROLE" C-m
tmux send-keys -t "$SESSION" "claude --agent leader --permission-mode bypassPermissions" C-m

echo "[OK] Leader lanzado. Detach: Ctrl-b d. Reconectar: tmux attach -t $SESSION"
exec tmux attach -t "$SESSION"
