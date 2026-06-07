# Operacion del Leader: persistente y autonoma

Como operar el leader contra un servidor remoto sin perder la sesion al
desconectar, y como dejarlo trabajando de forma autonoma.

## Nivel 1 — Sesion persistente (tmux)

Una sesion interactiva de `claude` muere al caer la conexion SSH (SIGHUP). Para
que sobreviva, se ejecuta dentro de `tmux` en el servidor.

```bash
cd <proyecto-generado>
bash scripts/run_leader.sh
```

`run_leader.sh`:

- Crea (o reconecta) una sesion tmux llamada `leader`.
- Exporta `CLAUDE_HARNESS_ROLE=leader` (necesario: Claude Code reporta la sesion
  principal como `agent_type: "claude"`, ver `docs/architecture/role-guard.md`).
- Lanza `claude --agent leader --permission-mode bypassPermissions`.

Atajos tmux:

- **Detach** (dejarlo corriendo): `Ctrl-b` y luego `d`.
- **Reconectar** desde cualquier maquina: `bash scripts/run_leader.sh` o
  `tmux attach -t leader`.
- **Listar / matar**: `tmux ls` · `tmux kill-session -t leader`.

Recomendado: usa **mosh** en vez de `ssh` para que tu conexion resista cortes y
cambios de red. `mosh` + `tmux` = trabajas, apagas la workstation, vuelves y
sigue en el servidor.

## Nivel 2 — Operacion autonoma

Tras lanzar el leader, dale esta instruccion permanente (pegala como primer
mensaje) para que procese la cola sin supervision:

```text
Opera de forma autonoma como leader:
1. Consulta el estado de la cola y elige la siguiente feature accionable.
2. Llevala por su ciclo completo (spec -> arquitectura -> implementacion -> QA
   -> finalizacion) delegando en los subagentes y usando solo los scripts
   deterministas del harness.
3. No te detengas entre features: continua con la siguiente hasta que no quede
   trabajo accionable en la cola.
4. Si una decision critica no puede inferirse con seguridad, marca la feature
   BLOCKED, registra el motivo y continua con otra; no inventes un workaround.
5. Respeta los presupuestos de agente y los quality gates; si una operacion
   determinista falla, documenta el bloqueo y no lo eludas.
6. Al terminar (cola vacia o todo bloqueado), resume que features completaste y
   cuales quedaron pendientes de decision humana.
```

El harness es la red de seguridad: el Role Guard impide escrituras no
autorizadas, los quality gates bloquean avances con fallos, y los leases con TTL
permiten recuperar trabajo si una sesion muere (`recover_stale_leases.py`).

## Durabilidad y recuperacion

El plano de control (`queue.json`, `leases/`, `runs/`, worktrees) son ficheros en
el servidor: el estado es **durable**. Si la sesion muere a mitad:

- Los leases caducan por TTL y `recover_stale_leases.py` los recupera (la feature
  pasa a BLOCKED, sin corromper estado).
- Relanzas el leader (`bash scripts/run_leader.sh`) y continua.
- Lo unico no recuperable es el razonamiento en vuelo de esa sesion LLM.

## Observacion mientras corre

```bash
python3 scripts/project_status.py                 # estado de la cola
python3 scripts/metrics_status.py                 # metricas/presupuestos
tail -f <control_root>/role-guard/audit.jsonl      # decisiones del Role Guard
```

## Siguiente paso (Nivel 3)

Para operacion desatendida 24/7 (reinicio en boot, reinicio al fallar, procesar
features segun llegan), el camino es un driver headless con el **Claude Agent
SDK** (o un bucle de `claude -p`) corriendo como servicio `systemd`. Queda como
evolucion del template cuando se valide el comportamiento del Nivel 2.
