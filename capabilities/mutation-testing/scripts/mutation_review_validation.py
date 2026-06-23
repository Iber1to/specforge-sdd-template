#!/usr/bin/env python3
"""Deterministic validation of the Mutation Reviewer report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator


class MutationReviewValidationError(RuntimeError):
    """Invalid Mutation Reviewer report."""


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        content = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise MutationReviewValidationError(f"Missing {label}: {path}") from exc
    except json.JSONDecodeError as exc:
        raise MutationReviewValidationError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(content, dict):
        raise MutationReviewValidationError(f"{label} must be a JSON object: {path}")

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

    review = _load_json(review_path, "Mutation Reviewer report")
    schema = _load_json(schema_path, "Mutation Reviewer schema")

    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(review),
        key=lambda error: list(error.absolute_path),
    )

    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise MutationReviewValidationError(
            f"The Mutation Reviewer report violates the schema at {location}: {error.message}"
        )

    if review["feature_id"] != feature["id"]:
        raise MutationReviewValidationError(
            "The Mutation Reviewer report does not match the assigned feature"
        )

    gaps = [
        item["mutant_id"]
        for item in review["survivor_classifications"]
        if item["classification"] == "test_gap"
    ]

    if gaps:
        raise MutationReviewValidationError(
            "Mutation Reviewer detected test gaps: " + ", ".join(gaps)
        )

    return review


def parse_classification_arg(raw: str) -> dict[str, str]:
    """Convert 'MUT-001=classification:rationale' into a report classification.

    The rationale may contain additional ':' (only the first one is split on).
    """

    text = raw.strip()

    if "=" not in text:
        raise MutationReviewValidationError(
            f"Invalid classification (expected format MUT-XXX=class:rationale): {raw}"
        )

    mutant_id, rest = text.split("=", 1)

    if ":" not in rest:
        raise MutationReviewValidationError(f"Invalid classification (missing ':rationale'): {raw}")

    classification, rationale = rest.split(":", 1)

    return {
        "mutant_id": mutant_id.strip(),
        "classification": classification.strip(),
        "rationale": rationale.strip(),
    }


def build_mutation_review(
    *,
    feature_id: str,
    reviewer_id: str,
    mutation_evidence: str,
    classifications: list[str],
    summary: str,
    created_at: str,
) -> dict[str, Any]:
    """Build the Mutation Reviewer report from the reviewer's classifications.

    Does not validate against the schema; the caller writes the report and then uses
    validate_mutation_review_evidence to validate it deterministically.
    """

    return {
        "schema_version": 1,
        "feature_id": feature_id,
        "reviewer_id": reviewer_id,
        "mutation_evidence": mutation_evidence,
        "survivor_classifications": [parse_classification_arg(item) for item in classifications],
        "summary": summary,
        "created_at": created_at,
    }
