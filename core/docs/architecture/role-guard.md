# Role Guard de Claude Code

## Objetivo

El Role Guard aplica materialmente las restricciones de cada agente mediante
hooks deterministas de Claude Code.

Las instrucciones de los agentes orientan el comportamiento; el Role Guard
impide operaciones no autorizadas antes de que se ejecuten.

## Hooks instalados

### SessionStart

Registra el rol de la sesión principal. Claude Code reporta la sesión principal
como `agent_type: "claude"` (no transmite `--agent leader` al hook), por lo que el
rol se toma de la variable de entorno `CLAUDE_HARNESS_ROLE`, fijada por el operador
al lanzar:

```bash
CLAUDE_HARNESS_ROLE=leader claude --agent leader
```

Las sesiones sin esa variable quedan clasificadas como `unscoped` y no pueden
utilizar herramientas mutantes. Los subagentes se identifican por su `agent_type`
y no dependen de esta variable.

### PreToolUse

Intercepta las herramientas mutantes antes de su ejecución:

- `Write`
- `Edit`
- `Bash`
- `Agent`
- herramientas de equipos, workflows y worktrees no controlados por el harness

Un bloqueo devuelve exit code `2`; Claude Code cancela la llamada incluso en
`bypassPermissions`.

### ConfigChange

Bloquea cambios de settings del proyecto o settings locales durante una sesión
protegida.

## Políticas por rol

### Leader

- Puede consultar estado y ejecutar scripts deterministas de orquestación.
- Puede lanzar únicamente `specifier`, `architect`, `implementer` y
  `qa-reviewer`.
- No puede escribir directamente mediante `Write` o `Edit`.
- Solo puede añadir a Git documentos bajo `specs/features/`.

### Specifier

Solo puede escribir:

- `specification.md`
- `acceptance.yaml`

de features que estén en estado `DRAFT`.

### Architect

Solo puede escribir:

- `architecture.md`
- `implementation-plan.md`
- `test-plan.md`

de features que estén en estado `SPEC_READY` o `DESIGN_READY`.

### Implementer

- Debe tener exactamente un lease activo.
- Solo puede escribir dentro del worktree asignado.
- Sus escrituras se limitan a `src/`, `tests/`, `runtime/external/`,
  `pyproject.toml` y `uv.lock`.
- Bash se limita al worktree y a una allowlist de comandos de desarrollo.
- Solo puede ejecutar `heartbeat_lease.py` y `complete_implementation.py` del
  harness.

### QA Reviewer

- No puede escribir directamente.
- Debe tener exactamente un lease QA activo.
- Bash se limita a lecturas, verificaciones, `heartbeat_lease.py` y
  `complete_review.py`.

## Auditoría

Las decisiones se registran en:

`<control_root>/role-guard/audit.jsonl`

Las asociaciones entre sesión y rol se guardan en:

`<control_root>/role-sessions/`

## Validación manual

Después de instalar:

```bash
uv run pytest -q tests/unit/test_role_guard.py
./scripts/verify_full.sh
```

Al iniciar Claude Code:

```bash
CLAUDE_HARNESS_ROLE=leader claude --agent leader
```

Dentro de la sesión, utiliza `/hooks` para confirmar que aparecen los hooks de
proyecto `SessionStart`, `PreToolUse` y `ConfigChange`.
