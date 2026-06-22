#!/usr/bin/env python3
"""Deterministic project generator for the Agentic SDD template."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PROFILES = {"generic", "python", "node", "android"}
CAPABILITIES = {
    "documentation-pack",
    "eval-harness",
    "external-runtime",
    "git-publish",
    "mutation-testing",
    "performance-testing",
    "remote-notifications",
    "security-scanning",
    "tool-telemetry",
    "windows-validation",
}
DEFAULT_CAPABILITIES = {"documentation-pack"}
GIT_PUBLICATION_MODES = {"disabled", "local", "dry_run", "push"}
PROJECT_ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DOCUMENT_LAST_VERIFIED = "2026-06-07"
PROFILE_CAPABILITY_RULES = {
    "mutation-testing": {"python"},
}


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        raw_items = value[1:-1].strip()
        if not raw_items:
            return []
        return [item.strip().strip("'\"") for item in raw_items.split(",")]
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    return value.strip("'\"")


def load_simple_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"Invalid config line: {raw_line}")
        key, value = line.split(":", 1)
        data[key.strip()] = parse_scalar(value)

    return data


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    required = {"project_id", "name", "output_path", "profile"}
    missing = sorted(required - set(config))
    if missing:
        raise ValueError("Missing required config keys: " + ", ".join(missing))

    project_id = str(config["project_id"])
    if not PROJECT_ID_PATTERN.fullmatch(project_id):
        raise ValueError(
            "project_id must match ^[a-z0-9]+(?:-[a-z0-9]+)*$: " + project_id
        )

    profile = str(config["profile"])
    if profile not in PROFILES:
        raise ValueError(f"Unsupported profile: {profile}")

    capabilities = config.get("capabilities", [])
    if not isinstance(capabilities, list):
        raise ValueError("capabilities must be an inline list")

    unknown = sorted(set(capabilities) - CAPABILITIES)
    if unknown:
        raise ValueError("Unsupported capabilities: " + ", ".join(unknown))

    incompatible = sorted(
        capability
        for capability in capabilities
        if capability in PROFILE_CAPABILITY_RULES
        and profile not in PROFILE_CAPABILITY_RULES[capability]
    )
    if incompatible:
        raise ValueError(
            "Capabilities incompatible with profile "
            f"{profile}: " + ", ".join(incompatible)
        )

    enabled_capabilities: list[str] = []
    for capability in [*sorted(DEFAULT_CAPABILITIES), *capabilities]:
        if capability not in enabled_capabilities:
            enabled_capabilities.append(str(capability))

    return {
        "project_id": project_id,
        "name": str(config["name"]),
        "output_path": str(config["output_path"]),
        "profile": profile,
        "capabilities": enabled_capabilities,
        "data_root": str(config.get("data_root", "")),
        "worktree_root": str(config.get("worktree_root", "")),
        "control_root": str(config.get("control_root", "")),
        "artifact_root": str(config.get("artifact_root", "")),
        "git_publish_mode": str(config.get("git_publish_mode", "local")),
        "git_publish_remote": str(config.get("git_publish_remote", "origin")),
        "git_publish_branch": str(config.get("git_publish_branch", "main")),
        "git_publish_auto": bool(config.get("git_publish_auto", False)),
    }


EXCLUDED_TREE_NAMES = {
    ".venv",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
}


def ignore_generated(directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in EXCLUDED_TREE_NAMES or name.endswith(".pyc")}


def copy_core(output: Path) -> None:
    core = ROOT / "core"

    for child in core.iterdir():
        # Excluir entornos, repos y caches de nivel superior; el `ignore` de
        # copytree solo filtra nombres anidados, no el directorio raíz copiado.
        if child.name in EXCLUDED_TREE_NAMES:
            continue
        destination = output / child.name
        if child.is_dir():
            shutil.copytree(child, destination, ignore=ignore_generated)
        else:
            shutil.copy2(child, destination)

    (output / ".gitignore").write_text(
        "__pycache__/\n*.pyc\n.pytest_cache/\n.ruff_cache/\n.venv/\nnode_modules/\n",
        encoding="utf-8",
    )


def install_capability_files(output: Path, config: dict[str, Any]) -> None:
    for capability in config["capabilities"]:
        manifest_path = ROOT / "capabilities" / capability / "manifest.json"

        if not manifest_path.is_file():
            continue

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = manifest.get("files", [])

        if not isinstance(files, list):
            raise ValueError(f"{capability} manifest files must be a list")

        for entry in files:
            if not isinstance(entry, dict):
                raise ValueError(f"{capability} manifest file entries must be objects")

            source = entry.get("source")
            target = entry.get("target")

            if not isinstance(source, str) or not isinstance(target, str):
                raise ValueError(f"{capability} manifest file entries require source and target")

            source_path = (manifest_path.parent / source).resolve()
            target_path = (output / target).resolve()

            if manifest_path.parent.resolve() not in source_path.parents:
                raise ValueError(f"{capability} manifest source escapes capability root: {source}")

            if output.resolve() not in target_path.parents:
                raise ValueError(f"{capability} manifest target escapes project root: {target}")

            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)


def capability_quality_gates(config: dict[str, Any]) -> list[dict[str, Any]]:
    gates: list[dict[str, Any]] = []

    for capability in config["capabilities"]:
        manifest_path = ROOT / "capabilities" / capability / "manifest.json"

        if not manifest_path.is_file():
            continue

        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest_gates = manifest.get("quality_gates", [])

        if not isinstance(manifest_gates, list):
            raise ValueError(f"{capability} manifest quality_gates must be a list")

        for gate in manifest_gates:
            if not isinstance(gate, dict):
                raise ValueError(f"{capability} manifest quality gate entries must be objects")

            gates.append(dict(gate))

    return gates


def write_project_state(output: Path, config: dict[str, Any]) -> None:
    project_id = config["project_id"]
    data_root = (
        Path(config["data_root"]).expanduser().resolve()
        if config["data_root"]
        else output.parent / "data" / project_id
    )
    worktree_root = (
        Path(config["worktree_root"]).expanduser().resolve()
        if config["worktree_root"]
        else output.parent / "worktrees" / project_id
    )
    control_root = (
        Path(config["control_root"]).expanduser().resolve()
        if config["control_root"]
        else data_root / "control"
    )
    artifact_root = (
        Path(config["artifact_root"]).expanduser().resolve()
        if config["artifact_root"]
        else data_root / "artifacts"
    )
    git_publish_enabled = "git-publish" in config["capabilities"]
    git_publish_mode = config["git_publish_mode"]

    if git_publish_mode not in GIT_PUBLICATION_MODES:
        raise ValueError(f"Unsupported git_publish_mode: {git_publish_mode}")

    if not git_publish_enabled:
        git_publish_mode = "disabled"

    state = {
        "schema_version": 1,
        "project_id": project_id,
        "name": config["name"],
        "workflow": "spec-driven-development",
        "lifecycle_phase": "BOOTSTRAP",
        "canonical_host": "generated",
        "canonical_repository": str(output),
        "worktree_root": str(worktree_root),
        "data_root": str(data_root),
        "control_root": str(control_root),
        "artifact_root": str(artifact_root),
        "maximum_active_implementers": 1,
        "windows_validation_available": "windows-validation" in config["capabilities"],
        "canonical_branch": "main",
        "implementation_branch_prefix": "feature",
        "lease_ttl_minutes": 720,
        "profile": config["profile"],
        "capabilities": config["capabilities"],
        "git_publication": {
            "enabled": git_publish_enabled,
            "mode": git_publish_mode,
            "remote": config["git_publish_remote"],
            "branch": config["git_publish_branch"],
            "auto_publish_on_done": config["git_publish_auto"],
            "require_merged_head": True,
        },
    }

    (output / "state" / "project.json").write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    for directory in ("locks", "leases", "runs", "agent-metrics", "role-sessions"):
        (control_root / directory).mkdir(parents=True, exist_ok=True)

    (control_root / "queue.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_id": project_id,
                "updated_at": None,
                "features": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (control_root / "runtime.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_id": project_id,
                "active_feature": None,
                "active_runs": [],
                "last_completed_run": None,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    artifact_root.mkdir(parents=True, exist_ok=True)

    capability_gates = capability_quality_gates(config)
    if capability_gates:
        gates_path = output / "state" / "quality-gates.json"
        gates = json.loads(gates_path.read_text(encoding="utf-8"))
        gates.setdefault("gates", []).extend(capability_gates)
        gates_path.write_text(json.dumps(gates, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_python_smoke(output: Path) -> None:
    (output / "src").mkdir(exist_ok=True)
    (output / "src" / ".gitkeep").write_text("", encoding="utf-8")
    (output / "tests" / "unit").mkdir(parents=True, exist_ok=True)
    (output / "tests" / "unit" / "test_harness_smoke.py").write_text(
        "def test_generated_project_has_harness() -> None:\n    assert True\n",
        encoding="utf-8",
    )


def write_harness_suite(output: Path) -> None:
    """Suite minima del harness, ejecutable offline en el proyecto generado.

    Cubre logica determinista (transiciones por rol, Role Guard) sin depender del
    plano de control, Claude Code ni red. Se ejecuta con `uv run pytest tests/harness`.
    """

    harness = output / "tests" / "harness"
    harness.mkdir(parents=True, exist_ok=True)

    (harness / "conftest.py").write_text(
        """# Importa los scripts deterministas del harness en la suite minima.
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
""",
        encoding="utf-8",
    )

    (harness / "test_workflow_transitions.py").write_text(
        """import pytest
