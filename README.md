# Agentic SDD Template

Template reutilizable para crear proyectos con un harness de Spec Driven Development agentico. Incluye el plano de control, agentes, scripts deterministas, contratos de especificacion, gates de calidad, capacidades opcionales y perfiles base para proyectos genericos, Python y Node.

Estado actual: extraido y validado en `jarvis:/srv/agentic/workspace/agentic-sdd-template` el 2026-06-06. El roadmap original quedo cerrado y documentado en `docs/estado-y-roadmap-harness-agentico.md`.

## Que Incluye

- `core/`: harness comun que se copia a cada proyecto generado.
- `profiles/`: adaptadores de stack para `generic`, `python` y `node`.
- `capabilities/`: capacidades como `documentation-pack`, `mutation-testing` y `windows-validation`.
- `generator/`: notas del generador determinista.
- `tests/`: pruebas del template y de generacion.
- `create_project.py`: entrypoint para crear un proyecto nuevo desde `project.yaml`.

El proyecto generado contiene scripts, estado, specs, agentes, quality gates y evidencias versionadas. El estado operativo pesado vive fuera de Git en `data/<project_id>/control` y `data/<project_id>/artifacts`.

## Requisitos Y Plataforma

El harness de orquestacion (leader, scripts deterministas, Role Guard) esta
disenado para ejecutarse en un host Linux. Requisitos:

- Linux (el plano de control usa bloqueo de archivos POSIX por defecto; en
  Windows degrada a `msvcrt`).
- Python 3.12 y `uv` disponibles en PATH.
- `git` y `bash`.
- Node.js solo para proyectos generados con `profile: node`.

Comprueba el entorno antes de generar o validar (preflight):

```bash
python3 core/scripts/check_environment.py            # antes de generar
python3 scripts/check_environment.py --profile node  # dentro de un proyecto node
```

En entornos sin acceso para descargar Python, exporta `UV_PYTHON_DOWNLOADS=never`
para que `uv` falle de forma explicita en vez de intentar descargar el runtime 3.12.

Notas importantes:

- Los hooks del Role Guard se ejecutan mediante `scripts/hook_entrypoint.sh`, que
  resuelve el interprete Python (`.venv/bin/python` -> `python3` -> `python`) y
  falla cerrado si no encuentra ninguno.
- Los proyectos generados con `profile: node` tambien incluyen los quality gates
  base del harness (`verify_fast.sh`/`verify_full.sh`), que ejecutan `ruff`,
  `pytest` y `compileall`. Por tanto un proyecto node requiere Python, `uv`,
  `ruff` y `pytest` para pasar QA y finalizacion, ademas de Node.
- Solo el runner de la capability `windows-validation` esta pensado para
  ejecutarse en una workstation Windows real.
- Los scripts bajo `capabilities/<cap>/scripts/` NO se ejecutan directamente
  desde el template: importan modulos de `core/scripts/` y solo son ejecutables
  una vez ensamblados en un proyecto generado (el generador los copia a
  `scripts/`). Para probarlos, genera un proyecto primero.

## Convencion De Idioma

La documentacion operativa y los agentes estan en espanol. Los identificadores,
las claves de esquema JSON y los nombres de estado se mantienen en ingles. Las
plantillas de specs usan ingles por compatibilidad con los validadores.

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

- `documentation-pack`: activa por defecto; genera estructura documental tecnica y scripts de refresco.
- `mutation-testing`: habilita flujo de mutation testing para features que lo declaren.
- `windows-validation`: marca el proyecto como preparado para evidencia opcional de Windows.
- `git-publish`: habilita publicacion local/remota auditada de features finalizadas.
- `external-runtime`: ejecuta o normaliza jobs externos con evidencia estructurada.
- `performance-testing`: mide comandos repetibles y registra estadisticas de rendimiento.
- `security-scanning`: detecta secretos y ficheros sensibles en modo observe.

## Perfiles

- `generic`: stack neutral, util para documentacion, repos de producto mixtos o proyectos que aun no tienen toolchain propio.
- `python`: paquete Python minimo con `src/`, pruebas `pytest`, `ruff`, `compileall` y smoke tests del harness.
- `node`: proyecto ESM con `npm`, `node:test`, checks de sintaxis y gates Node agregados al `state/quality-gates.json` generado.

Ver detalles en:

- `profiles/generic/README.md`
- `profiles/python/README.md`
- `profiles/node/README.md`

La matriz de combinaciones perfil x capability soportadas esta en
`docs/profile-capability-matrix.md`.

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

El template genera dos niveles de documentacion:

- Documentacion del harness/template: contratos de agentes, scripts, workflow, quality gates y capabilities.
- Documentacion tecnica del proyecto generado: estructura numerada bajo `docs/`.

Regla de organizacion del proyecto generado:

- `docs/`: documentacion viva y estable del proyecto.
- `specs/features/`: documentacion trazable de cada feature concreta.
- `evidence/`: evidencias ligeras versionadas.
- `control_root` y `artifact_root`: estado operativo, evidencias pesadas, artefactos y metricas.

La capability `documentation-pack` viene activa por defecto en `generic`, `python` y `node`. Genera:

- `docs/00-project/`
- `docs/10-architecture/`
- `docs/20-runtime/`
- `docs/30-quality/`
- `docs/40-operations/`
- `docs/50-releases/`
- `docs/90-generated/`

Scripts de refresco en proyectos generados:

```bash
python3 scripts/refresh_project_docs.py
python3 scripts/generate_docs_index.py
python3 scripts/refresh_feature_index.py
python3 scripts/refresh_quality_summary.py
python3 scripts/refresh_metrics_summary.py
```

`docs/90-generated/` no es fuente de verdad. Se puede borrar y regenerar.

`acceptance.yaml` tambien puede declarar requirements documentales. La
finalizacion bloquea `DONE` cuando una feature exige ADR, runtime, operaciones
o calidad y el diff revisado por QA no incluye la documentacion correspondiente.

- `docs/estado-y-roadmap-harness-agentico.md`: roadmap original completado, matriz de cumplimiento, commits y evidencias.
- `docs/architecture.md`: arquitectura del template, capas, control plane y contratos principales.
- `docs/development.md`: guia para modificar, probar y publicar cambios del template.
- `docs/operations.md`: operacion diaria del harness generado, lifecycle, evidencias y troubleshooting.
- `docs/quality-and-capabilities.md`: quality gates, mutation testing, mutation reviewer y validacion Windows.
- `docs/language-and-style.md`: convencion de idioma, acentos, naming, errores y commits.
- `docs/naming-and-contracts.md`: vocabulario canonico de los contratos JSON.

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
