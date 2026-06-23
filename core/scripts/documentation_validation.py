#!/usr/bin/env python3
"""Documentation validation declared by acceptance.yaml."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from feature_validation import FeatureValidationError, load_and_validate_acceptance


class DocumentationValidationError(RuntimeError):
    """Controlled documentation validation error."""


REQUIREMENTS = {
    "requires_adr": {
        "label": "ADR",
        "prefix": "docs/10-architecture/adr/",
    },
    "requires_runtime_update": {
        "label": "runtime documentation",
        "prefix": "docs/20-runtime/",
    },
    "requires_operations_update": {
        "label": "operations documentation",
        "prefix": "docs/40-operations/",
    },
    "requires_quality_update": {
        "label": "quality documentation",
        "prefix": "docs/30-quality/",
    },
}


def _normalise_path(value: str) -> str:
    return value.replace("\\", "/").lstrip("./")


def _matches_requirement(path: str, prefix: str) -> bool:
    normalised = _normalise_path(path)

    if not normalised.startswith(prefix):
        return False

    return normalised.endswith(".md")


def _documentation_block(acceptance: dict[str, Any]) -> dict[str, bool]:
    raw = acceptance.get("documentation", {})

    if raw is None:
        return {}

    if not isinstance(raw, dict):
        raise DocumentationValidationError("documentation must be an object")

    return {key: bool(raw.get(key, False)) for key in REQUIREMENTS}


def validate_documentation_requirements(
    repo_root: Path,
    feature: dict[str, Any],
    *,
    changed_files: list[str],
) -> dict[str, Any]:
    """Validate that the reviewed changes cover the declared documentation."""

    if not feature.get("spec_path"):
        return {
            "required": False,
            "requirements": {},
            "matched": [],
        }

    try:
        acceptance = load_and_validate_acceptance(repo_root, feature)
    except FeatureValidationError as exc:
        raise DocumentationValidationError(str(exc)) from exc

    requirements = _documentation_block(acceptance)

    if not any(requirements.values()):
        return {
            "required": False,
            "requirements": requirements,
            "matched": [],
        }

    normalised_files = [_normalise_path(path) for path in changed_files]
    matched: list[str] = []
    missing: list[str] = []

    for key, required in requirements.items():
        if not required:
            continue

        rule = REQUIREMENTS[key]
        prefix = str(rule["prefix"])
        matches = [path for path in normalised_files if _matches_requirement(path, prefix)]

        if matches:
            matched.extend(matches)
        else:
            missing.append(str(rule["label"]))

    if missing:
        raise DocumentationValidationError(
            "Missing required documentation changes: " + ", ".join(missing)
        )

    return {
        "required": True,
        "requirements": requirements,
        "matched": sorted(set(matched)),
    }
