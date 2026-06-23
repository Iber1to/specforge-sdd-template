# Roadmap

Living state of the work **after `v1.0-internal`**. This document consolidates in
one place what comes next and replaces the previous dispersion between the
CHANGELOG, the historical roadmap and the QA task document.

Where each thing lives:

- **Historical roadmap** (closed): [`estado-y-roadmap-harness-agentico.md`](estado-y-roadmap-harness-agentico.md).
- **Detail of what was delivered** per version: [`../CHANGELOG.md`](../CHANGELOG.md).
- **Operational backlog** of an in-progress project: its control plane
  (`queue.json` + `scripts/register_feature.py` + `scripts/project_status.py`).
- **Strategic future of the template** (Now / Next / Later): this document.

Convention: an item moves to **Done** when it enters a CHANGELOG release. The
`T-0xx` IDs follow the v1 task document.

_Last updated: 2026-06-21._

---

## Current state

`v1.0-internal` (2026-06-07). The core is stable (SDD workflow, Role Guard,
quality gates, durable control plane) along with the capabilities
`documentation-pack`, `mutation-testing` (python), `performance-testing`,
`security-scanning`, `git-publish`, `external-runtime`. Experimental:
`windows-validation` (code ready and covered offline; pending validation on real
Windows). 60 generator tests green.

In `[Unreleased]`: capability `remote-notifications` (Telegram alerts from the
leader, `Stop`/`Notification` hooks and a bidirectional gateway; see CHANGELOG)
and capability `eval-harness` (graders executable per `SCN-XXX` scenario,
`pass_at_k` / `pass_caret_k` metrics; see ADR-0002 and CHANGELOG). In addition,
`qa-reviewer` hardened with a default bias toward `CHANGES_REQUESTED`,
automatic-failure triggers and a pre-report gate (adopted from ECC /
agency-agents); all agents carry a "Prompt defense (baseline)" anti-injection
block; and `leader` and `implementer` treat the context reinjected after
resumption/compaction as a historical reference (stale-replay guard, adopted
from ECC). `architect` and `implementer` incorporate iterative context recovery
(DISPATCH/EVALUATE/REFINE/STOP, max 3 cycles; adopted from ECC
iterative-retrieval). And a new capability `tool-telemetry`:
`PreToolUse`/`PostToolUse` hooks that record each tool call as JSONL with secret
scrubbing (ECC continuous-learning substrate; the instincts engine is discarded
for being non-deterministic). In addition, `complete_review.py` generates,
alongside the JSON, a QA report in Markdown with fixed fields
(`evidence/reviews/<feature>.md`), readable and diffable (report template,
adopted from agency-agents). With this, the 7 ECC/agency-agents recommendations
are adopted. Second batch (from the full catalog): QA retry cap with escalation
(`qa_attempts`/`maximum_qa_attempts`, `complete_review.py` +
`start_implementation.py` + `leader`), minimal-change Scope Self-Check in
`implementer`, and "Capability contract" in `specifier`.

---

## Now — in progress or next

### Capability `eval-harness` — traceable per-scenario verification  (`T-015`)

- **Why.** The `SCN-XXX` scenarios are today a documentary contract: they are not
  executed. The `SCN-XXX -> grader -> evidence` link is missing so that
  acceptance is machine-checkable. Decision in
  [`adr-0002-eval-harness-verification-gate.md`](adr-0002-eval-harness-verification-gate.md).
- **MVP scope.** Deterministic `code` and `rule` graders declared in
  `specs/features/<FEATURE>/evals.json`; runner `run_evals.py` with `pass_at_k` /
  `pass_caret_k` metrics; validator and schema; policy with `mode`
  observe/enforce; gate `EVAL-001` in `qa_full`. `model`/`human` graders
  declarable but only advisory.
- **Inspiration.** `affaan-m/ECC` (`skills/eval-harness/SKILL.md`), adapted to
  deterministic execution; its `verification-loop` (prose, not deterministic) and
  its continuous-learning (implicit learning, contrary to SDD) are discarded.
- **Done when.** `create_project.py` installs the capability; the generated
  project runs `run_evals.py` and produces validated evidence; generator E2E test
  green; documented in `quality-and-capabilities.md` and the matrix.

### Real validation on hardware: Windows and SSH  (`T-008E`, `T-008F`)

- **Why.** The code and offline coverage exist, but `windows-validation` will not
  move from *experimental* to *stable* until it runs on real Windows, and the SSH
  adapter of `external-runtime` is only tested offline. This is what separates
  "covered in CI" from "validated in production".
- **What's missing.** Follow [`real-validation-runbook.md`](real-validation-runbook.md):
  generate the request from the Linux host, run the runner on Windows / over SSH,
  publish evidence and validate `commit`/`feature`.
- **Done when.** Real evidence published and validated in both cases;
  `windows-validation` reclassified as stable in README and CHANGELOG. On
  startup, wire a **non-blocking** Windows smoke.

### Unify the `PASS` / `PASSED` status vocabulary  (closing of `T-009F`)

- **Why.** The JSON contracts mix `PASS` and `PASSED`; documented in
  [`naming-and-contracts.md`](naming-and-contracts.md) as a non-blocking follow-up.
