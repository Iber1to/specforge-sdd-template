# State And Roadmap Of The Agentic Harness

Closure date: 2026-06-06  
Source harness repository: `/srv/agentic/workspace/desktop-overlay-assistant`  
Template repository: `/srv/agentic/workspace/agentic-sdd-template`

## Executive State

Roadmap closed. The harness already supports Spec Partner v2, controlled
maintenance of the harness itself, semantic architecture review, versioned
quality gates, deterministic mutation testing, mutation reviewer, external
runtime, performance testing, security scanning, audited Git publication,
documentation pack by default, a documentation finalization gate and template
extraction with the `generic`, `python` and `node` profiles.

The executable source remains Git, schemas, scripts and the control plane. This
document keeps the original roadmap and completes it with the final state,
evidence and applied technical decisions.

## Compliance Summary

| Block | State | Evidence |
| --- | --- | --- |
| `31A.1C` Spec Partner v2 and bootstrap | Completed | `e16a7f4`, `state/specification-policy.json`, `specs/schemas/acceptance-v2.schema.json` |
| `change_domain` and maintenance Role Guard | Completed | `scripts/register_feature.py`, `scripts/role_guard.py`, Role Guard tests |
| SDD/Windows docs fixed | Completed | `docs/conventions/spec-driven-development.md`, `docs/windows-runner/evidence-contract.md` |
| `31B` Semantic Architect Review | Completed | `specs/templates/architecture.md`, `scripts/feature_validation.py`, `architect` agent |
| `31C` Quality Gates Framework | Completed | `state/quality-gates.json`, `scripts/quality_gates.py`, integration in implementation, QA and finalization |
| `31D-31E` Mutation Capability | Completed | `scripts/mutation_runner.py`, `mutation-testing` capability, `mutation-reviewer` agent |
| Blocking Mutation Reviewer | Completed | `scripts/mutation_review_validation.py`, `specs/schemas/mutation-review.schema.json`, QA blocking |
| `31F` End-to-end validation | Completed | projects `test-generic-project`, `test-python-project`, `test-node-project` with `F-001` in `DONE` |
| Template extraction | Completed | `/srv/agentic/workspace/agentic-sdd-template` with `core/`, `profiles/`, `capabilities/`, `generator/`, `tests/` |
| `32A` Git Publish Capability | Completed | `scripts/publish_feature.py`, `repository-publisher` agent, tests `test_git_publish.py` |
| `32B` External Runtime Capability | Completed | `scripts/run_external_runtime.py`, `state/capabilities/external-runtime.json`, smoke evidence |
| `32C` Performance Testing Capability | Completed | `scripts/run_performance_gate.py`, `state/capabilities/performance-testing.json`, smoke evidence |
| `32D` Security Scanning Capability | Completed | `scripts/run_security_scan.py`, `state/capabilities/security-scanning.json`, smoke evidence |
| `CAP-009` Documentation Pack | Completed | `state/capabilities/documentation-pack.json`, `docs/00-project/`, `scripts/refresh_project_docs.py`, generator tests |
| `CAP-010` Documentation Finalization Gate | Completed | `scripts/documentation_validation.py`, `scripts/finalize_feature.py`, `acceptance.yaml documentation`, unit tests |

## Implemented Changes

### 31A.1C And Self-Maintenance Bootstrap

The bootstrap was closed with a direct audited operator commit. The harness was
prepared so that, from that point, maintenance goes through features of the
harness itself.

Implemented:

- Spec Partner v2 activated via `state/specification-policy.json`.
- Schema v2 in `specs/schemas/acceptance-v2.schema.json`.
- Template v2 by default in `specs/templates/acceptance.yaml`.
- Support for legacy v1 contracts for `F-001`.
- `specifier` and `leader` agent documentation updated.
- Fix of broken Markdown blocks in the SDD conventions.
- Fix of the Windows contract and removal of duplication.
- `change_domain` field with values `product`, `harness`, `template`; default
  `product`.
