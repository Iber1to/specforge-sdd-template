# Capability: External Runtime

Capacidad opcional para ejecutar o validar trabajos fuera del runtime principal del harness manteniendo evidencia centralizada.

## Alcance MVP

- Politica versionada en `state/capabilities/external-runtime.json`.
- Target `local` para comandos deterministas.
- Target `manual-drop` para normalizar resultados externos.
- Runner: `scripts/run_external_runtime.py`.
- Validador: `scripts/validate_external_runtime_result.py`.
- Evidencia en `artifact_root/capabilities/external-runtime/<feature>/`.

## Uso

El unico modo de ejecucion es seleccionar un command template declarado en la
policy del target (`allowed_command_templates`) mediante `--command-id`. No
existe ejecucion de comandos libres.

```bash
python3 scripts/run_external_runtime.py \
  --feature F-001 \
  --target local \
  --command-id python-version
```

Validacion:

```bash
python3 scripts/validate_external_runtime_result.py \
  --feature F-001 \
  --evidence <artifact_root>/capabilities/external-runtime/F-001/latest.json \
  --require-pass
```

## Estado

Modo inicial: `observe`.

El adapter SSH queda como extension futura. El MVP ya cubre el contrato `request -> execute/collect -> validate` con target local y manual-drop.
