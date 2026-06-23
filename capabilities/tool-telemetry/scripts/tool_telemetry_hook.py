#!/usr/bin/env python3
"""Tool usage telemetry hook (capability tool-telemetry).

Records each PreToolUse/PostToolUse as a deterministic JSONL line, with secret
scrubbing. Fail-soft: never breaks the tool call (always returns exit 0).
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

CAPABILITY = "tool-telemetry"

PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")
AWS_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
INLINE_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|secret|token|password|authorization|bearer)\b"
    r"(\s*[:=]\s*)"
    r"(\"[^\"]*\"|'[^']*'|\S+)"
)
JSON_SECRET_RE = re.compile(
    r"(?i)\"(api[_-]?key|secret|token|password|authorization)\"(\s*:\s*)\"[^\"]*\""
)


def scrub(text: str) -> str:
    text = PRIVATE_KEY_RE.sub("[REDACTED-PRIVATE-KEY]", text)
    text = AWS_RE.sub("[REDACTED-AWS]", text)
    text = JSON_SECRET_RE.sub(r'"\1"\2"[REDACTED]"', text)
    text = INLINE_SECRET_RE.sub(r"\1\2[REDACTED]", text)
    return text


def main() -> int:
    try:
        raw = sys.stdin.read()
    except Exception:
        return 0

    try:
        payload = json.loads(raw) if raw.strip() else {}
    except Exception:
        payload = {"raw": raw}
    if not isinstance(payload, dict):
        payload = {"raw": raw}

    project_dir = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))

    try:
        policy = json.loads(
            (project_dir / "state" / "capabilities" / f"{CAPABILITY}.json").read_text(
                encoding="utf-8"
            )
        )
    except Exception:
        return 0
    if not isinstance(policy, dict) or policy.get("enabled") is not True:
        return 0

    do_scrub = policy.get("scrub_secrets", True) is not False
    try:
        max_chars = int(policy.get("max_value_chars", 2000))
    except Exception:
        max_chars = 2000

    try:
        project = json.loads((project_dir / "state" / "project.json").read_text(encoding="utf-8"))
        artifact_root = Path(str(project["artifact_root"])).expanduser()
    except Exception:
        return 0

    def render(value: object) -> str:
        try:
            text = json.dumps(value, ensure_ascii=False)
        except Exception:
            text = str(value)
        if do_scrub:
            text = scrub(text)
        if len(text) > max_chars:
            text = text[:max_chars] + "...<truncated>"
        return text

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event": payload.get("hook_event_name") or payload.get("event"),
        "tool": payload.get("tool_name") or payload.get("tool"),
        "session": payload.get("session_id") or payload.get("session"),
        "agent": payload.get("agent_type") or payload.get("agent_id"),
    }
    if "tool_input" in payload:
        record["tool_input"] = render(payload.get("tool_input"))
    if "tool_response" in payload:
        record["tool_response"] = render(payload.get("tool_response"))

    try:
        out_dir = artifact_root / "capabilities" / CAPABILITY
        out_dir.mkdir(parents=True, exist_ok=True)
        day = datetime.now(timezone.utc).strftime("%Y%m%d")
        with (out_dir / f"observations-{day}.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        return 0

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
