# Architecture Of The Agentic SDD Template

This document describes the technical architecture of the template and of the
generated project. The goal of the template is to create repos that can operate
features with a reproducible, audited Spec Driven Development cycle governed by
deterministic scripts.

## Overview

```text
agentic-sdd-template
  create_project.py
  core/              common harness
  profiles/          per-stack adapters
  capabilities/      optional capabilities
  tests/             generator tests

generated-project
  .claude/           agents and configuration
  scripts/           deterministic control plane
  specs/             spec, architecture and test plan contracts
  state/             versioned configuration
  docs/              harness technical documentation
  evidence/          small versioned evidence
  src/, tests/       product code per profile
```

## Layers

### Generator

`create_project.py` reads a simple YAML, validates `project_id`, `name`,
`output_path`, `profile` and `capabilities`, copies `core/`, applies the selected
profile and creates an initial commit in Git.

The YAML parser is intentionally minimal. It supports `key: value` lines, simple
booleans and inline lists such as `[mutation-testing]`.

### Core

`core/` contains the harness that all projects receive:

- agents in `.claude/agents`
- lifecycle and control scripts
- specification and evidence schemas
- spec templates
- default quality gates
- architecture and conventions documentation
- `pyproject.toml` and `uv.lock` of the harness Python toolchain

The core should be treated as a syncable unit from the source harness.

### Profiles

The profiles add the minimum necessary for a generated project to be validated
from the first commit.

- `generic`: harness and smoke test only.
- `python`: Python package under `src/` and unit tests.
- `node`: `package.json`, ESM, `node:test` and Node gates.

### Capabilities

The capabilities are opt-in. The template documents them and the generated
project can activate them by configuration or per feature.

Current capabilities:

- `documentation-pack` (included by default)
- `eval-harness`
- `external-runtime`
- `git-publish`
- `mutation-testing`
- `performance-testing`
- `remote-notifications`
- `security-scanning`
- `tool-telemetry`
- `windows-validation`

## Control Plane

The generated project separates the Git repo from the operational state.

Versioned state:

- `state/project.json`
- `state/workflow.json`
- `state/quality-gates.json`
- `state/specification-policy.json`
- `state/agent-budgets.json`

Operational state outside Git:

- `data/<project_id>/control/queue.json`
- `data/<project_id>/control/runtime.json`
- `data/<project_id>/control/runs/`
- `data/<project_id>/control/leases/`
- `data/<project_id>/control/locks/`
- `data/<project_id>/control/agent-metrics/`
- `data/<project_id>/artifacts/`

This separation prevents logs, locks and runtime from contaminating the Git
history.

## Feature Lifecycle

Main states:

```text
DRAFT -> SPEC_READY -> DESIGN_READY -> READY_FOR_DEVELOPMENT
READY_FOR_DEVELOPMENT -> IN_PROGRESS -> READY_FOR_QA
READY_FOR_QA -> APPROVED -> DONE
READY_FOR_QA -> CHANGES_REQUESTED -> IN_PROGRESS
```

The roles authorized per transition are defined in `state/workflow.json` and
enforced by `scripts/control_common.py`.

## Spec Partner v2

Spec Partner v2 hardens the entry into development.

Components:

- `state/specification-policy.json`
- `specs/schemas/acceptance-v2.schema.json`
- `specs/templates/acceptance.yaml`
- `scripts/validate_spec.py`
- `scripts/feature_validation.py`

The architecture must include a `Specification Review` for v2 specs. That section
documents whether the Architect found contradictions, non-verifiable criteria,
missing dependencies, ambiguous scope or critical questions.

## Role Guard And Change Domains

`change_domain` classifies the intent of a feature:

- `product`: normal product changes. It is the default.
- `harness`: controlled harness maintenance.
- `template`: changes to the template or its packaging.

Role Guard uses that domain to allow or block paths. In the `harness` domain,
controlled changes are allowed in scripts, agents, schemas, templates, docs,
state and tests. The external control plane remains out of scope.

## Quality Gates

`scripts/quality_gates.py` runs the gates configured in
`state/quality-gates.json`.

Phases:

- `implementation_fast`
- `qa_full`
- `finalization`
- `optional_capability`

Each gate defines:

- `id`
- `phase`
- `command`
- `blocking`
- `timeout_seconds`

The results are written as structured JSON in
`artifact_root/quality-gates/<feature>/`. The full logs are stored next to the
evidence.

## Mutation Testing

The `mutation-testing` capability uses `scripts/mutation_runner.py`.

The runner:

- detects changed Python code
- generates deterministic mutants
- applies each mutant temporarily
- runs the test command
- restores files
- classifies mutants as `killed`, `survived` or `invalid`
- writes JSON evidence

The final review is performed by `mutation-reviewer` and validated with
`scripts/mutation_review_validation.py`.

## Evidence

Versioned evidence:

- `evidence/implementations/<feature>.json`
- `evidence/reviews/<feature>.json`
- `evidence/mutation-reviews/<feature>.json`

Heavy artifacts:

- `artifact_root/quality-gates/<feature>/`
- `artifact_root/mutation-tests/<feature>/`
- `artifact_root/git-publish/<feature>/`

## Git Publication

Git publication is an optional capability (`git-publish`) that operates after
`DONE`.

Components:

- `scripts/publish_feature.py`
- `repository-publisher` agent
- `state/project.json::git_publication` configuration
- evidence in `artifact_root/git-publish/<feature>/`

The design separates local integration from remote publication:

- `finalize_feature.py` integrates the approved feature into the local canonical
  branch.
- `publish_feature.py` validates that the feature is in `DONE` and records or
  pushes the commit.

Role Guard blocks a direct `git push`. A real push can only happen inside the
deterministic script, with a clean repo, a finalized feature and a configured
remote.

## Synchronization Model

The template is not the source harness; it is a distribution. When the source
harness evolves:

1. Synchronize `core/`.
2. Adjust profiles/capabilities if the contract changed.
3. Regenerate test projects.
4. Run the template suite.
5. Complete at least one real feature if the change touches the lifecycle, gates
   or control.
