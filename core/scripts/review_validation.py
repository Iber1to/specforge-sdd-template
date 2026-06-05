#!/usr/bin/env python3
"""Validación determinista de informes QA."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class ReviewValidationError(RuntimeError):
    """Informe QA inválido."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReviewValidationError(f"Falta {label}: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReviewValidationError(f"JSON inválido en {path}: {exc}") from exc

    if not isinstance(content, dict):
        raise ReviewValidationError(f"{label} debe ser un objeto JSON: {path}")

    return content


def validate_review_evidence(
    repo_root: Path,
    feature: dict[str, Any],
    *,
    expected_verdict: str | None = None,
) -> dict[str, Any]:
    """Valida estructura, feature, veredicto y log de un informe QA."""

    root = repo_root.resolve()

    review_path = root / "evidence" / "reviews" / f"{feature['id']}.json"
    schema_path = root / "specs" / "schemas" / "review.schema.json"

    review = _load_json(review_path, "informe de revisión")
    schema = _load_json(schema_path, "esquema de revisión")

    validator = Draft202012Validator(schema)

    errors = sorted(
        validator.iter_errors(review),
        key=lambda error: list(error.absolute_path),
    )

    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"

        raise ReviewValidationError(
            f"El informe QA incumple el esquema en {location}: {error.message}"
        )

    if review["feature_id"] != feature["id"]:
        raise ReviewValidationError(
            "El informe QA no corresponde a la feature asignada: "
            f"esperado {feature['id']}, recibido {review['feature_id']}"
        )

    if expected_verdict is not None and review["verdict"] != expected_verdict:
        raise ReviewValidationError(
            f"El veredicto esperado es {expected_verdict}, "
            f"pero el informe contiene {review['verdict']}"
        )

    verification_log = Path(review["verification"]["log"]).resolve()

    if not verification_log.is_file():
        raise ReviewValidationError(f"No existe el log de verificación QA: {verification_log}")

    return review
