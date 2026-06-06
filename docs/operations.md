# Guia Operativa Del Harness Generado

Esta guia describe como usar el harness dentro de un proyecto generado por el template.

## Estado Del Proyecto

Comando principal:

```bash
python3 scripts/project_status.py
```

Muestra la cola de features, feature activa, runs activos y ultimo run completado.

Archivos utiles:

- `state/project.json`: configuracion versionada del proyecto.
- `state/workflow.json`: transiciones y roles.
- `data/<project_id>/control/queue.json`: cola operativa.
- `data/<project_id>/control/runtime.json`: runtime operativo.

## Registrar Una Feature

```bash
python3 scripts/register_feature.py \
  --title "Add export command" \
  --slug add-export-command \
  --description "Permite exportar el estado del proyecto a JSON." \
  --priority 10 \
  --requested-by "operator" \
  --change-domain product
```

Dominios:

- `product`: cambios de producto.
- `harness`: mantenimiento controlado del harness.
- `template`: cambios del template.

Capability por feature:

```bash
python3 scripts/register_feature.py \
  --title "Harden parser" \
  --slug harden-parser \
  --description "Endurece el parser y requiere mutation testing." \
  --capability mutation-testing
```

## Preparar Especificacion Y Arquitectura

El specifier completa los documentos bajo:

```text
specs/features/<feature-slug>/
  specification.md
  acceptance.yaml
  architecture.md
  implementation-plan.md
  test-plan.md
```

Transiciones:

```bash
python3 scripts/transition_feature.py \
  --feature F-001 \
  --to SPEC_READY \
  --role specifier \
  --reason "Spec v2 completa y acceptance verificable."

python3 scripts/transition_feature.py \
  --feature F-001 \
  --to DESIGN_READY \
  --role architect \
  --reason "Architecture incluye Specification Review sin bloqueos."

python3 scripts/transition_feature.py \
  --feature F-001 \
  --to READY_FOR_DEVELOPMENT \
  --role leader \
  --reason "Scope aprobado para implementacion."
```

## Implementacion

El implementer solicita un lease y worktree:

```bash
python3 scripts/start_implementation.py --feature F-001 --agent-id implementer-1
```

El script registra el run y crea un worktree aislado. La implementacion se hace en ese worktree.

Al terminar:

```bash
python3 scripts/complete_implementation.py \
  --feature F-001 \
  --agent-id implementer-1 \
  --reason "Implementacion lista con gates fast verdes."
```

Esta fase ejecuta quality gates `implementation_fast`. Un gate bloqueante fallido impide pasar a `READY_FOR_QA`.

## QA

Inicio:

```bash
python3 scripts/start_review.py --feature F-001 --agent-id qa-1
```

Completar con aprobacion:

```bash
python3 scripts/complete_review.py \
  --feature F-001 \
  --agent-id qa-1 \
  --verdict APPROVED \
  --summary "QA aprobado con suite completa y evidencias validas."
```

Completar con cambios requeridos:

```bash
python3 scripts/complete_review.py \
  --feature F-001 \
  --agent-id qa-1 \
  --verdict CHANGES_REQUESTED \
  --summary "QA encontro una regresion verificable." \
  --required-change "Corregir el caso limite documentado en el test plan."
```

QA ejecuta gates `qa_full`. No se permite `APPROVED` si los gates bloqueantes fallan.

## Finalizacion

```bash
python3 scripts/finalize_feature.py \
  --feature F-001 \
  --reason "Feature aprobada e integrada."
```

La finalizacion ejecuta gates `finalization`, integra la feature aprobada y mueve el estado a `DONE`.

## Publicacion Git

Si el proyecto tiene `git_publication.enabled: true`, una feature finalizada puede publicarse con:

```bash
uv run python scripts/publish_feature.py --feature F-001
```

El agente recomendado es `repository-publisher`. El agente no debe ejecutar `git push` directamente; Role Guard lo bloquea.

Modos soportados:

- `local`: registra evidencia de integracion local.
- `dry_run`: verifica que el push remoto seria posible.
- `push`: sube la rama canonica al remote configurado.
- `disabled`: desactiva publicacion.

La evidencia queda en:

```text
artifact_root/git-publish/<feature>/
```

Para activar push remoto en un proyecto generado, configura `state/project.json` o `project.yaml`:

```yaml
capabilities: [git-publish]
git_publish_mode: push
git_publish_remote: origin
git_publish_branch: main
```

## Mutation Testing

Para features con capability `mutation-testing`:

```bash
python3 scripts/mutation_runner.py \
  --feature F-001 \
  --output "$ARTIFACT_ROOT/mutation-tests/F-001/latest.json" \
  --max-mutants 100 \
  --max-duration-seconds 600 \
  --test-command python3 -m pytest -q
```

El mutation reviewer debe registrar evidencia en:

```text
evidence/mutation-reviews/F-001.json
```

La aprobacion requiere cero mutantes supervivientes relevantes sin justificar. Cualquier `test_gap` debe producir `CHANGES_REQUESTED`.

## External Runtime

```bash
python3 scripts/run_external_runtime.py \
  --feature F-001 \
  --target local \
  --command python3 --version
```

Evidencia:

```text
artifact_root/capabilities/external-runtime/<feature>/latest.json
```

## Performance Testing

```bash
python3 scripts/run_performance_gate.py \
  --feature F-001 \
  --benchmark python-smoke \
  --measured-runs 3
```

Evidencia:

```text
artifact_root/capabilities/performance-testing/<feature>/latest.json
```

## Security Scanning

```bash
python3 scripts/run_security_scan.py --feature F-001
```

Evidencia:

```text
artifact_root/capabilities/security-scanning/<feature>/latest.json
```

## Evidencias

Versionadas en Git:

- `evidence/implementations/<feature>.json`
- `evidence/reviews/<feature>.json`
- `evidence/mutation-reviews/<feature>.json`

Fuera de Git:

- `artifact_root/quality-gates/<feature>/`
- `artifact_root/mutation-tests/<feature>/`

## Recuperacion

Si un lease queda colgado:

```bash
python3 scripts/recover_stale_leases.py
```

Si necesitas inspeccionar locks, leases o runs, revisa `data/<project_id>/control/`, pero aplica cambios de estado solo mediante scripts.

## Problemas Frecuentes

### `uv` No Aparece En SSH No Interactivo

Los scripts de verificacion exportan `PATH="$HOME/.local/bin:$PATH"` y tienen fallback a `.venv/bin`. Si aun falla, comprueba:

```bash
which uv
ls -la "$HOME/.local/bin/uv"
```

### Un Gate Bloqueante Falla

Busca la evidencia JSON en:

```text
artifact_root/quality-gates/<feature>/
```

El JSON pequeno apunta al log pesado con stdout/stderr.

### QA No Puede Aprobar

Comprueba:

- estado actual de la feature
- lease activo de QA
- que el worktree no haya cambiado desde `reviewed_commit`
- gates `qa_full`
- evidencia mutation si la feature requiere `mutation-testing`

### Git Publish Falla

Comprueba:

- la feature esta en `DONE`
- el repositorio canonico esta limpio
- la rama actual es la canonica
- `merged_commit` coincide con `HEAD` si `require_merged_head` esta activo
- existe el remote configurado para `dry_run` o `push`
- las credenciales Git del host permiten escribir en el remote
