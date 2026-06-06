# Estado Y Roadmap Del Harness Agentico

Fecha de cierre: 2026-06-06  
Repositorio harness fuente: `/srv/agentic/workspace/desktop-overlay-assistant`  
Repositorio template: `/srv/agentic/workspace/agentic-sdd-template`

## Estado Ejecutivo

Roadmap cerrado. El harness ya soporta Spec Partner v2, mantenimiento controlado del propio harness, revision semantica de arquitectura, quality gates versionados, mutation testing determinista, mutation reviewer y extraccion de template con perfiles `generic`, `python` y `node`.

La fuente ejecutable sigue siendo Git, schemas, scripts y plano de control. Este documento conserva el roadmap original y lo completa con el estado final, evidencias y decisiones tecnicas aplicadas.

## Resumen De Cumplimiento

| Bloque | Estado | Evidencia |
| --- | --- | --- |
| `31A.1C` Spec Partner v2 y bootstrap | Completado | `e16a7f4`, `state/specification-policy.json`, `specs/schemas/acceptance-v2.schema.json` |
| `change_domain` y Role Guard de mantenimiento | Completado | `scripts/register_feature.py`, `scripts/role_guard.py`, tests de Role Guard |
| Docs SDD/Windows corregidas | Completado | `docs/conventions/spec-driven-development.md`, `docs/windows-runner/evidence-contract.md` |
| `31B` Semantic Architect Review | Completado | `specs/templates/architecture.md`, `scripts/feature_validation.py`, agente `architect` |
| `31C` Quality Gates Framework | Completado | `state/quality-gates.json`, `scripts/quality_gates.py`, integracion en implementacion, QA y finalizacion |
| `31D-31E` Mutation Capability | Completado | `scripts/mutation_runner.py`, capability `mutation-testing`, agente `mutation-reviewer` |
| Mutation Reviewer bloqueante | Completado | `scripts/mutation_review_validation.py`, `specs/schemas/mutation-review.schema.json`, bloqueo en QA |
| `31F` Validacion end-to-end | Completado | proyectos `test-generic-project`, `test-python-project`, `test-node-project` con `F-001` en `DONE` |
| Template extraction | Completado | `/srv/agentic/workspace/agentic-sdd-template` con `core/`, `profiles/`, `capabilities/`, `generator/`, `tests/` |

## Cambios Implementados

### 31A.1C Y Bootstrap De Self-Maintenance

Se cerro el bootstrap con un commit directo auditado de operador. El harness quedo preparado para que, desde ese punto, el mantenimiento pase por features del propio harness.

Implementado:

- Spec Partner v2 activado mediante `state/specification-policy.json`.
- Schema v2 en `specs/schemas/acceptance-v2.schema.json`.
- Template v2 por defecto en `specs/templates/acceptance.yaml`.
- Soporte de contratos legacy v1 para `F-001`.
- Documentacion de agentes `specifier` y `leader` actualizada.
- Correccion de bloques Markdown rotos en convenciones SDD.
- Correccion del contrato Windows y eliminacion de duplicacion.
- Campo `change_domain` con valores `product`, `harness`, `template`; default `product`.
- Role Guard ampliado para permitir cambios controlados de mantenimiento en dominio `harness`.

Restriccion mantenida: `change_domain: harness` no autoriza edicion directa del plano de control externo.

Commits principales:

- `e16a7f4 feat: close spec partner bootstrap`
- `08c5945 feat: validate structured acceptance contracts v2`

### 31B Semantic Architect Review

El Architect debe revisar semanticamente la especificacion antes del diseno.

Implementado:

- `architecture.md` requiere seccion `Specification Review` para acceptance v2.
- La validacion bloquea `DESIGN_READY` si faltan conclusiones criticas.
- El agente `architect` fue actualizado para revisar contradicciones, criterios no verificables, dependencias no declaradas, alcance ambiguo y preguntas criticas sin resolver.

Archivos principales:

- `specs/templates/architecture.md`
- `scripts/feature_validation.py`
- `.claude/agents/architect.md`

Commit principal:

- `0a7c859 feat: add semantic gates and mutation capability`

### 31C Quality Gates Framework

Se agrego un framework versionado de quality gates por fase.

Implementado:

- Configuracion en `state/quality-gates.json`.
- Fases: `implementation_fast`, `qa_full`, `finalization`, `optional_capability`.
- Compatibilidad con `scripts/verify_fast.sh` y `scripts/verify_full.sh` como defaults.
- Evidencia estructurada JSON.
- Logs pesados fuera de Git en `artifact_root/quality-gates/<feature>/`.
- Gates bloqueantes impiden avanzar segun fase:
  - `implementation_fast` bloquea `READY_FOR_QA`.
  - `qa_full` impide `APPROVED`.
  - `finalization` bloquea `DONE`.
- Scripts de verificacion robustecidos para sesiones SSH no interactivas.

Archivos principales:

- `scripts/quality_gates.py`
- `state/quality-gates.json`
- `scripts/complete_implementation.py`
- `scripts/complete_review.py`
- `scripts/finalize_feature.py`
- `scripts/verify_fast.sh`
- `scripts/verify_full.sh`