- Role Guard extended to allow controlled maintenance changes in the `harness`
  domain.

Constraint maintained: `change_domain: harness` does not authorize direct editing
of the external control plane.

Main commits:

- `e16a7f4 feat: close spec partner bootstrap`
- `08c5945 feat: validate structured acceptance contracts v2`

### 31B Semantic Architect Review

The Architect must semantically review the specification before the design.

Implemented:

- `architecture.md` requires a `Specification Review` section for acceptance v2.
- The validation blocks `DESIGN_READY` if critical conclusions are missing.
- The `architect` agent was updated to review contradictions, non-verifiable
  criteria, undeclared dependencies, ambiguous scope and unresolved critical
  questions.

Main files:

- `specs/templates/architecture.md`
- `scripts/feature_validation.py`
- `.claude/agents/architect.md`

Main commit:

- `0a7c859 feat: add semantic gates and mutation capability`

### 31C Quality Gates Framework

A versioned framework of per-phase quality gates was added.

Implemented:

- Configuration in `state/quality-gates.json`.
- Phases: `implementation_fast`, `qa_full`, `finalization`, `optional_capability`.
- Compatibility with `scripts/verify_fast.sh` and `scripts/verify_full.sh` as
  defaults.
- Structured JSON evidence.
- Heavy logs outside Git in `artifact_root/quality-gates/<feature>/`.
- Blocking gates prevent advancing per phase:
  - `implementation_fast` blocks `READY_FOR_QA`.
  - `qa_full` prevents `APPROVED`.
  - `finalization` blocks `DONE`.
- Verification scripts hardened for non-interactive SSH sessions.

Main files:

- `scripts/quality_gates.py`
- `state/quality-gates.json`
- `scripts/complete_implementation.py`
- `scripts/complete_review.py`
- `scripts/finalize_feature.py`
- `scripts/verify_fast.sh`
- `scripts/verify_full.sh`

Main commits:

- `0a7c859 feat: add semantic gates and mutation capability`
- `d83012c fix: harden verification gates for noninteractive runs`
- `f596ef7 fix: locate uv in noninteractive verification`

### 31D-31E Mutation Capability

Deterministic mutation testing was implemented with its own runner, without an
external tool.

Implemented:

- Python runner in `scripts/mutation_runner.py`.
- Initial scope `changed_code`.
- Defaults:
  - `max_mutants: 100`
  - `max_duration_seconds: 600`
- Initial deterministic mutations:
  - booleans
  - comparators
  - simple arithmetic operators
  - logical operators
- The runner applies mutants, runs tests, restores files and classifies:
  - `killed`
  - `survived`
  - `invalid`
- Optional `mutation-testing` capability activatable per feature.
- `mutation-reviewer` agent authorized by the Leader.
- Agent budget in `state/agent-budgets.json`.
- Evidence validated by schema and a deterministic script.

Approval criterion:

- Zero relevant surviving mutants without justification.
- Any `test_gap` forces `CHANGES_REQUESTED`.

Main files:

- `scripts/mutation_runner.py`
- `scripts/mutation_review_validation.py`
- `specs/schemas/mutation-review.schema.json`
- `.claude/agents/mutation-reviewer.md`
- `state/agent-budgets.json`

Main commits:

- `0a7c859 feat: add semantic gates and mutation capability`
- `de957d3 feat: execute mutation tests deterministically`

### 31F End-To-End Validation And Template Extraction

The reusable template was created and validated with real projects.

Final template structure:

```text
agentic-sdd-template/
  core/
  profiles/
    generic/
    python/
    node/
  capabilities/
    mutation-testing/
    windows-validation/
  generator/
  tests/
  create_project.py
  project.example.yaml
```

Generator:

```bash
python3 create_project.py --config project.yaml
```

Validated projects:

- `/srv/agentic/workspace/test-generic-project`
- `/srv/agentic/workspace/test-python-project`
- `/srv/agentic/workspace/test-node-project`