from control_common import ControlPlaneError, validate_role_for_transition


def test_specifier_can_open_spec() -> None:
    validate_role_for_transition("specifier", "DRAFT", "SPEC_READY")


def test_architect_can_mark_ready_for_development() -> None:
    validate_role_for_transition("architect", "DESIGN_READY", "READY_FOR_DEVELOPMENT")


def test_qa_reviewer_can_approve() -> None:
    validate_role_for_transition("qa-reviewer", "READY_FOR_QA", "APPROVED")


def test_implementer_cannot_approve() -> None:
    with pytest.raises(ControlPlaneError):
        validate_role_for_transition("implementer", "READY_FOR_QA", "APPROVED")


def test_leader_can_block() -> None:
    validate_role_for_transition("leader", "IN_PROGRESS", "BLOCKED")


def test_leader_cannot_advance_spec() -> None:
    with pytest.raises(ControlPlaneError):
        validate_role_for_transition("leader", "DRAFT", "SPEC_READY")
""",
        encoding="utf-8",
    )

    (harness / "test_role_guard_basic.py").write_text(
        """from role_guard import split_command_segments, starts_read_only


def test_split_on_shell_operators() -> None:
    assert split_command_segments("cat x && python evil.py") == ["cat x", "python evil.py"]
    assert split_command_segments("git diff | head") == ["git diff", "head"]


def test_quoted_operator_is_not_split() -> None:
    assert split_command_segments('git commit -m "a && b"') == ["git commit -m a && b"]


def test_read_only_detection() -> None:
    assert starts_read_only("git status") is True
    assert starts_read_only("ls") is True
    assert starts_read_only("python evil.py") is False
