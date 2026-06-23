# Capability: Eval Harness

Optional capability to convert each `SCN-XXX` scenario of a feature into
executable *graders* and require their result as quality evidence. It closes the
`AC-XXX -> SCN-XXX -> grader -> evidence` traceability.

Inspired by the `eval-harness` pattern of `affaan-m/ECC` (MIT), reexpressed as a
deterministic artifact governed by harness scripts. Decision recorded in
`docs/adr-0002-eval-harness-verification-gate.md`.

## Activation

Per project:

```yaml
capabilities: [eval-harness]
```

Per feature:

```bash
python3 scripts/register_feature.py \
  --title "Harden parser scenarios" \
  --slug harden-parser-scenarios \
  --description "Anade graders ejecutables a los escenarios criticos." \
  --capability eval-harness
```

## Grader definition

Each feature declares its graders in `specs/features/<FEATURE>/evals.json`:

```json
{
  "schema_version": 1,
  "feature_id": "F-001",
  "graders": [
    {
      "id": "G-001",
      "scenario": "SCN-001",
      "type": "code",
      "command": ["python3", "-m", "pytest", "tests/test_parser.py", "-q"],
      "gate": true,
      "release_critical": true
    },
    {
      "id": "G-002",
      "scenario": "SCN-002",
      "type": "rule",
      "rule": {"kind": "file_contains", "path": "src/parser.py", "pattern": "def parse_hand"},
      "gate": true
    },
    {
      "id": "G-003",
      "scenario": "SCN-003",
      "type": "model",
      "rubric": "La salida explica el rango en lenguaje natural.",
      "gate": false
    }
  ]
}
```

Grader types:

- `code` -- runs a command; passes if the exit code is `0`. Eligible for gate.
- `rule` -- deterministic constraint over files. Eligible for gate.
- `model` -- LLM-as-judge with a rubric. Advisory, never decides the automatic gate.
- `human` -- manual adjudication. Advisory.

Supported `rule` rules (`kind`): `file_exists`, `file_contains` (with `pattern`
regex) and `file_absent`.

## Runner

```bash
python3 scripts/run_evals.py --feature F-001 --scope repository
```

Each eligible grader runs `runs` times (policy). `pass_at_k`
(at least one run passes) and `pass_caret_k` (all pass) are computed.

## Policy

`state/capabilities/eval-harness.json`:

- `mode`: `observe` (does not block) or `enforce` (blocks on failure).
- `runs`: repetitions per grader (default 1).
- `pass_at_k_min`: minimum ratio for capability graders.
- `require_pass_caret_k_for_release_critical`: requires `pass_caret_k = 1.00` on `release_critical` graders.
- `grader_timeout_seconds`: limit per `code` command.

## Evidence and validation

```text
artifact_root/capabilities/eval-harness/<feature>/latest.json
```

```bash
python3 scripts/validate_eval_result.py \
  --feature F-001 \
  --evidence <artifact_root>/capabilities/eval-harness/F-001/latest.json \
  --require-pass
```

Schema: `specs/schemas/eval-result.schema.json`.

## Approval rule

- In `enforce`, any eligible `code`/`rule` grader that does not pass produces
  `status=FAILED` and returns exit code 2.
- `release_critical` graders require `pass_caret_k = 1.00` when
  `require_pass_caret_k_for_release_critical` is active.
- `model`/`human` graders are recorded as `SKIPPED` advisory and never block.
- An `SCN-XXX` scenario without at least one `code` or `rule` grader is reported in
  `unverifiable_scenarios`.
