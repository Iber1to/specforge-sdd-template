#!/usr/bin/env python3
"""Agregación determinista de métricas de agentes y runs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

if __package__:
    from .control_common import ControlPlaneError, load_json, utc_now
else:
    from control_common import ControlPlaneError, load_json, utc_now


TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "total_tokens_observed",
    "assistant_turns_observed",
)


def _positive_integer(value: Any) -> int:
    if isinstance(value, int) and value >= 0:
        return value

    return 0


def empty_agent_totals() -> dict[str, Any]:
    return {
        "invocations": 0,
        "completed": 0,
        "active": 0,
        "blocked_results": 0,
        "budget_violations": 0,
        "duration_seconds": 0,
        **{field: 0 for field in TOKEN_FIELDS},
    }


def empty_run_totals() -> dict[str, Any]:
    return {
        "runs": 0,
        "completed": 0,
        "active": 0,
        "expired": 0,
        "retries": 0,
        "duration_seconds": 0,
        "heartbeat_count": 0,
        "results": {},
    }


def empty_scope() -> dict[str, Any]:
    return {
        "agents": empty_agent_totals(),
        "runs": empty_run_totals(),
    }


def _scope(
    collection: dict[str, dict[str, Any]],
    key: str,
) -> dict[str, Any]:
    if key not in collection:
        collection[key] = empty_scope()

    return collection[key]


def add_agent_metric(
    scope: dict[str, Any],
    metric: dict[str, Any],
) -> None:
    totals = scope["agents"]
    status = metric.get("status")

    totals["invocations"] += 1

    if status == "COMPLETED":
        totals["completed"] += 1
    elif status == "ACTIVE":
        totals["active"] += 1

    totals["duration_seconds"] += _positive_integer(metric.get("duration_seconds"))

    usage = metric.get("usage")

    if isinstance(usage, dict):
        for field in TOKEN_FIELDS:
            totals[field] += _positive_integer(usage.get(field))

    evaluation = metric.get("budget_evaluation")

    if isinstance(evaluation, dict) and evaluation.get("within_budget") is False:
        totals["budget_violations"] += 1

    message = metric.get("last_assistant_message")

    if isinstance(message, str) and message.startswith("BLOCKED"):
        totals["blocked_results"] += 1


def add_run_metric(
    scope: dict[str, Any],
    run: dict[str, Any],
) -> None:
    totals = scope["runs"]
    status = run.get("status")

    totals["runs"] += 1

    if status == "COMPLETED":
        totals["completed"] += 1
    elif status == "ACTIVE":
        totals["active"] += 1
    elif status == "EXPIRED":
        totals["expired"] += 1

    metrics = run.get("metrics")

    if not isinstance(metrics, dict):
        return

    if metrics.get("is_retry") is True:
        totals["retries"] += 1

    totals["duration_seconds"] += _positive_integer(metrics.get("duration_seconds"))
    totals["heartbeat_count"] += _positive_integer(metrics.get("heartbeat_count"))

    result = metrics.get("result")

    if isinstance(result, str) and result:
        results = totals["results"]
        results[result] = int(results.get(result, 0)) + 1


def _read_records(
    root: Path,
) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    invalid = 0

    if not root.exists():
        return records, invalid

    for path in sorted(root.glob("*.json")):
        try:
            records.append(load_json(path))
        except ControlPlaneError:
            invalid += 1

    return records, invalid


def aggregate_metrics(control_root: Path) -> dict[str, Any]:
    """Agrega métricas sin modificar sus fuentes."""

    summary: dict[str, Any] = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "project": empty_scope(),
        "roles": {},
        "features": {},
        "invalid_records": {
            "agent_metrics": 0,
            "runs": 0,
        },
    }

    agent_records, invalid_agents = _read_records(control_root / "agent-metrics")
    run_records, invalid_runs = _read_records(control_root / "runs")

    summary["invalid_records"]["agent_metrics"] = invalid_agents
    summary["invalid_records"]["runs"] = invalid_runs

    for metric in agent_records:
        role = str(metric.get("role") or "unknown")
        feature_id = metric.get("feature_id")

        add_agent_metric(summary["project"], metric)
        add_agent_metric(_scope(summary["roles"], role), metric)

        if isinstance(feature_id, str) and feature_id:
            add_agent_metric(
                _scope(summary["features"], feature_id),
                metric,
            )

    for run in run_records:
        role = str(run.get("role") or "unknown")
        feature_id = run.get("feature_id")

        add_run_metric(summary["project"], run)
        add_run_metric(_scope(summary["roles"], role), run)

        if isinstance(feature_id, str) and feature_id:
            add_run_metric(
                _scope(summary["features"], feature_id),
                run,
            )

    summary["roles"] = dict(sorted(summary["roles"].items()))
    summary["features"] = dict(sorted(summary["features"].items()))

    return summary
