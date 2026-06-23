#!/usr/bin/env python3
"""Deterministic validators for Spec Driven Development documents."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

SPECIFICATION_SECTIONS = (
    "Problem",
    "Goal",
    "Scope",
    "Out of Scope",
    "User Scenarios",
    "Functional Requirements",
    "Non-Functional Requirements",
    "Assumptions",
    "Acceptance Summary",
    "Open Questions",
)

ARCHITECTURE_SECTIONS = (
    "Context",
    "Decision",
    "Components",
    "Interfaces",
    "Data Flow",
    "Data Model",
    "Performance Considerations",
    "Failure Modes",
    "Windows Runtime Impact",
    "Open Questions",
)

ARCHITECTURE_V2_SECTIONS = (
    "Specification Review",
    *ARCHITECTURE_SECTIONS,
)

IMPLEMENTATION_PLAN_SECTIONS = (
    "Strategy",
    "Work Breakdown",
    "Files Expected to Change",
    "Dependencies",
    "Risks",
    "Rollback",
)

TEST_PLAN_SECTIONS = (
    "Test Strategy",
    "Acceptance Traceability",
    "Unit Tests",
    "Integration Tests",
    "Windows E2E Tests",
    "Performance Tests",
    "Exit Criteria",
)

ACCEPTANCE_ID_PATTERN = re.compile(r"AC-\d{3,}")
REQUIRED_PLACEHOLDER = "<!-- REQUIRED:"


class FeatureValidationError(RuntimeError):
    """Invalid feature document."""


def _load_specification_policy(
    repo_root: Path,
) -> dict[str, Any]:
    """Load and validate the declarative Spec Partner policy."""

    policy_path = repo_root.resolve() / "state" / "specification-policy.json"

    if not policy_path.is_file():
        return {
            "default_acceptance_schema_version": 1,
            "legacy_v1_features": [],
        }

    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FeatureValidationError(f"Invalid specification policy JSON: {exc}") from exc

    if not isinstance(policy, dict):
        raise FeatureValidationError("The specification policy must be a JSON object")

    default_version = policy.get(
        "default_acceptance_schema_version",
        1,
    )
    legacy_features = policy.get("legacy_v1_features", [])

    if not isinstance(default_version, int) or default_version < 1:
        raise FeatureValidationError("default_acceptance_schema_version must be a positive integer")

    if not isinstance(legacy_features, list) or not all(
        isinstance(feature_id, str) for feature_id in legacy_features
    ):
        raise FeatureValidationError("legacy_v1_features must be a list of strings")

    return policy


def _resolve_spec_root(repo_root: Path, feature: dict[str, Any]) -> Path:
    root = repo_root.resolve()
    spec_root = (root / feature["spec_path"]).resolve()

    if root not in spec_root.parents:
        raise FeatureValidationError(
            f"The specification path falls outside the repository: {spec_root}"
        )

    return spec_root


def _read_nonempty_text(path: Path, label: str) -> str:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FeatureValidationError(f"Missing {label}: {path}") from exc

    if not content.strip():
        raise FeatureValidationError(f"{label} is empty: {path}")

    return content


def _visible_content(value: str) -> str:
    return re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL).strip()


def _extract_sections(content: str, path: Path) -> dict[str, str]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", content, flags=re.MULTILINE))
    sections: dict[str, str] = {}

    for index, match in enumerate(matches):
        name = match.group(1).strip()

        if name in sections:
            raise FeatureValidationError(f"Duplicate section '{name}' in {path}")

        body_start = match.end()
        body_end = matches[index + 1].start() if index + 1 < len(matches) else len(content)
        sections[name] = content[body_start:body_end]

    return sections


def validate_markdown_document(
    path: Path,
    label: str,
    required_sections: tuple[str, ...],
) -> dict[str, str]:
    content = _read_nonempty_text(path, label)

    if REQUIRED_PLACEHOLDER in content:
        raise FeatureValidationError(f"{label} still has unresolved REQUIRED markers: {path}")

    if not re.search(r"^#\s+\S", content, flags=re.MULTILINE):
        raise FeatureValidationError(f"{label} does not contain an H1 title: {path}")

    sections = _extract_sections(content, path)
    missing = [section for section in required_sections if section not in sections]

    if missing:
        raise FeatureValidationError(
            f"{label} does not contain the required sections: {', '.join(missing)}"
        )

    empty = [section for section in required_sections if not _visible_content(sections[section])]

    if empty:
        raise FeatureValidationError(f"{label} contains empty sections: {', '.join(empty)}")

    return sections


def _validate_sequential_identifiers(
    items: list[dict[str, Any]],
    *,
    prefix: str,
    label: str,
) -> None:
    """Validate sequential identifiers starting at PREFIX-001."""

    identifiers = [item["id"] for item in items]
    expected = [f"{prefix}-{index:03d}" for index in range(1, len(items) + 1)]

    if identifiers != expected:
        raise FeatureValidationError(
            f"The {label} identifiers must be sequential "
            f"and start at {prefix}-001. "
            f"Expected: {expected}; received: {identifiers}"
        )


def _validate_acceptance_v2(acceptance: dict[str, Any]) -> None:
    """Validate additional semantic rules of the v2 contract."""

    specification = acceptance["specification"]

    _validate_sequential_identifiers(
        specification["assumptions"],
        prefix="ASM",
        label="assumptions",
    )
    _validate_sequential_identifiers(
        specification["decisions"],
        prefix="DEC",
        label="decisions",
    )
    _validate_sequential_identifiers(
        specification["open_questions"],
        prefix="Q",
        label="open questions",
    )
    _validate_sequential_identifiers(
        acceptance["scenarios"],
        prefix="SCN",
        label="scenarios",
    )

    blocking_questions = [
        question["id"]
        for question in specification["open_questions"]
        if question["blocking"] is True
    ]

    if blocking_questions:
        raise FeatureValidationError(
            "The specification still has blocking critical questions: "
            + ", ".join(blocking_questions)
        )

    criteria = acceptance["criteria"]
    criterion_ids = {criterion["id"] for criterion in criteria}

    scenario_references = {
        criterion_id
        for scenario in acceptance["scenarios"]
        for criterion_id in scenario["criteria"]
    }

    unknown_references = sorted(scenario_references - criterion_ids)

    if unknown_references:
        raise FeatureValidationError(
            "The scenarios reference nonexistent criteria: " + ", ".join(unknown_references)
        )

    required_criteria = {criterion["id"] for criterion in criteria if criterion["required"] is True}

    uncovered_required = sorted(required_criteria - scenario_references)

    if uncovered_required:
        raise FeatureValidationError(
            "The required criteria are not covered by scenarios: " + ", ".join(uncovered_required)
        )


def load_and_validate_acceptance(
    repo_root: Path,
    feature: dict[str, Any],
) -> dict[str, Any]:
    spec_root = _resolve_spec_root(repo_root, feature)
    acceptance_path = spec_root / "acceptance.yaml"

    acceptance_text = _read_nonempty_text(
        acceptance_path,
        "acceptance criteria",
    )

    try:
        acceptance = yaml.safe_load(acceptance_text)
    except yaml.YAMLError as exc:
        raise FeatureValidationError(f"Invalid YAML in {acceptance_path}: {exc}") from exc

    if not isinstance(acceptance, dict):
        raise FeatureValidationError(
            f"acceptance.yaml must contain a YAML object: {acceptance_path}"
        )

    schema_version = acceptance.get("schema_version")

    specification_policy = _load_specification_policy(repo_root)

    default_schema_version = specification_policy.get(
        "default_acceptance_schema_version",
        1,
    )
    legacy_v1_features = specification_policy.get(
        "legacy_v1_features",
        [],
    )

    if (
        schema_version == 1
        and default_schema_version >= 2
        and feature["id"] not in legacy_v1_features
    ):
        raise FeatureValidationError(
            f"{feature['id']} requires acceptance.yaml schema_version 2. "
            "The v1 contract is only allowed for historical features "
            "declared explicitly."
        )

    if schema_version == 1:
        schema_filename = "acceptance.schema.json"
    elif schema_version == 2:
        schema_filename = "acceptance-v2.schema.json"
    else:
        raise FeatureValidationError(
            f"acceptance.yaml contains an unsupported schema_version: {schema_version!r}"
        )

    schema_path = repo_root / "specs" / "schemas" / schema_filename

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FeatureValidationError(
            f"The acceptance schema does not exist: {schema_path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise FeatureValidationError(f"Invalid JSON schema in {schema_path}: {exc}") from exc

    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(acceptance),
        key=lambda error: list(error.absolute_path),
    )

    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"

        raise FeatureValidationError(
            f"acceptance.yaml violates the schema at {location}: {error.message}"
        )

    if acceptance["feature_id"] != feature["id"]:
        raise FeatureValidationError(
            "acceptance.yaml does not correspond to the assigned feature: "
            f"expected {feature['id']}, received {acceptance['feature_id']}"
        )

    if acceptance["title"] != feature["title"]:
        raise FeatureValidationError("The acceptance.yaml title must match the queue exactly")

    criteria = acceptance["criteria"]

    _validate_sequential_identifiers(
        criteria,
        prefix="AC",
        label="criteria",
    )

    for criterion in criteria:
        if len(criterion["statement"].strip()) < 10:
            raise FeatureValidationError(
                f"{criterion['id']} does not contain a verifiable statement"
            )

    if schema_version == 2:
        _validate_acceptance_v2(acceptance)

    return acceptance


def validate_specification(
    repo_root: Path,
    feature: dict[str, Any],
) -> dict[str, Any]:
    spec_root = _resolve_spec_root(repo_root, feature)

    validate_markdown_document(
        spec_root / "specification.md",
        "specification",
        SPECIFICATION_SECTIONS,
    )

    return load_and_validate_acceptance(repo_root, feature)


def validate_architecture(
    repo_root: Path,
    feature: dict[str, Any],
) -> dict[str, Any]:
    acceptance = validate_specification(repo_root, feature)
    spec_root = _resolve_spec_root(repo_root, feature)

    required_sections = (
        ARCHITECTURE_V2_SECTIONS if acceptance["schema_version"] == 2 else ARCHITECTURE_SECTIONS
    )

    validate_markdown_document(
        spec_root / "architecture.md",
        "architecture",
        required_sections,
    )

    return acceptance


def validate_development_readiness(
    repo_root: Path,
    feature: dict[str, Any],
) -> dict[str, Any]:
    acceptance = validate_architecture(repo_root, feature)
    spec_root = _resolve_spec_root(repo_root, feature)

    validate_markdown_document(
        spec_root / "implementation-plan.md",
        "implementation plan",
        IMPLEMENTATION_PLAN_SECTIONS,
    )

    test_sections = validate_markdown_document(
        spec_root / "test-plan.md",
        "test plan",
        TEST_PLAN_SECTIONS,
    )

    criterion_ids = {criterion["id"] for criterion in acceptance["criteria"]}

    traceability_references = set(
        ACCEPTANCE_ID_PATTERN.findall(test_sections["Acceptance Traceability"])
    )

    missing = sorted(criterion_ids - traceability_references)
    unknown = sorted(traceability_references - criterion_ids)

    if missing:
        raise FeatureValidationError(
            "The test plan does not trace the criteria: " + ", ".join(missing)
        )

    if unknown:
        raise FeatureValidationError(
            "The test plan references nonexistent criteria: " + ", ".join(unknown)
        )

    if feature.get("windows_validation_required", False):
        windows_criteria = [
            criterion
            for criterion in acceptance["criteria"]
            if criterion["verification"] == "windows_e2e"
        ]

        if not windows_criteria:
            raise FeatureValidationError(
                "The feature requires Windows validation, but no criterion "
                "uses verification: windows_e2e"
            )

    return acceptance
