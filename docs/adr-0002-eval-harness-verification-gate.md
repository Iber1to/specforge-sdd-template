---
owner: alejandro
last_verified: 2026-06-21
---

# ADR-0002 - Eval-Harness as a traceable verification gate

## Status

Accepted

## Context

The harness feature contract already produces traceable acceptance criteria
`AC-XXX` and structured scenarios `SCN-XXX` (`acceptance.yaml`,
`schema_version: 2`). However, those scenarios are today a **documentary
contract**: they describe `given`/`when`/`then`, but are not executed. Effective
verification relies on the human reading of QA and on the generic quality gates,
without a machine-checkable link between each `SCN-XXX` and a check that passes
or fails deterministically.

This leaves a gap in the traceability chain:

`AC-XXX` (what) → `SCN-XXX` (how it is observed) → **?** (how it is checked)

The `eval-harness` pattern of the external project `affaan-m/ECC` (MIT) has been
evaluated. Its two useful contributions are (1) a taxonomy of *graders* and (2)
the `pass@k` / `pass^k` metrics as a release threshold. The ECC operational loop
(`verification-loop`) is written as prose for the LLM and is non-deterministic;
**it is not adopted as-is**. What is incorporated is the model of graders and
metrics, re-expressed as a deterministic template capability, consistent with the
rest of the capabilities (`security-scanning`, `performance-testing`, etc.).

Harness constraints that this decision must respect:

- State transitions go through deterministic scripts.
- The role-guard limits which files each role edits.
- Lightweight evidence lives in `evidence/`; heavy artifacts in `artifact_root`.
- Capabilities are modular and activated per project
  (`state/capabilities/*.json`), installed by `create_project.py` via
  `manifest.json`.

## Decision

Introduce an `eval-harness` capability that converts each `SCN-XXX` into one or
more executable *graders* and requires their result as gate evidence.

1. **Modular capability.** New capability `eval-harness` with its directory
   `capabilities/eval-harness/` (manifest, runner, validator, schema and
   policy), registered in `create_project.py` (`CAPABILITIES`) and in
   `register_feature.py` (`--capability`). Inactive by default.

2. **Grader taxonomy.** Four types, two eligible for gate and two advisory only:
   - `code` — runs a command; passes if exit code `0`. **Gate.**
   - `rule` — deterministic constraint over files (exists / contains regex /
     absent). **Gate.**
   - `model` — LLM-as-judge with a rubric. **Advisory, never blocks the
     automatic gate.**
   - `human` — manual adjudication. **Advisory.**

   Only `code` and `rule` decide an automatic transition. This preserves the
   determinism of the harness.

3. **Definition alongside the feature.** Each grader is declared in
   `specs/features/<FEATURE>/evals.json`, referencing the `SCN-XXX` it
   verifies. A scenario without at least one `code` or `rule` grader is reported
   as non-verifiable.

4. **Metrics and thresholds (via policy).**
   - `runs` repetitions per grader; `pass_at_k` (at least one passes) and
     `pass_caret_k` (all pass).
   - `pass_at_k_min` for capability criteria.
   - `require_pass_caret_k_for_release_critical` requires `pass_caret_k = 1.00`
     for graders marked `release_critical`.

5. **Gate and evidence.** The runner `run_evals.py` runs the eligible graders
   and deposits normalized evidence in
   `artifact_root/capabilities/eval-harness/<feature>/latest.json`, validated by
   `validate_eval_result.py` against `specs/schemas/eval-result.schema.json`. The
   quality gate `EVAL-001` is installed in the `qa_full` phase, in `observe` mode
   by default.

The 6-phase loop of `verification-loop` (build, typecheck, lint,
test+coverage, security, diff) **does not enter this ADR**: fast verification is
already covered by `verify_fast.sh` / `verify_full.sh` and the existing
capabilities; mixing them would be another decision.

## Consequences

- Traceability closes end to end:
  `AC-XXX → SCN-XXX → executable grader → evidence`.
- The quality gate becomes deterministic and reproducible, aligned with the
  capabilities model and script-based transitions.
- The `release_critical` graders with `pass_caret_k = 1.00` protect the critical
  paths.
- Authoring cost: each verifiable scenario requires at least one `code` or `rule`
  grader; it increases the work of the `specifier`/`architect`.
- New surface to maintain: runner, validator, schema, policy and the registration
  block in the generator and its tests.
- Risk of non-determinism if `model`/`human` graders were used in the gate;
  mitigated by design by excluding them from the automatic decision.

## Alternatives Considered

- **Adopt ECC's `verification-loop` as-is.** Rejected: it is prose for the LLM,
  depends on the model's judgment and reintroduces non-determinism into the gate.
- **Adopt ECC's instincts / continuous-learning system.** Rejected: it mutates
  the agent's behavior after the fact and breaks the reproducibility that
  sustains the specification-driven flow.
- **Leave `SCN-XXX` as a documentary-only contract.** Rejected: it keeps the
  verification gap and leaves acceptance to non-traceable human reading.
- **Graders embedded in the project's tests without a capability.** Rejected: it
  breaks modularity and per-project activation.

## Related Features

Implementation delivered as the template's `eval-harness` capability:
`capabilities/eval-harness/` (manifest, `run_evals.py`,
`validate_eval_result.py`, `eval-result.schema.json`, policy), registration in
`create_project.py` and `register_feature.py`, documentation in
`docs/quality-and-capabilities.md` and `docs/profile-capability-matrix.md`, and an
E2E test in `tests/test_generator.py`. Capability source: `affaan-m/ECC`
(`skills/eval-harness/SKILL.md`), adapted to deterministic execution.
