# De Cero a Hero — Manual de Operacion del Agentic SDD Template

Tutorial completo: desde clonar el template en GitHub hasta dejar un proyecto
corriendo en modo semiautomatico con el leader procesando features.

> Tiempo estimado: 20-30 min. Plataforma: host Linux (el harness de orquestacion
> usa bloqueo de archivos POSIX). Windows solo interviene como runner opcional de
> la capability `windows-validation`.

---

## 0. Que vas a conseguir

```text
git clone           ->  tienes el template
check_environment   ->  tu entorno cumple requisitos
project.yaml        ->  describes tu proyecto
create_project.py   ->  generas un proyecto con el harness completo
verify_full.sh      ->  confirmas que el harness esta sano
run_leader.sh       ->  lanzas el leader en una sesion persistente
prompt autonomo     ->  el leader procesa la cola de features solo (semiautomatico)
```

El **template** genera **proyectos**. Cada proyecto incluye un *harness* agentico
de Spec-Driven Development: roles (leader, specifier, architect, implementer,
qa-reviewer, ...), un plano de control durable fuera de Git, quality gates,
capabilities opcionales y un Role Guard que aplica los permisos por rol.

---

## 1. Requisitos

| Herramienta | Para que | Comprobacion |
|---|---|---|
| Linux | Host del harness | `uname -s` |
| Python 3.12 | Scripts deterministas del harness | `python3 --version` |
| `uv` | Entorno y tests del proyecto | `uv --version` |
| `git` | Versionado y publicacion | `git --version` |
| `bash` | Gates y wrappers | `bash --version` |
| `tmux` | Sesiones persistentes del leader | `tmux -V` |
| Claude Code | Ejecutar los agentes | `claude --version` |
| Node.js | Solo perfil `node` | `node --version` |

En entornos sin acceso a descargar Python, exporta `UV_PYTHON_DOWNLOADS=never`
para que `uv` falle de forma explicita en vez de intentar bajar el runtime.

---

## 2. Paso 1 — Clonar el template

```bash
cd /srv/agentic/workspace
git clone https://github.com/<org>/agentic-sdd-template.git
cd agentic-sdd-template
```

> Sustituye `<org>` por tu organizacion/usuario de GitHub.

Comprueba el entorno **antes** de generar nada:

```bash
python3 core/scripts/check_environment.py
```

Debe terminar en `[OK] Entorno preparado.` (exit 0). Si falta algo, lo lista con
`[FALTA]` y sale con codigo 2.

---

## 3. Paso 2 — El modelo en dos minutos

- **Features**: unidades de cambio trazables que avanzan por estados
  `DRAFT -> SPEC_READY -> DESIGN_READY -> READY_FOR_DEVELOPMENT -> IN_PROGRESS ->
  READY_FOR_QA -> APPROVED -> DONE` (con `BLOCKED` y `CHANGES_REQUESTED`).
- **Roles**: el `leader` orquesta y delega; `specifier`/`architect` escriben
  spec/arquitectura; `implementer` codifica en un worktree aislado; `qa-reviewer`
  revisa. Cada rol solo puede escribir lo suyo (lo aplica el Role Guard).
- **Plano de control** (fuera de Git, en `control_root`): `queue.json`,
  `leases/`, `runs/`. Es **durable**: si una sesion muere, el estado sobrevive.
- **Quality gates** y **capabilities** opcionales (security, performance,
  mutation, windows-validation, external-runtime, git-publish).

Solo `scripts/finalize_feature.py` puede pasar una feature a `DONE`, y solo tras
gates verdes y evidencia valida.

---

## 4. Paso 3 — Configurar tu proyecto (`project.yaml`)

Crea un archivo de configuracion. Ejemplo:

```yaml
project_id: mi-proyecto
name: Mi Proyecto
output_path: /srv/agentic/workspace/mi-proyecto
profile: python
capabilities: [security-scanning, performance-testing]
```

Claves:

| Clave | Obligatoria | Por defecto | Notas |
|---|---|---|---|
| `project_id` | si | — | `^[a-z0-9]+(-[a-z0-9]+)*$` |
| `name` | si | — | Nombre legible |
| `output_path` | si | — | Donde se genera el proyecto |
| `profile` | si | — | `generic` \| `python` \| `node` |
| `capabilities` | no | `[]` | Lista inline; `documentation-pack` se incluye siempre |
| `data_root` | no | `<output_parent>/data/<id>` | Raiz de estado operativo |
| `control_root` | no | `<data_root>/control` | Cola, leases, runs, metricas |
| `artifact_root` | no | `<data_root>/artifacts` | Logs pesados y evidencias |
| `worktree_root` | no | `<output_parent>/worktrees/<id>` | Worktrees de features |
| `git_publish_mode` | no | `local` | `disabled`/`local`/`dry_run`/`push` |

Combinaciones perfil x capability soportadas: `docs/profile-capability-matrix.md`
(p. ej. `mutation-testing` solo con perfil `python`).

---

## 5. Paso 4 — Generar el proyecto

```bash
python3 create_project.py --config project.yaml
```

Esto crea en `output_path`:

```text
scripts/            scripts deterministas del harness (+ capabilities elegidas)
state/              project.json, workflow.json, quality-gates.json, capabilities/
specs/  docs/  evidence/  tests/   (incl. tests/harness)
.claude/            agentes, settings.json (hooks del Role Guard)
CLAUDE.md  AGENTS.md  pyproject.toml
```

