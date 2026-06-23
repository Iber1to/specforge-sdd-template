#!/usr/bin/env python3
"""Deterministic operations on the lifecycle phase."""

from __future__ import annotations

from typing import Any

if __package__:
    from .control_common import ControlPlaneError, utc_now
else:
    from control_common import ControlPlaneError, utc_now

TRANSITIONS = {
    "BOOTSTRAP": {"ACTIVE_DEVELOPMENT"},
    "ACTIVE_DEVELOPMENT": set(),
}


def current_lifecycle_phase(
    project: dict[str, Any],
    runtime: dict[str, Any],
) -> str:
    """Return the current operational phase."""

    return str(
        runtime.get(
            "lifecycle_phase",
            project.get("lifecycle_phase", "BOOTSTRAP"),
        )
    )


def apply_lifecycle_transition(
    *,
    project: dict[str, Any],
    queue: dict[str, Any],
    runtime: dict[str, Any],
    target_phase: str,
    actor: str,
    reason: str,
) -> bool:
    """Apply a valid transition. Returns False when it is already applied."""

    current_phase = current_lifecycle_phase(project, runtime)

    if current_phase == target_phase:
        return False

    allowed_targets = TRANSITIONS.get(current_phase)

    if allowed_targets is None or target_phase not in allowed_targets:
        raise ControlPlaneError(
            f"Lifecycle transition not allowed: {current_phase} -> {target_phase}"
        )

    if target_phase == "ACTIVE_DEVELOPMENT":
        completed_features = [
            feature for feature in queue.get("features", []) if feature.get("state") == "DONE"
        ]

        if not completed_features:
            raise ControlPlaneError("ACTIVE_DEVELOPMENT requires at least one DONE feature")

    timestamp = utc_now()

    runtime["lifecycle_phase"] = target_phase
    runtime.setdefault("lifecycle_history", []).append(
        {
            "timestamp": timestamp,
            "actor": actor,
            "from": current_phase,
            "to": target_phase,
            "reason": reason,
        }
    )

    return True
