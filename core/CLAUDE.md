# Instrucciones del proyecto

## Autoridad operativa

El contrato con máxima prioridad es:

`docs/architecture/harness-contract.md`

Las definiciones específicas de cada rol se encuentran en:

`.claude/agents/`

## Reglas universales

- Lee `AGENTS.md` y el contrato operativo antes de actuar.
- Respeta estrictamente el rol activo y su propiedad de archivos.
- No edites directamente el plano de control externo.
- No cambies manualmente estados de features.
- No marques una feature como `DONE`.
- Utiliza exclusivamente los scripts deterministas del harness para operaciones
  sobre cola, leases, runs, revisiones y finalización.
- No trabajes simultáneamente sobre varias features.
- No sustituyas un fallo del harness por un workaround improvisado.
- Si una operación determinista falla, documenta el bloqueo y detente.
- La sesión operativa principal debe iniciarse mediante `claude --agent leader`.
- Una sesión iniciada sin agente explícito debe limitarse a consulta y análisis.

## Prioridad

En caso de contradicción:

1. `docs/architecture/harness-contract.md`
2. Definición del agente activo
3. `AGENTS.md`
4. Documentación específica de la feature
5. Resto de documentación