""",
        encoding="utf-8",
    )


def write_doc(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = content.strip() + "\n"

    if not body.startswith("---\n"):
        body = (
            "---\n"
            "owner: template\n"
            f"last_verified: {DOCUMENT_LAST_VERIFIED}\n"
            "---\n\n"
            + body
        )

    path.write_text(body, encoding="utf-8")


def format_capabilities(config: dict[str, Any]) -> str:
    capabilities = config.get("capabilities", [])
    if not capabilities:
        return "none"
    return ", ".join(str(capability) for capability in capabilities)


def apply_documentation_pack(output: Path, config: dict[str, Any]) -> None:
    if "documentation-pack" not in config["capabilities"]:
        return

    project_name = config["name"]
    project_id = config["project_id"]
    profile = config["profile"]
    capabilities = format_capabilities(config)

    docs = output / "docs"
    directories = [
        "00-project",
        "10-architecture/adr",
        "20-runtime",
        "30-quality",
        "40-operations",
        "50-releases/release-notes",
        "90-generated",
    ]

    for directory in directories:
        (docs / directory).mkdir(parents=True, exist_ok=True)

    write_doc(
        docs / "README.md",
        f"""
# Project Documentation

This project separates stable project documentation from traceable feature
documentation and operational evidence.

- `docs/00-project/`: product context, goals, glossary, roadmap and source-of-truth matrix.
- `docs/10-architecture/`: consolidated architecture and accepted ADRs.
- `docs/20-runtime/`: local development, configuration and runtime matrix.
- `docs/30-quality/`: test strategy, quality gates and capabilities.
- `docs/40-operations/`: runbook, troubleshooting, recovery and maintenance.
- `docs/50-releases/`: changelog and release notes.
- `docs/90-generated/`: regenerated summaries. These files are not authoritative.

Feature-specific documentation lives under `specs/features/`. Lightweight
versioned evidence lives under `evidence/`. Heavy artifacts and control-plane
state live under the configured `artifact_root` and `control_root`.

Agent context starts at `CLAUDE.md`. That router points agents to the smallest
authoritative document for each question and defines which documents are always
loaded, loaded on demand or human-oriented.

The non-numbered directories copied under `docs/`, such as `docs/architecture`
or `docs/conventions`, are harness contracts used by the agentic workflow.
""",
    )

    write_doc(
        docs / "00-project" / "overview.md",
        f"""
# Project Overview

## Name

{project_name}

## Identifier

`{project_id}`

## Profile

`{profile}`

## Capabilities

{capabilities}

## Problem

Document the problem this project solves before the first product feature is
approved.

## Users Or Consumers

Document the people, systems or agents that consume this project.

## Current Scope

The generated baseline includes the agentic SDD harness, project state,
quality gates and documentation structure.

## Out Of Scope

Anything not declared in `docs/00-project/goals-and-scope.md` or in an
approved feature specification remains out of scope.

## Status

Bootstrap generated. Product status is derived from `state/`, `control_root`,
`specs/features/` and Git.
""",
    )

    write_doc(
        docs / "00-project" / "goals-and-scope.md",
        """
# Goals And Scope

## Functional Goals

- Define functional goals through approved feature specifications.

## Non-Functional Goals

- Keep the workflow auditable.
- Keep quality gates deterministic.
- Keep generated summaries reproducible from source state.

## System Boundaries

The repository contains product code, specs, lightweight evidence and stable
documentation. Heavy artifacts and operational control files live outside Git.

## Known Constraints

- State transitions must go through harness scripts.
- Feature documentation must remain traceable under `specs/features/`.

## External Dependencies

List external services, runtimes, repositories or operators here when they
become required.
""",
    )

    write_doc(
        docs / "00-project" / "source-of-truth.md",
        """
# Source Of Truth

This matrix prevents roadmap, changelog, generated summaries and feature docs
from becoming competing authorities.

| Information | Authoritative Source | Owner | Notes |
| --- | --- | --- | --- |
| Current feature state | `control_root/queue.json` | Harness scripts | Use `scripts/project_status.py` for a readable view. |
| Feature requirements | `specs/features/<FEATURE>/specification.md` and `acceptance.yaml` | Spec Partner | Feature truth until finalization. |
| Feature architecture proposal | `specs/features/<FEATURE>/architecture.md` | Architect | Consolidate accepted decisions into ADRs when required. |
| Stable architecture decisions | `docs/10-architecture/adr/` | Architect | ADRs are stable project documentation. |
| Runtime and configuration | `state/project.json`, `docs/20-runtime/` | Architect or Implementer | `state/project.json` wins for exact configured paths. |
| Quality gates | `state/quality-gates.json`, `docs/30-quality/quality-gates.md` | Architect or Capability installer | State is executable; docs explain interpretation. |
| Capability policy | `state/capabilities/*.json` | Capability installer | Only active capabilities should have policy files. |
| Lightweight evidence | `evidence/` | Harness scripts | Versioned summaries and review records. |
| Heavy artifacts | `artifact_root` | Harness scripts | Logs and large outputs stay outside Git. |
| Exact code changes | Git history | Implementer and Finalizer | Git remains authoritative for diffs. |
| Human release narrative | `docs/50-releases/changelog.md` | Maintainer | Complements Git; it does not replace Git. |
| Generated summaries | `docs/90-generated/` | Deterministic scripts | Regenerable and not authoritative. |

`docs/90-generated/` may be deleted and recreated from `state/`, control state,
`specs/`, `evidence/` and Git without losing project truth.
""",
    )

    write_doc(
        docs / "00-project" / "glossary.md",
        """
# Glossary

This file is generated from `docs/00-project/glossary.yaml`.

