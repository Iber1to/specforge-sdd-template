# Agentic harness operational contract

## 1. Objective

This contract defines the mandatory rules for coordination, writing,
verification and finalization of the agentic system.

The rules described here take precedence over any instruction generated
during a session.

## 2. Sources of truth

| Information | Source of truth |
|---|---|
| Project configuration | `state/project.json` |
| Flow and allowed transitions | `state/workflow.json` |
| Active queue and feature state | `<control_root>/queue.json` |
| Active assignments | `<control_root>/leases/` |
| Active and historical runs | `<control_root>/runs/` |
| Specifications and code | Git repository |
| Heavy artifacts | `<artifact_root>/` |

Agents must not directly edit control plane files.
Every modification must be made through deterministic scripts.

## 3. Mandatory invariants

1. At most one active implementer may exist.
2. A feature may only have one active writer agent.
3. Each implementation is carried out in an independent branch and worktree.
4. No agent may manually change a feature's state.
5. No agent may mark a feature as `DONE`.
6. Only `scripts/finalize_feature.py` may perform the transition to `DONE`.
7. A feature cannot enter development without a specification, architecture,
   acceptance criteria and test plan.
8. A feature cannot be approved with failing verifications.
9. A feature that requires the Windows runtime cannot finalize without valid
   evidence from the Windows Test Runner.
10. Heavy artifacts are not stored inside the Git repository.

## 4. Responsibilities

### Leader

- Queries the control plane.
- Selects and delegates work.
- Launches specialized agents.
- Requests transitions through scripts.
- Does not write specifications, architecture, code or tests.
- Does not approve or finalize features.

### Specifier

- Writes exclusively the functional specification and the acceptance criteria.
- Does not design architecture.
- Does not write code.
- Does not change states directly.

### Architect

- Writes architecture, implementation plan and test plan.
- Does not implement code.
- Does not change states directly.

### Implementer

- Works exclusively within the assigned worktree.
- Implements a single feature.
- Writes code, tests and implementation evidence.
- Does not call other agents.
- Does not approve its own work.
- Does not change states directly.

### QA Reviewer

- Works in read mode over code and specifications.
- Runs the allowed verifications.
- Writes exclusively the review report.
- Does not fix code.
- Does not change states directly.

## 5. File ownership

| Area | Authorized writer |
|---|---|
| `specs/features/<feature>/specification.md` | Specifier |
| `specs/features/<feature>/acceptance.yaml` | Specifier |
| `specs/features/<feature>/architecture.md` | Architect |
| `specs/features/<feature>/implementation-plan.md` | Architect |
| `specs/features/<feature>/test-plan.md` | Architect |
| `src/`, `tests/` and `runtime/external/` | Implementer |
| `pyproject.toml` and `uv.lock` | Implementer, when required by the design |
| `evidence/implementations/` | `complete_implementation.py`, invoked by Implementer |
| `evidence/reviews/` | `complete_review.py`, invoked by QA Reviewer |
| External control plane | Deterministic scripts |
| Transition to `DONE` | `finalize_feature.py` |

## 6. Evidence required to finalize

A feature may only finalize when the following exist:

- Validated specification.
- Validated architecture.
- Verifiable acceptance criteria.
- Test plan.
- Versioned implementation.
- Correct related tests.
- Correct full Linux suite.
- QA verdict `APPROVED`.
- Correct Windows evidence when required.
- Repository and worktree with no pending changes.

## 7. Performance policy

- Fast verifications run during development.
- Related tests run when the implementation is completed.
- The full suite runs before final approval.
- Windows tests run only when the feature requires them.
- Extensive information is transmitted through files, not through complete
  messages between agents.
