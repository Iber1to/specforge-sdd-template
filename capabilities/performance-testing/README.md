# Capability: Performance Testing

Capacidad opcional para medir comandos repetibles y generar evidencia de rendimiento sin mezclarla con tests funcionales.

## Alcance MVP

- Politica versionada en `state/capabilities/performance-testing.json`.
- Runner local de comandos repetidos.
- Warmup opcional.
- Medicion con reloj monotono.
- Timeout por run.
- Estadisticas `min_ms`, `median_ms`, `p95_ms`, `max_ms`.
- Validador determinista.
- Evidencia en `artifact_root/capabilities/performance-testing/<feature>/`.

## Uso

```bash
python3 scripts/run_performance_gate.py \
  --feature F-001 \
  --benchmark python-smoke \
  --measured-runs 3
```

Validacion:

```bash
python3 scripts/validate_performance_result.py \
  --feature F-001 \
  --evidence <artifact_root>/capabilities/performance-testing/F-001/latest.json \
  --require-pass
```

## Estado

Modo inicial: `observe`. En `observe`, un presupuesto excedido queda registrado sin bloquear salvo que la politica pase a `enforce`.
