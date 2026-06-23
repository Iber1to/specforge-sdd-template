#!/usr/bin/env python3
"""Summarized status of the derived per-feature metrics snapshot."""

from __future__ import annotations

from pathlib import Path
from typing import Any

if __package__:
    from .control_common import ControlPlaneError, load_json
else:
    from control_common import ControlPlaneError, load_json


def _nonnegative_integer(value: Any) -> int:
    return value if isinstance(value, int) and value >= 0 else 0


def summarize_metrics_snapshot(
    control_root: str | Path,
    queue: dict[str, Any],
) -> dict[str, Any]:
    """Summarize availability, freshness, and key metrics."""

    path = Path(control_root).resolve() / "feature-metrics.json"

    base = {
        "status": "missing",
        "path": str(path),
        "authoritative": False,
        "generated_at": None,
        "features": 0,
        "agent_invocations": 0,
        "runs": 0,
        "budget_violations": 0,
        "invalid_records": 0,
    }

    if not path.is_file():
        return base

    try:
        snapshot = load_json(path)
    except ControlPlaneError as exc:
        return {
            **base,
            "status": "invalid",
            "error": str(exc),
        }

    features = snapshot.get("features", {})
    project_metrics = snapshot.get("project_metrics", {})
    invalid_records = snapshot.get("invalid_records", {})

    if not isinstance(features, dict):
        return {
            **base,
            "status": "invalid",
            "error": "features is not an object",
        }

    if not isinstance(project_metrics, dict):
        project_metrics = {}

    agents = project_metrics.get("agents", {})
    runs = project_metrics.get("runs", {})

    if not isinstance(agents, dict):
        agents = {}

    if not isinstance(runs, dict):
        runs = {}

    current_states = {
        feature["id"]: feature.get("state")
        for feature in queue.get("features", [])
        if isinstance(feature, dict) and isinstance(feature.get("id"), str)
    }

    snapshot_states = {
        feature_id: feature.get("state_at_generation")
        for feature_id, feature in features.items()
        if isinstance(feature_id, str) and isinstance(feature, dict)
    }

    status = "available" if current_states == snapshot_states else "stale"

    invalid_total = 0

    if isinstance(invalid_records, dict):
        invalid_total = sum(_nonnegative_integer(value) for value in invalid_records.values())

    return {
        **base,
        "status": status,
        "generated_at": snapshot.get("generated_at"),
        "features": len(features),
        "agent_invocations": _nonnegative_integer(agents.get("invocations")),
        "runs": _nonnegative_integer(runs.get("runs")),
        "budget_violations": _nonnegative_integer(agents.get("budget_violations")),
        "invalid_records": invalid_total,
    }


def format_metrics_snapshot_status(summary: dict[str, Any]) -> str:
    """Generate a human-readable line for project_status.py."""

    status = summary.get("status")

    if status == "missing":
        return "unavailable"

    if status == "invalid":
        return f"invalid ({summary.get('error', 'unknown error')})"

    label = "up to date" if status == "available" else "stale"

    return (
        f"{label}; "
        f"{summary['features']} features; "
        f"{summary['agent_invocations']} invocations; "
        f"{summary['runs']} runs; "
        f"{summary['budget_violations']} overruns"
    )