| Term | Definition | Context | Aliases | Relations |
| --- | --- | --- | --- | --- |
| Feature | A traceable unit of product or harness change. | SDD workflow | feature | Spec, QA, evidence |
| Quality gate | Deterministic validation command attached to a workflow phase. | Quality | gate | Evidence, artifact |
| Artifact root | External location for heavy logs and generated evidence. | Operations | artifact_root | control_root |
| Control root | External location for queue, leases, runtime and metrics. | Operations | control_root | state/project.json |
""",
    )

    (docs / "00-project" / "glossary.yaml").write_text(
        """
schema_version: 1
terms:
  - term: Feature
    definition: A traceable unit of product or harness change.
    aliases:
      - feature
    context: SDD workflow
    relations:
      - Spec
      - QA
      - evidence
  - term: Quality gate
    definition: Deterministic validation command attached to a workflow phase.
    aliases:
      - gate
    context: Quality
    relations:
      - Evidence
      - artifact
  - term: Artifact root
    definition: External location for heavy logs and generated evidence.
    aliases:
      - artifact_root
    context: Operations
    relations:
      - control_root
  - term: Control root
    definition: External location for queue, leases, runtime and metrics.
    aliases:
      - control_root
    context: Operations
    relations:
      - state/project.json
""".strip()
        + "\n",
        encoding="utf-8",
    )

    write_doc(
        docs / "00-project" / "roadmap.md",
        """
# Roadmap

## Current Phase

Bootstrap.

## Planned Features

Register planned work through `scripts/register_feature.py`.

## Open Risks

- Product risks should be documented here once known.
- Harness and capability risks should be tied to feature specs or ADRs.

## Dependencies

Use this section to record dependencies between roadmap blocks.
""",
    )

    write_doc(
        docs / "10-architecture" / "system-context.md",
        """
# System Context

## System

Describe the concrete system being built with this generated harness.

## Actors And External Systems

List users, external services, automation agents and runtime targets.

## Inputs And Outputs

Document commands, APIs, files, events and generated artifacts.

## Boundaries

Separate repository state, feature specs, versioned evidence and external
artifacts.
""",
    )

    write_doc(
        docs / "10-architecture" / "architecture-overview.md",
        """
# Architecture Overview

## Overview

The generated baseline provides a spec-driven workflow, control-plane scripts,
quality gates and project documentation. Product architecture must be
consolidated here as approved features land.

## Main Components

See `components.md`.

## Architectural Decisions

Accepted decisions live under `docs/10-architecture/adr/`.
""",
    )

    write_doc(
        docs / "10-architecture" / "components.md",
        """
# Components

| Component | Responsibility | Inputs | Outputs | Dependencies | Tests |
| --- | --- | --- | --- | --- | --- |
| Agentic harness | Controls feature lifecycle and gates. | Specs, state, commands | Evidence, transitions | Python scripts | Harness tests |
| Product code | Implements project behavior. | Product inputs | Product outputs | Profile stack | Product tests |
""",
    )

    write_doc(
        docs / "10-architecture" / "data-model.md",
        """
# Data Model

## Persistent Files

- `state/project.json`: project configuration.
- `state/workflow.json`: lifecycle transitions and roles.
- `state/quality-gates.json`: versioned gate configuration.
- `specs/features/`: feature specifications and plans.
- `evidence/`: lightweight versioned evidence.

## External State

- `control_root`: queue, runtime, leases, locks and metrics.
- `artifact_root`: heavy logs and capability evidence.

## Retention

Keep Git-tracked docs and evidence. Rotate heavy artifacts according to the
project operations policy.
""",
    )

    write_doc(
        docs / "10-architecture" / "interfaces.md",
        """
# Interfaces

## CLI

The harness exposes deterministic scripts under `scripts/`.

## Files

Contracts are represented as JSON, YAML and Markdown files under `state/`,
`specs/`, `docs/` and `evidence/`.

## Events

Lifecycle transitions are explicit script calls recorded in the control plane.

## External Protocols

Document project-specific APIs, events or remote runtimes here when introduced.
""",
    )

    write_doc(
        docs / "10-architecture" / "deployment.md",
        """
# Deployment

## Execution Model

The generated project runs locally or on the configured canonical host.

## Requirements

- Git
- Python runtime for harness scripts
- Profile-specific toolchain

## Configuration

Runtime paths and publication settings are stored in `state/project.json`.
""",
    )

    write_doc(
        docs / "10-architecture" / "adr" / "ADR-0001-template-baseline.md",
        f"""
# ADR-0001 - Template Baseline

## Status

Accepted

## Context

The project was generated from the Agentic SDD template using profile
`{profile}`.

## Decision

Use the generated harness as the baseline for feature specification,
architecture review, implementation, QA, finalization, quality gates,
capabilities and documentation.

## Consequences

- Feature work is traceable through `specs/features/`.
- Operational state is controlled by deterministic scripts.
- Project documentation is maintained under numbered `docs/` sections.

## Alternatives Considered

- Manual repository setup without the harness.
- Documentation added after implementation instead of as a project contract.

## Related Features

Bootstrap.
""",
    )

    write_doc(
        docs / "20-runtime" / "local-development.md",
        """
# Local Development

## Harness Validation

```bash
bash scripts/verify_fast.sh
bash scripts/verify_full.sh
python3 scripts/project_status.py
```

## Feature Workflow

Use the harness scripts to register, implement, review and finalize features.
""",
    )

    write_doc(
        docs / "20-runtime" / "configuration.md",
        """
# Configuration

## Versioned Configuration

- `state/project.json`
- `state/workflow.json`
- `state/quality-gates.json`
- `state/capabilities/*.json`

## Secrets

Do not commit secrets, tokens, private keys or `.env` files.

## Defaults

Project defaults are created by `create_project.py` and can be changed through
reviewed features.

## Generator Inputs

