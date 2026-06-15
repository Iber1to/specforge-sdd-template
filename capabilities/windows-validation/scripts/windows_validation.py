#!/usr/bin/env python3
"""Validación determinista de evidencias generadas en Windows."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class WindowsEvidenceValidationError(RuntimeError):
    """Evidencia Windows inválida."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise WindowsEvidenceValidationError(f"Falta {label}: {path}") from exc
    except json.JSONDecodeError as exc:
        raise WindowsEvidenceValidationError(f"JSON inválido en {path}: {exc}") from exc

    if not isinstance(content, dict):
        raise WindowsEvidenceValidationError(f"{label} debe ser un objeto JSON: {path}")

    return content


def _parse_timestamp(value: str, label: str) -> datetime:
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise WindowsEvidenceValidationError(f"Timestamp inválido en {label}: {value}") from exc

    if timestamp.tzinfo is None:
        raise WindowsEvidenceValidationError(f"El timestamp de {label} no contiene zona horaria")

    return timestamp


def default_windows_evidence_path(
    artifact_root: Path,
    feature_id: str,
) -> Path:
    return artifact_root.resolve() / "windows-tests" / feature_id / "latest.json"


def _reroot_under_canonical(value: str, base_dir: Path) -> Path:
    """Re-enraíza ``value`` por basename bajo ``base_dir``.

    Normaliza separadores POSIX (``/``) y Windows (``\\``), extrae el último
    componente como basename y exige que sea un basename simple no vacío,
    distinto de ``.`` y ``..``, sin separadores residuales, y que la ruta
    resultante quede contenida bajo ``base_dir`` resuelto. La confianza se
    ancla en ``base_dir`` (el directorio canónico de la feature) y no en la
    cadena nativa emitida por el runner. Lanza
    ``WindowsEvidenceValidationError`` en caso contrario.
    """

    normalized = value.replace("\\", "/")
    basename = normalized.rsplit("/", 1)[-1]

    if basename in ("", ".", "..") or "/" in basename or "\\" in basename:
        raise WindowsEvidenceValidationError(
            f"Ruta de evidencia Windows insegura o ambigua: {value!r}"
        )

    base_resolved = base_dir.resolve()
    candidate_resolved = (base_resolved / basename).resolve()

    if not candidate_resolved.is_relative_to(base_resolved):
        raise WindowsEvidenceValidationError(
            f"La ruta de evidencia Windows escapa del directorio canónico: {value!r}"
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
    """Valida el resultado Windows requerido para finalizar una feature."""

    root = repo_root.resolve()
    schema_path = root / "specs" / "schemas" / "windows-evidence.schema.json"

    selected_path = (
        evidence_path.resolve()
        if evidence_path is not None
        else default_windows_evidence_path(artifact_root, feature["id"])
    )

    evidence = _load_json(selected_path, "evidencia Windows")
    schema = _load_json(schema_path, "esquema de evidencia Windows")

    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(evidence),
        key=lambda error: list(error.absolute_path),
    )

    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"

        raise WindowsEvidenceValidationError(
            f"La evidencia Windows incumple el esquema en {location}: {error.message}"
        )

    if evidence["feature_id"] != feature["id"]:
        raise WindowsEvidenceValidationError(
            "La evidencia Windows no corresponde a la feature asignada: "
            f"esperado {feature['id']}, recibido {evidence['feature_id']}"
        )

    if evidence["tested_commit"] != expected_commit:
        raise WindowsEvidenceValidationError(
            "La evidencia Windows no corresponde al commit esperado: "
            f"esperado {expected_commit}, recibido {evidence['tested_commit']}"
        )

    if evidence["status"] != "PASS":
        raise WindowsEvidenceValidationError(
            f"La evidencia Windows no está aprobada: {evidence['status']}"
        )

    identifiers = [check["id"] for check in evidence["checks"]]
    expected_identifiers = [f"WIN-{index:03d}" for index in range(1, len(identifiers) + 1)]

    if identifiers != expected_identifiers:
        raise WindowsEvidenceValidationError(
            "Los checks Windows deben ser secuenciales y comenzar en WIN-001. "
            f"Esperado: {expected_identifiers}; recibido: {identifiers}"
        )

    failed_checks = [check["id"] for check in evidence["checks"] if check["status"] != "PASS"]

    if failed_checks:
        raise WindowsEvidenceValidationError(
            "Existen checks Windows fallidos: " + ", ".join(failed_checks)
        )

    started_at = _parse_timestamp(evidence["started_at"], "started_at")
    completed_at = _parse_timestamp(evidence["completed_at"], "completed_at")

    if completed_at < started_at:
        raise WindowsEvidenceValidationError("completed_at no puede ser anterior a started_at")

    canonical_dir = artifact_root.resolve() / "windows-tests" / feature["id"]

    log_path = _reroot_under_canonical(evidence["log"], canonical_dir)

    if not log_path.is_file():
        raise WindowsEvidenceValidationError(f"No existe el log Windows: {evidence['log']}")

    missing_artifacts = [
        value
        for value in evidence["artifacts"]
        if not _reroot_under_canonical(value, canonical_dir).is_file()
    ]

    if missing_artifacts:
        raise WindowsEvidenceValidationError(
            "No existen los artefactos Windows: " + ", ".join(missing_artifacts)
        )

    return evidence
