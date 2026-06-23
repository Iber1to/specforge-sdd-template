# Claude Code Role Guard

## Objective

The Role Guard materially enforces each agent's restrictions through
deterministic Claude Code hooks.

Agent instructions guide behavior; the Role Guard prevents unauthorized
operations before they run.

## Installed hooks

### SessionStart

Records the role of the main session. Claude Code reports the main session
as `agent_type: "claude"` (it does not pass `--agent leader` to the hook), so the
role is taken from the `CLAUDE_HARNESS_ROLE` environment variable, set by the operator
when launching:

```bash
CLAUDE_HARNESS_ROLE=leader claude --agent leader
```

Sessions without that variable are classified as `unscoped` and cannot
use mutating tools. Subagents are identified by their `agent_type`
and do not depend on this variable.

### PreToolUse

Intercepts mutating tools before they run:

- `Write`
- `Edit`
- `Bash`
- `Agent`
- team, workflow and worktree tools not controlled by the harness

A block returns exit code `2`; Claude Code cancels the call even in
`bypassPermissions`.

### ConfigChange

Blocks changes to project settings or local settings during a protected
session.

## Per-role policies

### Leader

- May query state and run deterministic orchestration scripts.
- May launch only `specifier`, `architect`, `implementer` and
  `qa-reviewer`.
- May not write directly through `Write` or `Edit`.
- May only add to Git documents under `specs/features/`.

### Specifier

May only write:

- `specification.md`
- `acceptance.yaml`

of features that are in `DRAFT` state.

### Architect

May only write:

- `architecture.md`
- `implementation-plan.md`
- `test-plan.md`

of features that are in `SPEC_READY` or `DESIGN_READY` state.

### Implementer

- Must have exactly one active lease.
- May only write within the assigned worktree.
- In `change_domain=product`, its base writes are `src/`, `tests/`,
  `runtime/external/`, `pyproject.toml` and `uv.lock`, plus the feature
  documentation subtrees `docs/10-architecture/adr/`, `docs/20-runtime/`,
  `docs/30-quality/` and `docs/40-operations/` (those required by
  `documentation_validation` when the feature declares `requires_*`). The rest of
  `docs/` is outside the product scope.
- The policy is **profile-aware** (it reads `profile` from `state/project.json`): the
  `android` profile adds the `app/` module, the `gradle/` wrapper and the root
  Gradle files (`settings.gradle.kts`, `build.gradle.kts`, `gradle.properties`).
- In `change_domain=harness` it may write the harness subtrees
  (`.claude/`, `docs/`, `scripts/`, `specs/`, `state/`, `tests/`) and
  `AGENTS.md`/`CLAUDE.md`/`pyproject.toml`/`uv.lock`.
- Bash is limited to the worktree and to an allowlist of development commands.
- May only run the harness's `heartbeat_lease.py` and `complete_implementation.py`.

### QA Reviewer

- May not write directly.
- Must have exactly one active QA lease.
- Bash is limited to reads, verifications, `heartbeat_lease.py` and
  `complete_review.py`.

## Auditing

Decisions are recorded in:

`<control_root>/role-guard/audit.jsonl`

Session-to-role associations are stored in:

`<control_root>/role-sessions/`

## Manual validation

After installing:

```bash
uv run pytest -q tests/unit/test_role_guard.py
./scripts/verify_full.sh
```

When starting Claude Code:

```bash
CLAUDE_HARNESS_ROLE=leader claude --agent leader
```

Inside the session, use `/hooks` to confirm that the project
`SessionStart`, `PreToolUse` and `ConfigChange` hooks appear.