Commits principales:

- `0a7c859 feat: add semantic gates and mutation capability`
- `d83012c fix: harden verification gates for noninteractive runs`
- `f596ef7 fix: locate uv in noninteractive verification`

### 31D-31E Mutation Capability

Se implemento mutation testing determinista con runner propio, sin herramienta externa.

Implementado:

- Runner Python en `scripts/mutation_runner.py`.
- Alcance inicial `changed_code`.
- Defaults:
  - `max_mutants: 100`
  - `max_duration_seconds: 600`
- Mutaciones deterministas iniciales:
  - booleanos
  - comparadores
  - operadores aritmeticos simples
  - operadores logicos
- El runner aplica mutantes, ejecuta tests, restaura archivos y clasifica:
  - `killed`
  - `survived`
  - `invalid`
- Capability opcional `mutation-testing` activable por feature.
- Agente `mutation-reviewer` autorizado por Leader.
- Presupuesto de agente en `state/agent-budgets.json`.
- Evidencia validada por schema y script determinista.

Criterio de aprobacion:

- Cero mutantes supervivientes relevantes sin justificar.
- Cualquier `test_gap` fuerza `CHANGES_REQUESTED`.

Archivos principales:

- `scripts/mutation_runner.py`
- `scripts/mutation_review_validation.py`
- `specs/schemas/mutation-review.schema.json`
- `.claude/agents/mutation-reviewer.md`
- `state/agent-budgets.json`

Commits principales:

- `0a7c859 feat: add semantic gates and mutation capability`
- `de957d3 feat: execute mutation tests deterministically`

### 31F Validacion End-To-End Y Template Extraction

Se creo el template reutilizable y se valido con proyectos reales.

Estructura final del template:

```text
agentic-sdd-template/
  core/
  profiles/
    generic/
    python/
    node/
  capabilities/
    mutation-testing/
    windows-validation/
  generator/
  tests/
  create_project.py
  project.example.yaml
```

Generador:

```bash
python3 create_project.py --config project.yaml
```

Proyectos validados:

- `/srv/agentic/workspace/test-generic-project`
- `/srv/agentic/workspace/test-python-project`
- `/srv/agentic/workspace/test-node-project`

Cada proyecto completo una feature real `F-001` hasta `DONE`.

Evidencia especial:

- Python proyecto generado ejecuto mutation testing con resultado:
  - `generated: 1`
  - `killed: 1`
  - `survived: 0`
  - `invalid: 0`
- Evidencia mutation:
  - `/srv/agentic/workspace/data/test-python-project/artifacts/mutation-tests/F-001/latest.json`
- Revision mutation:
  - `/srv/agentic/workspace/test-python-project/evidence/mutation-reviews/F-001.json`

Commits principales del template:

- `036fa17 chore: initialize agentic sdd template`
- `cc607ad chore: sync template core with harness`
- `e4df145 feat: generate harness smoke tests for profiles`
- `faf7f23 feat: add node quality gates to generated projects`
- `52c35ef chore: sync mutation runner execution into core`

## Pruebas Ejecutadas

Harness fuente:

```bash
cd /srv/agentic/workspace/desktop-overlay-assistant
bash scripts/verify_full.sh
```

Resultado final:

- agent budget validation OK
- `compileall` OK
- `ruff check` OK
- `ruff format --check` OK
- `pytest`: `105 passed`
- `git diff --check` OK

Template:

```bash
cd /srv/agentic/workspace/agentic-sdd-template
python3 -m unittest discover -s tests -v
```

Resultado final:

- `test_generates_generic_project`: OK
- `test_generates_python_project`: OK
- `test_generates_node_project`: OK
- `Ran 3 tests`: OK

Proyectos generados:

```bash
python3 scripts/project_status.py
```

Resultado final:

- `test-generic-project`: `F-001 DONE`
- `test-python-project`: `F-001 DONE`
- `test-node-project`: `F-001 DONE`

## Decisiones Tecnicas

- El bootstrap inicial se permitio como unico commit directo de operador.
- El mantenimiento posterior debe pasar por el propio harness.
- `change_domain` separa cambios de producto, harness y template.
- Mutation testing usa runner propio determinista para controlar alcance, reproducibilidad y evidencia.
- Quality gates mantienen compatibilidad con `verify_fast.sh` y `verify_full.sh`.
- Logs pesados quedan en `artifact_root`; Git conserva evidencias pequenas y revisables.
- Windows validation queda como capability opcional, no dependencia core.
- Node es el primer perfil no Python y usa `npm`, ESM y `node:test`.

## Estado Residual

No quedan bloques abiertos del roadmap original. Los siguientes pasos ya no son cierre del roadmap, sino mejora continua:

- Publicar version/tag del template.
- Crear mas perfiles (`go`, `rust`, `frontend`) si aparecen proyectos reales.
- Ampliar mutation testing a mas lenguajes cuando exista necesidad.
- Anadir documentacion de ejemplos end-to-end con capturas de salida reales si se quiere usar como onboarding.
