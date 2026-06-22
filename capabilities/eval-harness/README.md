# Capability: Eval Harness

Capacidad opcional para convertir cada escenario `SCN-XXX` de una feature en
*graders* ejecutables y exigir su resultado como evidencia de calidad. Cierra la
trazabilidad `AC-XXX -> SCN-XXX -> grader -> evidencia`.

Inspirada en el patron `eval-harness` de `affaan-m/ECC` (MIT), reexpresado como
artefacto determinista gobernado por scripts del harness. Decision registrada en
`docs/adr-0002-eval-harness-verification-gate.md`.

## Activacion

Por proyecto:

```yaml
capabilities: [eval-harness]
```

Por feature:

```bash
python3 scripts/register_feature.py \
  --title "Harden parser scenarios" \
  --slug harden-parser-scenarios \
  --description "Anade graders ejecutables a los escenarios criticos." \
  --capability eval-harness
```

## Definicion de graders

Cada feature declara sus graders en `specs/features/<FEATURE>/evals.json`:

```json
{
  "schema_version": 1,
  "feature_id": "F-001",
  "graders": [
    {
      "id": "G-001",
      "scenario": "SCN-001",
      "type": "code",
      "command": ["python3", "-m", "pytest", "tests/test_parser.py", "-q"],
      "gate": true,
      "release_critical": true
    },
    {
      "id": "G-002",
      "scenario": "SCN-002",
      "type": "rule",
      "rule": {"kind": "file_contains", "path": "src/parser.py", "pattern": "def parse_hand"},
      "gate": true
    },
    {
      "id": "G-003",
      "scenario": "SCN-003",
      "type": "model",
      "rubric": "La salida explica el rango en lenguaje natural.",
      "gate": false
    }
  ]
}
```

Tipos de grader:

- `code` -- ejecuta un comando; pasa si el exit code es `0`. Elegible para gate.
- `rule` -- restriccion determinista sobre ficheros. Elegible para gate.
- `model` -- LLM-as-judge con rubrica. Consultivo, nunca decide el gate automatico.
- `human` -- adjudicacion manual. Consultivo.

Reglas `rule` soportadas (`kind`): `file_exists`, `file_contains` (con `pattern`
regex) y `file_absent`.

## Runner

```bash
python3 scripts/run_evals.py --feature F-001 --scope repository
```

Cada grader elegible se ejecuta `runs` veces (politica). Se calculan `pass_at_k`
(al menos una ejecucion pasa) y `pass_caret_k` (todas pasan).

## Politica

`state/capabilities/eval-harness.json`:

- `mode`: `observe` (no bloquea) o `enforce` (bloquea en fallo).
- `runs`: repeticiones por grader (default 1).
- `pass_at_k_min`: ratio minimo para graders de capacidad.
- `require_pass_caret_k_for_release_critical`: exige `pass_caret_k = 1.00` en graders `release_critical`.
- `grader_timeout_seconds`: limite por comando `code`.

## Evidencia y validacion

```text
artifact_root/capabilities/eval-harness/<feature>/latest.json
```

```bash
python3 scripts/validate_eval_result.py \
  --feature F-001 \
  --evidence <artifact_root>/capabilities/eval-harness/F-001/latest.json \
  --require-pass
```

Schema: `specs/schemas/eval-result.schema.json`.

## Regla de aprobacion

- En `enforce`, cualquier grader `code`/`rule` elegible que no pase produce
  `status=FAILED` y devuelve exit code 2.
- Los graders `release_critical` exigen `pass_caret_k = 1.00` cuando
  `require_pass_caret_k_for_release_critical` esta activo.
- Los graders `model`/`human` se registran como `SKIPPED` consultivo y nunca bloquean.
- Un escenario `SCN-XXX` sin al menos un grader `code` o `rule` se reporta en
  `unverifiable_scenarios`.
