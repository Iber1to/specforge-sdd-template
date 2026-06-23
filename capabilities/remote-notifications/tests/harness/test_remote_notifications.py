"""Hermetic tests for the remote-notifications capability.

They touch neither the network nor real credentials: each case builds a minimal
project in tmp_path with a policy that points at nonexistent credentials and has
no debounce, and clears the TELEGRAM_* variables from the environment.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from notify_common import (
    debounce_stamp_path,
    format_event_text,
    load_policy,
    parse_env_file,
    redact_token,
    should_debounce,
    split_message,
)
from role_guard import _leader_segment_allowed

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
FIXTURE_PROJECT_ID = "hermetic-fixture"


def hermetic_env(project_dir: Path, role: str | None = None) -> dict[str, str]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("TELEGRAM_") and key != "CLAUDE_HARNESS_ROLE"
    }
    env["CLAUDE_PROJECT_DIR"] = str(project_dir)

    if role is not None:
        env["CLAUDE_HARNESS_ROLE"] = role

    return env


def write_hermetic_project(root: Path, enabled: bool = True) -> None:
    (root / "state" / "capabilities").mkdir(parents=True, exist_ok=True)
    (root / "state" / "project.json").write_text(
        json.dumps({"project_id": FIXTURE_PROJECT_ID}) + "\n", encoding="utf-8"
    )
    policy = {
        "schema_version": 1,
        "enabled": enabled,
        "transport": "telegram",
        "roles": ["leader"],
        "debounce_seconds": 0,
        "credentials_file": str(root / "missing-credentials.env"),
    }
    (root / "state" / "capabilities" / "remote-notifications.json").write_text(
        json.dumps(policy, indent=2) + "\n", encoding="utf-8"
    )


def test_repository_policy_is_valid() -> None:
    policy = load_policy(REPO_ROOT)

    assert policy["schema_version"] == 1
    assert isinstance(policy.get("enabled"), bool)
    assert policy.get("transport") == "telegram"


def test_format_event_text_includes_prefix_feature_and_project(tmp_path: Path) -> None:
    write_hermetic_project(tmp_path)

    text = format_event_text("blocked", "motivo breve", feature="F-001", root=tmp_path)

    assert text.startswith(f"[BLOCKED] {FIXTURE_PROJECT_ID} | F-001")
    assert "motivo breve" in text


def test_split_message_chunks_long_text() -> None:
    chunks = split_message("a" * 8000, limit=3900)

    assert [len(chunk) for chunk in chunks] == [3900, 3900, 200]


def test_redact_token_hides_bot_token() -> None:
    token = "123456:AAA-bbb_CCC"
    redacted = redact_token(f"error bot{token} y token suelto {token}", token)

    assert token not in redacted


def test_parse_env_file_ignores_comments_and_quotes(tmp_path: Path) -> None:
    credentials = tmp_path / "telegram.env"
    credentials.write_text(
        "# comentario\nTELEGRAM_BOT_TOKEN='abc'\nTELEGRAM_CHAT_ID=42\n", encoding="utf-8"
    )

    values = parse_env_file(credentials)

    assert values["TELEGRAM_BOT_TOKEN"] == "abc"
    assert values["TELEGRAM_CHAT_ID"] == "42"


def test_should_debounce_blocks_second_event(tmp_path: Path) -> None:
    write_hermetic_project(tmp_path)
    debounce_stamp_path("stop", tmp_path).unlink(missing_ok=True)
    policy = {"debounce_seconds": 3600}

    assert should_debounce(policy, "stop", tmp_path) is False
    assert should_debounce(policy, "stop", tmp_path) is True

    debounce_stamp_path("stop", tmp_path).unlink(missing_ok=True)


def test_notify_cli_is_fail_soft_without_credentials(tmp_path: Path) -> None:
    write_hermetic_project(tmp_path)
    command = [
        sys.executable,
        str(SCRIPTS / "notify.py"),
        "--event",
        "info",
        "--message",
        "fixture",
    ]

    soft = subprocess.run(
        command,
        check=False,
        text=True,
        capture_output=True,
        env=hermetic_env(tmp_path),
    )

    assert soft.returncode == 0
    assert "[ERROR]" in soft.stderr

    strict = subprocess.run(
        [*command, "--strict"],
        check=False,
        text=True,
        capture_output=True,
        env=hermetic_env(tmp_path),
    )

    assert strict.returncode == 2


def test_notify_cli_disabled_policy_sends_nothing(tmp_path: Path) -> None:
    write_hermetic_project(tmp_path, enabled=False)

    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "notify.py"), "--event", "info", "--message", "x"],
        check=False,
        text=True,
        capture_output=True,
        env=hermetic_env(tmp_path),
    )

    assert result.returncode == 0
    assert "disabled" in result.stdout


def test_notify_hook_is_silent_without_role(tmp_path: Path) -> None:
    write_hermetic_project(tmp_path)
    event = json.dumps({"hook_event_name": "Stop", "session_id": "s1"})

    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "notify_hook.py")],
        check=False,
        text=True,
        capture_output=True,
        input=event,
        env=hermetic_env(tmp_path),
    )

    assert result.returncode == 0
    assert "[ERROR]" not in result.stderr


def test_notify_hook_fail_soft_with_leader_role(tmp_path: Path) -> None:
    write_hermetic_project(tmp_path)
    debounce_stamp_path("stop", tmp_path).unlink(missing_ok=True)
    event = json.dumps({"hook_event_name": "Stop", "session_id": "s1"})

    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "notify_hook.py")],
        check=False,
        text=True,
        capture_output=True,
        input=event,
        env=hermetic_env(tmp_path, role="leader"),
    )

    assert result.returncode == 0
    assert "[ERROR]" in result.stderr


def test_leader_allowlist_includes_notify() -> None:
    allowed, reason = _leader_segment_allowed(
        'uv run python scripts/notify.py --event blocked --message "motivo"'
    )

    assert allowed, reason