Each project completed a real feature `F-001` up to `DONE`.

Special evidence:

- The generated Python project ran mutation testing with the result:
  - `generated: 1`
  - `killed: 1`
  - `survived: 0`
  - `invalid: 0`
- Mutation evidence:
  - `/srv/agentic/workspace/data/test-python-project/artifacts/mutation-tests/F-001/latest.json`
- Mutation review:
  - `/srv/agentic/workspace/test-python-project/evidence/mutation-reviews/F-001.json`

Main template commits:

- `036fa17 chore: initialize agentic sdd template`
- `cc607ad chore: sync template core with harness`
- `e4df145 feat: generate harness smoke tests for profiles`
- `faf7f23 feat: add node quality gates to generated projects`
- `52c35ef chore: sync mutation runner execution into core`

### CAP-009 Documentation Pack

The technical documentation of the generated projects was turned into a template
contract.

Implemented:

- `documentation-pack` capability active by default in the `generic`, `python`
  and `node` profiles.
- Base structure:
  - `docs/00-project/`
  - `docs/10-architecture/`
  - `docs/20-runtime/`
  - `docs/30-quality/`
  - `docs/40-operations/`
  - `docs/50-releases/`
  - `docs/90-generated/`
- Initial ADR `docs/10-architecture/adr/ADR-0001-template-baseline.md`.
- Profile-specific documentation:
  - `docs/20-runtime/python-environment.md`
  - `docs/20-runtime/node-environment.md`
- Additional documentation when `windows-validation` is active:
  - `docs/20-runtime/windows-runner.md`
  - `docs/30-quality/windows-validation.md`
- Regenerable scripts:
  - `scripts/generate_docs_index.py`
  - `scripts/refresh_project_docs.py`
  - `scripts/refresh_feature_index.py`
  - `scripts/refresh_quality_summary.py`
  - `scripts/refresh_metrics_summary.py`
- Versioned policy in `state/capabilities/documentation-pack.json`.
- Schema `specs/schemas/documentation-policy.schema.json`.

Decision:

- `docs/` contains living and stable project documentation.
- `specs/features/` keeps the traceability of features.
- `docs/90-generated/` is not a source of truth.
- A `technical-writer` agent is not added; each agent maintains the documentation
  that corresponds to its responsibility and the summaries are generated by
  deterministic scripts.

### CAP-010 Documentation Finalization Gate

Documentation enforcement was added at finalization.

Implemented:

- `acceptance.yaml` supports an optional block:
  - `requires_adr`
  - `requires_runtime_update`
  - `requires_operations_update`
  - `requires_quality_update`
- Schema updated in `specs/schemas/acceptance-v2.schema.json`.
- Template updated in `specs/templates/acceptance.yaml`.
- Deterministic validator `scripts/documentation_validation.py`.
- `scripts/finalize_feature.py` validates the diff between the `merge-base` and
  the QA-reviewed commit.
- If a documentation requirement is marked `true` and there is no corresponding
  change, the feature does not advance to `DONE`.

Requirement mapping:

- `requires_adr`: `docs/10-architecture/adr/*.md`
- `requires_runtime_update`: `docs/20-runtime/*.md`
- `requires_operations_update`: `docs/40-operations/*.md`
- `requires_quality_update`: `docs/30-quality/*.md`

## Tests Run

Source harness:

```bash
cd /srv/agentic/workspace/desktop-overlay-assistant
bash scripts/verify_full.sh
```

Final result:

- agent budget validation OK
- `compileall` OK
- `ruff check` OK
- `ruff format --check` OK
- `pytest`: `116 passed, 5 subtests passed`
- `git diff --check` OK

Template:

```bash
cd /srv/agentic/workspace/agentic-sdd-template
python3 -m unittest discover -s tests -v
```

Final result:

- `test_generates_generic_project`: OK
- `test_generates_python_project`: OK
- `test_generates_node_project`: OK
- `test_generates_pending_capability_policies`: OK
- `test_generates_documentation_pack_structure`: OK
- `test_refreshes_generated_documentation`: OK
- `test_generates_windows_validation_documentation`: OK
- `Ran 8 tests`: OK

