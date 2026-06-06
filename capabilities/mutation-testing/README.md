# Capability: Mutation Testing

Capacidad opcional para exigir mutation testing en features seleccionadas.

## Activacion

Por feature:

```bash
python3 scripts/register_feature.py \
  --title "Improve critical logic" \
  --slug improve-critical-logic \
  --description "Endurece logica critica y sus tests." \
  --capability mutation-testing
```

## Runner

```bash
python3 scripts/mutation_runner.py \
  --feature F-001 \
  --output /srv/agentic/workspace/data/<project_id>/artifacts/mutation-tests/F-001/latest.json \
  --max-mutants 100 \
  --max-duration-seconds 600 \
  --test-command python3 -m pytest -q
```

## Alcance Actual

- Lenguaje: Python.
- Alcance: codigo cambiado.
- Mutaciones:
  - booleanos
  - comparadores
  - operadores aritmeticos simples
  - operadores logicos

## Evidencia

Artefacto runner:

```text
artifact_root/mutation-tests/<feature>/latest.json
```

Revision:

```text
evidence/mutation-reviews/<feature>.json
```

## Regla De Aprobacion

- Cero mutantes supervivientes relevantes sin justificar.
- Cualquier `test_gap` fuerza `CHANGES_REQUESTED`.
- La evidencia debe validar contra `specs/schemas/mutation-review.schema.json`.
