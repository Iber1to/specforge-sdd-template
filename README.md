# SpecForge SDD Template

Template reutilizable que **genera proyectos con un harness agentico de
Spec-Driven Development** para Claude Code: roles gobernados, plano de control
durable, Role Guard, quality gates y capabilities opcionales.

![status](https://img.shields.io/badge/status-v1.0--internal-blue)
![python](https://img.shields.io/badge/python-3.12-blue)
![platform](https://img.shields.io/badge/platform-linux-lightgrey)
![tests](https://img.shields.io/badge/tests-48%20passing-brightgreen)
![license](https://img.shields.io/badge/license-TBD-lightgrey)

> **Usa este repo como plantilla:** marcalo como *Template Repository* en
> Settings y pulsa **"Use this template"** para arrancar uno nuevo. O clona y
> genera con `create_project.py` (ver Quickstart).

> **Primera vez?** Empieza por **[De Zero a Hero](docs/zero-to-hero.md)**: del
> clone de GitHub a operar en semiautomatico, paso a paso.

---

## Que es

El **template** genera **proyectos**. Cada proyecto incluye un harness agentico
de Spec-Driven Development:

- **Roles gobernados**: el `leader` orquesta y delega; `specifier`/`architect`
  escriben spec y arquitectura; `implementer` codifica en un worktree aislado;
  `qa-reviewer` revisa. Un **Role Guard** (hooks de Claude Code) aplica los
  permisos por rol antes de cada operacion.
- **Workflow SDD**: `DRAFT -> SPEC_READY -> DESIGN_READY ->
  READY_FOR_DEVELOPMENT -> IN_PROGRESS -> READY_FOR_QA -> APPROVED -> DONE`
  (con `BLOCKED`/`CHANGES_REQUESTED`). Solo `finalize_feature.py` llega a `DONE`.
- **Plano de control durable** fuera de Git (`queue.json`, `leases/`, `runs/`):
  el estado sobrevive a caidas de sesion; los leases caducan y se recuperan.
- **Quality gates** versionados y **capabilities** opcionales.

---

## Quickstart

```bash
# 1. Clonar
git clone https://github.com/Iber1to/specforge-sdd-template.git
cd specforge-sdd-template

# 2. Comprobar el entorno
python3 core/scripts/check_environment.py

# 3. Describir tu proyecto (project.yaml)
cat > project.yaml <<'YAML'
project_id: mi-proyecto
name: Mi Proyecto
output_path: /srv/agentic/workspace/mi-proyecto
profile: python
capabilities: [security-scanning, performance-testing]
YAML

# 4. Generar
python3 create_project.py --config project.yaml

# 5. Verificar el proyecto generado
cd /srv/agentic/workspace/mi-proyecto
bash scripts/verify_full.sh

# 6. Lanzar el leader (sesion persistente en tmux)
bash scripts/run_leader.sh
```

Detalle completo, configuracion, primera feature y **modo semiautomatico** en
[`docs/zero-to-hero.md`](docs/zero-to-hero.md).

---

## Perfiles y capabilities

| Perfil | documentation-pack | mutation-testing | external-runtime | windows-validation | performance-testing | security-scanning | git-publish |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| generic | si | no | si | opcional | si | si | si |
| python | si | si | si | opcional | si | si | si |
| node | si | no (futuro) | si | opcional | si | si | si |

`documentation-pack` se incluye siempre. Detalle y reglas en
[`docs/profile-capability-matrix.md`](docs/profile-capability-matrix.md).

---

## Estructura del repositorio

```text
core/            harness comun que se copia a cada proyecto generado
profiles/        adaptadores de stack: generic, python, node
capabilities/    capacidades opcionales (security, performance, mutation, ...)
generator/       notas del generador determinista
docs/            documentacion del template
tests/           suite del generador (tests/test_generator.py)
create_project.py   generador determinista
```

---

## Requisitos y plataforma

El harness de orquestacion esta disenado para **Linux**. Necesitas: Python 3.12,
`uv`, `git`, `bash`, `tmux`, y Claude Code. `node` solo para el perfil `node`.
Windows interviene solo como runner opcional de `windows-validation`.

Comprueba todo con `python3 core/scripts/check_environment.py`. En entornos sin
acceso a descargar Python, exporta `UV_PYTHON_DOWNLOADS=never`.

---

## Operar el leader

- **Persistente** (sobrevive a desconexiones SSH): `bash scripts/run_leader.sh`
  lanza el leader en `tmux` con `CLAUDE_HARNESS_ROLE=leader`. Detach con
  `Ctrl-b d`; reconecta con `tmux attach -t leader`.
- **Semiautomatico**: dale al leader el prompt de operacion autonoma y procesara
  la cola solo.

Guia completa (incluido `mosh`, observacion y recuperacion) en
[`docs/leader-operation.md`](docs/leader-operation.md).

> Claude Code reporta la sesion principal como `agent_type: "claude"`; por eso el
> rol se toma de `CLAUDE_HARNESS_ROLE`. Sin esa variable la sesion queda
> `unscoped` (solo lectura).

---

## Documentacion

| Doc | Para que |
|---|---|
| [zero-to-hero.md](docs/zero-to-hero.md) | Manual de operacion de cero a semiautomatico (empieza aqui) |
| [leader-operation.md](docs/leader-operation.md) | Operar el leader persistente y autonomo |
| [profile-capability-matrix.md](docs/profile-capability-matrix.md) | Combinaciones perfil x capability |
| [real-validation-runbook.md](docs/real-validation-runbook.md) | Validacion real Windows / SSH |
| [architecture/harness-contract.md](core/docs/architecture/harness-contract.md) | Contrato operativo del harness |
| [architecture/role-guard.md](core/docs/architecture/role-guard.md) | Role Guard y resolucion de rol |
| [naming-and-contracts.md](docs/naming-and-contracts.md) | Vocabulario canonico de contratos JSON |
| [language-and-style.md](docs/language-and-style.md) | Convencion de idioma y estilo |
| [CHANGELOG.md](CHANGELOG.md) | Historial de versiones |

---

## Estado

`v1.0-internal` (2026-06-07). Estable: perfiles `generic`/`python`/`node`,
workflow + Role Guard + gates + plano de control, y capabilities
`documentation-pack`, `mutation-testing` (python), `performance-testing`,
`security-scanning`, `git-publish`, `external-runtime`. Experimental:
`windows-validation` (codigo listo y cubierto offline; pendiente validar en
Windows real). Ver [`CHANGELOG.md`](CHANGELOG.md).

---

## Licencia

TBD.
