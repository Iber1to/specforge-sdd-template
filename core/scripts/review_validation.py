#!/usr/bin/env python3
"""Deterministic validation of QA reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class ReviewValidationError(RuntimeError):
    """Invalid QA report."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ReviewValidationError(f"Missing {label}: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ReviewValidationError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(content, dict):
        raise ReviewValidationError(f"{label} must be a JSON object: {path}")

    return content


def validate_review_evidence(
    repo_root: Path,
    feature: dict[str, Any],
    *,
    expected_verdict: str | None = None,
) -> dict[str, Any]:
    """Validates the structure, feature, verdict and log of a QA report."""

    root = repo_root.resolve()

    review_path = root / "evidence" / "reviews" / f"{feature['id']}.json"
    schema_path = root / "specs" / "schemas" / "review.schema.json"

    review = _load_json(review_path, "review report")
    schema = _load_json(schema_path, "review schema")

    validator = Draft202012Validator(schema)

    errors = sorted(
        validator.iter_errors(review),
        key=lambda error: list(error.absolute_path),
    )

    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"

        raise ReviewValidationError(
            f"The QA report violates the schema at {location}: {error.message}"
        )

    if review["feature_id"] != feature["id"]:
        raise ReviewValidationError(
            "The QA report does not match the assigned feature: "
            f"expected {feature['id']}, received {review['feature_id']}"
        )

    if expected_verdict is not None and review["verdict"] != expected_verdict:
        raise ReviewValidationError(
            f"The expected verdict is {expected_verdict}, "
            f"but the report contains {review['verdict']}"
        )

    verification_log = Path(review["verification"]["log"]).resolve()

    if not verification_log.is_file():
        raise ReviewValidationError(f"The QA verification log does not exist: {verification_log}")

    return review