| Key | Required | Default | Notes |
| --- | --- | --- | --- |
| `project_id` | Yes | None | Must match `^[a-z0-9]+(?:-[a-z0-9]+)*$`. |
| `profile` | Yes | None | One of `generic`, `python`, `node`. |
| `capabilities` | No | `[]` | Must be compatible with the selected profile. |
| `data_root` | No | `<output_parent>/data/<project_id>` | Parent for generated operational data. |
| `worktree_root` | No | `<output_parent>/worktrees/<project_id>` | Root for feature worktrees. |
| `control_root` | No | `<data_root>/control` | Queue, leases, runs and metrics. |
| `artifact_root` | No | `<data_root>/artifacts` | Heavy logs and external evidence. |

Absolute operational paths are environment-specific and should be supplied by
configuration, not hardcoded in core files.
""",
    )

    write_doc(
        docs / "20-runtime" / "external-runtimes.md",
        """
# External Runtimes

| target_id | Type | Platform | Capabilities | Connection | Expected Artifacts |
| --- | --- | --- | --- | --- | --- |
| local | Local process | Current host | Harness checks | Direct command | JSON evidence |

Add remote workstations, containers, VMs, GPU hosts or cloud runners when they
become part of the project.
""",
    )

    write_doc(
        docs / "20-runtime" / "environment-matrix.md",
        """
# Environment Matrix

| Environment | System | Runtime | Dependencies | Use |
| --- | --- | --- | --- | --- |
| Canonical host | Generated | Python harness | Git, Python | Development and validation |
| Workstation | Operator-defined | Profile-specific | Project tools | Optional validation |
""",
    )

    write_doc(
        docs / "30-quality" / "test-strategy.md",
        """
# Test Strategy

## Unit Tests

Validate isolated product and harness behavior.

## Integration Tests

Validate interactions between scripts, state, specs and evidence.

## End To End Tests

Validate full feature flow when required.

## Minimum Before QA

Blocking `implementation_fast` gates must pass before `READY_FOR_QA`.
""",
    )

    write_doc(
        docs / "30-quality" / "quality-gates.md",
        """
# Quality Gates

Quality gates are configured in `state/quality-gates.json`.

## Contract

Each gate declares:

| Field | Meaning |
| --- | --- |
| `id` | Stable gate identifier. |
| `phase` | Workflow phase such as `implementation_fast`, `qa_full`, `finalization` or `optional_capability`. |
| `command` | Command list executed from the repository root. |
| `blocking` | Whether a failure blocks the phase. |
| `mode` | `enforce` for blocking gates, `observe` for non-blocking evidence. |
| `timeout_seconds` | Maximum runtime before timeout. |

Commands may use `{feature_id}`, `{run_id}` and `{artifact_root}` placeholders.

## Phases

- `implementation_fast`
- `qa_full`
- `finalization`
- `optional_capability`

## Evidence

Gate summaries are written as structured JSON. Heavy logs live under
`artifact_root`.

## Blocking Rule

A failed gate with `blocking: true` blocks the corresponding transition.
""",
    )

    write_doc(
        docs / "30-quality" / "mutation-testing.md",
        """
# Mutation Testing

Mutation testing is optional and feature-scoped. When enabled, surviving
relevant mutants must be justified or fixed before approval.

Evidence is produced under `artifact_root/mutation-tests/` and reviewed through
`evidence/mutation-reviews/`.
""",
    )

    write_doc(
        docs / "30-quality" / "performance-testing.md",
        """
# Performance Testing

Performance gates are capability-driven. Use `performance-testing` for
repeatable benchmarks with structured evidence and baselines.
""",
    )

    write_doc(
        docs / "30-quality" / "security-scanning.md",
        """
# Security Scanning

Security scanning is capability-driven. The baseline scanner detects secrets
and sensitive files and records structured evidence.
""",
    )

    write_doc(
        docs / "30-quality" / "eval-harness.md",
        """
# Eval Harness

Eval harness is capability-driven. It turns each `SCN-XXX` scenario into
executable graders so acceptance becomes machine-checkable, closing the
`AC-XXX -> SCN-XXX -> grader -> evidence` chain.

Graders are declared per feature in `specs/features/<FEATURE>/evals.json`.
Deterministic `code` and `rule` graders are gate-eligible; `model` and `human`
graders are advisory and never decide the automatic gate. The runner records
`pass_at_k` and `pass_caret_k` metrics as structured evidence under
`artifact_root/capabilities/eval-harness/`.
""",
    )

    write_doc(
        docs / "30-quality" / "threat-model.md",
        """
# Threat Model

## Scope

The baseline threat model covers repository contents, harness scripts,
generated evidence, operational state, external runtimes and publication
workflows.

## Assets

- Source code and feature specifications.
- Lightweight evidence under `evidence/`.
- Heavy artifacts under `artifact_root`.
- Control-plane state under `control_root`.
- Git remotes and publication credentials.

## Trust Boundaries

- Repository to external runtimes.
- Repository to `artifact_root` and `control_root`.
- Local Git history to remote publication targets.
- Human-authored docs to generated summaries.

## Default Controls

- Secrets are scanned deterministically.
- Evidence and publish logs redact likely credentials.
- Accepted findings must be declared in the security capability baseline.
- `git-publish` remains manual and supports dry-run.

## Blocking Policy

The default policy observes most security findings and blocks only when
explicitly enforced for clear critical secrets or confirmed critical issues.
""",
    )

    write_doc(
        docs / "30-quality" / "data-classification.md",
        """
# Data Classification

## Public

Documentation, examples and generated summaries intended for repository users.

## Internal

Feature specifications, review evidence, quality summaries and operational
runbooks.

## Sensitive

Credentials, private keys, tokens, personal data, unpublished remote URLs and
raw external-runtime logs.

## Handling Rules

