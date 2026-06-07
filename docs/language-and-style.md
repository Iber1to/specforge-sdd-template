# Convencion de Idioma y Estilo

Convencion aplicable al template y a los proyectos generados. Su objetivo es
evitar mezcla de idiomas y mantener un estilo consistente que tanto humanos como
agentes puedan seguir.

## Idioma

- **Documentacion operativa y de agentes**: espanol. Incluye `CLAUDE.md`,
  `AGENTS.md`, contratos en `docs/architecture/`, convenciones y runbooks.
- **Identificadores y contratos de maquina**: ingles. Incluye claves de esquema
  JSON, nombres de estado (`DRAFT`, `READY_FOR_QA`, ...), ids de capability y de
  gate, y nombres de archivos/scripts.
- **Plantillas de specs** (`specs/templates/`): ingles, por compatibilidad con los
  validadores y con el contenido que producen los agentes.
- No se mezclan idiomas dentro de una misma frase salvo terminos tecnicos
  (`worktree`, `lease`, `merge`, `commit`).

## Acentos

- Los documentos bajo `core/docs/` usan acentuacion correcta en espanol.
- Los documentos raiz del template, los mensajes de scripts (`print`) y los
  archivos `.sh` usan ASCII para evitar problemas de codificacion en entornos
  heterogeneos. No se mezcla: un archivo es consistente consigo mismo.

## Nombres tecnicos

- Claves JSON y campos de evidencia: `snake_case` (`feature_id`, `baseline_p95_ms`).
- Ids de capability, gate y target: `kebab-case` (`external-runtime`, `python-smoke`).
- Estados del workflow: `SCREAMING_SNAKE_CASE` (`READY_FOR_DEVELOPMENT`).
- Funciones y modulos Python: `snake_case`; clases: `PascalCase`.

## Mensajes de error y salida

- Mensajes de scripts en espanol, con prefijo `[OK]`, `[ERROR]` o `[HOOK_FATAL]`.
- Los errores controlados terminan con exit code `2`; el exito con `0`.
- Nunca se imprimen secretos: las muestras se redactan (`redacted`, `redact_sensitive_text`).

## Commits

- Conventional Commits en ingles: `type(scope): subject`.
- `type` habitual: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.
- Asunto en imperativo y minuscula; cuerpo opcional con bullets.
- Un commit por unidad logica de cambio; evitar cambios masivos no relacionados.

## Documentacion

- Markdown. Lineas <= 100 caracteres donde sea razonable.
- Una idea por seccion; preferir prosa breve y tablas a parrafos largos.
- Los resumenes generados (`docs/90-generated/`) no son fuente de verdad.
