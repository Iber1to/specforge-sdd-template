# Quality Gates And Capabilities

This document summarizes the gates and optional capabilities of the template.

## Quality Gates

The versioned configuration lives in:

```text
state/quality-gates.json
```

Base example:

```json
{
  "schema_version": 1,
  "gates": [
    {
      "id": "GATE-001",
      "phase": "implementation_fast",
      "command": ["bash", "scripts/verify_fast.sh"],
      "blocking": true,
      "timeout_seconds": 900
    }
  ]
}
```

Fields:

- `id`: stable identifier.
- `phase`: phase where it runs.
- `command`: command as a list of strings.
- `blocking`: if `true`, a failure blocks the transition.
- `timeout_seconds`: execution limit.

## Phases

`implementation_fast`:

- Runs when implementation is completed.
- Blocks `READY_FOR_QA` if a blocking gate fails.
- Default: `bash scripts/verify_fast.sh`.

`qa_full`:

- Runs when QA is completed.
- Prevents `APPROVED` if a blocking gate fails.
- Default: `bash scripts/verify_full.sh`.

`finalization`:

- Runs before finalizing.
- Blocks `DONE` if a blocking gate fails.
- Default: `bash scripts/verify_full.sh`.

`optional_capability`:

- Reserved for capabilities that have their own checks.
- Can be used for mutation testing or other future capabilities.

## Gate Evidence

Each run produces:

- structured JSON evidence
- a full stdout/stderr log

Location:

```text
artifact_root/quality-gates/<feature>/<run>-<phase>.json
artifact_root/quality-gates/<feature>/<run>-<phase>-<gate>.log
```

States:

- `PASS`: all gates passed.
- `WARN`: non-blocking gates failed.
- `FAIL`: at least one blocking gate failed.

## Capability: Mutation Testing

Activation per feature:

```bash
python3 scripts/register_feature.py \
  --title "Improve parser checks" \
  --slug improve-parser-checks \
  --description "Endurece parser y tests." \
  --capability mutation-testing
```

Runner:

```bash
python3 scripts/mutation_runner.py \
  --feature F-001 \
  --output /path/to/artifacts/mutation-tests/F-001/latest.json \
  --max-mutants 100 \
  --max-duration-seconds 600 \
  --test-command python3 -m pytest -q
```

Initial scope:

- Python.
- Changed code.
- Deterministic mutations of booleans, comparators, simple arithmetic operators
  and logical operators.

Output:

- `generated`
- `killed`
- `survived`
- `invalid`
- list of mutants with location, operator and result

Review:

- Agent: `mutation-reviewer`.
- Evidence: `evidence/mutation-reviews/<feature>.json`.
- Schema: `specs/schemas/mutation-review.schema.json`.
- Validator: `scripts/mutation_review_validation.py`.

Blocking rule:

- If there is a `test_gap`, QA must emit `CHANGES_REQUESTED`.
- If relevant mutants survive without justification, it must not be approved.

## Capability: External Runtime

Project or feature activation:

```yaml
capabilities: [external-runtime]
```

Runner:

```bash
python3 scripts/run_external_runtime.py \
  --feature F-001 \
  --target local \
  --command-id python-version
```

Validator:

```bash
python3 scripts/validate_external_runtime_result.py \
  --feature F-001 \
  --evidence <artifact_root>/capabilities/external-runtime/F-001/latest.json \
  --require-pass
```

The MVP includes the `local` and `manual-drop` targets. SSH remains a future
extension.

## Capability: Performance Testing

Activation:

```yaml
capabilities: [performance-testing]
```

Runner:

```bash
python3 scripts/run_performance_gate.py \
  --feature F-001 \
  --benchmark python-smoke \
  --measured-runs 3
```

Produces `min_ms`, `median_ms`, `p95_ms` and `max_ms` statistics. The initial
mode is `observe`; `enforce` can block once critical benchmarks stabilize.

## Capability: Security Scanning

Activation:

```yaml
capabilities: [security-scanning]
```

Runner:

```bash
python3 scripts/run_security_scan.py --feature F-001
```

The MVP detects secrets by regex, sensitive files such as `.env`, private keys
and common tokens. It redacts sensitive samples in the evidence.

## Capability: Eval Harness

Activation:

```yaml
capabilities: [eval-harness]
```

Goal:

