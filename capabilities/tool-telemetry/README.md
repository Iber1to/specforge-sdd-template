# Capability: Tool Telemetry

Optional capability that records each tool call (`PreToolUse` and
`PostToolUse`) as a deterministic JSONL line, with secret scrubbing. It is
the **telemetry/evidence** layer (`hooks -> JSONL` substrate) inspired by the
continuous-learning of `affaan-m/ECC`. The self-learned "instincts" engine was
deliberately discarded as contrary to the determinism of the SDD flow.

## Activation

Per project:

```yaml
capabilities: [tool-telemetry]
```

## Hook wiring

- `core/.claude/settings.json` wires `PreToolUse` (matcher `""`) and `PostToolUse`
  to `hook_entrypoint.sh tool_telemetry`.
- Without the capability installed, the hook is a **no-op** (the dispatcher checks
  the existence of `scripts/tool_telemetry_hook.py` and exits successfully).
- The hook is **fail-soft**: any error returns exit 0 and never breaks the
  tool call.

## Policy

```text
state/capabilities/tool-telemetry.json
```

- `enabled`: enables or disables capture (without uninstalling the hook).
- `scrub_secrets`: redacts `api_key`/`token`/`secret`/`password`/`authorization`,
  private keys and AWS keys before persisting.
- `max_value_chars`: truncates long `tool_input`/`tool_response`.

## Evidence

```text
artifact_root/capabilities/tool-telemetry/observations-<YYYYMMDD>.jsonl
```

Each line: `timestamp`, `event`, `tool`, `session`, `agent` and, when present,
redacted and truncated `tool_input`/`tool_response`. It is a heavy artifact: it lives
in `artifact_root`, outside Git.

## Current Scope

- Deterministic capture per hook, one line per event.
- Regex scrubbing (inline and JSON) of common secrets.
- No analysis or learning: only recording. Downstream consumption
  (auditing, metrics) is outside this capability.
