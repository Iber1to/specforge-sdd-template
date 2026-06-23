# Capability: Mutation Testing

Optional capability to require mutation testing on selected features.

## Activation

Per feature:

```bash
python3 scripts/register_feature.py \
  --title "Improve critical logic" \
  --slug improve-critical-logic \
  --description "Endurece logica critica y sus tests." \
  --capability mutation-testing
```

## Runner

```bash
python3 scripts/mutation_runner.py \
  --feature F-001 \
  --output /srv/agentic/workspace/data/<project_id>/artifacts/mutation-tests/F-001/latest.json \
  --max-mutants 100 \
  --max-duration-seconds 600 \
  --test-command python3 -m pytest -q
```

## Current Scope

- Language: Python.
- Scope: changed code.
- Mutations:
  - booleans
  - comparators
  - simple arithmetic operators
  - logical operators

## Evidence

Runner artifact:

```text
artifact_root/mutation-tests/<feature>/latest.json
```

Review:

```text
evidence/mutation-reviews/<feature>.json
```

## Approval Rule

- Zero relevant surviving mutants without justification.
- Any `test_gap` forces `CHANGES_REQUESTED`.
- Evidence must validate against `specs/schemas/mutation-review.schema.json`.
