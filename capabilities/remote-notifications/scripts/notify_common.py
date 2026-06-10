#!/usr/bin/env python3
"""Helpers compartidos de la capability remote-notifications.

Carga la politica, resuelve credenciales y envia mensajes por el transporte
configurado (telegram). Diseno fail-soft: una notificacion fallida nunca debe
romper el harness ni bloquear al leader.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

POLICY_RELATIVE_PATH = Path("state") / "capabilities" / "remote-notifications.json"
DEFAULT_CREDENTIALS_FILE = "~/.config/agentic-harness/telegram.env"
TELEGRAM_API_BASE = "https://api.telegram.org"
TELEGRAM_MESSAGE_LIMIT = 3900
DEFAULT_DEBOUNCE_SECONDS = 60

EVENT_PREFIXES = {
    "blocked": "[BLOCKED]",
    "completed": "[COMPLETED]",
    "attention": "[ATTENTION]",
    "stop": "[STOP]",
    "notification": "[ATTENTION]",
    "info": "[INFO]",
}


class NotificationError(RuntimeError):
    """Error controlado de la capability remote-notifications."""


def repo_root() -> Path:
    value = os.environ.get("CLAUDE_PROJECT_DIR")

    if value:
        return Path(value).expanduser().resolve()

    return Path(__file__).resolve().parent.parent


def load_policy(root: Path | None = None) -> dict[str, Any]:
    base = root or repo_root()
    path = base / POLICY_RELATIVE_PATH

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise NotificationError(f"No existe la politica de notificaciones: {path}") from exc
    except json.JSONDecodeError as exc:
        raise NotificationError(f"Politica JSON invalida en {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise NotificationError(f"La politica {path} debe contener un objeto JSON")

    if data.get("schema_version") != 1:
        raise NotificationError("remote-notifications: schema_version debe ser 1")

    return data


def policy_enabled(policy: dict[str, Any]) -> bool:
    return policy.get("enabled") is True


def event_enabled(policy: dict[str, Any], event: str) -> bool:
    events = policy.get("events", {})

    if not isinstance(events, dict):
        return True

    return events.get(event, True) is True


def parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("'\"")

    return values


def load_credentials(policy: dict[str, Any]) -> tuple[str, str]:
    """Resuelve token y chat_id de Telegram.

    Prioridad: variables de entorno TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID y,
    si faltan, el archivo de credenciales declarado en la politica. El archivo
    vive fuera del repositorio: los secretos nunca se versionan.
    """

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if token and chat_id:
        return token, chat_id

    credentials_file = str(policy.get("credentials_file") or DEFAULT_CREDENTIALS_FILE)
    path = Path(credentials_file).expanduser()

    if path.is_file():
        values = parse_env_file(path)
        token = token or values.get("TELEGRAM_BOT_TOKEN", "").strip()
        chat_id = chat_id or values.get("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        raise NotificationError(
            "Faltan credenciales Telegram: define TELEGRAM_BOT_TOKEN y "
            f"TELEGRAM_CHAT_ID en el entorno o en {credentials_file}"
        )

    return token, chat_id


def project_label(root: Path | None = None) -> str:
    base = root or repo_root()

    try:
        state = json.loads((base / "state" / "project.json").read_text(encoding="utf-8"))
        project_id = state.get("project_id")
        if isinstance(project_id, str) and project_id:
            return project_id
    except (OSError, json.JSONDecodeError):
        pass

    return base.name


def redact_token(text: str, token: str) -> str:
    if token:
        text = text.replace(token, "<redacted>")

    return re.sub(r"bot\d+:[A-Za-z0-9_-]+", "bot<redacted>", text)


def telegram_api_call(
    token: str,
    method: str,
    payload: dict[str, Any],
    timeout_seconds: int = 15,
) -> dict[str, Any]:
    url = f"{TELEGRAM_API_BASE}/bot{token}/{method}"
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:300]
        raise NotificationError(
            f"Telegram {method} fallo con HTTP {exc.code}: {redact_token(detail, token)}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise NotificationError(
            f"Telegram {method} inaccesible: {redact_token(str(exc), token)}"
        ) from exc

    if not isinstance(data, dict) or data.get("ok") is not True:
        raise NotificationError(
            f"Telegram {method} respondio error: {redact_token(json.dumps(data)[:300], token)}"
        )

    return data


def split_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    chunks: list[str] = []
    remaining = text

    while remaining:
        chunks.append(remaining[:limit])
        remaining = remaining[limit:]

    return chunks or [""]


def send_message(policy: dict[str, Any], text: str) -> None:
    transport = str(policy.get("transport", "telegram"))

    if transport != "telegram":
        raise NotificationError(f"Transporte no soportado: {transport}")

    token, chat_id = load_credentials(policy)

    for chunk in split_message(text):
        telegram_api_call(
            token,
            "sendMessage",
            {
                "chat_id": chat_id,
                "text": chunk,
                "disable_web_page_preview": True,
            },
        )


def format_event_text(
    event: str,
    message: str,
    *,
    feature: str | None = None,
    root: Path | None = None,
) -> str:
    prefix = EVENT_PREFIXES.get(event, "[INFO]")
    header = f"{prefix} {project_label(root)}"

    if feature:
        header += f" | {feature}"

    body = message.strip()

    if body:
        return f"{header}\n{body}"

    return header


def debounce_stamp_path(event: str, root: Path | None = None) -> Path:
    label = re.sub(r"[^A-Za-z0-9_-]", "_", project_label(root))
    return Path(tempfile.gettempdir()) / f"agentic-notify-{label}-{event}.stamp"


def should_debounce(policy: dict[str, Any], event: str, root: Path | None = None) -> bool:
    """Devuelve True si el evento debe omitirse por haberse notificado hace poco.

    Aplica solo a eventos automaticos de hooks (stop, notification). Si el
    evento procede, registra el timestamp actual.
    """

    raw = policy.get("debounce_seconds", DEFAULT_DEBOUNCE_SECONDS)
    seconds = raw if isinstance(raw, (int, float)) else DEFAULT_DEBOUNCE_SECONDS

    if seconds <= 0:
        return False

    stamp = debounce_stamp_path(event, root)
    now = time.time()

    try:
        last = float(stamp.read_text(encoding="utf-8").strip())
        if now - last < seconds:
            return True
    except (OSError, ValueError):
        pass

    try:
        stamp.write_text(str(now), encoding="utf-8")
    except OSError:
        pass

    return False
