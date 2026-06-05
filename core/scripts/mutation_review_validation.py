#!/usr/bin/env python3
"""Validación determinista del informe de Mutation Reviewer."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class MutationReviewValidationError(RuntimeError):
    """Informe de Mutation Reviewer inválido."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MutationReviewValidationError(f"Falta {label}: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MutationReviewValidationError(f"JSON inválido en {path}: {exc}") from exc

    if not isinstance(content, dict):
        raise MutationReviewValidationError(f"{label} debe ser un objeto JSON: {path}")

    return content


def mutation_testing_required(feature: dict[str, Any]) -> bool:
    capabilities = feature.get("capabilities", [])
    return isinstance(capabilities, list) and "mutation-testing" in capabilities


def validate_mutation_review_evidence(
    repo_root: Path,
    feature: dict[str, Any],
) -> dict[str, Any]:
    root = repo_root.resolve()
    review_path = root / "evidence" / "mutation-reviews" / f"{feature['id']}.json"
    schema_path = root / "specs" / "schemas" / "mutation-review.schema.json"

    review = _load_json(review_path, "informe de Mutation Reviewer")
    schema = _load_json(schema_path, "esquema de Mutation Reviewer")

    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(review),
        key=lambda error: list(error.absolute_path),
    )

    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise MutationReviewValidationError(
            f"El informe de Mutation Reviewer incumple el esquema en {location}: {error.message}"
        )

    if review["feature_id"] != feature["id"]:
        raise MutationReviewValidationError(
            "El informe de Mutation Reviewer no corresponde a la feature asignada"
        )

    gaps = [
        item["mutant_id"]
        for item in review["survivor_classifications"]
        if item["classification"] == "test_gap"
    ]

    if gaps:
        raise MutationReviewValidationError(
            "Mutation Reviewer detectó test gaps: " + ", ".join(gaps)
        )

    return review
