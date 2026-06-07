# Changelog

All notable changes to `agentic-sdd-template`. Format loosely follows Keep a
Changelog; the project uses Conventional Commits.

## [v1.0-internal] - 2026-06-07

First internal release. The template generates projects with a working
Spec-Driven Development harness (roles, durable control plane, Role Guard,
quality gates, optional capabilities) and is hardened for internal use.

### Scope

- **Stable**: profiles `generic`, `python`, `node`; the SDD workflow, Role Guard,
  quality gates and control plane; capabilities `documentation-pack`,
  `mutation-testing` (python), `performance-testing`, `security-scanning`,
  `git-publish`, `external-runtime`.
- **Experimental**: `windows-validation` — code is ready and covered offline
  (`collect --allow-non-windows` + `validate`), but not yet validated on a real
  Windows host. Follow `docs/real-validation-runbook.md`.
- **Platform**: Linux host for orchestration; Windows only as the optional
  `windows-validation` runner.

### Security and correctness

- Lease recovery blocks orphaned QA features (not only `IN_PROGRESS`) and keeps
  the control plane consistent.
- Portable file locking (POSIX `fcntl` / Windows `msvcrt`) so the Windows
  evidence runner can import the core modules.
- Role Guard: per-segment Bash allowlist (closes the command-chaining bypass),
  repo-local `control_root` fallback (not `/tmp`), and main-session role taken
  from `CLAUDE_HARNESS_ROLE` (Claude Code reports `--agent leader` as
  `agent_type: "claude"`).
- `external-runtime`: only declared command templates via `--command-id`; the
  free-command path was removed entirely.
- Windows evidence CLI no longer crashes on a string `artifact_root`.

### Generator and template

- Generated projects start clean (no `.venv`/caches), enforced by a test.
- `windows-validation` decoupled: project-level `windows_validation_available`
  (capability installed) vs per-feature `windows_validation_required` (opt-in).
- Hooks run via `scripts/hook_entrypoint.sh` (resolves the interpreter, fails
  closed); `settings.json` no longer calls `python3` directly.
- New `scripts/check_environment.py` preflight.
- Minimal harness test suite generated under `tests/harness/`.
- `docs/profile-capability-matrix.md`; `legacy_v1_features` empty in generated
  projects.

### Capabilities

- `git-publish`: richer audited evidence (`source_branch`, `remote_url_hash`,
  `started_at`/`completed_at`); credentials redacted; push to a local bare remote
  is tested.
- `mutation-testing`: scoped to the reviewed diff, refuses a dirty worktree, and
  excludes test files.
- `performance-testing`: per-benchmark baselines with base commit and an explicit
  `--update-baseline`.
- `security-scanning`: baseline classification (accepted / false_positive /
  risk_accepted / fixed) with optional expiry; per-profile adapters (Python
  `eval`/`exec`/`pickle`/`os.system`/`shell=True`; Node lifecycle hooks).
- SSH adapter hardened (`BatchMode`/`ConnectTimeout`); offline coverage plus a
  real-validation runbook for Windows and SSH hardware.

### Operations

- Persistent leader launcher `scripts/run_leader.sh` (tmux) with
  `CLAUDE_HARNESS_ROLE=leader`.
- Semi-automatic operation via an autonomous standing prompt
  (`docs/leader-operation.md`).
- `docs/zero-to-hero.md`: end-to-end operation manual from GitHub clone to
  semi-automatic running.
- Platform requirements and offline Python/`uv` guidance.

### Documentation

- Added: Zero to Hero, leader operation, real-validation runbook, profile x
  capability matrix, language-and-style and naming-and-contracts conventions.

### Tests

- 48 template tests (`tests/test_generator.py`), plus 9 harness tests run inside
  every generated project via `verify_full.sh`.

### Known follow-ups (non-blocking for v1)

- Unify the `status` vocabulary `PASS`/`PASSED` (documented in
  `docs/naming-and-contracts.md`).
- Real Windows and real SSH validation on hardware (runbook provided).
- Level 3 unattended operation: headless driver (Claude Agent SDK) as a `systemd`
  service.
- P3 backlog: ESLint/Prettier (node), Docker external runtime, optional MCP
  integrations, metrics dashboards.
