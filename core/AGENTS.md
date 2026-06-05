# AGENTS.md — Mapa de navegación

## Lectura inicial obligatoria

1. `docs/architecture/harness-contract.md`
2. `state/project.json`
3. `state/workflow.json`
4. Los documentos específicos de la feature asignada.

## Reglas fundamentales

- No edites directamente `/srv/data/desktop-overlay-assistant/control`.
- No cambies manualmente estados de features.
- No marques ninguna feature como `DONE`.
- No trabajes fuera del worktree asignado.
- No asumas permisos de escritura fuera de tu responsabilidad.
- Ante contradicciones, aplica `docs/architecture/harness-contract.md`.

## Mapa del repositorio

| Ruta | Finalidad |
|---|---|
| `.claude/agents/` | Definiciones de agentes |
| `.claude/commands/` | Comandos operativos |
| `specs/product/` | Visión y requisitos globales |
| `specs/features/` | Especificaciones por feature |
| `state/` | Configuración y definición del workflow |
| `evidence/` | Informes ligeros versionados |
| `docs/` | Arquitectura, convenciones y decisiones |
| `scripts/` | Operaciones deterministas |
| `src/` | Código de aplicación |
| `tests/` | Pruebas automatizadas |
| `runtime/windows-runner/` | Código del runner Windows |
