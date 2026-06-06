#!/usr/bin/env python3
"""Helpers compartidos para capabilities opcionales del harness."""

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
    """Error controlado para runners y validadores de capabilities."""


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
        raise CapabilityError(f"No existe la politica de capability: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CapabilityError(f"Politica JSON invalida en {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise CapabilityError(f"La politica {path} debe contener un objeto JSON")

    return data


def ensure_policy_enabled(policy: dict[str, Any], capability: str) -> None:
    if policy.get("schema_version") != 1:
        raise CapabilityError(f"{capability}: schema_version debe ser 1")

    if policy.get("enabled") is not True:
        raise CapabilityError(f"{capability}: capability deshabilitada por politica")

    if policy.get("mode") not in {"observe", "enforce"}:
        raise CapabilityError(f"{capability}: mode debe ser observe o enforce")


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
        raise CapabilityError("Evidencia incompleta: " + ", ".join(missing))

    if evidence["schema_version"] != 1:
        raise CapabilityError("schema_version debe ser 1")

    if evidence["feature_id"] != feature_id:
        raise CapabilityError(f"Evidencia no corresponde a {feature_id}")

    if evidence["gate_id"] != capability:
        raise CapabilityError(f"gate_id debe ser {capability}")

    if evidence["status"] not in CAPABILITY_STATUSES:
        raise CapabilityError(f"status invalido: {evidence['status']}")

    if not isinstance(evidence["duration_seconds"], int) or evidence["duration_seconds"] < 0:
        raise CapabilityError("duration_seconds debe ser entero no negativo")

    if not isinstance(evidence["checks"], list):
        raise CapabilityError("checks debe ser una lista")

    if not isinstance(evidence["artifacts"], list):
        raise CapabilityError("artifacts debe ser una lista")


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
        raise CapabilityError(f"No existe evidencia: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CapabilityError(f"Evidencia JSON invalida en {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise CapabilityError(f"La evidencia debe ser un objeto JSON: {path}")

    return data
