# Convenciones Spec Driven Development

## Documentos obligatorios por feature

Cada feature se almacena en:

`specs/features/<feature-id>-<slug>/`

Y debe contener:

- `specification.md`
- `acceptance.yaml`
- `architecture.md`
- `implementation-plan.md`
- `test-plan.md`

## Reglas para criterios de aceptación

- Cada criterio tiene un identificador secuencial: `AC-001`, `AC-002`, etc.
- Los identificadores no pueden repetirse.
- Todos los criterios deben ser objetivamente verificables.
- Todos los criterios deben aparecer en `test-plan.md`.
- No se admiten propiedades distintas de las definidas en el esquema.
- Las features que requieran validación Windows deben incluir al menos un criterio
  verificado mediante `windows_e2e`.

## Reglas Markdown

- Todos los documentos deben tener un título H1.
- Todas las secciones obligatorias deben existir.
- Las secciones obligatorias no pueden quedar vacías.
- No pueden permanecer marcadores `<!-- REQUIRED: ... -->`.
- Antes de solicitar una transición deben ejecutarse los validadores correspondientes.

## Validación manual

```bash
uv run python scripts/validate_spec.py --feature F-001
uv run python scripts/validate_design.py --feature F-001 --level architecture
uv run python scripts/validate_design.py --feature F-001 --level ready
```

## Spec Partner autónomo

Las nuevas features utilizan `acceptance.yaml` con `schema_version: 2`.

El agente técnico `specifier` actúa como Spec Partner autónomo:

- analiza y endurece la idea funcional inicial;
- documenta hipótesis mediante `ASM-XXX`;
- documenta decisiones funcionales mediante `DEC-XXX`;
- registra preguntas pendientes mediante `Q-XXX`;
- bloquea únicamente cuando una pregunta crítica no puede resolverse de forma
  segura;
- genera escenarios estructurados `SCN-XXX` con `given`, `when` y `then`;
- asegura la cobertura de todos los criterios obligatorios `AC-XXX`.

Los escenarios no son Gherkin ejecutable ni implican TDD. Constituyen un
contrato estructurado y trazable para arquitectura, implementación y QA.

Las features históricas declaradas en
`state/specification-policy.json::legacy_v1_features` pueden conservar
contratos `schema_version: 1`.
