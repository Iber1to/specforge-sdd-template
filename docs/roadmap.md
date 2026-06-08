# Roadmap

Estado vivo del trabajo **posterior a `v1.0-internal`**. Este documento consolida
en un solo sitio lo que viene despues y sustituye a la dispersion previa entre el
CHANGELOG, el roadmap historico y el documento de tareas de QA.

Donde vive cada cosa:

- **Roadmap historico** (cerrado): [`estado-y-roadmap-harness-agentico.md`](estado-y-roadmap-harness-agentico.md).
- **Detalle de lo entregado** por version: [`../CHANGELOG.md`](../CHANGELOG.md).
- **Backlog operativo** de un proyecto en marcha: su plano de control
  (`queue.json` + `scripts/register_feature.py` + `scripts/project_status.py`).
- **Futuro estrategico del template** (Now / Next / Later): este documento.

Convencion: un item se mueve a **Hecho** cuando entra en un release del CHANGELOG.
Los IDs `T-0xx` siguen el documento de tareas v1.

_Ultima actualizacion: 2026-06-08._

---

## Estado actual

`v1.0-internal` (2026-06-07). Estable el nucleo (workflow SDD, Role Guard, quality
gates, plano de control durable) y las capabilities `documentation-pack`,
`mutation-testing` (python), `performance-testing`, `security-scanning`,
`git-publish`, `external-runtime`. Experimental: `windows-validation` (codigo listo
y cubierto offline; pendiente validar en Windows real). 48 tests del generador en
verde.

---

## Now — en curso o siguiente

### Validacion real en hardware: Windows y SSH  (`T-008E`, `T-008F`)

- **Por que.** El codigo y la cobertura offline existen, pero `windows-validation`
  no pasara de *experimental* a *estable* hasta ejecutarse en un Windows real, y el
  adapter SSH de `external-runtime` solo esta probado offline. Es lo que separa
  "cubierto en CI" de "validado en produccion".
- **Que falta.** Seguir [`real-validation-runbook.md`](real-validation-runbook.md):
  generar la solicitud desde el host Linux, ejecutar el runner en Windows / sobre
  SSH, publicar evidencia y validar `commit`/`feature`.
- **Done when.** Evidencia real publicada y validada en ambos casos;
  `windows-validation` reclasificada como estable en README y CHANGELOG. Al
  arrancar, cablear un smoke de Windows **no bloqueante**.

### Unificar el vocabulario de status `PASS` / `PASSED`  (cierre de `T-009F`)

- **Por que.** Los contratos JSON mezclan `PASS` y `PASSED`; quedo documentado en
  [`naming-and-contracts.md`](naming-and-contracts.md) como follow-up no bloqueante.
- **Que falta.** Elegir el termino canonico, migrar emisores y lectores en un unico
  cambio acotado y actualizar schema y documentacion.
- **Done when.** Un solo termino en todo el plano de control y las evidencias, con
  un test que lo fije.

### Smoke de carga del harness en Claude Code (proyecto generado)  (`T-014`)

- **Por que.** La suite offline y el job *Generated project smoke* validan que el
  template genera proyectos operables, pero el CI no ejecuta Claude Code (contrato
  en [`ci-cd.md`](ci-cd.md)). Que Claude Code **cargue de verdad** el harness, los
  agentes y los hooks sobre un proyecto generado solo se comprueba en una sesion
  real; hoy es deuda manual sin cubrir.
- **Que falta.** Documentar el procedimiento manual como runbook
  (`harness-load-runbook.md`) con la carga de agentes (`claude agents`), arranque
  del Leader (`--agent leader`), bloqueo del Role Guard en vivo y subagente real;
  opcionalmente, automatizar la parte **sin Claude** (checks de `.claude/agents/*`,
  `hooks` de `settings.json`, wrapper `hook_entrypoint.sh`, `project_status.py` /
  `metrics_status.py`) dentro de `verify_full.sh` como smoke **no bloqueante**. Se
  ejecuta sobre un proyecto generado, nunca sobre el repo del template.
- **Done when.** Sobre un proyecto generado: Claude arranca con `--agent leader`;
  `claude agents` lista los agentes del proyecto (`leader`, `specifier`,
  `architect`, `implementer`, `qa-reviewer` y los de capabilities instaladas);
  `project_status.py` corre desde el Leader; los hooks no fallan; el Role Guard
  bloquea una escritura no autorizada; `SubagentStart`/`SubagentStop` generan
  metrica; y `git status` queda limpio al salir.

