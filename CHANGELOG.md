# Changelog

All notable changes to `agentic-sdd-template`. Format loosely follows Keep a
Changelog; the project uses Conventional Commits.

## [Unreleased]

## [2.0.0] - 2026-06-23

Cierre del harness multi-stack y del perfil `android`. Novedades mayores desde
`v1.0-internal`: nuevo perfil **Android** (Kotlin/Gradle); **Role Guard
profile-aware** (autoriza `app/`+Gradle para android y los subtrees de
documentación de feature para producto); **mutation-testing finalizable**
end-to-end (informe plegado en el commit único de QA); y las adopciones
ECC/agency-agents (eval-harness, prompt-defense, stale-replay guard,
iterative-retrieval, tool-telemetry, QA pre-report gate, plantillas de informe).
Validado en un piloto real (proyectos PokeCards: app Android + backend de
scraping, ambos al 100% de features). CI en verde.

### Added

- Capability `eval-harness`: convierte los escenarios `SCN-XXX` de cada feature en
  graders ejecutables (`code`/`rule` elegibles para gate; `model`/`human`
  consultivos) con metricas `pass_at_k`/`pass_caret_k`. Runner
  `scripts/run_evals.py`, validador, schema y politica; gate `EVAL-001` en
  `qa_full`. Decision en `docs/adr-0002-eval-harness-verification-gate.md`.
  Adoptado de `affaan-m/ECC`.
- Capability `tool-telemetry`: hooks `PreToolUse`/`PostToolUse` registran cada
  llamada a herramienta como JSONL con scrubbing de secretos
  (`scripts/tool_telemetry_hook.py`); no-op y fail-soft sin la capability.
- Informe QA en Markdown de campos fijos (`evidence/reviews/<feature>.md`) junto
  al JSON, generado por `scripts/complete_review.py` (report template).
- Endurecimiento de agentes (adoptado de ECC / agency-agents): bloque "Defensa de
  prompt" anti-inyeccion en los 7 agentes; `qa-reviewer` con sesgo por defecto a
  `CHANGES_REQUESTED`, disparadores de fallo automatico y pre-report gate; guard
  stale-replay en `leader`/`implementer`; recuperacion de contexto iterativa en
  `architect`/`implementer`.
- Tope de reintentos de QA con escalado: `complete_review.py` cuenta los
  `CHANGES_REQUESTED` en `qa_attempts`; `start_implementation.py` rechaza un
  nuevo intento cuando se alcanza `maximum_qa_attempts` (default 3 en
  `state/project.json`) y el `leader` escala a decision humana. Evita bucles
  infinitos QA<->implementer (adoptado de agency-agents handoff-templates).
- `implementer` con disciplina de cambio minimo y Scope Self-Check (cada linea
  del diff justificable por `AC-XXX`, sin scope creep; adoptado de agency-agents
  minimal-change-engineer).
- `specifier` con seccion "Contrato de capacidad" (promesa observable vs
  implementacion, invariantes, estados/transiciones, incertidumbre como `Q-XXX`,
  no-goals; adoptado de ECC product-capability).

### Changed

- `finalize_feature.py` admite el informe QA Markdown junto al JSON en el commit
  de evidencia posterior al commit revisado.

### Fixed

- Role Guard implementer write policy is now profile-aware (`scripts/role_guard.py`).
  For `change_domain=product` the base layout stays Python (`src/`, `tests/`,
  `runtime/external/`, `pyproject.toml`, `uv.lock`); the `android` profile now also
  authorizes the `app/` module, the `gradle/` wrapper directory and the root Gradle
  files (`settings.gradle.kts`, `build.gradle.kts`, `gradle.properties`). The
  profile is read from `state/project.json`. Without this fix the implementer in an
  `android` project was blocked from writing any product file (the generator emitted
  an Android layout the guard did not allow), discovered on the `pokecards-app`
  pilot. The deterministic lifecycle E2E did not catch it because Role Guard runs as
  a Claude Code hook, not inside the harness scripts the test drives.

- Role Guard product implementer can now write feature documentation subtrees
  (`scripts/role_guard.py`). For `change_domain=product` (all profiles) the
  implementer may write under `docs/10-architecture/adr/`, `docs/20-runtime/`,
  `docs/30-quality/` and `docs/40-operations/` — the documentation that
  `documentation_validation.py` requires in the reviewed commit when a feature
  declares `requires_adr` / `requires_runtime_update` / `requires_quality_update` /
  `requires_operations_update`. The rest of `docs/` stays out of product scope
  (owned by `change_domain=harness`). Without this, any feature with a `requires_*`
  flag could not be finalized: the ADR/doc had to ship in the reviewed content but
  no product role could author it (discovered finalizing `pokecards-app` F-001).


Harness fixes backported on 2026-06-11 from the `poker-assistant` pilot
(features F-008/F-009/F-010/F-011 of that project):

