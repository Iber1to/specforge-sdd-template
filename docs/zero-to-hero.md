# Zero to Hero — Operation Manual for the Agentic SDD Template

Complete tutorial: from cloning the template on GitHub to leaving a project
running in semi-automatic mode with the leader processing features.

> Estimated time: 20-30 min. Platform: Linux host (the orchestration harness
> uses POSIX file locking). Windows participates only as the optional runner of
> the `windows-validation` capability.

---

## 0. What you will get

```text
git clone           ->  you have the template
check_environment   ->  your environment meets the requirements
project.yaml        ->  you describe your project
create_project.py   ->  you generate a project with the full harness
verify_full.sh      ->  you confirm the harness is healthy
run_leader.sh       ->  you launch the leader in a persistent session
autonomous prompt   ->  the leader processes the feature queue on its own (semi-automatic)
```

The **template** generates **projects**. Each project includes an agentic
Spec-Driven Development *harness*: roles (leader, specifier, architect,
implementer, qa-reviewer, ...), a durable control plane outside Git, quality
gates, optional capabilities and a Role Guard that enforces per-role permissions.

---

## 1. Requirements

| Tool | For what | Check |
|---|---|---|
| Linux | Harness host | `uname -s` |
| Python 3.12 | Deterministic harness scripts | `python3 --version` |
| `uv` | Project environment and tests | `uv --version` |
| `git` | Versioning and publishing | `git --version` |
| `bash` | Gates and wrappers | `bash --version` |
| `tmux` | Persistent leader sessions | `tmux -V` |
| Claude Code | Run the agents | `claude --version` |
| Node.js | `node` profile only | `node --version` |

In environments without access to download Python, export
`UV_PYTHON_DOWNLOADS=never` so that `uv` fails explicitly instead of trying to
download the runtime.

---

## 2. Step 1 — Clone the template

```bash
cd /srv/agentic/workspace
git clone https://github.com/<org>/agentic-sdd-template.git
cd agentic-sdd-template
```

> Replace `<org>` with your GitHub organization/user.

Check the environment **before** generating anything:

```bash
python3 core/scripts/check_environment.py
```

It must finish with `[OK] Entorno preparado.` (exit 0). If something is missing,
it lists it with `[FALTA]` and exits with code 2.

---

## 3. Step 2 — The model in two minutes

- **Features**: traceable units of change that advance through the states
  `DRAFT -> SPEC_READY -> DESIGN_READY -> READY_FOR_DEVELOPMENT -> IN_PROGRESS ->
  READY_FOR_QA -> APPROVED -> DONE` (with `BLOCKED` and `CHANGES_REQUESTED`).
- **Roles**: the `leader` orchestrates and delegates; `specifier`/`architect`
  write the spec/architecture; `implementer` codes in an isolated worktree;
  `qa-reviewer` reviews. Each role can only write what is its own (enforced by
  the Role Guard).
- **Control plane** (outside Git, in `control_root`): `queue.json`,
  `leases/`, `runs/`. It is **durable**: if a session dies, the state survives.
- **Quality gates** and optional **capabilities** (security, performance,
  mutation, windows-validation, external-runtime, git-publish,
  remote-notifications).

Only `scripts/finalize_feature.py` can move a feature to `DONE`, and only after
green gates and valid evidence.

---

## 4. Step 3 — Configure your project (`project.yaml`)

Create a configuration file. Example:

```yaml
project_id: mi-proyecto
name: Mi Proyecto
output_path: /srv/agentic/workspace/mi-proyecto
profile: python
capabilities: [security-scanning, performance-testing]
```

Keys:

| Key | Required | Default | Notes |
|---|---|---|---|
| `project_id` | yes | — | `^[a-z0-9]+(-[a-z0-9]+)*$` |
| `name` | yes | — | Human-readable name |
| `output_path` | yes | — | Where the project is generated |
| `profile` | yes | — | `generic` \| `python` \| `node` |
| `capabilities` | no | `[]` | Inline list; `documentation-pack` is always included |
| `data_root` | no | `<output_parent>/data/<id>` | Operational state root |
| `control_root` | no | `<data_root>/control` | Queue, leases, runs, metrics |
| `artifact_root` | no | `<data_root>/artifacts` | Heavy logs and evidence |
| `worktree_root` | no | `<output_parent>/worktrees/<id>` | Feature worktrees |
| `git_publish_mode` | no | `local` | `disabled`/`local`/`dry_run`/`push` |

Supported profile x capability combinations: `docs/profile-capability-matrix.md`
(e.g. `mutation-testing` only with the `python` profile).

---

## 5. Step 4 — Generate the project

```bash
python3 create_project.py --config project.yaml
```

This creates, under `output_path`:

```text
scripts/            deterministic harness scripts (+ chosen capabilities)
state/              project.json, workflow.json, quality-gates.json, capabilities/
specs/  docs/  evidence/  tests/   (incl. tests/harness)
.claude/            agents, settings.json (Role Guard hooks)
CLAUDE.md  AGENTS.md  pyproject.toml
```

And, outside Git, the control plane in `control_root`
(`queue.json`, `runtime.json`, `leases/`, `runs/`, `role-sessions/`, ...) and the
`artifact_root`. The project is initialized as a Git repository with a first
commit.

---

## 6. Step 5 — Verify the installation

