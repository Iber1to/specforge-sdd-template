# Capability: Tool Telemetry

Capacidad opcional que registra cada llamada a herramienta (`PreToolUse` y
`PostToolUse`) como una linea JSONL determinista, con scrubbing de secretos. Es
la capa de **telemetria/evidencia** (sustrato `hooks -> JSONL`) inspirada en el
continuous-learning de `affaan-m/ECC`. Se descarto a proposito el motor de
"instintos" auto-aprendidos por ser contrario al determinismo del flujo SDD.

## Activacion

Por proyecto:

```yaml
capabilities: [tool-telemetry]
```

## Cableado de hooks

- `core/.claude/settings.json` cablea `PreToolUse` (matcher `""`) y `PostToolUse`
  a `hook_entrypoint.sh tool_telemetry`.
- Sin la capability instalada, el hook es **no-op** (el dispatcher comprueba la
  existencia de `scripts/tool_telemetry_hook.py` y sale con exito).
- El hook es **fail-soft**: cualquier error devuelve exit 0 y nunca rompe la
  llamada a la herramienta.

## Politica

```text
state/capabilities/tool-telemetry.json
```

- `enabled`: activa o desactiva la captura (sin desinstalar el hook).
- `scrub_secrets`: redacta `api_key`/`token`/`secret`/`password`/`authorization`,
  claves privadas y claves AWS antes de persistir.
- `max_value_chars`: trunca `tool_input`/`tool_response` largos.

## Evidencia

```text
artifact_root/capabilities/tool-telemetry/observations-<YYYYMMDD>.jsonl
```

Cada linea: `timestamp`, `event`, `tool`, `session`, `agent` y, cuando existen,
`tool_input`/`tool_response` redactados y truncados. Es un artefacto pesado: vive
en `artifact_root`, fuera de Git.

## Alcance Actual

- Captura determinista por hook, una linea por evento.
- Scrubbing por regex (inline y JSON) de secretos comunes.
- No hay analisis ni aprendizaje: solo registro. El consumo posterior
  (auditoria, metricas) queda fuera de esta capability.