Generated projects:

```bash
python3 scripts/project_status.py
```

Final result:

- `test-generic-project`: `F-001 DONE`
- `test-python-project`: `F-001 DONE`
- `test-node-project`: `F-001 DONE`

## Technical Decisions

- The initial bootstrap was allowed as the only direct operator commit.
- Subsequent maintenance must go through the harness itself.
- `change_domain` separates product, harness and template changes.
- Mutation testing uses its own deterministic runner to control scope,
  reproducibility and evidence.
- Quality gates keep compatibility with `verify_fast.sh` and `verify_full.sh`.
- Heavy logs stay in `artifact_root`; Git keeps small, reviewable evidence.
- Windows validation remains an optional capability, not a core dependency.
- Node is the first non-Python profile and uses `npm`, ESM and `node:test`.
- Remote Git publication is separated from `finalize_feature.py`: first it is
  integrated locally and then `repository-publisher` runs
  `scripts/publish_feature.py`.
- Role Guard blocks a direct `git push`; the real push can only happen inside the
  deterministic publication script.

## Capabilities Roadmap

This matrix turns the harness capabilities into a maintainable backlog. It
includes already closed capabilities, newly incorporated capabilities and
recommended extensions.

| ID | Capability | State | Priority | Result |
| --- | --- | --- | --- | --- |
| `CAP-001` | Quality Gates Framework | Completed | High | Versioned per-phase gates with structured evidence |
| `CAP-002` | External Runtime | Completed | High | local/manual-drop target, runner, validator, schema and evidence |
| `CAP-003` | Windows Validation | Completed | High | Policy, minimal runner, Windows evidence validated by schema and blocking when required |
| `CAP-004` | Performance Testing | Completed | Medium | Local runner with warmup, measurements, p95 and validator |
| `CAP-005` | Security Scanning | Completed | Medium | Deterministic scanner of secrets/sensitive files in observe mode |
| `CAP-006` | Mutation Testing | Completed | High | Deterministic Python runner with mutation reviewer |
| `CAP-007` | Template Generator | Completed | High | `generic`, `python`, `node` profiles generable and validated |
| `CAP-008` | Git Publish | Completed | High | local/remote publication audited via `repository-publisher` |

### 32A Git Publish Capability

Motivation:

The harness could already work with local Git: the implementers work in
worktrees, QA reviews feature branches and `finalize_feature.py` integrates into
the local canonical branch. An explicit, safe and auditable capability to publish
completed tasks to a remote was missing.

Implemented:

- New script `scripts/publish_feature.py`.
- New agent `repository-publisher`.
- New budget in `state/agent-budgets.json`.
- Role Guard recognizes `repository-publisher`.
- Role Guard blocks a direct `git push` and only allows publication via the
  script.
- `git_publication` configuration in `state/project.json`.
- The generator accepts the `git-publish` capability.
- The template generates `git_publication` in new projects.
- Unit tests cover local mode, push to a bare remote, rejection of non-`DONE`
  features and blocking of a direct `git push`.
- Operational run on a generated project:
  - project: `/srv/agentic/workspace/test-generic-project`
  - feature: `F-001`
  - result: `LOCAL_RECORDED`
  - evidence: `/srv/agentic/workspace/data/test-generic-project/artifacts/git-publish/F-001/latest.json`

Supported modes:

- `disabled`
- `local`
- `dry_run`
- `push`

Answer to the operational question:

Yes, the setup already works with local Git via branches, worktrees and
deterministic merges. With `git-publish`, it can also work with remote Git: a
specialized agent can push completed tasks to the configured repository, but not
via free commands, rather via an audited script that validates state, commit,
branch, repo cleanliness and remote.

### 32B External Runtime Capability

Implemented:

