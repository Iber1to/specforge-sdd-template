#!/usr/bin/env python3
"""Bidirectional Telegram gateway for the harness (remote-notifications capability).

Long-polling daemon against the Telegram Bot API. It needs no public endpoint
nor tunnel: the machine only makes outbound requests.

Supported commands (only from the authorized chat):

    /ping          checks that the gateway is alive
    /status        runs scripts/project_status.py and returns the output
    /tail [n]      returns the last n lines of the leader's tmux session
    /help          lists the commands
    <free text>    is injected as a prompt into the leader's tmux session

Launch with scripts/run_gateway.sh (persistent tmux session) or as a service.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from notify_common import (
    NotificationError,
    load_credentials,
    load_policy,
    project_label,
    repo_root,
    telegram_api_call,
)

DEFAULT_POLL_TIMEOUT_SECONDS = 50
DEFAULT_TAIL_LINES = 40
MAX_REPLY_CHARS = 3500
MAX_INJECTED_CHARS = 2000
RETRY_DELAY_SECONDS = 5

HELP_TEXT = (
    "Gateway commands:\n"
    "/ping - checks the gateway\n"
    "/status - project status (project_status.py)\n"
    "/tail [n] - last n lines of the leader's session\n"
    "/help - this help\n"
    "Any other text is sent as a prompt to the leader."
)


def gateway_policy(policy: dict[str, Any]) -> dict[str, Any]:
    gateway = policy.get("gateway", {})
    return gateway if isinstance(gateway, dict) else {}


def tmux_session(policy: dict[str, Any]) -> str:
    return str(policy.get("tmux_session", "leader"))


def tmux_available() -> bool:
    return shutil.which("tmux") is not None


def tmux_session_exists(session: str) -> bool:
    result = subprocess.run(
        ["tmux", "has-session", "-t", session],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def tmux_tail(session: str, lines: int) -> str:
    result = subprocess.run(
        ["tmux", "capture-pane", "-p", "-t", session],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return f"[ERROR] tmux capture-pane failed: {result.stderr.strip()}"

    captured = [line for line in result.stdout.splitlines() if line.strip()]
    return "\n".join(captured[-lines:]) or "(empty screen)"


def tmux_inject(session: str, text: str) -> str:
    sanitized = "".join(
        character for character in text if character.isprintable() or character == " "
    ).strip()

    if not sanitized:
        return "[ERROR] Empty text after sanitizing; nothing is injected."

    if len(sanitized) > MAX_INJECTED_CHARS:
        return f"[ERROR] Text too long (max {MAX_INJECTED_CHARS} characters)."

    literal = subprocess.run(
        ["tmux", "send-keys", "-t", session, "-l", sanitized],
        check=False,
        capture_output=True,
        text=True,
    )

    if literal.returncode != 0:
        return f"[ERROR] tmux send-keys failed: {literal.stderr.strip()}"

    submit = subprocess.run(
        ["tmux", "send-keys", "-t", session, "Enter"],
        check=False,
        capture_output=True,
        text=True,
    )

    if submit.returncode != 0:
        return f"[ERROR] tmux Enter failed: {submit.stderr.strip()}"

    return "[OK] Prompt sent to the leader."


def run_status(root: Path) -> str:
    commands = (
        ["uv", "run", "python", "scripts/project_status.py"],
        [sys.executable, "scripts/project_status.py"],
    )

    for command in commands:
        if shutil.which(command[0]) is None and not Path(command[0]).exists():
            continue

        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            cwd=root,
            timeout=120,
        )

        output = (result.stdout or result.stderr).strip()

        if output:
            return output

    return "[ERROR] Could not run project_status.py"


def truncate_reply(text: str) -> str:
    if len(text) <= MAX_REPLY_CHARS:
        return text

    return text[-MAX_REPLY_CHARS:]


def handle_text(text: str, policy: dict[str, Any], root: Path) -> str:
    gateway = gateway_policy(policy)
    session = tmux_session(policy)
    stripped = text.strip()

    if stripped in {"/ping", "/start"}:
        return f"pong - {project_label(root)} gateway active"

    if stripped == "/help":
        return HELP_TEXT

    if stripped == "/status":
        return truncate_reply(run_status(root))

    if stripped.startswith("/tail"):
        parts = stripped.split()
        lines = DEFAULT_TAIL_LINES

        if len(parts) > 1 and parts[1].isdigit():
            lines = max(1, min(int(parts[1]), 200))

        if not tmux_available():
            return "[ERROR] tmux is not available on the host."

        if not tmux_session_exists(session):
            return f"[ERROR] The tmux session '{session}' does not exist."

        return truncate_reply(tmux_tail(session, lines))

    if stripped.startswith("/"):
        return f"Unknown command: {stripped.split()[0]}\n\n{HELP_TEXT}"

    if gateway.get("allow_text_injection", True) is not True:
        return (
            "[ERROR] Text injection disabled by policy (gateway.allow_text_injection)."
        )

    if not tmux_available():
        return "[ERROR] tmux is not available on the host."

    if not tmux_session_exists(session):
        return f"[ERROR] The tmux session '{session}' does not exist. Launch the leader with scripts/run_leader.sh."

    return tmux_inject(session, stripped)


def drain_backlog(token: str) -> int:
    """Discard pending updates to avoid reprocessing old messages."""

    offset = 0

    while True:
        data = telegram_api_call(
            token,
            "getUpdates",
            {"offset": offset, "timeout": 0, "limit": 100},
            timeout_seconds=15,
        )
        updates = data.get("result", [])

        if not updates:
            return offset

        offset = max(int(update["update_id"]) for update in updates) + 1


def poll_loop(policy: dict[str, Any], token: str, chat_id: str, root: Path) -> None:
    gateway = gateway_policy(policy)
    raw_timeout = gateway.get("poll_timeout_seconds", DEFAULT_POLL_TIMEOUT_SECONDS)
    poll_timeout = (
        raw_timeout
        if isinstance(raw_timeout, int) and raw_timeout > 0
        else (DEFAULT_POLL_TIMEOUT_SECONDS)
    )
    offset = drain_backlog(token)
    print(f"[OK] Gateway listening (authorized chat: {chat_id})")

    while True:
        try:
            data = telegram_api_call(
                token,
                "getUpdates",
                {"offset": offset, "timeout": poll_timeout, "limit": 20},
                timeout_seconds=poll_timeout + 15,
            )
        except NotificationError as exc:
            print(
                f"[ERROR] getUpdates failed; retrying in {RETRY_DELAY_SECONDS}s: {exc}",
                file=sys.stderr,
            )
            time.sleep(RETRY_DELAY_SECONDS)
            continue

        for update in data.get("result", []):
            offset = max(offset, int(update.get("update_id", 0)) + 1)
            message = update.get("message") or update.get("edited_message") or {}
            chat = message.get("chat", {})
            text = message.get("text")

            if str(chat.get("id", "")) != str(chat_id):
                print(
                    f"[ERROR] Message ignored from unauthorized chat: {chat.get('id')}",
                    file=sys.stderr,
                )
                continue

            if not isinstance(text, str) or not text.strip():
                continue

            try:
                reply = handle_text(text, policy, root)
            except Exception as exc:  # noqa: BLE001 - the gateway must stay alive
                reply = f"[ERROR] Failed processing the message: {exc}"

            try:
                telegram_api_call(
                    token,
                    "sendMessage",
                    {"chat_id": chat_id, "text": reply, "disable_web_page_preview": True},
                )
            except NotificationError as exc:
                print(f"[ERROR] Could not reply: {exc}", file=sys.stderr)


def main() -> int:
    root = repo_root()

    try:
        policy = load_policy(root)
    except NotificationError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    if policy.get("enabled") is not True:
        print("[ERROR] remote-notifications disabled by policy", file=sys.stderr)
        return 2

    if gateway_policy(policy).get("enabled", True) is not True:
        print("[ERROR] gateway disabled by policy (gateway.enabled)", file=sys.stderr)
        return 2

    try:
        token, chat_id = load_credentials(policy)
        me = telegram_api_call(token, "getMe", {}, timeout_seconds=15)
    except NotificationError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2

    username = me.get("result", {}).get("username", "unknown")
    print(f"[OK] Connected as @{username} for project {project_label(root)}")

    try:
        poll_loop(policy, token, chat_id, root)
    except KeyboardInterrupt:
        print("[OK] Gateway stopped by the operator")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