- convert each feature's `SCN-XXX` scenario into executable graders
- close the `AC-XXX -> SCN-XXX -> grader -> evidence` traceability
- decide the quality gate deterministically, without depending on the model's
  judgment

Definition of graders per feature:

```text
specs/features/<FEATURE>/evals.json
```

Grader types:

- `code`: runs a command; passes if the exit code is `0`. Eligible for gate.
- `rule`: deterministic constraint over files (`file_exists`, `file_contains`,
  `file_absent`). Eligible for gate.
- `model`: LLM-as-judge with a rubric. Advisory, never decides the automatic
  gate.
- `human`: manual adjudication. Advisory.

Runner:

```bash
python3 scripts/run_evals.py --feature F-001 --scope repository
```

Each eligible grader runs `runs` times (policy). `pass_at_k` (at least one run
passes) and `pass_caret_k` (all pass) are computed.

Validator:

```bash
python3 scripts/validate_eval_result.py \
  --feature F-001 \
  --evidence <artifact_root>/capabilities/eval-harness/F-001/latest.json \
  --require-pass
```

Policy:

```text
state/capabilities/eval-harness.json
```

Fields:

- `mode`: `observe` (does not block) or `enforce` (blocks on failure).
- `runs`: repetitions per grader (default 1).
- `pass_at_k_min`: minimum ratio for capability graders.
- `require_pass_caret_k_for_release_critical`: requires `pass_caret_k = 1.00` for
  `release_critical` graders.
- `grader_timeout_seconds`: limit per `code` command.

Gate:

- `EVAL-001` in the `qa_full` phase, `observe` mode by default.
- In `enforce`, any eligible `code`/`rule` grader that does not pass produces
  `FAILED`.
- `model`/`human` graders are recorded as advisory `SKIPPED` and do not block.

Evidence schema: `specs/schemas/eval-result.schema.json`. Decision:
`docs/adr-0002-eval-harness-verification-gate.md`. Capability source:
`affaan-m/ECC` (`skills/eval-harness/SKILL.md`), adapted to deterministic
execution.

## Capability: Tool Telemetry

Activation:

```yaml
capabilities: [tool-telemetry]
```

Goal:

- record each tool call (`PreToolUse`/`PostToolUse`) as a deterministic JSONL
  line (telemetry/evidence of which tools each role uses)
- redact secrets before persisting
- feed auditing and observability without altering the agents' behavior

It is neither a gate nor does it learn patterns: it is the substrate layer
(hooks -> JSONL) inspired by the continuous-learning of `affaan-m/ECC`. The
self-learned "instincts" engine was deliberately discarded for being contrary to
SDD determinism.

Hook wiring:

- `core/.claude/settings.json` wires `PreToolUse` (matcher `""`) and
  `PostToolUse` to `hook_entrypoint.sh tool_telemetry`.
- If the capability is not installed, the hook is **no-op** (it does not break
  the project).
- Script: `scripts/tool_telemetry_hook.py` (fail-soft: always exit 0).

Policy:

```text
state/capabilities/tool-telemetry.json
```

Fields:

- `enabled`: enables/disables the capture.
- `scrub_secrets`: redacts api_key/token/secret/password/private keys/AWS.
- `max_value_chars`: truncates long `tool_input`/`tool_response`.

Evidence:

```text
artifact_root/capabilities/tool-telemetry/observations-<YYYYMMDD>.jsonl
```

Each line includes `timestamp`, `event`, `tool`, `session`, `agent` and, if they
exist, redacted and truncated `tool_input`/`tool_response`.

## Capability: Windows Validation

Project activation:

```yaml
capabilities: [windows-validation]
```

Effect:

- `state/project.json` marks `windows_validation_available`.
- The requirement for Windows evidence is per feature, not global.
- The project keeps scripts and schemas to validate Windows evidence.

Main files:

- `scripts/collect_windows_evidence.py`
- `scripts/windows_validation.py`
- `scripts/validate_windows_evidence.py`
- `specs/schemas/windows-evidence.schema.json`
- `docs/windows-runner/evidence-contract.md`

Windows validation is optional in the core template. It does not block projects
that do not enable it.

Minimal runner:

```bash
python3 scripts/collect_windows_evidence.py --feature F-001 --commit <commit>
```

On Jarvis an infrastructure smoke can be run with `--allow-non-windows`; on real
Windows the platform check must pass without an override.