- Versioned policy `state/capabilities/external-runtime.json`.
- Schema `specs/schemas/external-runtime-result.schema.json`.
- Common helper `scripts/capability_common.py`.
- Runner `scripts/run_external_runtime.py`.
- Validator `scripts/validate_external_runtime_result.py`.
- `local` target for deterministic execution.
- `manual-drop` target to normalize external results.
- Unit tests in `tests/unit/test_capability_runners.py`.

Real smoke evidence:

- project: `/srv/agentic/workspace/test-capabilities-project`
- feature: `F-001`
- evidence: `/srv/agentic/workspace/data/test-capabilities-project/artifacts/capabilities/external-runtime/F-001/latest.json`
- state: `PASSED`

### 32B.1 Windows Validation Runner

Implemented:

- Versioned policy `state/capabilities/windows-validation.json`.
- Minimal runner `scripts/collect_windows_evidence.py`.
- Validator `scripts/validate_windows_evidence.py`.
- Schema `specs/schemas/windows-evidence.schema.json`.
- Finalization integration: `finalize_feature.py` blocks `DONE` if a feature
  requires Windows and valid evidence is missing.
- Unit tests in `tests/unit/test_windows_validation.py`.

Real smoke evidence:

- project: `/srv/agentic/workspace/test-capabilities-project`
- feature: `F-001`
- evidence: `/srv/agentic/workspace/data/test-capabilities-project/artifacts/windows-tests/F-001/latest.json`
- state: `PASS`
- note: run on Jarvis with `--allow-non-windows` to validate infrastructure; on a
  real Windows workstation the platform check needs no override.

### 32C Performance Testing Capability

Implemented:

- Versioned policy `state/capabilities/performance-testing.json`.
- Schema `specs/schemas/performance-result.schema.json`.
- Runner `scripts/run_performance_gate.py`.
- Validator `scripts/validate_performance_result.py`.
- Configurable warmup.
- Measured runs.
- Timeout.
- `min_ms`, `median_ms`, `p95_ms`, `max_ms` statistics.
- Initial `observe` mode.
- Unit tests in `tests/unit/test_capability_runners.py`.

Real smoke evidence:

- project: `/srv/agentic/workspace/test-capabilities-project`
- feature: `F-001`
- evidence: `/srv/agentic/workspace/data/test-capabilities-project/artifacts/capabilities/performance-testing/F-001/latest.json`
- state: `PASSED`

### 32D Security Scanning Capability

Implemented:

- Versioned policy `state/capabilities/security-scanning.json`.
- Schema `specs/schemas/security-result.schema.json`.
- Runner `scripts/run_security_scan.py`.
- Validator `scripts/validate_security_result.py`.
- Deterministic scanner of secrets and sensitive files.
- Redaction of sensitive samples.
- Initial `observe` mode.
- Unit tests in `tests/unit/test_capability_runners.py`.

Real smoke evidence:

- project: `/srv/agentic/workspace/test-capabilities-project`
- feature: `F-001`
- evidence: `/srv/agentic/workspace/data/test-capabilities-project/artifacts/capabilities/security-scanning/F-001/latest.json`
- state: `PASSED`

## Future Extensions Not Included In This Execution

These ideas are documented as later evolution, not as capabilities pending from
the current closure:

- Remote PR Publishing: create real PRs with a concrete provider when there is a
  remote repository and platform credentials.
- Release Tagging: tag milestones or releases when the template has a versioning
  policy.
- Additional profiles: `frontend`, `go`, `rust` according to real project demand.

## Residual State

There are no open blocks left from the original roadmap, the pending capabilities
document or `CAP-008 Git Publish`. The following steps are no longer closure of
the roadmap, but continuous improvement:

- Publish a template version/tag.
- Create more profiles (`go`, `rust`, `frontend`) if real projects appear.
- Extend mutation testing to more languages when there is a need.
- Add end-to-end example documentation with real output captures if it is to be
  used for onboarding.
- Implement `Remote PR Publishing` if opening pull requests is preferred over a
  direct push to the canonical branch.
```