- **What's missing.** Choose the canonical term, migrate emitters and readers in a
  single scoped change and update the schema and documentation.
- **Done when.** A single term across the whole control plane and evidence, with a
  test that fixes it.

### Harness load smoke in Claude Code (generated project)  (`T-014`)

- **Why.** The offline suite and the *Generated project smoke* job validate that
  the template generates operable projects, but the CI does not run Claude Code
  (contract in [`ci-cd.md`](ci-cd.md)). That Claude Code **actually loads** the
  harness, the agents and the hooks on a generated project is only verified in a
  real session; today it is manual debt that is not covered.
- **What's missing.** Document the manual procedure as a runbook
  (`harness-load-runbook.md`) with loading the agents (`claude agents`), launching
  the Leader (`--agent leader`), the live Role Guard block and a real subagent;
  optionally, automate the **Claude-free** part (checks of `.claude/agents/*`,
  `settings.json` `hooks`, `hook_entrypoint.sh` wrapper, `project_status.py` /
  `metrics_status.py`) inside `verify_full.sh` as a **non-blocking** smoke. It runs
  on a generated project, never on the template repo.
- **Done when.** On a generated project: Claude starts with `--agent leader`;
  `claude agents` lists the project's agents (`leader`, `specifier`, `architect`,
  `implementer`, `qa-reviewer` and those of the installed capabilities);
  `project_status.py` runs from the Leader; the hooks do not fail; the Role Guard
  blocks an unauthorized write; `SubagentStart`/`SubagentStop` generate a metric;
  and `git status` is clean on exit.

---

## Next — planned

### `T-013` — Level 3 unattended operation (headless driver + `systemd`)

- **Why.** Level 2 leaves the `leader` persistent but **directed by a person**.
  Level 3 turns it into a **service that processes the queue on its own, 24/7**,
  surviving crashes and restarts. It is needed when continuous throughput /
  hands-off operation is sought; if features are only launched now and then, Level
  2 is enough.
- **MVP scope.** Headless driver (Claude Agent SDK or a `claude -p` loop) that
  reads `queue.json` and drives features; `systemd` unit with start on boot and
  `Restart=on-failure`; idempotent startup (runs `recover_stale_leases.py`, cleans
  orphaned worktrees, resumes from the control plane); **token budget with a real
  cutoff** (gives "teeth" to `agent-budgets.json` / `agent_budget_observer`) and a
  **kill switch**; structured logging to `journald` and a basic alert.
- **Full scope.** Watchdog/healthcheck; circuit breaker on consecutive failures;
  allowlist of unattended actions (never `git-publish --push` nor merge to `main`
  without approval); metrics dashboard; backlog intake (file or webhook); human
  decision mailbox for `BLOCKED` features.
- **Depends on.** Validating the behavior of Levels 1+2 in real use before
  automating.
- **Done when.** The service processes features from the queue without
  intervention, recovers from a host restart without corrupt state and respects
  the budget and kill switch.

### `T-009G` — Optional clean packaging (ZIP for audits)  _(optional)_

- **Why.** The official deployment is by Git, but a clean, reproducible ZIP is
  useful for deliveries or external audits.
- **Scope.** `scripts/package_template.py` + `scripts/validate_package.py`,
  excluding `.git`, `.venv`, caches, `node_modules`, `dist`.
- **Done when.** Verifiable clean ZIP, documented as an auxiliary artifact and not
  as a deployment path.

### Milestone: public `v1.0`

- **Why.** Today it is `v1.0-internal`. Publishing requires closing the real
  validations above and deciding on a **license** (today `TBD` in README).
- **Done when.** Real validations green, license chosen, README/CHANGELOG updated
  and `v1.0` tag.

---

## Later — future (P3)

Non-blocking improvements; they are promoted to **Next** when there is real
demand.

| ID | Item | Area | Note |
|---|---|---|---|
| `T-010A` | Optional ESLint/Prettier (`node_linting: full`) | Node profile | `npm ci` + lockfile; not mandatory |
| `T-010B` | Docker as an `external-runtime` target | External runtime | timeout, limits, cleanup, evidence |
| `T-010C` | Advisory integration with Code-Recall MCP | Memory | not a source of truth; only verified learnings |
| `T-010D` | Integration with Graphify | Navigation / context | explicit tool, no automatic hooks |
| `T-010E` | Metrics dashboards (runs, tokens, features, gates) | Observability | MD / JSON / CSV output; input for Level 3 |

---

## Done

Summary; the per-version detail is in [`../CHANGELOG.md`](../CHANGELOG.md).

- **`v1.0-internal`** (2026-06-07): final hardening and functional closure.
  - `T-007A..E` — `command-id` in external-runtime, hooks wrapper, `artifact_root`
    fix, `windows_validation_available`, hardening tests.
  - `T-008A..D`, `T-008G` — preflight, offline portability, minimal harness
    suite, profile x capability matrix, git-publish evidence.
  - `T-008E/F` — **offline** coverage + runbook (real validation remains in *Now*).
  - `T-009A..F` — performance baselines, security baseline classification,
    mutation limited to the diff, per-profile security adapters, and
    language/style and naming/contracts conventions.
  - `T-011` — removed the free-command path in external-runtime.
  - `T-012` — main session role via `CLAUDE_HARNESS_ROLE`.
