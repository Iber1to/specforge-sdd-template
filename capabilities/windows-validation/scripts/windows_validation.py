#!/usr/bin/env python3
"""Deterministic validation of evidence generated on Windows."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class WindowsEvidenceValidationError(RuntimeError):
    """Invalid Windows evidence."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WindowsEvidenceValidationError(f"Missing {label}: {path}") from exc
    except json.JSONDecodeError as exc:
        raise WindowsEvidenceValidationError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(content, dict):
        raise WindowsEvidenceValidationError(f"{label} must be a JSON object: {path}")

    return content


def _parse_timestamp(value: str, label: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise WindowsEvidenceValidationError(f"Invalid timestamp in {label}: {value}") from exc

    if timestamp.tzinfo is None:
        raise WindowsEvidenceValidationError(f"The {label} timestamp does not include a timezone")

    return timestamp


def default_windows_evidence_path(
    artifact_root: Path,
    feature_id: str,
) -> Path:
    return artifact_root.resolve() / "windows-tests" / feature_id / "latest.json"


def _reroot_under_canonical(value: str, base_dir: Path) -> Path:
    """Re-root ``value`` by basename under ``base_dir``.

    Normalizes POSIX (``/``) and Windows (``\\``) separators, extracts the last
    component as the basename and requires it to be a simple non-empty basename,
    distinct from ``.`` and ``..``, without residual separators, and that the
    resulting path stays contained under the resolved ``base_dir``. Trust is
    anchored in ``base_dir`` (the canonical directory of the feature) and not in
    the native string emitted by the runner. Raises
    ``WindowsEvidenceValidationError`` otherwise.
    """

    normalized = value.replace("\\", "/")
    basename = normalized.rsplit("/", 1)[-1]

    if basename in ("", ".", "..") or "/" in basename or "\\" in basename:
        raise WindowsEvidenceValidationError(
            f"Unsafe or ambiguous Windows evidence path: {value!r}"
        )

    base_resolved = base_dir.resolve()
    candidate_resolved = (base_resolved / basename).resolve()

    if not candidate_resolved.is_relative_to(base_resolved):
        raise WindowsEvidenceValidationError(
            f"The Windows evidence path escapes the canonical directory: {value!r}"
        )

    return candidate_resolved


def validate_windows_evidence(
    *,
    repo_root: Path,
    artifact_root: Path,
    feature: dict[str, Any],
    expected_commit: str,
    evidence_path: Path | None = None,
) -> dict[str, Any]:
    """Validate the Windows result required to finalize a feature."""

    root = repo_root.resolve()
    schema_path = root / "specs" / "schemas" / "windows-evidence.schema.json"

    selected_path = (
        evidence_path.resolve()
        if evidence_path is not None
        else default_windows_evidence_path(artifact_root, feature["id"])
    )

    evidence = _load_json(selected_path, "Windows evidence")
    schema = _load_json(schema_path, "Windows evidence schema")

    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(evidence),
        key=lambda error: list(error.absolute_path),
    )

    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"

        raise WindowsEvidenceValidationError(
            f"The Windows evidence violates the schema at {location}: {error.message}"
        )

    if evidence["feature_id"] != feature["id"]:
        raise WindowsEvidenceValidationError(
            "The Windows evidence does not correspond to the assigned feature: "
            f"expected {feature['id']}, received {evidence['feature_id']}"
        )

    if evidence["tested_commit"] != expected_commit:
        raise WindowsEvidenceValidationError(
            "The Windows evidence does not correspond to the expected commit: "
            f"expected {expected_commit}, received {evidence['tested_commit']}"
        )

    if evidence["status"] != "PASS":
        raise WindowsEvidenceValidationError(
            f"The Windows evidence is not approved: {evidence['status']}"
        )

    identifiers = [check["id"] for check in evidence["checks"]]
    expected_identifiers = [f"WIN-{index:03d}" for index in range(1, len(identifiers) + 1)]

    if identifiers != expected_identifiers:
        raise WindowsEvidenceValidationError(
            "The Windows checks must be sequential and start at WIN-001. "
            f"Expected: {expected_identifiers}; received: {identifiers}"
        )

    failed_checks = [check["id"] for check in evidence["checks"] if check["status"] != "PASS"]

    if failed_checks:
        raise WindowsEvidenceValidationError(
            "There are failed Windows checks: " + ", ".join(failed_checks)
        )

    started_at = _parse_timestamp(evidence["started_at"], "started_at")
    completed_at = _parse_timestamp(evidence["completed_at"], "completed_at")

    if completed_at < started_at:
        raise WindowsEvidenceValidationError("completed_at cannot be earlier than started_at")

    canonical_dir = artifact_root.resolve() / "windows-tests" / feature["id"]

    log_path = _reroot_under_canonical(evidence["log"], canonical_dir)

    if not log_path.is_file():
        raise WindowsEvidenceValidationError(f"The Windows log does not exist: {evidence['log']}")

    missing_artifacts = [
        value
        for value in evidence["artifacts"]
        if not _reroot_under_canonical(value, canonical_dir).is_file()
    ]

    if missing_artifacts:
        raise WindowsEvidenceValidationError(
            "The Windows artifacts do not exist: " + ", ".join(missing_artifacts)
        )

    return evidence
