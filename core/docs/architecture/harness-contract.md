# Contrato operativo del harness agéntico

## 1. Objetivo

Este contrato define las reglas obligatorias de coordinación, escritura,
verificación y finalización del sistema agéntico.

Las reglas aquí descritas tienen prioridad sobre cualquier instrucción generada
durante una sesión.

## 2. Fuentes de verdad

| Información | Fuente de verdad |
|---|---|
| Configuración del proyecto | `state/project.json` |
| Flujo y transiciones permitidas | `state/workflow.json` |
| Cola activa y estado de features | `<control_root>/queue.json` |
| Asignaciones activas | `<control_root>/leases/` |
| Ejecuciones activas e históricas | `<control_root>/runs/` |
| Especificaciones y código | Repositorio Git |
| Artefactos pesados | `<artifact_root>/` |

Los agentes no deben editar directamente los archivos del plano de control.
Toda modificación debe realizarse mediante scripts deterministas.

## 3. Invariantes obligatorios

1. Como máximo puede existir un implementador activo.
2. Una feature solo puede tener un agente escritor activo.
3. Cada implementación se realiza en una rama y worktree independientes.
4. Ningún agente puede cambiar manualmente el estado de una feature.
5. Ningún agente puede marcar una feature como `DONE`.
6. Solo `scripts/finalize_feature.py` puede realizar la transición a `DONE`.
7. Una feature no puede entrar en desarrollo sin especificación, arquitectura,
   criterios de aceptación y plan de pruebas.
8. Una feature no puede aprobarse con verificaciones fallidas.
9. Una feature que requiera runtime Windows no puede finalizar sin evidencias
   válidas del Windows Test Runner.
10. Los artefactos pesados no se almacenan dentro del repositorio Git.

## 4. Responsabilidades

### Leader

- Consulta el plano de control.
- Selecciona y delega trabajo.
- Lanza agentes especializados.
- Solicita transiciones mediante scripts.
- No escribe especificaciones, arquitectura, código ni tests.
- No aprueba ni finaliza features.

### Specifier

- Escribe exclusivamente la especificación funcional y los criterios de aceptación.
- No diseña arquitectura.
- No escribe código.
- No cambia estados directamente.

### Architect

- Escribe arquitectura, plan de implementación y plan de pruebas.
- No implementa código.
- No cambia estados directamente.

### Implementer

- Trabaja exclusivamente dentro del worktree asignado.
- Implementa una sola feature.
- Escribe código, tests y evidencia de implementación.
- No llama a otros agentes.
- No aprueba su propio trabajo.
- No cambia estados directamente.

### QA Reviewer

- Trabaja en modo lectura sobre código y especificaciones.
- Ejecuta las verificaciones permitidas.
- Escribe exclusivamente el informe de revisión.
- No corrige código.
- No cambia estados directamente.

## 5. Propiedad de archivos

| Área | Escritor autorizado |
|---|---|
| `specs/features/<feature>/specification.md` | Specifier |
| `specs/features/<feature>/acceptance.yaml` | Specifier |
| `specs/features/<feature>/architecture.md` | Architect |
| `specs/features/<feature>/implementation-plan.md` | Architect |
| `specs/features/<feature>/test-plan.md` | Architect |
| `src/`, `tests/` y `runtime/external/` | Implementer |
| `pyproject.toml` y `uv.lock` | Implementer, cuando lo requiera el diseño |
| `evidence/implementations/` | `complete_implementation.py`, invocado por Implementer |
| `evidence/reviews/` | `complete_review.py`, invocado por QA Reviewer |
| Plano de control externo | Scripts deterministas |
| Transición a `DONE` | `finalize_feature.py` |

## 6. Evidencias requeridas para finalizar

Una feature solo puede finalizar cuando existan:

- Especificación validada.
- Arquitectura validada.
- Criterios de aceptación verificables.
- Plan de pruebas.
- Implementación versionada.
- Tests relacionados correctos.
- Suite completa Linux correcta.
- Veredicto QA `APPROVED`.
- Evidencia Windows correcta cuando sea requerida.
- Repositorio y worktree sin cambios pendientes.

## 7. Política de rendimiento

- Las verificaciones rápidas se ejecutan durante el desarrollo.
- Los tests relacionados se ejecutan al finalizar la implementación.
- La suite completa se ejecuta antes de la aprobación final.
- Las pruebas Windows se ejecutan únicamente cuando la feature lo requiera.
- La información extensa se transmite mediante archivos, no mediante mensajes
  completos entre agentes.