Y, fuera de Git, el plano de control en `control_root`
(`queue.json`, `runtime.json`, `leases/`, `runs/`, `role-sessions/`, ...) y el
`artifact_root`. El proyecto queda inicializado como repositorio Git con un
primer commit.

---

## 6. Paso 5 — Verificar la instalacion

```bash
cd /srv/agentic/workspace/mi-proyecto
python3 scripts/check_environment.py --profile python
bash scripts/verify_full.sh
uv run pytest -q tests/harness
```

- `verify_full.sh`: ruff (lint + format), `compileall`, pytest y `git diff --check`.
- `tests/harness`: suite minima del harness (transiciones de rol, Role Guard),
  rapida y sin red.

Si todo sale verde, el proyecto esta sano.

---

## 7. Paso 6 — Lanzar el leader (persistente)

El leader es la sesion principal de Claude Code. **Importante**: Claude Code
reporta la sesion principal al hook como `agent_type: "claude"`, asi que el rol
se toma de la variable `CLAUDE_HARNESS_ROLE`. El launcher la fija por ti y arranca
todo dentro de `tmux` para que sobreviva a desconexiones:

```bash
bash scripts/run_leader.sh
```

- Detach (dejarlo corriendo): `Ctrl-b` y luego `d`.
- Reconectar desde cualquier maquina: `bash scripts/run_leader.sh` o
  `tmux attach -t leader`.

Equivalente manual (sin el launcher):

```bash
CLAUDE_HARNESS_ROLE=leader claude --agent leader --permission-mode bypassPermissions
```

> Sin `CLAUDE_HARNESS_ROLE` la sesion queda `unscoped` (solo lectura) y el leader
> no puede usar Bash. Es el comportamiento de diseno.

Comprobacion: en `<control_root>/role-sessions/<session_id>.json` debe verse
`"role": "leader"`.

---

## 8. Paso 7 — Tu primera feature

Con el leader lanzado, dale un objetivo concreto. El leader registrara la feature
y la llevara por su ciclo delegando en los subagentes. Ejemplo de mensaje:

```text
Registra y completa una feature: una funcion de healthcheck en src/ que devuelva
{"status":"ok"} y sus tests. Llevala hasta DONE pasando por spec, arquitectura,
implementacion, QA y finalizacion.
```

El leader usara los scripts deterministas (`register_feature.py`,
`transition_feature.py`, `start_implementation.py`, `complete_implementation.py`,
`start_review.py`, `complete_review.py`, `finalize_feature.py`). Tu no tocas
estados a mano: el harness los gobierna.

> Referencia rapida del registro manual (si quieres intervenir tu):
> `python3 scripts/register_feature.py --title "Healthcheck" --slug "healthcheck" --description "..."`

---

## 9. Paso 8 — Modo semiautomatico

Para que el leader procese la cola de forma autonoma, pega esta instruccion
permanente como primer mensaje:

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

Haz detach (`Ctrl-b d`) y el leader sigue trabajando en el servidor. Usa **mosh**
en vez de `ssh` para que tu conexion resista cortes. Detalle completo en
`docs/leader-operation.md`.

---

## 10. Paso 9 — Observar y operar

```bash
python3 scripts/project_status.py                  # estado de la cola
python3 scripts/metrics_status.py                  # metricas y presupuestos
tail -f <control_root>/role-guard/audit.jsonl       # decisiones del Role Guard
```

Operaciones habituales:

- **Recuperar leases caducados** (si una sesion murio):
  `python3 scripts/recover_stale_leases.py --all`
- **Publicar una feature DONE** (si activaste `git-publish`):
  `python3 scripts/publish_feature.py --feature F-001 --mode push --remote origin --branch main`
- **Refrescar documentacion generada**:
  `python3 scripts/refresh_project_docs.py`

---

## 11. Troubleshooting

| Sintoma | Causa probable | Solucion |
|---|---|---|
| `El rol unscoped no tiene autorizacion para Bash` | Falta `CLAUDE_HARNESS_ROLE` | Lanza con `bash scripts/run_leader.sh` (o exporta la variable) |
| `ModuleNotFoundError` / falla un gate Python | Python no es 3.12 o falta `uv`/`ruff`/`pytest` | `python3 scripts/check_environment.py`; instala lo que falte |
| `uv` intenta descargar Python | Sin 3.12 local | Instala Python 3.12 o usa `UV_PYTHON_DOWNLOADS=never` y documenta |
| El leader muere al cerrar SSH | Sesion no persistente | Usala dentro de `tmux` (`run_leader.sh`) + `mosh` |
| `tmux no esta instalado` | Falta tmux | Instala `tmux` en el host |
| Una feature queda atascada | Lease caducado o gate fallido | `project_status.py`; `recover_stale_leases.py`; revisa `artifact_root/quality-gates/` |

---

## 12. Siguientes pasos

- **Nivel 3 (24/7 desatendido)**: driver headless con el **Claude Agent SDK** (o
  un bucle de `claude -p`) como servicio `systemd`. Ver nota en
  `docs/leader-operation.md`.
- **Validaciones reales** (Windows / SSH): `docs/real-validation-runbook.md`.
- **Contratos y convenciones**: `docs/architecture/harness-contract.md`,
  `docs/naming-and-contracts.md`, `docs/language-and-style.md`.

Con esto pasaste de cero a operar el harness en semiautomatico. Hero unlocked.
