# CLAUDE.md - Agent Context Router

This file is a router, not the source of truth. It tells agents which contract
or project document to read for the current question. Do not duplicate
authoritative content here.

## Always Load

Read these before acting:

1. `AGENTS.md`
2. `docs/architecture/harness-contract.md`
3. `state/project.json`
4. `state/workflow.json`
5. The active agent definition in `.claude/agents/`
6. The assigned feature files under `specs/features/<FEATURE>/`

## Where To Look

| Question | Read |
| --- | --- |
| What is the operational contract? | `docs/architecture/harness-contract.md` |
| Which files can my role edit? | `docs/architecture/role-guard.md` and `.claude/agents/<role>.md` |
| How do feature states advance? | `state/workflow.json` and `docs/architecture/finalization-contract.md` |
| What is the product or project scope? | `docs/00-project/overview.md`, `docs/00-project/goals-and-scope.md` |
| What domain terms should agents use? | `docs/00-project/glossary.yaml` and `docs/00-project/glossary.md` |
| What architecture is accepted? | `docs/10-architecture/architecture-overview.md` and `docs/10-architecture/adr/` |
| How do I run or configure this project? | `docs/20-runtime/local-development.md` and `docs/20-runtime/configuration.md` |
| What quality gates apply? | `state/quality-gates.json` and `docs/30-quality/quality-gates.md` |
| Which capabilities are enabled? | `state/capabilities/*.json` and capability docs under `docs/30-quality/` or `docs/20-runtime/` |
| How do I operate or recover the harness? | `docs/40-operations/runbook.md` and `docs/40-operations/troubleshooting.md` |
| Where is the active feature truth? | `specs/features/<FEATURE>/specification.md`, `acceptance.yaml`, `architecture.md` |
| Where are lightweight evidences? | `evidence/` |
| Where are heavy artifacts? | The configured `artifact_root` in `state/project.json` |
| Where is external control state? | The configured `control_root` in `state/project.json` |

## Context Budget

| Class | Load Policy | Examples |
| --- | --- | --- |
| Always loaded | Small contracts required before action | `AGENTS.md`, this router, active agent file, active feature spec |
| On demand | Read only when the task touches the topic | architecture docs, runtime docs, quality docs, operations docs, ADRs |
| Machine context | Parse or summarize, do not read exhaustively | `state/*.json`, `state/capabilities/*.json`, schemas |
| Human first | Use for orientation, not as operational truth | changelog, release notes, generated summaries |

`docs/90-generated/` is regenerated context and is not authoritative. If it
conflicts with `state/`, `specs/`, control state or Git, trust the latter.

## Priority

When documents conflict, apply this order:

1. `docs/architecture/harness-contract.md`
2. Active agent definition
3. `AGENTS.md`
4. Active feature specification and acceptance criteria
5. Project documentation under `docs/`
6. Generated summaries under `docs/90-generated/`
