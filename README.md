# SpecForge SDD Template

Reusable template that **generates projects with an agentic Spec-Driven
Development harness** for Claude Code: governed roles, a durable control plane,
Role Guard, quality gates and optional capabilities.

![status](https://img.shields.io/badge/status-v2.0.0-blue)
![ci](https://github.com/Iber1to/specforge-sdd-template/actions/workflows/ci-cd.yml/badge.svg)
![python](https://img.shields.io/badge/python-3.12-blue)
![platform](https://img.shields.io/badge/platform-linux-lightgrey)
![tests](https://img.shields.io/badge/tests-62%20passing-brightgreen)
![license](https://img.shields.io/badge/license-TBD-lightgrey)

> **Use this repo as a template:** mark it as a *Template Repository* in
> Settings and click **"Use this template"** to start a new one. Or clone and
> generate with `create_project.py` (see Quickstart).

> **First time?** Start with **[Zero to Hero](docs/zero-to-hero.md)**: from a
> GitHub clone to semi-automatic operation, step by step.

---

## What it is

The **template** generates **projects**. Each project includes an agentic
Spec-Driven Development harness:

- **Governed roles**: the `leader` orchestrates and delegates;
  `specifier`/`architect` write the spec and architecture; `implementer` codes
  in an isolated worktree; `qa-reviewer` reviews. A **Role Guard** (Claude Code
  hooks) enforces per-role permissions before every operation.
- **SDD workflow**: `DRAFT -> SPEC_READY -> DESIGN_READY ->
  READY_FOR_DEVELOPMENT -> IN_PROGRESS -> READY_FOR_QA -> APPROVED -> DONE`
  (with `BLOCKED`/`CHANGES_REQUESTED`). Only `finalize_feature.py` reaches `DONE`.
- **Durable control plane** outside Git (`queue.json`, `leases/`, `runs/`):
  state survives session crashes; leases expire and are recovered.
- Versioned **quality gates** and optional **capabilities**.

---

## Quickstart

```bash
# 1. Clone
git clone https://github.com/Iber1to/specforge-sdd-template.git
cd specforge-sdd-template

# 2. Check the environment
python3 core/scripts/check_environment.py

# 3. Describe your project (project.yaml)
cat > project.yaml <<'YAML'
project_id: mi-proyecto
name: Mi Proyecto
output_path: /srv/agentic/workspace/mi-proyecto
profile: python
capabilities: [security-scanning, performance-testing]
YAML

# 4. Generate
python3 create_project.py --config project.yaml

# 5. Verify the generated project
cd /srv/agentic/workspace/mi-proyecto
bash scripts/verify_full.sh

# 6. Launch the leader (persistent tmux session)
bash scripts/run_leader.sh
```

Full detail, configuration, first feature and **semi-automatic mode** in
[`docs/zero-to-hero.md`](docs/zero-to-hero.md).

---

## Profiles and capabilities

| Profile | documentation-pack | mutation-testing | external-runtime | windows-validation | performance-testing | security-scanning | git-publish | remote-notifications | eval-harness | tool-telemetry |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| generic | yes | no | yes | optional | yes | yes | yes | optional | optional | optional |
| python | yes | yes | yes | optional | yes | yes | yes | optional | optional | optional |
| node | yes | no (future) | yes | optional | yes | yes | yes | optional | optional | optional |
| android | yes | no | yes | optional | yes | yes | yes | optional | optional | optional |

`documentation-pack` is always included. Detail and rules in
[`docs/profile-capability-matrix.md`](docs/profile-capability-matrix.md).

---

## Repository structure

```text
core/            common harness copied into each generated project
profiles/        stack adapters: generic, python, node, android
capabilities/    optional capabilities (security, performance, mutation, ...)
generator/       deterministic generator notes
docs/            template documentation
tests/           generator suite (tests/test_generator.py)
create_project.py   deterministic generator
```

---

## Requirements and platform

The orchestration harness is designed for **Linux**. You need: Python 3.12,
`uv`, `git`, `bash`, `tmux`, and Claude Code. `node` only for the `node` profile.
Windows participates only as the optional `windows-validation` runner.

Check everything with `python3 core/scripts/check_environment.py`. In
environments without access to download Python, export
`UV_PYTHON_DOWNLOADS=never`.

---

## Operating the leader

- **Persistent** (survives SSH disconnections): `bash scripts/run_leader.sh`
  launches the leader in `tmux` with `CLAUDE_HARNESS_ROLE=leader`. Detach with
  `Ctrl-b d`; reconnect with `tmux attach -t leader`.
- **Semi-automatic**: give the leader the autonomous operation prompt and it
  will process the queue on its own.

Full guide (including `mosh`, observation and recovery) in
[`docs/leader-operation.md`](docs/leader-operation.md).

> Claude Code reports the main session as `agent_type: "claude"`; that is why
> the role is taken from `CLAUDE_HARNESS_ROLE`. Without that variable the
> session stays `unscoped` (read-only).

---

## Documentation

| Doc | For what |
|---|---|
| [zero-to-hero.md](docs/zero-to-hero.md) | Operation manual from zero to semi-automatic (start here) |
| [leader-operation.md](docs/leader-operation.md) | Operate the persistent and autonomous leader |
| [ci-cd.md](docs/ci-cd.md) | CI/CD cycle, checks, release and GitHub configuration |
| [profile-capability-matrix.md](docs/profile-capability-matrix.md) | Profile x capability combinations |
| [quality-and-capabilities.md](docs/quality-and-capabilities.md) | Quality gates and all optional capabilities |
| [adr-0002-eval-harness-verification-gate.md](docs/adr-0002-eval-harness-verification-gate.md) | Decision: eval-harness as a traceable verification gate |
| [real-validation-runbook.md](docs/real-validation-runbook.md) | Real Windows / SSH validation |
| [architecture/harness-contract.md](core/docs/architecture/harness-contract.md) | Operational contract of the harness |
| [architecture/role-guard.md](core/docs/architecture/role-guard.md) | Role Guard and role resolution |
| [naming-and-contracts.md](docs/naming-and-contracts.md) | Canonical vocabulary of JSON contracts |
| [language-and-style.md](docs/language-and-style.md) | Language and style convention |
| [roadmap.md](docs/roadmap.md) | Living roadmap post-`v1.0`: what comes in Now / Next / Later |
| [notifications/setup.md](capabilities/remote-notifications/docs/notifications/setup.md) | Telegram notifications and gateway setup (capability `remote-notifications`) |
| [CHANGELOG.md](CHANGELOG.md) | Version history |

---

## Status

`v2.0.0` (2026-06-23). Stable: profiles `generic`/`python`/`node`/`android`,
workflow + Role Guard + gates + control plane, and capabilities
`documentation-pack`, `mutation-testing` (python), `performance-testing`,
`security-scanning`, `git-publish`, `external-runtime`. Experimental:
`windows-validation` (code ready and covered offline; pending validation on
real Windows). Added in v2.0.0: `remote-notifications` (Telegram),
`eval-harness` (graders executable per `SCN-XXX` scenario), `tool-telemetry`
(tool telemetry in JSONL), a QA report in Markdown, and hardening of the
agents (anti-injection defense, reinjected-state guard, iterative context
recovery and QA with a pre-report gate) — adopted from ECC/agency-agents. The
`android` profile (Kotlin/Gradle) was validated in a real pilot (PokeCards
projects): *profile-aware* Role Guard (authorizes the `app/` module, the
`gradle/` wrapper and the root Gradle files for an android product, and the
feature documentation subtrees under `docs/` for any profile), real Android
build via `external-runtime` (`android-assemble`/`android-unit-tests`) and
Android gates in observe mode. See [`CHANGELOG.md`](CHANGELOG.md) for the
history and [`roadmap.md`](docs/roadmap.md) for what comes next (Now / Next /
Later).

---

## License

TBD.
