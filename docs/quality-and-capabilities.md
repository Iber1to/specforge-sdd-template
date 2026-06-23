# Quality Gates Y Capacidades

Este documento resume los gates y capacidades opcionales del template.

## Quality Gates

La configuracion versionada vive en:

```text
state/quality-gates.json
```

Ejemplo base:

```json
{
  "schema_version": 1,
  "gates": [
    {
      "id": "GATE-001",
      "phase": "implementation_fast",
      "command": ["bash", "scripts/verify_fast.sh"],
      "blocking": true,
      "timeout_seconds": 900
    }
  ]
}
```

Campos:

- `id`: identificador estable.
- `phase`: fase donde se ejecuta.
- `command`: comando como lista de strings.
- `blocking`: si `true`, un fallo bloquea la transicion.
- `timeout_seconds`: limite de ejecucion.

## Fases

`implementation_fast`:

- Se ejecuta al completar implementacion.
- Bloquea `READY_FOR_QA` si falla un gate bloqueante.
- Default: `bash scripts/verify_fast.sh`.

`qa_full`:

- Se ejecuta al completar QA.
- Impide `APPROVED` si falla un gate bloqueante.
- Default: `bash scripts/verify_full.sh`.

`finalization`:

- Se ejecuta antes de finalizar.
- Bloquea `DONE` si falla un gate bloqueante.
- Default: `bash scripts/verify_full.sh`.

`optional_capability`:

- Reservada para capacidades que tengan verificaciones propias.
- Puede usarse para mutation testing u otras capacidades futuras.

## Evidencia De Gates

Cada ejecucion produce:

- evidencia JSON estructurada
- log completo de stdout/stderr

Ubicacion:

```text
artifact_root/quality-gates/<feature>/<run>-<phase>.json
artifact_root/quality-gates/<feature>/<run>-<phase>-<gate>.log
```

Estados:

- `PASS`: todos los gates pasaron.
- `WARN`: fallaron gates no bloqueantes.
- `FAIL`: fallo al menos un gate bloqueante.

## Capability: Mutation Testing

Activacion por feature:

```bash
python3 scripts/register_feature.py \
  --title "Improve parser checks" \
  --slug improve-parser-checks \
  --description "Endurece parser y tests." \
  --capability mutation-testing
```

Runner:

```bash
python3 scripts/mutation_runner.py \
  --feature F-001 \
  --output /path/to/artifacts/mutation-tests/F-001/latest.json \
  --max-mutants 100 \
  --max-duration-seconds 600 \
  --test-command python3 -m pytest -q
```

Alcance inicial:

- Python.
- Codigo cambiado.
- Mutaciones deterministas de booleanos, comparadores, operadores aritmeticos simples y operadores logicos.

Salida:

- `generated`
- `killed`
- `survived`
- `invalid`
- lista de mutantes con ubicacion, operador y resultado

Revision:

- Agente: `mutation-reviewer`.
- Evidencia: `evidence/mutation-reviews/<feature>.json`.
- Schema: `specs/schemas/mutation-review.schema.json`.
- Validador: `scripts/mutation_review_validation.py`.

Regla de bloqueo:

- Si hay `test_gap`, QA debe emitir `CHANGES_REQUESTED`.
- Si sobreviven mutantes relevantes sin justificacion, no se debe aprobar.

## Capability: External Runtime

Activacion de proyecto o feature:

```yaml
capabilities: [external-runtime]
```

Runner:

```bash
python3 scripts/run_external_runtime.py \
  --feature F-001 \
  --target local \
  --command-id python-version
```

Validador:

```bash
python3 scripts/validate_external_runtime_result.py \
  --feature F-001 \
  --evidence <artifact_root>/capabilities/external-runtime/F-001/latest.json \
  --require-pass
```

El MVP incluye target `local` y `manual-drop`. SSH queda como extension futura.

## Capability: Performance Testing

Activacion:

```yaml
capabilities: [performance-testing]
```

Runner:

```bash
python3 scripts/run_performance_gate.py \
  --feature F-001 \
  --benchmark python-smoke \
  --measured-runs 3
```

Produce estadisticas `min_ms`, `median_ms`, `p95_ms` y `max_ms`. El modo inicial es `observe`; `enforce` puede bloquear cuando se estabilicen benchmarks criticos.

## Capability: Security Scanning

Activacion:

```yaml
capabilities: [security-scanning]
```

Runner:

```bash
python3 scripts/run_security_scan.py --feature F-001
```

El MVP detecta secretos por regex, ficheros sensibles como `.env`, claves privadas y tokens comunes. Redacta muestras sensibles en la evidencia.

## Capability: Eval Harness

Activacion:

```yaml
capabilities: [eval-harness]
```

Objetivo:

