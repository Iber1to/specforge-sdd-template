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

## Capability: Windows Validation

Activacion de proyecto:

```yaml
capabilities: [windows-validation]
```

Efecto:

- `state/project.json` marca `windows_validation_required`.
- El proyecto conserva scripts y schemas para validar evidencia Windows.

Archivos principales:

- `scripts/windows_validation.py`
- `scripts/validate_windows_evidence.py`
- `specs/schemas/windows-evidence.schema.json`
- `docs/windows-runner/evidence-contract.md`

La validacion Windows es opcional en el template core. No bloquea proyectos que no la activen.

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
