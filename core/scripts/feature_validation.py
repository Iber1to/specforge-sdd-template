#!/usr/bin/env python3
"""Validadores deterministas de documentos Spec Driven Development."""

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
    """Documento de feature inválido."""


def _load_specification_policy(
    repo_root: Path,
) -> dict[str, Any]:
    """Carga y valida la política declarativa del Spec Partner."""

    policy_path = repo_root.resolve() / "state" / "specification-policy.json"

    if not policy_path.is_file():
        return {
            "default_acceptance_schema_version": 1,
            "legacy_v1_features": [],
        }

    try:
        policy = json.loads(policy_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise FeatureValidationError(f"Política de especificación JSON inválida: {exc}") from exc

    if not isinstance(policy, dict):
        raise FeatureValidationError("La política de especificación debe ser un objeto JSON")

    default_version = policy.get(
        "default_acceptance_schema_version",
        1,
    )
    legacy_features = policy.get("legacy_v1_features", [])

    if not isinstance(default_version, int) or default_version < 1:
        raise FeatureValidationError(
            "default_acceptance_schema_version debe ser un entero positivo"
        )

    if not isinstance(legacy_features, list) or not all(
        isinstance(feature_id, str) for feature_id in legacy_features
    ):
        raise FeatureValidationError("legacy_v1_features debe ser una lista de strings")

    return policy


def _resolve_spec_root(repo_root: Path, feature: dict[str, Any]) -> Path:
    root = repo_root.resolve()
    spec_root = (root / feature["spec_path"]).resolve()

    if root not in spec_root.parents:
        raise FeatureValidationError(
            f"La ruta de especificación queda fuera del repositorio: {spec_root}"
        )

    return spec_root


def _read_nonempty_text(path: Path, label: str) -> str:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FeatureValidationError(f"Falta {label}: {path}") from exc

    if not content.strip():
        raise FeatureValidationError(f"{label} está vacío: {path}")

    return content


def _visible_content(value: str) -> str:
    return re.sub(r"<!--.*?-->", "", value, flags=re.DOTALL).strip()


def _extract_sections(content: str, path: Path) -> dict[str, str]:
    matches = list(re.finditer(r"^##\s+(.+?)\s*$", content, flags=re.MULTILINE))
    sections: dict[str, str] = {}

    for index, match in enumerate(matches):
        name = match.group(1).strip()

        if name in sections:
            raise FeatureValidationError(f"Sección duplicada '{name}' en {path}")

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
        raise FeatureValidationError(f"{label} conserva marcadores REQUIRED sin resolver: {path}")

    if not re.search(r"^#\s+\S", content, flags=re.MULTILINE):
        raise FeatureValidationError(f"{label} no contiene un título H1: {path}")

    sections = _extract_sections(content, path)
    missing = [section for section in required_sections if section not in sections]

    if missing:
        raise FeatureValidationError(
            f"{label} no contiene las secciones obligatorias: {', '.join(missing)}"
        )

    empty = [section for section in required_sections if not _visible_content(sections[section])]

    if empty:
        raise FeatureValidationError(f"{label} contiene secciones vacías: {', '.join(empty)}")

    return sections


def _validate_sequential_identifiers(
    items: list[dict[str, Any]],
    *,
    prefix: str,
    label: str,
) -> None:
    """Valida identificadores secuenciales comenzando en PREFIX-001."""

    identifiers = [item["id"] for item in items]
    expected = [f"{prefix}-{index:03d}" for index in range(1, len(items) + 1)]

    if identifiers != expected:
        raise FeatureValidationError(
            f"Los identificadores de {label} deben ser secuenciales "
            f"y comenzar en {prefix}-001. "
            f"Esperado: {expected}; recibido: {identifiers}"
        )


def _validate_acceptance_v2(acceptance: dict[str, Any]) -> None:
    """Valida reglas semánticas adicionales del contrato v2."""

    specification = acceptance["specification"]

    _validate_sequential_identifiers(
        specification["assumptions"],
        prefix="ASM",
        label="hipótesis",
    )
    _validate_sequential_identifiers(
        specification["decisions"],
        prefix="DEC",
        label="decisiones",
    )
    _validate_sequential_identifiers(
        specification["open_questions"],
        prefix="Q",
        label="preguntas abiertas",
    )
    _validate_sequential_identifiers(
        acceptance["scenarios"],
        prefix="SCN",
        label="escenarios",
    )

    blocking_questions = [
        question["id"]
        for question in specification["open_questions"]
        if question["blocking"] is True
    ]

    if blocking_questions:
        raise FeatureValidationError(
            "La especificación conserva preguntas críticas bloqueantes: "
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
            "Los escenarios referencian criterios inexistentes: " + ", ".join(unknown_references)
        )

    required_criteria = {criterion["id"] for criterion in criteria if criterion["required"] is True}

    uncovered_required = sorted(required_criteria - scenario_references)

    if uncovered_required:
        raise FeatureValidationError(
            "Los criterios obligatorios no están cubiertos por escenarios: "
            + ", ".join(uncovered_required)
        )


def load_and_validate_acceptance(
    repo_root: Path,
    feature: dict[str, Any],
) -> dict[str, Any]:
    spec_root = _resolve_spec_root(repo_root, feature)
    acceptance_path = spec_root / "acceptance.yaml"

    acceptance_text = _read_nonempty_text(
        acceptance_path,
        "criterios de aceptación",
    )

    try:
        acceptance = yaml.safe_load(acceptance_text)
    except yaml.YAMLError as exc:
        raise FeatureValidationError(f"YAML inválido en {acceptance_path}: {exc}") from exc

    if not isinstance(acceptance, dict):
        raise FeatureValidationError(
            f"acceptance.yaml debe contener un objeto YAML: {acceptance_path}"
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
            f"{feature['id']} requiere acceptance.yaml schema_version 2. "
            "El contrato v1 solo está permitido para features históricas "
            "declaradas explícitamente."
        )

    if schema_version == 1:
        schema_filename = "acceptance.schema.json"
    elif schema_version == 2:
        schema_filename = "acceptance-v2.schema.json"
    else:
        raise FeatureValidationError(
            f"acceptance.yaml contiene una schema_version no soportada: {schema_version!r}"
        )

    schema_path = repo_root / "specs" / "schemas" / schema_filename

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FeatureValidationError(f"No existe el esquema de aceptación: {schema_path}") from exc
    except json.JSONDecodeError as exc:
        raise FeatureValidationError(f"Esquema JSON inválido en {schema_path}: {exc}") from exc

    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(acceptance),
        key=lambda error: list(error.absolute_path),
    )

    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"

        raise FeatureValidationError(
            f"acceptance.yaml incumple el esquema en {location}: {error.message}"
        )

    if acceptance["feature_id"] != feature["id"]:
        raise FeatureValidationError(
            "acceptance.yaml no corresponde a la feature asignada: "
            f"esperado {feature['id']}, recibido {acceptance['feature_id']}"
        )

    if acceptance["title"] != feature["title"]:
        raise FeatureValidationError(
            "El título de acceptance.yaml debe coincidir exactamente con la cola"
        )

    criteria = acceptance["criteria"]

    _validate_sequential_identifiers(
        criteria,
        prefix="AC",
        label="criterios",
    )

    for criterion in criteria:
        if len(criterion["statement"].strip()) < 10:
            raise FeatureValidationError(
                f"{criterion['id']} no contiene una declaración verificable"
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
        "especificación",
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
        "arquitectura",
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
        "plan de implementación",
        IMPLEMENTATION_PLAN_SECTIONS,
    )

    test_sections = validate_markdown_document(
        spec_root / "test-plan.md",
        "plan de pruebas",
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
            "El plan de pruebas no traza los criterios: " + ", ".join(missing)
        )

    if unknown:
        raise FeatureValidationError(
            "El plan de pruebas referencia criterios inexistentes: " + ", ".join(unknown)
        )

    if feature.get("windows_validation_required", False):
        windows_criteria = [
            criterion
            for criterion in acceptance["criteria"]
            if criterion["verification"] == "windows_e2e"
        ]

        if not windows_criteria:
            raise FeatureValidationError(
                "La feature requiere validación Windows, pero ningún criterio "
                "utiliza verification: windows_e2e"
            )

    return acceptance
