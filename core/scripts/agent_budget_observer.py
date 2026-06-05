#!/usr/bin/env python3
"""Observa duración, turnos y tokens de subagentes Claude Code.

Este hook nunca bloquea el workflow. Todos los errores se muestran como warning
y terminan con exit code 0.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)

ROLE_STATES = {
    "specifier": {"DRAFT"},
    "architect": {"SPEC_READY", "DESIGN_READY"},
    "implementer": {"IN_PROGRESS"},
    "qa-reviewer": {"READY_FOR_QA"},
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))

    if not isinstance(value, dict):
        raise ValueError(f"{path} debe contener un objeto JSON")

    return value


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    os.replace(temporary, path)


def repo_root() -> Path:
    return Path(os.environ.get("CLAUDE_PROJECT_DIR", Path.cwd())).expanduser().resolve()


def control_root(root: Path) -> Path:
    project = read_json(root / "state" / "project.json")
    return Path(project["control_root"]).expanduser().resolve()


def metric_path(root: Path, agent_id: str) -> Path:
    safe_id = re.sub(r"[^A-Za-z0-9_.-]", "_", agent_id)
    return control_root(root) / "agent-metrics" / f"{safe_id}.json"


def load_budget(root: Path, role: str) -> dict[str, Any]:
    policy = read_json(root / "state" / "agent-budgets.json")
    value = policy.get("roles", {}).get(role, {})

    return value if isinstance(value, dict) else {}


def infer_feature_id(root: Path, role: str) -> str | None:
    states = ROLE_STATES.get(role)

    if not states:
        return None

    queue = read_json(control_root(root) / "queue.json")

    matches = [
        str(feature["id"])
        for feature in queue.get("features", [])
        if isinstance(feature, dict) and feature.get("state") in states and feature.get("id")
    ]

    return matches[0] if len(matches) == 1 else None


def extract_transcript_usage(path: Path) -> dict[str, int]:
    totals = {field: 0 for field in TOKEN_FIELDS}
    assistant_turns = 0

    if not path.is_file():
        return {
            **totals,
            "total_tokens_observed": 0,
            "assistant_turns_observed": 0,
        }

    for line in path.read_text(
        encoding="utf-8",
        errors="replace",
    ).splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue

        if not isinstance(record, dict):
            continue

        message = record.get("message")
        usage = None

        if isinstance(message, dict) and isinstance(
            message.get("usage"),
            dict,
        ):
            usage = message["usage"]
        elif isinstance(record.get("usage"), dict):
            usage = record["usage"]

        if not isinstance(usage, dict):
            continue

        if record.get("type") == "assistant" or (
            isinstance(message, dict) and message.get("role") == "assistant"
        ):
            assistant_turns += 1

        for field in TOKEN_FIELDS:
            value = usage.get(field, 0)

            if isinstance(value, int) and value >= 0:
                totals[field] += value

    return {
        **totals,
        "total_tokens_observed": sum(totals.values()),
        "assistant_turns_observed": assistant_turns,
    }


def evaluate_budget(
    *,
    duration_seconds: int,
    usage: dict[str, int],
    budget: dict[str, Any],
) -> dict[str, Any]:
    warnings: list[str] = []

    comparisons = {
        "duration_seconds": (
            duration_seconds,
            budget.get("max_duration_seconds"),
        ),
        "assistant_turns_observed": (
            usage["assistant_turns_observed"],
            budget.get("max_turns"),
        ),
        "total_tokens_observed": (
            usage["total_tokens_observed"],
            budget.get("max_total_tokens"),
        ),
    }

    for name, (observed, limit) in comparisons.items():
        if isinstance(limit, int) and observed > limit:
            warnings.append(f"{name}: {observed} > {limit}")

    return {
        "mode": "observe",
        "within_budget": not warnings,
        "warnings": warnings,
    }


def start_subagent(root: Path, event: dict[str, Any]) -> None:
    agent_id = str(event.get("agent_id", "")).strip()
    role = str(event.get("agent_type", "")).strip()

    if not agent_id or not role:
        return

    record = {
        "schema_version": 1,
        "agent_id": agent_id,
        "session_id": event.get("session_id"),
        "role": role,
        "feature_id": infer_feature_id(root, role),
        "status": "ACTIVE",
        "started_at": utc_now(),
        "completed_at": None,
        "duration_seconds": None,
        "budget": load_budget(root, role),
        "usage": None,
        "budget_evaluation": None,
        "transcript_path": None,
        "last_assistant_message": None,
    }

    write_json(metric_path(root, agent_id), record)


def stop_subagent(root: Path, event: dict[str, Any]) -> None:
    agent_id = str(event.get("agent_id", "")).strip()

    if not agent_id:
        return

    path = metric_path(root, agent_id)

    if path.exists():
        record = read_json(path)
    else:
        start_subagent(root, event)
        record = read_json(path)

    completed_at = utc_now()
    started_at = str(record.get("started_at") or completed_at)

    duration_seconds = max(
        0,
        int((parse_timestamp(completed_at) - parse_timestamp(started_at)).total_seconds()),
    )

    transcript_value = event.get("agent_transcript_path")
    transcript = Path(str(transcript_value)).expanduser().resolve() if transcript_value else Path()

    usage = extract_transcript_usage(transcript)
    budget = record.get("budget", {})

    record.update(
        {
            "status": "COMPLETED",
            "completed_at": completed_at,
            "duration_seconds": duration_seconds,
            "usage": usage,
            "budget_evaluation": evaluate_budget(
                duration_seconds=duration_seconds,
                usage=usage,
                budget=budget if isinstance(budget, dict) else {},
            ),
            "transcript_path": (str(transcript) if transcript_value else None),
            "last_assistant_message": event.get("last_assistant_message"),
        }
    )

    write_json(path, record)


def main() -> int:
    try:
        event = json.load(sys.stdin)
        root = repo_root()

        if event.get("hook_event_name") == "SubagentStart":
            start_subagent(root, event)

        elif event.get("hook_event_name") == "SubagentStop":
            stop_subagent(root, event)

    except Exception as exc:
        print(f"Agent budget observer warning: {exc}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