---

## Next — planificado

### `T-013` — Operacion desatendida Nivel 3 (driver headless + `systemd`)

- **Por que.** El Nivel 2 deja el `leader` persistente pero **dirigido por una
  persona**. El Nivel 3 lo convierte en un **servicio que procesa la cola solo,
  24/7**, sobreviviendo a caidas y reinicios. Hace falta cuando se busca throughput
  continuo / operacion sin manos; si solo se lanzan features de vez en cuando, el
  Nivel 2 basta.
- **Alcance MVP.** Driver headless (Claude Agent SDK o bucle `claude -p`) que lee
  `queue.json` y conduce features; unidad `systemd` con arranque en boot y
  `Restart=on-failure`; arranque idempotente (corre `recover_stale_leases.py`,
  limpia worktrees huerfanos, reanuda desde el plano de control); **presupuesto de
  tokens con corte real** (da "dientes" a `agent-budgets.json` /
  `agent_budget_observer`) y **kill switch**; logging estructurado a `journald` y
  una alerta basica.
- **Alcance completo.** Watchdog/healthcheck; circuit breaker por fallos
  consecutivos; allowlist de acciones desatendidas (nunca `git-publish --push` ni
  merge a `main` sin aprobacion); dashboard de metricas; intake de backlog (fichero
  o webhook); buzon de decisiones humanas para features `BLOCKED`.
- **Depende de.** Validar el comportamiento de los Niveles 1+2 en uso real antes de
  automatizar.
- **Done when.** El servicio procesa features de la cola sin intervencion, se
  recupera de un reinicio del host sin estado corrupto y respeta presupuesto y kill
  switch.

### `T-009G` — Packaging opcional limpio (ZIP para auditorias)  _(opcional)_

- **Por que.** El despliegue oficial es por Git, pero un ZIP reproducible y limpio
  es util para entregas o auditorias externas.
- **Alcance.** `scripts/package_template.py` + `scripts/validate_package.py`,
  excluyendo `.git`, `.venv`, caches, `node_modules`, `dist`.
- **Done when.** ZIP limpio verificable, documentado como artefacto auxiliar y no
  como via de despliegue.

### Milestone: `v1.0` publico

- **Por que.** Hoy es `v1.0-internal`. Publicar exige cerrar las validaciones
  reales de arriba y decidir **licencia** (hoy `TBD` en README).
- **Done when.** Validaciones reales en verde, licencia elegida, README/CHANGELOG
  actualizados y tag `v1.0`.

---

## Later — futuro (P3)

Mejoras no bloqueantes; se promueven a **Next** cuando haya demanda real.

| ID | Item | Area | Nota |
|---|---|---|---|
| `T-010A` | ESLint/Prettier opcional (`node_linting: full`) | Perfil node | `npm ci` + lockfile; no obligatorio |
| `T-010B` | Docker como target de `external-runtime` | External runtime | timeout, limites, limpieza, evidencia |
| `T-010C` | Integracion consultiva con Code-Recall MCP | Memoria | no fuente de verdad; solo aprendizajes verificados |
| `T-010D` | Integracion con Graphify | Navegacion / contexto | herramienta explicita, sin hooks automaticos |
| `T-010E` | Dashboards de metricas (runs, tokens, features, gates) | Observabilidad | salida MD / JSON / CSV; insumo del Nivel 3 |

---

## Hecho

Resumen; el detalle por version esta en [`../CHANGELOG.md`](../CHANGELOG.md).

- **`v1.0-internal`** (2026-06-07): hardening final y cierre funcional.
  - `T-007A..E` — `command-id` en external-runtime, wrapper de hooks, fix de
    `artifact_root`, `windows_validation_available`, tests de hardening.
  - `T-008A..D`, `T-008G` — preflight, portabilidad offline, suite minima del
    harness, matriz perfil x capability, evidencia de git-publish.
  - `T-008E/F` — cobertura **offline** + runbook (la validacion real sigue en *Now*).
  - `T-009A..F` — baselines de performance, clasificacion de security baseline,
    mutation limitado al diff, adapters de security por perfil, y convenciones de
    idioma/estilo y naming/contratos.
  - `T-011` — eliminado el camino de comando libre en external-runtime.
  - `T-012` — rol de la sesion principal via `CLAUDE_HARNESS_ROLE`.
