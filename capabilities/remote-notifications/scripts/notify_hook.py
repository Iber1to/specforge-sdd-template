#!/usr/bin/env python3
"""Hook de notificacion remota para Claude Code (Stop / Notification).

Red de seguridad determinista: avisa por Telegram cuando la sesion principal
del leader se detiene (turno completado o a la espera de instrucciones) o
cuando Claude Code emite una notificacion (espera de input o de permisos).

Reglas:
- Solo notifica si CLAUDE_HARNESS_ROLE esta en policy.roles (defecto: leader).
- Aplica debounce para no inundar el canal.
- Siempre termina con exit 0: un fallo de notificacion jamas bloquea la sesion.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from notify_common import (
    NotificationError,
    event_enabled,
    format_event_text,
    load_policy,
    policy_enabled,
    send_message,
    should_debounce,
)

DEFAULT_ROLES = ["leader"]
EXCERPT_LIMIT = 500


def read_event() -> dict[str, Any]:
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return {}

    return data if isinstance(data, dict) else {}


def role_allowed(policy: dict[str, Any]) -> bool:
    roles = policy.get("roles", DEFAULT_ROLES)

    if not isinstance(roles, list) or not roles:
        roles = DEFAULT_ROLES

    return os.environ.get("CLAUDE_HARNESS_ROLE", "").strip() in roles


def transcript_excerpt(event: dict[str, Any]) -> str:
    """Extrae (best-effort) el ultimo mensaje del asistente del transcript."""

    raw_path = event.get("transcript_path")

    if not isinstance(raw_path, str) or not raw_path.strip():
        return ""

    path = Path(raw_path).expanduser()

    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""

    for line in reversed(lines[-200:]):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(entry, dict) or entry.get("type") != "assistant":
            continue

        message = entry.get("message", {})
        content = message.get("content", []) if isinstance(message, dict) else []
        texts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        excerpt = "\n".join(text for text in texts if text).strip()

        if excerpt:
            if len(excerpt) > EXCERPT_LIMIT:
                excerpt = excerpt[-EXCERPT_LIMIT:]
                excerpt = "..." + excerpt[excerpt.find(" ") + 1 :]
            return excerpt

    return ""


def build_message(event: dict[str, Any], hook_event: str) -> str:
    if hook_event == "Stop":
        excerpt = transcript_excerpt(event)
        body = "Leader detenido: turno completado o a la espera de instrucciones."

        if excerpt:
            body += f"\n---\n{excerpt}"

        return body

    notification_text = str(event.get("message", "")).strip()
    return notification_text or "Claude Code espera intervencion humana."


def main() -> int:
    event = read_event()
    hook_event = str(event.get("hook_event_name", ""))

    if hook_event not in {"Stop", "Notification"}:
        return 0

    # Evita bucles si otro hook Stop ya esta forzando la continuacion.
    if hook_event == "Stop" and event.get("stop_hook_active") is True:
        return 0

    internal_event = "stop" if hook_event == "Stop" else "notification"

    try:
        policy = load_policy()

        if not policy_enabled(policy):
            return 0

        if not role_allowed(policy):
            return 0

        if not event_enabled(policy, internal_event):
            return 0

        if should_debounce(policy, internal_event):
            return 0

        text = format_event_text(internal_event, build_message(event, hook_event))
        send_message(policy, text)
    except NotificationError as exc:
        print(f"[ERROR] Hook de notificacion fallo (ignorado): {exc}", file=sys.stderr)
    except Exception as exc:  # noqa: BLE001 - el hook nunca debe romper la sesion
        print(f"[ERROR] Hook de notificacion inesperado (ignorado): {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
