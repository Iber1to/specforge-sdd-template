#!/usr/bin/env python3
"""Métricas deterministas asociadas a ejecuciones del harness."""

from __future__ import annotations

from pathlib import Path
from typing import Any

if __package__:
    from .control_common import (
        ControlPlaneError,
        load_json,
        parse_utc_timestamp,
        utc_now,
    )
else:
    from control_common import (
        ControlPlaneError,
        load_json,
        parse_utc_timestamp,
        utc_now,
    )


def next_attempt_number(
    runs_root: Path,
    feature_id: str,
    role: str,
) -> int:
    """Calcula el siguiente intento para una combinación feature/rol."""

    previous_attempts = 0

    for run_path in runs_root.glob("RUN-*.json"):
        try:
            run = load_json(run_path)
        except Exception:
            continue

        if run.get("feature_id") == feature_id and run.get("role") == role:
            previous_attempts += 1

    return previous_attempts + 1


def initialize_run_metrics(
    *,
    runs_root: Path,
    feature_id: str,
    role: str,
    started_at: str,
) -> dict[str, Any]:
    """Crea el bloque inicial de métricas de un nuevo run."""

    attempt = next_attempt_number(
        runs_root=runs_root,
        feature_id=feature_id,
        role=role,
    )

    return {
        "attempt": attempt,
        "is_retry": attempt > 1,
        "started_at": started_at,
        "completed_at": None,
        "duration_seconds": None,
        "heartbeat_count": 0,
        "last_heartbeat_at": None,
        "result": None,
    }


def record_run_heartbeat(
    run: dict[str, Any],
    timestamp: str | None = None,
) -> None:
    """Registra un heartbeat dentro de las métricas del run."""

    heartbeat_at = timestamp or utc_now()
    metrics = run.setdefault("metrics", {})

    metrics.setdefault("attempt", 1)
    metrics.setdefault("is_retry", False)
    metrics.setdefault("started_at", run.get("started_at"))
    metrics.setdefault("completed_at", None)
    metrics.setdefault("duration_seconds", None)
    metrics.setdefault("result", None)

    metrics["heartbeat_count"] = int(metrics.get("heartbeat_count", 0)) + 1
    metrics["last_heartbeat_at"] = heartbeat_at


def finalize_run_metrics(
    run: dict[str, Any],
    *,
    result: str,
    completed_at: str | None = None,
) -> None:
    """Completa las métricas temporales y el resultado de un run."""

    completion_timestamp = completed_at or utc_now()
    metrics = run.setdefault("metrics", {})

    started_at = metrics.get("started_at") or run.get("started_at")

    if not isinstance(started_at, str):
        raise ControlPlaneError("El run no contiene un timestamp started_at válido")

    started = parse_utc_timestamp(started_at)
    completed = parse_utc_timestamp(completion_timestamp)

    if completed < started:
        raise ControlPlaneError("completed_at no puede ser anterior a started_at")

    metrics.setdefault("attempt", 1)
    metrics.setdefault("is_retry", False)
    metrics.setdefault("heartbeat_count", 0)
    metrics.setdefault("last_heartbeat_at", None)

    metrics["started_at"] = started_at
    metrics["completed_at"] = completion_timestamp
    metrics["duration_seconds"] = int((completed - started).total_seconds())
    metrics["result"] = result