- convertir cada escenario `SCN-XXX` de una feature en graders ejecutables
- cerrar la trazabilidad `AC-XXX -> SCN-XXX -> grader -> evidencia`
- decidir el gate de calidad de forma determinista, sin depender del juicio del modelo

Definicion de graders por feature:

```text
specs/features/<FEATURE>/evals.json
```

Tipos de grader:

- `code`: ejecuta un comando; pasa si el exit code es `0`. Elegible para gate.
- `rule`: restriccion determinista sobre ficheros (`file_exists`, `file_contains`, `file_absent`). Elegible para gate.
- `model`: LLM-as-judge con rubrica. Consultivo, nunca decide el gate automatico.
- `human`: adjudicacion manual. Consultivo.

Runner:

```bash
python3 scripts/run_evals.py --feature F-001 --scope repository
```

Cada grader elegible se ejecuta `runs` veces (politica). Se calculan `pass_at_k`
(al menos una ejecucion pasa) y `pass_caret_k` (todas pasan).

Validador:

```bash
python3 scripts/validate_eval_result.py \
  --feature F-001 \
  --evidence <artifact_root>/capabilities/eval-harness/F-001/latest.json \
  --require-pass
```

Politica:

```text
state/capabilities/eval-harness.json
```

Campos:

- `mode`: `observe` (no bloquea) o `enforce` (bloquea en fallo).
- `runs`: repeticiones por grader (default 1).
- `pass_at_k_min`: ratio minimo para graders de capacidad.
- `require_pass_caret_k_for_release_critical`: exige `pass_caret_k = 1.00` en graders `release_critical`.
- `grader_timeout_seconds`: limite por comando `code`.

Gate:

- `EVAL-001` en fase `qa_full`, modo `observe` por defecto.
- En `enforce`, cualquier grader `code`/`rule` elegible que no pase produce `FAILED`.
- Los graders `model`/`human` se registran como `SKIPPED` consultivo y no bloquean.

Schema de evidencia: `specs/schemas/eval-result.schema.json`. Decision:
`docs/adr-0002-eval-harness-verification-gate.md`. Capability source:
`affaan-m/ECC` (`skills/eval-harness/SKILL.md`), adaptado a ejecucion determinista.

## Capability: Tool Telemetry

Activacion:

```yaml
capabilities: [tool-telemetry]
```

Objetivo:

- registrar cada llamada a herramienta (`PreToolUse`/`PostToolUse`) como una
  linea JSONL determinista (telemetria/evidencia de que herramientas usa cada rol)
- redactar secretos antes de persistir
- alimentar auditoria y observabilidad sin alterar el comportamiento de los agentes

No es un gate ni aprende patrones: es la capa de sustrato (hooks -> JSONL)
inspirada en el continuous-learning de `affaan-m/ECC`. Se descarto a proposito el
motor de "instintos" auto-aprendidos por ser contrario al determinismo SDD.

Cableado de hooks:

- `core/.claude/settings.json` cablea `PreToolUse` (matcher `""`) y `PostToolUse`
  a `hook_entrypoint.sh tool_telemetry`.
- Si la capability no esta instalada, el hook es **no-op** (no rompe el proyecto).
- Script: `scripts/tool_telemetry_hook.py` (fail-soft: siempre exit 0).

Politica:

```text
state/capabilities/tool-telemetry.json
```

Campos:

- `enabled`: activa/desactiva la captura.
- `scrub_secrets`: redacta api_key/token/secret/password/claves privadas/AWS.
- `max_value_chars`: trunca `tool_input`/`tool_response` largos.

Evidencia:

```text
artifact_root/capabilities/tool-telemetry/observations-<YYYYMMDD>.jsonl
```

Cada linea incluye `timestamp`, `event`, `tool`, `session`, `agent` y, si
existen, `tool_input`/`tool_response` redactados y truncados.

## Capability: Windows Validation

Activacion de proyecto:

```yaml
capabilities: [windows-validation]
```

Efecto:

- `state/project.json` marca `windows_validation_available`.
- La obligatoriedad de evidencia Windows es por feature, no global.
- El proyecto conserva scripts y schemas para validar evidencia Windows.

Archivos principales:

- `scripts/collect_windows_evidence.py`
- `scripts/windows_validation.py`
- `scripts/validate_windows_evidence.py`
- `specs/schemas/windows-evidence.schema.json`
- `docs/windows-runner/evidence-contract.md`

La validacion Windows es opcional en el template core. No bloquea proyectos que no la activen.

Runner minimo:

```bash
python3 scripts/collect_windows_evidence.py --feature F-001 --commit <commit>
```

En Jarvis puede ejecutarse un smoke de infraestructura con `--allow-non-windows`; en Windows real el check de plataforma debe pasar sin override.

## Capability: Documentation Pack

Activacion:

