# Capability: Performance Testing

Optional capability to measure repeatable commands and generate performance evidence without mixing it with functional tests.

## MVP Scope

- Versioned policy in `state/capabilities/performance-testing.json`.
- Local runner for repeated commands.
- Optional warmup.
- Measurement with a monotonic clock.
- Per-run timeout.
- Statistics `min_ms`, `median_ms`, `p95_ms`, `max_ms`.
- Deterministic validator.
- Evidence in `artifact_root/capabilities/performance-testing/<feature>/`.

## Usage

```bash
python3 scripts/run_performance_gate.py \
  --feature F-001 \
  --benchmark python-smoke \
  --measured-runs 3
```

Validation:

```bash
python3 scripts/validate_performance_result.py \
  --feature F-001 \
  --evidence <artifact_root>/capabilities/performance-testing/F-001/latest.json \
  --require-pass
```

## Status

Initial mode: `observe`. In `observe`, an exceeded budget is recorded without blocking unless the policy moves to `enforce`.
