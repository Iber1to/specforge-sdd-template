# Capability: External Runtime

Optional capability to run or validate jobs outside the harness's main runtime while keeping evidence centralized.

## MVP Scope

- Versioned policy in `state/capabilities/external-runtime.json`.
- `local` target for deterministic commands.
- `manual-drop` target to normalize external results.
- Runner: `scripts/run_external_runtime.py`.
- Validator: `scripts/validate_external_runtime_result.py`.
- Evidence in `artifact_root/capabilities/external-runtime/<feature>/`.

## Usage

The only execution mode is to select a command template declared in the
target's policy (`allowed_command_templates`) via `--command-id`. There is no
free-form command execution.

```bash
python3 scripts/run_external_runtime.py \
  --feature F-001 \
  --target local \
  --command-id python-version
```

Validation:

```bash
python3 scripts/validate_external_runtime_result.py \
  --feature F-001 \
  --evidence <artifact_root>/capabilities/external-runtime/F-001/latest.json \
  --require-pass
```

## Status

Initial mode: `observe`.

The SSH adapter is left as a future extension. The MVP already covers the `request -> execute/collect -> validate` contract with the local and manual-drop targets.
