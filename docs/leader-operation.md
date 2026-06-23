# Leader Operation: persistent and autonomous

How to operate the leader against a remote server without losing the session
when disconnecting, and how to leave it working autonomously.

## Level 1 — Persistent session (tmux)

An interactive `claude` session dies when the SSH connection drops (SIGHUP). For
it to survive, it runs inside `tmux` on the server.

```bash
cd <proyecto-generado>
bash scripts/run_leader.sh
```

`run_leader.sh`:

- Creates (or reconnects to) a tmux session named `leader`.
- Exports `CLAUDE_HARNESS_ROLE=leader` (required: Claude Code reports the main
  session as `agent_type: "claude"`, see `docs/architecture/role-guard.md`).
- Launches `claude --agent leader --permission-mode bypassPermissions`.

tmux shortcuts:

- **Detach** (leave it running): `Ctrl-b` and then `d`.
- **Reconnect** from any machine: `bash scripts/run_leader.sh` or
  `tmux attach -t leader`.
- **List / kill**: `tmux ls` · `tmux kill-session -t leader`.

Recommended: use **mosh** instead of `ssh` so your connection survives drops and
network changes. `mosh` + `tmux` = you work, power off the workstation, come
back and it continues on the server.

## Level 2 — Autonomous operation

After launching the leader, give it this standing instruction (paste it as the
first message) so it processes the queue without supervision:

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

The harness is the safety net: the Role Guard blocks unauthorized writes, the
quality gates block advances with failures, and leases with a TTL allow work to
be recovered if a session dies (`recover_stale_leases.py`).

## Durability and recovery

The control plane (`queue.json`, `leases/`, `runs/`, worktrees) are files on the
server: the state is **durable**. If the session dies midway:

- Leases expire by TTL and `recover_stale_leases.py` recovers them (the feature
  moves to BLOCKED, without corrupting state).
- You relaunch the leader (`bash scripts/run_leader.sh`) and it continues.
- The only thing not recoverable is the in-flight reasoning of that LLM session.

## Observation while it runs

```bash
python3 scripts/project_status.py                 # queue state
python3 scripts/metrics_status.py                 # metrics/budgets
tail -f <control_root>/role-guard/audit.jsonl      # Role Guard decisions
```

## Next step (Level 3)

For 24/7 unattended operation (restart on boot, restart on failure, process
features as they arrive), the path is a headless driver with the **Claude Agent
SDK** (or a `claude -p` loop) running as a `systemd` service. It remains as an
evolution of the template once Level 2 behavior is validated.