## Capability: Documentation Pack

Activation:

```yaml
capabilities: [documentation-pack]
```

This capability is active by default in all generated profiles.

Goal:

- create a minimal technical structure under `docs/`
- separate stable documentation from per-feature specs
- document runtime, architecture, quality, operations and releases
- regenerate indexes and derived summaries in `docs/90-generated/`

Scripts:

```bash
python3 scripts/refresh_project_docs.py
python3 scripts/generate_docs_index.py
python3 scripts/refresh_feature_index.py
python3 scripts/refresh_quality_summary.py
python3 scripts/refresh_metrics_summary.py
```

Policy:

```text
state/capabilities/documentation-pack.json
specs/schemas/documentation-policy.schema.json
```

Authority rule:

- `docs/90-generated/` is not a source of truth.
- The source of truth remains `state/`, `control_root`, `specs/features/`,
  `evidence/` and Git.

Finalization gate:

`acceptance.yaml` can declare documentation requirements:

```yaml
documentation:
  requires_adr: true
  requires_runtime_update: false
  requires_operations_update: true
  requires_quality_update: false
```

`scripts/finalize_feature.py` validates the QA-reviewed changes before
integrating the feature. If a documentation requirement is marked `true` and the
reviewed diff does not contain the corresponding document, the feature does not
move to `DONE`.

## Capability: Git Publish

Project activation:

```yaml
capabilities: [git-publish]
git_publish_mode: local
git_publish_remote: origin
git_publish_branch: main
git_publish_auto: false
```

Goal:

- register or publish already finalized features (`DONE`) to local or remote Git
- prevent direct `git push` from agents
- store audited evidence of the publication

Script:

```bash
uv run python scripts/publish_feature.py --feature F-001
```

Agent:

- `repository-publisher`

Modes:

- `local`: records that the local merge was integrated.
- `dry_run`: validates the remote push with `git push --dry-run`.
- `push`: pushes `HEAD` to `refs/heads/<branch>` of the configured remote.
- `disabled`: does not publish.

Evidence:

```text
artifact_root/git-publish/<feature>/<operation>.json
artifact_root/git-publish/<feature>/latest.json
```

Blocking rules:

- The feature must be in `DONE`.
- The canonical repo must be clean.
- The feature's `merged_commit` must belong to `HEAD`.
- By default, `merged_commit` must be exactly `HEAD` to avoid accidentally
  publishing later commits.
- `dry_run` and `push` require an existing Git remote.

## Capability: Remote Notifications

Project activation:

```yaml
capabilities: [remote-notifications]
```

Goal:

- alert via Telegram when the leader stops, blocks a feature or completes the
  work (`scripts/notify.py`, instructed in `leader.md`)
- a deterministic safety net via Claude Code `Stop`/`Notification` hooks
  (`scripts/notify_hook.py` through `hook_entrypoint.sh notify`; no-op if the
  capability is not installed)
- an optional bidirectional gateway (`scripts/telegram_gateway.py`): `/status`,
  `/tail` and free text injected as a prompt into the leader's tmux session

Explicit notification:

```bash
uv run python scripts/notify.py --event blocked --feature F-001 --message "<motivo>"
```

Gateway (persistent tmux session):

```bash
bash scripts/run_gateway.sh
```

Policy:

```text
state/capabilities/remote-notifications.json
```

Rules:

- Fail-soft: a failed notification never blocks the harness (exit 0 unless
  `--strict`).
- Credentials outside Git (`~/.config/agentic-harness/telegram.env`); the token
  is redacted in errors.
- Only the authorized `chat_id` can talk to the gateway.

Full setup: `docs/notifications/setup.md` (in the generated project) or
`capabilities/remote-notifications/docs/notifications/setup.md` (in the template).

## Node Profile And Additional Gates

The `node` profile adds specific gates:

- `npm test` in `implementation_fast`
- `npm test` in `qa_full`
- `npm run lint` in `qa_full`
- `npm test` in `finalization`

This lets the generated project validate both the Python harness and the Node
stack.

## Best Practices

- Keep gates fast in `implementation_fast`.
- Reserve full suites for `qa_full` and `finalization`.
- Store heavy logs outside Git.
- Make each gate have a clear purpose and a stable name.
- Avoid non-deterministic gates as a blocking requirement.
- For optional capabilities, always document evidence, validator and blocking
  rule.