- Lease invariant (`scripts/start_implementation.py`): refuse to create an
  implementer lease when any other implementer lease exists (matching
  `role_guard.active_lease()`, which requires exactly one), with a clear error
  pointing to `scripts/recover_stale_leases.py`. Previously a feature left
  `BLOCKED` with a live lease deadlocked every other implementer (observed
  2026-06-10; required manual lease deletion).
- Worktree resync (`scripts/worktree_common.py`): reused feature worktrees and
  branches are resynchronized with the canonical branch via
  `git merge --no-edit` on start (idempotent no-op when already in sync; abort
  with a clean restore on conflict or dirty worktree; no control-plane writes
  on failure). Previously a resumed feature branch could silently stay behind
  `main`.
- `ruff format` conformance of capability scripts that ship into generated
  projects and are checked by GATE-001 (`verify_fast.sh`):
  `capabilities/performance-testing/scripts/run_performance_gate.py` and
  `capabilities/remote-notifications/scripts/telegram_gateway.py`.

### Added

- New project profile `android` (Kotlin + Gradle). The generator emits a minimal
  Android app skeleton: `settings.gradle.kts`, root and `app/` Kotlin DSL build
  files, `AndroidManifest.xml`, a `MainActivity.kt`, a JVM unit test, and
  localized string resources for English (default), Spanish, Japanese and Korean
  (`app/src/main/res/values{,-es,-ja,-ko}/`). Following the `node` v1 philosophy,
  the generator installs no external toolchain (no Android SDK / Gradle download).
  The Android gates (`ANDROID-001` in `implementation_fast`, `ANDROID-002` in
  `qa_full`) are non-blocking `observe` gates that run through
  `scripts/verify_android.sh`, which detects Gradle/`gradlew` and skips with
  success when the Android toolchain is absent, so the Python-orchestrated
  lifecycle stays green offline. Blocking gates remain the Python harness gates.
  `mutation-testing` stays exclusive to `python`. Covered by
  `test_generates_android_project` and an end-to-end lifecycle test; documented in
  `profiles/android/README.md`, `docs/profile-capability-matrix.md` and a
  generated `docs/20-runtime/android-environment.md`.

- Regression test `test_role_guard_product_write_paths_are_profile_aware`
  (`tests/test_generator.py`) covering the two Role Guard write-policy gaps found
  on the `pokecards` pilot: it loads a generated project's `role_guard.py`, creates
  an implementer lease, and asserts that a product implementer may write `app/`,
  the root Gradle files and the feature documentation subtrees
  (`docs/10-architecture/adr/`, `20-runtime`, `30-quality`, `40-operations`) in an
  `android` project, that `docs/00-project/` and `runtime/` (non-`runtime/external`)
  stay blocked, and that a `python` project blocks the Android paths while still
  allowing the documentation subtrees. These gaps had slipped because Role Guard
  runs as a Claude Code hook, outside the deterministic lifecycle the E2E exercises.

- `mutation-testing` is now finalizable end-to-end (closes the gap that forced
  removing the capability on the `pokecards` pilot). The Mutation Reviewer emits
  per-mutant classifications (`MUT-XXX=class:rationale`); QA runs `mutation_runner.py`
  in the worktree (added to the QA harness-script allowlist) and passes the
  classifications to `complete_review.py` via `--mutation-classification`
  (+`--mutation-reviewer-id`/`--mutation-summary`). `complete_review.py` builds and
  validates the report (`mutation_review_validation.build_mutation_review`), writes
  `evidence/mutation-reviews/<F>.json` and folds it into the **single** QA evidence
  commit; `finalize_feature.py` and the finalization contract now allow that path in
  that commit. All of this is gated behind `mutation_testing_required(feature)`, so
  features without the capability are unaffected. A `test_gap` classification fails
  validation (the fix is more tests, not reclassification). Covered by
  `test_mutation_review_builder_and_validation`.

- Hermetic harness tests for the two fixes above, copied into generated
  projects from `core/tests/harness/`: `test_lease_invariant.py` and
  `test_worktree_resync.py` (unit + subprocess E2E against temporary Git
  repositories and control planes).

- New optional capability `remote-notifications`: Telegram alerts when the
  leader stops, blocks or completes its work, plus a long-polling gateway
  (`scripts/telegram_gateway.py`) to read status and inject prompts into the
  leader tmux session from a phone. Transport is abstracted behind
  `scripts/notify_common.py` (a WhatsApp Cloud API adapter can be added later
  without touching callers). Hooks `Stop`/`Notification` route through
  `hook_entrypoint.sh notify` and are a no-op when the capability is not
  installed. `notify.py` added to the leader Bash allowlist in Role Guard.
  Credentials live outside the repository
  (`~/.config/agentic-harness/telegram.env`).

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
