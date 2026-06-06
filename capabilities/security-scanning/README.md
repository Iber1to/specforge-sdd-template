# Capability: Security Scanning

Capacidad opcional para detectar secretos y configuraciones sensibles con checks locales de bajo ruido.

## Alcance MVP

- Politica versionada en `state/capabilities/security-scanning.json`.
- Scanner determinista de secretos y ficheros sensibles.
- Redaccion de muestras sensibles.
- Salida normalizada con severidades.
- Validador determinista.
- Evidencia en `artifact_root/capabilities/security-scanning/<feature>/`.

## Uso

```bash
python3 scripts/run_security_scan.py --feature F-001
```

Validacion:

```bash
python3 scripts/validate_security_result.py \
  --feature F-001 \
  --evidence <artifact_root>/capabilities/security-scanning/F-001/latest.json \
  --require-pass
```

## Estado

Modo inicial: `observe`. Los hallazgos quedan registrados y normalizados; el bloqueo por severidad critica se activa al cambiar la politica a `enforce`.