- Do not commit Sensitive data.
- Store heavy or sensitive operational artifacts under `artifact_root`.
- Redact secrets before writing evidence.
- Treat `control_root` as operational state, not publishable product data.
""",
    )

    write_doc(
        docs / "40-operations" / "runbook.md",
        """
# Runbook

## Status

```bash
python3 scripts/project_status.py
```

## Regenerate Documentation Summaries

```bash
python3 scripts/refresh_project_docs.py
```

## Validate

```bash
bash scripts/verify_full.sh
```

## Finalize Feature

```bash
python3 scripts/finalize_feature.py --feature F-001 --reason "Approved and integrated"
```
""",
    )

    write_doc(
        docs / "40-operations" / "troubleshooting.md",
        """
# Troubleshooting

| Symptom | Likely Cause | Diagnostic Command | Recommended Fix | Risk |
| --- | --- | --- | --- | --- |
| Lease expired | Agent stopped or timeout elapsed | `python3 scripts/project_status.py` | Recover stale leases | Lost active work |
| QA blocked | Gate failure or invalid evidence | Inspect `artifact_root/quality-gates/` | Fix issue and rerun QA | Premature approval |
| Metrics stale | Feature states changed | `python3 scripts/metrics_status.py` | Refresh metrics | Misleading dashboard |
| Documentation stale | Generated summaries not refreshed | `python3 scripts/refresh_project_docs.py` | Regenerate summaries | Outdated docs |
""",
    )

    write_doc(
        docs / "40-operations" / "backup-and-restore.md",
        """
# Backup And Restore

## Back Up

- Git repository.
- `control_root` if in-flight state matters.
- `artifact_root` if historical heavy evidence matters.

## Regenerable

- `docs/90-generated/`
- Metrics snapshots.
- Quality summaries.

## Restore

Restore Git first, then restore the configured `control_root` and
`artifact_root` paths from backup if needed.
""",
    )

    write_doc(
        docs / "40-operations" / "maintenance.md",
        """
# Maintenance

## Periodic Tasks

- Clean stale worktrees.
- Rotate heavy logs in `artifact_root`.
- Refresh metrics snapshots.
- Regenerate documentation summaries.
- Review dependency updates through normal features.
""",
    )

    write_doc(
        docs / "50-releases" / "changelog.md",
        """
# Changelog

This file records human-readable release changes. Git remains the source of
truth for exact diffs.

## Unreleased

- Generated project baseline.
""",
    )

    (docs / "50-releases" / "release-notes" / ".gitkeep").write_text("", encoding="utf-8")
    (docs / "90-generated" / ".gitkeep").write_text("", encoding="utf-8")

    if profile == "python":
        write_doc(
            docs / "20-runtime" / "python-environment.md",
            """
# Python Environment

## Commands

```bash
uv sync
uv run pytest
uv run ruff check .
uv run python -m compileall -q scripts src tests
```
""",
        )

    if profile == "node":
        write_doc(
            docs / "20-runtime" / "node-environment.md",
            """
# Node Environment

## Commands

```bash
npm test
npm run lint
```

## Harness Toolchain

The product uses Node, but the agentic harness itself is written in Python and
its base quality gates run `ruff`, `pytest` and `compileall`. Python 3.12, `uv`,
`ruff` and `pytest` must therefore be available to pass `qa_full` and
`finalization`, in addition to Node.
""",
        )

    if profile == "android":
        write_doc(
            docs / "20-runtime" / "android-environment.md",
            """
# Android Environment

## Product Toolchain

The product is an Android app written in Kotlin and built with Gradle.

```bash
./gradlew testDebugUnitTest
./gradlew lintDebug
./gradlew assembleDebug
```

The generated skeleton ships application sources under `app/src/main/`,
JVM unit tests under `app/src/test/`, and localized resources under
`app/src/main/res/values{,-es,-ja,-ko}/` (English default plus Spanish,
Japanese and Korean).

## Harness Toolchain

The product targets Android, but the agentic harness itself is written in
Python and its blocking quality gates run `ruff`, `pytest` and `compileall`.
Python 3.12, `uv`, `ruff` and `pytest` must therefore be available to pass
`qa_full` and `finalization`.

## Android Gates

The Android gates (`ANDROID-001`, `ANDROID-002`) run through
`scripts/verify_android.sh` in `observe` mode: they are non-blocking and skip
with success when Gradle or the Android SDK is not present on the host. Run the
real Android build and tests on a developer machine, in Android Studio, or on a
provisioned runner (for example via the `external-runtime` capability).
""",
        )

    if "windows-validation" in config["capabilities"]:
        write_doc(
            docs / "20-runtime" / "windows-runner.md",
            """
# Windows Runner

Windows validation is optional and capability-scoped. Use the Windows evidence
contract under `docs/windows-runner/evidence-contract.md` and validate evidence
with `scripts/validate_windows_evidence.py`.

## Transport

Supported transport patterns are declarative:

- `external-runtime` SSH/SCP adapter for automated remote execution.
- SMB or shared workspace for operator-managed artifact drops.
- Manual drop into `artifact_root/windows-tests/<FEATURE>/latest.json`.

The evidence file must reference the reviewed feature and commit. Windows
validation is not active by default.
""",
        )
        write_doc(
            docs / "30-quality" / "windows-validation.md",
            """
# Windows Validation

