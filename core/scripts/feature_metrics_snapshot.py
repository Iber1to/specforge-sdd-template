#!/usr/bin/env python3
"""Snapshots regenerables de métricas agregadas por feature."""

from __future__ import annotations

from pathlib import Path
from typing import Any

if __package__:
    from .control_common import atomic_write_json
    from .metrics_common import aggregate_metrics, empty_scope
else:
    from control_common import atomic_write_json
    from metrics_common import aggregate_metrics, empty_scope


SNAPSHOT_FILENAME = "feature-metrics.json"


def snapshot_path(control_root: Path) -> Path:
    """Devuelve la ruta canónica del snapshot derivado."""

    return control_root.resolve() / SNAPSHOT_FILENAME


def build_feature_metrics_snapshot(
    *,
    queue: dict[str, Any],
    metrics_summary: dict[str, Any],
) -> dict[str, Any]:
    """Construye un snapshot para todas las features registradas."""

    features: dict[str, Any] = {}
    aggregated_features = metrics_summary.get("features", {})

    if not isinstance(aggregated_features, dict):
        aggregated_features = {}

    for feature in queue.get("features", []):
        if not isinstance(feature, dict):
            continue

        feature_id = feature.get("id")

        if not isinstance(feature_id, str) or not feature_id:
            continue

        feature_metrics = aggregated_features.get(feature_id)

        if not isinstance(feature_metrics, dict):
            feature_metrics = empty_scope()

        features[feature_id] = {
            "feature_id": feature_id,
            "title": feature.get("title"),
            "state_at_generation": feature.get("state"),
            "priority": feature.get("priority"),
            "windows_validation_required": bool(feature.get("windows_validation_required", False)),
            "metrics": feature_metrics,
        }

    return {
        "schema_version": 1,
        "authoritative": False,
        "description": (
            "Snapshot derivado y regenerable. No debe utilizarse como fuente de verdad."
        ),
        "generated_at": metrics_summary.get("generated_at"),
        "sources": {
            "queue": "queue.json",
            "runs": "runs/*.json",
            "agent_metrics": "agent-metrics/*.json",
        },
        "project_metrics": metrics_summary.get(
            "project",
            empty_scope(),
        ),
        "invalid_records": metrics_summary.get(
            "invalid_records",
            {
                "agent_metrics": 0,
                "runs": 0,
            },
        ),
        "features": dict(sorted(features.items())),
    }


def refresh_feature_metrics_snapshot(
    *,
    control_root: Path,
    queue: dict[str, Any],
) -> dict[str, Any]:
    """Regenera y guarda atómicamente el snapshot del plano de control."""

    root = control_root.resolve()
    metrics_summary = aggregate_metrics(root)

    snapshot = build_feature_metrics_snapshot(
        queue=queue,
        metrics_summary=metrics_summary,
    )

    atomic_write_json(snapshot_path(root), snapshot)

    return snapshot
