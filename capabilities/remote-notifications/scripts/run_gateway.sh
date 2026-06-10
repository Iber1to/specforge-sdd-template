#!/usr/bin/env bash
# Lanza el gateway Telegram del harness en una sesion tmux persistente.
#
# La sesion sobrevive a desconexiones SSH. Reconecta volviendo a ejecutar
# este script, o con:  tmux attach -t notify-gateway
#
# Variables opcionales:
#   GATEWAY_TMUX_SESSION   nombre de la sesion tmux (por defecto: notify-gateway)
set -euo pipefail

SESSION="${GATEWAY_TMUX_SESSION:-notify-gateway}"
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if ! command -v tmux >/dev/null 2>&1; then
    echo "[ERROR] tmux no esta instalado; instalalo para sesiones persistentes." >&2
    exit 2
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
    echo "[OK] El gateway ya esta corriendo en la sesion: $SESSION"
    exit 0
fi

echo "[OK] Creando sesion tmux '$SESSION' en $PROJECT_DIR"
tmux new-session -d -s "$SESSION" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION" 'export PATH="$HOME/.local/bin:$PATH"' C-m
tmux send-keys -t "$SESSION" 'python3 scripts/telegram_gateway.py' C-m

echo "[OK] Gateway lanzado. Logs: tmux attach -t $SESSION (detach: Ctrl-b d)"