```bash
cd /srv/agentic/workspace/mi-proyecto
python3 scripts/check_environment.py --profile python
bash scripts/verify_full.sh
uv run pytest -q tests/harness
```

- `verify_full.sh`: ruff (lint + format), `compileall`, pytest and `git diff --check`.
- `tests/harness`: harness suite (role transitions, Role Guard, implementer
  lease invariant, resync of reused worktrees), hermetic and without network.

If everything comes out green, the project is healthy.

---

## 7. Step 6 — Launch the leader (persistent)

The leader is the main Claude Code session. **Important**: Claude Code reports
the main session to the hook as `agent_type: "claude"`, so the role is taken
from the `CLAUDE_HARNESS_ROLE` variable. The launcher sets it for you and starts
everything inside `tmux` so it survives disconnections:

```bash
bash scripts/run_leader.sh
```

- Detach (leave it running): `Ctrl-b` and then `d`.
- Reconnect from any machine: `bash scripts/run_leader.sh` or
  `tmux attach -t leader`.

Manual equivalent (without the launcher):

```bash
CLAUDE_HARNESS_ROLE=leader claude --agent leader --permission-mode bypassPermissions
```

> Without `CLAUDE_HARNESS_ROLE` the session stays `unscoped` (read-only) and the
> leader cannot use Bash. This is by design.

Check: in `<control_root>/role-sessions/<session_id>.json` you should see
`"role": "leader"`.

---

## 8. Step 7 — Your first feature

With the leader launched, give it a concrete goal. The leader will register the
feature and take it through its cycle by delegating to the subagents. Example
message:

```text
Registra y completa una feature: una funcion de healthcheck en src/ que devuelva
{"status":"ok"} y sus tests. Llevala hasta DONE pasando por spec, arquitectura,
implementacion, QA y finalizacion.
```

The leader will use the deterministic scripts (`register_feature.py`,
`transition_feature.py`, `start_implementation.py`, `complete_implementation.py`,
`start_review.py`, `complete_review.py`, `finalize_feature.py`). You do not touch
states by hand: the harness governs them.

> Quick reference for manual registration (if you want to intervene yourself):
> `python3 scripts/register_feature.py --title "Healthcheck" --slug "healthcheck" --description "..."`

---

## 9. Step 8 — Semi-automatic mode

To have the leader process the queue autonomously, paste this standing
instruction as the first message:

```text
Opera de forma autonoma como leader:
1. Consulta el estado de la cola y elige la siguiente feature accionable.
2. Llevala por su ciclo completo (spec -> arquitectura -> implementacion -> QA ->
   finalizacion) delegando en los subagentes y usando solo los scripts deterministas.
3. No te detengas entre features: continua hasta que no quede trabajo accionable.
4. Si una decision critica no se infiere con seguridad, marca BLOCKED, registra el
   motivo y continua; no inventes workarounds.
5. Respeta presupuestos de agente y quality gates; si algo determinista falla,
   documenta el bloqueo y no lo eludas.
6. Al terminar, resume que completaste y que quedo pendiente de decision humana.
```

Detach (`Ctrl-b d`) and the leader keeps working on the server. Use **mosh**
instead of `ssh` so your connection survives drops. Full detail in
`docs/leader-operation.md`.

---

## 10. Step 9 — Observe and operate

```bash
python3 scripts/project_status.py                  # queue state
python3 scripts/metrics_status.py                  # metrics and budgets
tail -f <control_root>/role-guard/audit.jsonl       # Role Guard decisions
```

Common operations:

- **Recover expired leases** (if a session died):
  `python3 scripts/recover_stale_leases.py --all`
- **Publish a DONE feature** (if you enabled `git-publish`):
  `python3 scripts/publish_feature.py --feature F-001 --mode push --remote origin --branch main`
- **Refresh generated documentation**:
  `python3 scripts/refresh_project_docs.py`

---

## 11. Troubleshooting

| Symptom | Probable cause | Solution |
|---|---|---|
| `El rol unscoped no tiene autorizacion para Bash` | Missing `CLAUDE_HARNESS_ROLE` | Launch with `bash scripts/run_leader.sh` (or export the variable) |
| `ModuleNotFoundError` / a Python gate fails | Python is not 3.12 or `uv`/`ruff`/`pytest` is missing | `python3 scripts/check_environment.py`; install what is missing |
| `uv` tries to download Python | No local 3.12 | Install Python 3.12 or use `UV_PYTHON_DOWNLOADS=never` and document it |
| The leader dies when closing SSH | Non-persistent session | Use it inside `tmux` (`run_leader.sh`) + `mosh` |
| `tmux no esta instalado` | tmux missing | Install `tmux` on the host |
| A feature gets stuck | Expired lease or failed gate | `project_status.py`; `recover_stale_leases.py`; check `artifact_root/quality-gates/` |

---

## 12. Next steps

- **Level 3 (24/7 unattended)**: headless driver with the **Claude Agent SDK**
  (or a `claude -p` loop) as a `systemd` service. See note in
  `docs/leader-operation.md`.
- **Real validations** (Windows / SSH): `docs/real-validation-runbook.md`.
- **Contracts and conventions**: `docs/architecture/harness-contract.md`,
  `docs/naming-and-contracts.md`, `docs/language-and-style.md`.

With this you went from zero to operating the harness semi-automatically. Hero
unlocked.
