# AGENTS.md — Navigation map

## Mandatory initial reading

1. `docs/architecture/harness-contract.md`
2. `state/project.json`
3. `state/workflow.json`
4. The documents specific to the assigned feature.

## Fundamental rules

- Do not edit the configured `control_root` directly.
- Do not manually change feature states.
- Do not mark any feature as `DONE`.
- Do not work outside the assigned worktree.
- Do not assume write permissions outside your responsibility.
- In case of contradictions, apply `docs/architecture/harness-contract.md`.

## Repository map

| Path | Purpose |
|---|---|
| `.claude/agents/` | Agent definitions |
| `.claude/commands/` | Operational commands |
| `specs/product/` | Vision and global requirements |
| `specs/features/` | Per-feature specifications |
| `state/` | Workflow configuration and definition |
| `evidence/` | Versioned lightweight reports |
| `docs/` | Architecture, conventions and decisions |
| `scripts/` | Deterministic operations |
| `src/` | Application code |
| `tests/` | Automated tests |
| `runtime/` | Optional adapters and runtimes |
