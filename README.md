# Agentic SDD Template

Template reutilizable para crear proyectos con un harness de Spec Driven Development agentico. Incluye el plano de control, agentes, scripts deterministas, contratos de especificacion, gates de calidad, capacidades opcionales y perfiles base para proyectos genericos, Python y Node.

Estado actual: extraido y validado en `jarvis:/srv/agentic/workspace/agentic-sdd-template` el 2026-06-06. El roadmap original quedo cerrado y documentado en `docs/estado-y-roadmap-harness-agentico.md`.

## Que Incluye

- `core/`: harness comun que se copia a cada proyecto generado.
- `profiles/`: adaptadores de stack para `generic`, `python` y `node`.
- `capabilities/`: capacidades opcionales como `mutation-testing` y `windows-validation`.
- `generator/`: notas del generador determinista.
- `tests/`: pruebas del template y de generacion.
- `create_project.py`: entrypoint para crear un proyecto nuevo desde `project.yaml`.

El proyecto generado contiene scripts, estado, specs, agentes, quality gates y evidencias versionadas. El estado operativo pesado vive fuera de Git en `data/<project_id>/control` y `data/<project_id>/artifacts`.

## Inicio Rapido

1. Crea un archivo de configuracion:

```yaml
project_id: example-project
name: Example Project
output_path: /srv/agentic/workspace/example-project
profile: python
capabilities: [mutation-testing]
```

2. Genera el proyecto:

```bash
python3 create_project.py --config project.yaml
```

3. Entra al proyecto generado y valida el harness:

```bash
cd /srv/agentic/workspace/example-project
bash scripts/verify_full.sh
python3 scripts/project_status.py
```

4. Registra una feature:

```bash
python3 scripts/register_feature.py \
  --title "First product slice" \
  --slug first-product-slice \
  --description "Implementa una primera funcionalidad verificable." \
  --change-domain product
```

## Configuracion De `project.yaml`

Campos obligatorios:

- `project_id`: identificador estable del proyecto. Se usa para rutas de datos y control.
- `name`: nombre humano del proyecto.
- `output_path`: ruta absoluta o expandible donde se creara el repo generado.
- `profile`: uno de `generic`, `python`, `node`.

Campos opcionales:

- `capabilities`: lista inline con capacidades soportadas. Ejemplo: `[mutation-testing]`.

Capacidades soportadas:

- `mutation-testing`: habilita flujo de mutation testing para features que lo declaren.
- `windows-validation`: marca el proyecto como preparado para evidencia opcional de Windows.
- `git-publish`: habilita publicacion local/remota auditada de features finalizadas.

## Perfiles

- `generic`: stack neutral, util para documentacion, repos de producto mixtos o proyectos que aun no tienen toolchain propio.
- `python`: paquete Python minimo con `src/`, pruebas `pytest`, `ruff`, `compileall` y smoke tests del harness.
- `node`: proyecto ESM con `npm`, `node:test`, checks de sintaxis y gates Node agregados al `state/quality-gates.json` generado.

Ver detalles en:

- `profiles/generic/README.md`
- `profiles/python/README.md`
- `profiles/node/README.md`

## Workflow Del Proyecto Generado

El harness trabaja con una cola de features y transiciones controladas:

```text
DRAFT
  -> SPEC_READY
  -> DESIGN_READY
  -> READY_FOR_DEVELOPMENT
  -> IN_PROGRESS
  -> READY_FOR_QA
  -> APPROVED
  -> DONE
```

Comandos principales:

```bash
python3 scripts/register_feature.py --title "..." --slug my-feature --description "..."
python3 scripts/transition_feature.py --feature F-001 --to SPEC_READY --role specifier --reason "spec lista"
python3 scripts/transition_feature.py --feature F-001 --to DESIGN_READY --role architect --reason "arquitectura lista"
python3 scripts/transition_feature.py --feature F-001 --to READY_FOR_DEVELOPMENT --role leader --reason "scope aprobado"
python3 scripts/start_implementation.py --feature F-001 --agent-id implementer-1
python3 scripts/complete_implementation.py --feature F-001 --agent-id implementer-1 --reason "implementacion lista"
python3 scripts/start_review.py --feature F-001 --agent-id qa-1
python3 scripts/complete_review.py --feature F-001 --agent-id qa-1 --verdict APPROVED --summary "QA aprobado con gates verdes."
python3 scripts/finalize_feature.py --feature F-001 --reason "feature aprobada e integrada"
```

Los comandos de implementacion y QA deben ejecutarse desde el worktree asignado por el harness cuando corresponda.

## Documentacion Tecnica

- `docs/estado-y-roadmap-harness-agentico.md`: roadmap original completado, matriz de cumplimiento, commits y evidencias.
- `docs/architecture.md`: arquitectura del template, capas, control plane y contratos principales.
- `docs/development.md`: guia para modificar, probar y publicar cambios del template.
- `docs/operations.md`: operacion diaria del harness generado, lifecycle, evidencias y troubleshooting.
- `docs/quality-and-capabilities.md`: quality gates, mutation testing, mutation reviewer y validacion Windows.

Tambien se copian al proyecto generado los documentos tecnicos del core en `docs/architecture`, `docs/conventions` y `docs/windows-runner`.

## Validacion Del Template

Suite del template:

```bash
python3 -m unittest discover -s tests -v
```

Validacion recomendada antes de publicar cambios:

```bash
python3 -m unittest discover -s tests -v
python3 create_project.py --config project.yaml
cd <generated-project>
bash scripts/verify_full.sh
```

Para el cierre del roadmap se validaron proyectos reales generados:

- `/srv/agentic/workspace/test-generic-project`
- `/srv/agentic/workspace/test-python-project`
- `/srv/agentic/workspace/test-node-project`

Cada uno completo una feature `F-001` hasta `DONE`.

La capability `git-publish` se valida con tests unitarios del harness y pruebas del generador. Para push remoto real, configura `git_publish_mode: push` y un remote accesible.

## Origen Y Sincronizacion

El `core/` del template fue extraido desde:

```text
/srv/agentic/workspace/desktop-overlay-assistant
```

Commits fuente relevantes:

- `e16a7f4 feat: close spec partner bootstrap`
- `0a7c859 feat: add semantic gates and mutation capability`
- `d83012c fix: harden verification gates for noninteractive runs`
- `f596ef7 fix: locate uv in noninteractive verification`
- `de957d3 feat: execute mutation tests deterministically`

Cuando el harness fuente evolucione, sincroniza `core/`, regenera proyectos de prueba y ejecuta la suite del template antes de publicar.
