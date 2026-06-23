#!/usr/bin/env python3
"""Shared helpers for optional harness capabilities."""

from __future__ import annotations

import json
import shutil
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from control_common import ControlPlaneError, atomic_write_json, load_project_config, repo_root

CAPABILITY_STATUSES = {"PASSED", "FAILED", "BLOCKED", "SKIPPED"}


class CapabilityError(ControlPlaneError):
    """Controlled error for capability runners and validators."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def operation_id(prefix: str) -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{prefix}-{timestamp}-{uuid.uuid4().hex[:8]}"


def monotonic_seconds() -> float:
    return time.monotonic()


def duration_seconds(started: float) -> int:
    return max(0, int(round(time.monotonic() - started)))


def artifact_root() -> Path:
    config = load_project_config()
    return Path(config["artifact_root"]).expanduser().resolve()


def capability_policy(capability: str) -> dict[str, Any]:
    path = repo_root() / "state" / "capabilities" / f"{capability}.json"

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CapabilityError(f"Capability policy does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CapabilityError(f"Invalid JSON policy in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise CapabilityError(f"Policy {path} must contain a JSON object")

    return data


def ensure_policy_enabled(policy: dict[str, Any], capability: str) -> None:
    if policy.get("schema_version") != 1:
        raise CapabilityError(f"{capability}: schema_version must be 1")

    if policy.get("enabled") is not True:
        raise CapabilityError(f"{capability}: capability disabled by policy")

    if policy.get("mode") not in {"observe", "enforce"}:
        raise CapabilityError(f"{capability}: mode must be observe or enforce")


def validate_capability_evidence(
    evidence: dict[str, Any], capability: str, feature_id: str
) -> None:
    required = {
        "schema_version",
        "feature_id",
        "gate_id",
        "status",
        "started_at",
        "completed_at",
        "duration_seconds",
        "scope",
        "summary",
        "checks",
        "artifacts",
    }
    missing = sorted(required - set(evidence))

    if missing:
        raise CapabilityError("Incomplete evidence: " + ", ".join(missing))

    if evidence["schema_version"] != 1:
        raise CapabilityError("schema_version must be 1")

    if evidence["feature_id"] != feature_id:
        raise CapabilityError(f"Evidence does not correspond to {feature_id}")

    if evidence["gate_id"] != capability:
        raise CapabilityError(f"gate_id must be {capability}")

    if evidence["status"] not in CAPABILITY_STATUSES:
        raise CapabilityError(f"invalid status: {evidence['status']}")

    if not isinstance(evidence["duration_seconds"], int) or evidence["duration_seconds"] < 0:
        raise CapabilityError("duration_seconds must be a non-negative integer")

    if not isinstance(evidence["checks"], list):
        raise CapabilityError("checks must be a list")

    if not isinstance(evidence["artifacts"], list):
        raise CapabilityError("artifacts must be a list")


def write_capability_evidence(
    *,
    capability: str,
    feature_id: str,
    operation: str,
    evidence: dict[str, Any],
) -> Path:
    validate_capability_evidence(evidence, capability, feature_id)

    output_root = artifact_root() / "capabilities" / capability / feature_id
    output_root.mkdir(parents=True, exist_ok=True)

    evidence_path = output_root / f"{operation}.json"
    latest_path = output_root / "latest.json"

    atomic_write_json(evidence_path, evidence)
    shutil.copy2(evidence_path, latest_path)

    return evidence_path


def load_evidence(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CapabilityError(f"Evidence does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CapabilityError(f"Invalid JSON evidence in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise CapabilityError(f"Evidence must be a JSON object: {path}")

    return data