```yaml
capabilities: [documentation-pack]
```

Esta capability esta activa por defecto en todos los perfiles generados.

Objetivo:

- crear una estructura tecnica minima en `docs/`
- separar documentacion estable de specs por feature
- documentar runtime, arquitectura, calidad, operaciones y releases
- regenerar indices y resumenes derivados en `docs/90-generated/`

Scripts:

```bash
python3 scripts/refresh_project_docs.py
python3 scripts/generate_docs_index.py
python3 scripts/refresh_feature_index.py
python3 scripts/refresh_quality_summary.py
python3 scripts/refresh_metrics_summary.py
```

Politica:

```text
state/capabilities/documentation-pack.json
specs/schemas/documentation-policy.schema.json
```

Regla de autoridad:

- `docs/90-generated/` no es fuente de verdad.
- La fuente de verdad sigue siendo `state/`, `control_root`, `specs/features/`, `evidence/` y Git.

Gate de finalizacion:

`acceptance.yaml` puede declarar requirements documentales:

```yaml
documentation:
  requires_adr: true
  requires_runtime_update: false
  requires_operations_update: true
  requires_quality_update: false
```

`scripts/finalize_feature.py` valida los cambios revisados por QA antes de
integrar la feature. Si una requirement documental esta marcada como `true` y
el diff revisado no contiene el documento correspondiente, la feature no pasa a
`DONE`.

## Capability: Git Publish

Activacion de proyecto:

```yaml
capabilities: [git-publish]
git_publish_mode: local
git_publish_remote: origin
git_publish_branch: main
git_publish_auto: false
```

Objetivo:

- registrar o publicar features ya finalizadas (`DONE`) en Git local o remoto
- impedir `git push` directo desde agentes
- guardar evidencia auditada de la publicacion

Script:

```bash
uv run python scripts/publish_feature.py --feature F-001
```

Agente:

- `repository-publisher`

Modos:

- `local`: registra que el merge local quedo integrado.
- `dry_run`: valida el push remoto con `git push --dry-run`.
- `push`: sube `HEAD` a `refs/heads/<branch>` del remote configurado.
- `disabled`: no publica.

Evidencia:

```text
artifact_root/git-publish/<feature>/<operation>.json
artifact_root/git-publish/<feature>/latest.json
```

Reglas de bloqueo:

- La feature debe estar en `DONE`.
- El repo canonico debe estar limpio.
- El `merged_commit` de la feature debe pertenecer al `HEAD`.
- Por defecto, `merged_commit` debe ser exactamente `HEAD` para evitar publicar commits posteriores por accidente.
- `dry_run` y `push` requieren un remote Git existente.

## Capability: Remote Notifications

Activacion de proyecto:

```yaml
capabilities: [remote-notifications]
```

Objetivo:

- avisar por Telegram cuando el leader se detiene, bloquea una feature o
  completa el trabajo (`scripts/notify.py`, instruido en `leader.md`)
- red de seguridad determinista via hooks `Stop`/`Notification` de Claude Code
  (`scripts/notify_hook.py` a traves de `hook_entrypoint.sh notify`; no-op si la
  capability no esta instalada)
- gateway bidireccional opcional (`scripts/telegram_gateway.py`): `/status`,
  `/tail` y texto libre inyectado como prompt en la sesion tmux del leader

Notificacion explicita:

```bash
uv run python scripts/notify.py --event blocked --feature F-001 --message "<motivo>"
```

Gateway (sesion tmux persistente):

```bash
bash scripts/run_gateway.sh
```

Politica:

```text
state/capabilities/remote-notifications.json
```

Reglas:

- Fail-soft: una notificacion fallida nunca bloquea el harness (exit 0 salvo
  `--strict`).
- Credenciales fuera de Git (`~/.config/agentic-harness/telegram.env`); el token
  se redacta en errores.
- Solo el `chat_id` autorizado puede hablar con el gateway.

Setup completo: `docs/notifications/setup.md` (en el proyecto generado) o
`capabilities/remote-notifications/docs/notifications/setup.md` (en el template).

## Perfil Node Y Gates Adicionales

El perfil `node` agrega gates especificos:

- `npm test` en `implementation_fast`
- `npm test` en `qa_full`
- `npm run lint` en `qa_full`
- `npm test` en `finalization`

Esto permite que el proyecto generado valide tanto el harness Python como el stack Node.

## Buenas Practicas

- Mantener gates rapidos en `implementation_fast`.
- Reservar suites completas para `qa_full` y `finalization`.
- Guardar logs pesados fuera de Git.
- Hacer que cada gate tenga un proposito claro y nombre estable.
- Evitar gates no deterministas como requisito bloqueante.
- Para capacidades opcionales, documentar siempre evidencia, validador y regla de bloqueo.