Windows validation evidence is accepted only when it matches
`specs/schemas/windows-evidence.schema.json`. Non-Windows smoke collection is
allowed only for infrastructure tests.
""",
        )


def apply_profile(output: Path, profile: str) -> None:
    write_python_smoke(output)

    if profile == "generic":
        (output / "README.md").write_text("# Generated Generic Project\n", encoding="utf-8")
        return

    if profile == "python":
        package = output.name.replace("-", "_")
        (output / "src" / package).mkdir(parents=True)
        (output / "src" / package / "__init__.py").write_text('VERSION = "0.1.0"\n', encoding="utf-8")
        (output / "tests" / "unit" / "test_profile_smoke.py").write_text(
            f"from src.{package} import VERSION\n\n\ndef test_version() -> None:\n    assert VERSION\n",
            encoding="utf-8",
        )
        return

    if profile == "node":
        (output / "src").mkdir(exist_ok=True)
        (output / "tests").mkdir(exist_ok=True)
        (output / "package.json").write_text(
            json.dumps(
                {
                    "type": "module",
                    "scripts": {
                        "test": "node --test",
                        "lint": "node --check src/index.js tests/index.test.js",
                    },
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (output / "src" / "index.js").write_text("export const version = '0.1.0';\n", encoding="utf-8")
        (output / "tests" / "index.test.js").write_text(
            "import test from 'node:test';\nimport assert from 'node:assert/strict';\nimport { version } from '../src/index.js';\n\ntest('exports version', () => {\n  assert.equal(version, '0.1.0');\n});\n",
            encoding="utf-8",
        )
        gates_path = output / "state" / "quality-gates.json"
        gates = json.loads(gates_path.read_text(encoding="utf-8"))
        gates["gates"].extend(
            [
                {
                    "id": "GATE-004",
                    "phase": "implementation_fast",
                    "command": ["npm", "test"],
                    "blocking": True,
                    "timeout_seconds": 300,
                },
                {
                    "id": "GATE-005",
                    "phase": "qa_full",
                    "command": ["npm", "test"],
                    "blocking": True,
                    "timeout_seconds": 300,
                },
                {
                    "id": "GATE-006",
                    "phase": "qa_full",
                    "command": ["npm", "run", "lint"],
                    "blocking": True,
                    "timeout_seconds": 300,
                },
                {
                    "id": "GATE-007",
                    "phase": "finalization",
                    "command": ["npm", "test"],
                    "blocking": True,
                    "timeout_seconds": 300,
                },
            ]
        )
        gates_path.write_text(json.dumps(gates, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if profile == "android":
        apply_android_profile(output)


ANDROID_LOCALE_STRINGS = {
    # `values/` es el recurso por defecto (inglés). Las variantes por idioma
    # demuestran el soporte multi-idioma requerido por el producto: castellano,
    # japonés y coreano, además del inglés por defecto.
    "values": ("en", "Card Collector", "Scan a card"),
    "values-es": ("es", "Coleccionista de Cartas", "Escanear una carta"),
    "values-ja": ("ja", "カードコレクター", "カードをスキャン"),
    "values-ko": ("ko", "카드 컬렉터", "카드 스캔"),
}


def apply_android_profile(output: Path) -> None:
    """Genera un skeleton Android (Kotlin + Gradle) con toolchain mínimo.

    Igual que el perfil Node v1, el harness no instala dependencias externas: el
    generador no descarga el Android SDK ni Gradle. Los gates Android se instalan
    en modo `observe` (no bloqueante) y se ejecutan a través de
    `scripts/verify_android.sh`, que detecta el toolchain y se omite con éxito
    cuando no está disponible. Los gates bloqueantes del harness siguen siendo los
    de Python (`verify_fast.sh` / `verify_full.sh`).
    """

    package = "com.generated." + output.name.replace("-", "")
    package_path = Path(*package.split("."))

    app = output / "app"
    main_java = app / "src" / "main" / "java" / package_path
    test_java = app / "src" / "test" / "java" / package_path
    main_java.mkdir(parents=True, exist_ok=True)
    test_java.mkdir(parents=True, exist_ok=True)

    (output / "settings.gradle.kts").write_text(
        'pluginManagement {\n'
        "    repositories {\n"
        "        google()\n"
        "        mavenCentral()\n"
        "        gradlePluginPortal()\n"
        "    }\n"
        "}\n"
        "dependencyResolutionManagement {\n"
        "    repositories {\n"
        "        google()\n"
        "        mavenCentral()\n"
        "    }\n"
        "}\n"
        f'rootProject.name = "{output.name}"\n'
        'include(":app")\n',
        encoding="utf-8",
    )

    (output / "build.gradle.kts").write_text(
        "// Configuración raíz de Gradle. Los plugins se aplican por módulo.\n"
        "plugins {\n"
        '    id("com.android.application") version "8.5.0" apply false\n'
        '    id("org.jetbrains.kotlin.android") version "1.9.24" apply false\n'
        "}\n",
        encoding="utf-8",
    )

    (output / "gradle.properties").write_text(
        "org.gradle.jvmargs=-Xmx2048m\n"
        "android.useAndroidX=true\n"
        "kotlin.code.style=official\n",
        encoding="utf-8",
    )

    (app / "build.gradle.kts").write_text(
        "plugins {\n"
        '    id("com.android.application")\n'
        '    id("org.jetbrains.kotlin.android")\n'
        "}\n\n"
        "android {\n"
        f'    namespace = "{package}"\n'
        "    compileSdk = 34\n\n"
        "    defaultConfig {\n"
        f'        applicationId = "{package}"\n'
        "        minSdk = 24\n"
        "        targetSdk = 34\n"
        "        versionCode = 1\n"
        '        versionName = "0.1.0"\n'
        '        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"\n'
        '        resConfigs("en", "es", "ja", "ko")\n'
        "    }\n\n"
        "    compileOptions {\n"
        "        sourceCompatibility = JavaVersion.VERSION_17\n"
        "        targetCompatibility = JavaVersion.VERSION_17\n"
        "    }\n"
        "    kotlinOptions {\n"
        '        jvmTarget = "17"\n'
        "    }\n"
        "}\n\n"
        "dependencies {\n"
        '    implementation("androidx.core:core-ktx:1.13.1")\n'
        '    implementation("androidx.appcompat:appcompat:1.7.0")\n'
        '    testImplementation("junit:junit:4.13.2")\n'
        "}\n",
        encoding="utf-8",
    )

    (app / "src" / "main" / "AndroidManifest.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<manifest xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <uses-permission android:name="android.permission.CAMERA" />\n'
        '    <uses-permission android:name="android.permission.INTERNET" />\n'
        "    <application\n"
        '        android:label="@string/app_name"\n'
        '        android:supportsRtl="true">\n'
        "        <activity\n"
        '            android:name=".MainActivity"\n'
        '            android:exported="true">\n'
        "            <intent-filter>\n"
        '                <action android:name="android.intent.action.MAIN" />\n'
        '                <category android:name="android.intent.category.LAUNCHER" />\n'
        "            </intent-filter>\n"
        "        </activity>\n"
        "    </application>\n"
        "</manifest>\n",
        encoding="utf-8",
    )

    (main_java / "MainActivity.kt").write_text(
        f"package {package}\n\n"
        "import android.app.Activity\n"
        "import android.os.Bundle\n"
        "import android.widget.TextView\n\n"
        "class MainActivity : Activity() {\n"
        "    override fun onCreate(savedInstanceState: Bundle?) {\n"
        "        super.onCreate(savedInstanceState)\n"
        "        val label = TextView(this)\n"
        "        label.setText(R.string.app_name)\n"
        "        setContentView(label)\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    for directory, (_, app_name, scan_label) in ANDROID_LOCALE_STRINGS.items():
        values_dir = app / "src" / "main" / "res" / directory
        values_dir.mkdir(parents=True, exist_ok=True)
        (values_dir / "strings.xml").write_text(
            '<?xml version="1.0" encoding="utf-8"?>\n'
            "<resources>\n"
            f'    <string name="app_name">{app_name}</string>\n'
            f'    <string name="action_scan_card">{scan_label}</string>\n'
            "</resources>\n",
            encoding="utf-8",
        )

    (test_java / "ExampleUnitTest.kt").write_text(
        f"package {package}\n\n"
        "import org.junit.Assert.assertEquals\n"
        "import org.junit.Test\n\n"
        "class ExampleUnitTest {\n"
        "    @Test\n"
        "    fun versionName_isParsable() {\n"
        '        val parts = "0.1.0".split(".")\n'
        "        assertEquals(3, parts.size)\n"
        "    }\n"
        "}\n",
        encoding="utf-8",
    )

    (output / "scripts" / "verify_android.sh").write_text(
        "#!/usr/bin/env bash\n"
        "# Verificación Android (observe). No bloquea el lifecycle del harness Python.\n"
        "# Ejecuta los gates de Gradle si el toolchain Android está disponible; en su\n"
        '# ausencia informa y termina con éxito (evidencia "skipped").\n'
        "set -uo pipefail\n\n"
        'cd "$(git rev-parse --show-toplevel)"\n\n'
        "if [ -x ./gradlew ]; then\n"
        "  gradle_cmd=(./gradlew)\n"
        "elif command -v gradle >/dev/null 2>&1; then\n"
        "  gradle_cmd=(gradle)\n"
        "else\n"
        '  echo "[SKIP] Android toolchain (Gradle/SDK) no disponible; gate observe omitido."\n'
        "  exit 0\n"
        "fi\n\n"
        "set -e\n"
        'echo "── Android unit tests ─────────────────────────────────"\n'
        '"${gradle_cmd[@]}" testDebugUnitTest\n'
        "echo\n"
        'echo "── Android lint ───────────────────────────────────────"\n'
        '"${gradle_cmd[@]}" lintDebug\n',
        encoding="utf-8",
    )

    gitignore = output / ".gitignore"
    gitignore.write_text(
        gitignore.read_text(encoding="utf-8")
        + ".gradle/\nbuild/\n/local.properties\n*.apk\n*.aab\n.cxx/\n",
        encoding="utf-8",
    )

    gates_path = output / "state" / "quality-gates.json"
    gates = json.loads(gates_path.read_text(encoding="utf-8"))
    gates["gates"].extend(
        [
            {
                "id": "ANDROID-001",
                "phase": "implementation_fast",
                "command": ["bash", "scripts/verify_android.sh"],
                "blocking": False,
                "mode": "observe",
                "timeout_seconds": 1800,
            },
            {
                "id": "ANDROID-002",
                "phase": "qa_full",
                "command": ["bash", "scripts/verify_android.sh"],
                "blocking": False,
                "mode": "observe",
                "timeout_seconds": 1800,
            },
        ]
    )
    gates_path.write_text(json.dumps(gates, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def initialize_git(output: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=output, check=True, text=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Agentic Template"], cwd=output, check=True)
    subprocess.run(["git", "config", "user.email", "agentic-template@example.invalid"], cwd=output, check=True)
    subprocess.run(["git", "add", "."], cwd=output, check=True)
    subprocess.run(["git", "commit", "-m", "chore: initialize generated project"], cwd=output, check=True, text=True, capture_output=True)


def create_project(config: dict[str, Any]) -> Path:
    output = Path(config["output_path"]).expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"Output path already exists: {output}")
    output.mkdir(parents=True)

    copy_core(output)
    install_capability_files(output, config)
    write_project_state(output, config)
    apply_profile(output, config["profile"])
    write_harness_suite(output)
    apply_documentation_pack(output, config)
    initialize_git(output)
    return output


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    config = validate_config(load_simple_yaml(Path(args.config)))
    output = create_project(config)
    print(f"[OK] Created project: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
