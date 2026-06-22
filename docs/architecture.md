# Arquitectura Del Template Agentic SDD

Este documento describe la arquitectura tecnica del template y del proyecto generado. El objetivo del template es crear repos que puedan operar features con un ciclo Spec Driven Development reproducible, auditado y gobernado por scripts deterministas.

## Vista General

```text
agentic-sdd-template
  create_project.py
  core/              harness comun
  profiles/          adaptadores por stack
  capabilities/      capacidades opcionales
  tests/             pruebas del generador

generated-project
  .claude/           agentes y configuracion
  scripts/           plano de control determinista
  specs/             contratos de spec, arquitectura y test plan
  state/             configuracion versionada
  docs/              documentacion tecnica del harness
  evidence/          evidencias pequenas versionadas
  src/, tests/       codigo del producto segun perfil
```

## Capas

### Generador

`create_project.py` lee un YAML simple, valida `project_id`, `name`, `output_path`, `profile` y `capabilities`, copia `core/`, aplica el perfil seleccionado y crea un commit inicial en Git.

El parser YAML es intencionadamente minimo. Soporta lineas `key: value`, booleanos simples y listas inline como `[mutation-testing]`.

### Core

`core/` contiene el harness que todos los proyectos reciben:

- agentes en `.claude/agents`
- scripts de lifecycle y control
- schemas de especificacion y evidencias
- templates de specs
- quality gates por defecto
- documentacion de arquitectura y convenciones
- `pyproject.toml` y `uv.lock` del toolchain Python del harness

El core debe tratarse como una unidad sincronizable desde el harness fuente.

### Profiles

Los perfiles agregan lo minimo necesario para que un proyecto generado pueda validarse desde el primer commit.

- `generic`: solo harness y smoke test.
- `python`: paquete Python bajo `src/` y pruebas unitarias.
- `node`: `package.json`, ESM, `node:test` y gates Node.

### Capabilities

Las capacidades son opt-in. El template las documenta y el proyecto generado puede activarlas por configuracion o por feature.

Capacidades actuales:

- `documentation-pack` (incluida por defecto)
- `eval-harness`
- `external-runtime`
- `git-publish`
- `mutation-testing`
- `performance-testing`
- `remote-notifications`
- `security-scanning`
- `tool-telemetry`
- `windows-validation`

## Plano De Control

El proyecto generado separa el repo Git del estado operativo.

Estado versionado:

- `state/project.json`
- `state/workflow.json`
- `state/quality-gates.json`
- `state/specification-policy.json`
- `state/agent-budgets.json`

Estado operativo fuera de Git:

- `data/<project_id>/control/queue.json`
- `data/<project_id>/control/runtime.json`
- `data/<project_id>/control/runs/`
- `data/<project_id>/control/leases/`
- `data/<project_id>/control/locks/`
- `data/<project_id>/control/agent-metrics/`
- `data/<project_id>/artifacts/`

Esta separacion evita que logs, locks y runtime contaminen el historial Git.

## Lifecycle De Features

Estados principales:

```text
DRAFT -> SPEC_READY -> DESIGN_READY -> READY_FOR_DEVELOPMENT
READY_FOR_DEVELOPMENT -> IN_PROGRESS -> READY_FOR_QA
READY_FOR_QA -> APPROVED -> DONE
READY_FOR_QA -> CHANGES_REQUESTED -> IN_PROGRESS
```

Los roles autorizados por transicion estan definidos en `state/workflow.json` y aplicados por `scripts/control_common.py`.

## Spec Partner v2

Spec Partner v2 endurece la entrada a desarrollo.

Componentes:

- `state/specification-policy.json`
- `specs/schemas/acceptance-v2.schema.json`
- `specs/templates/acceptance.yaml`
- `scripts/validate_spec.py`
- `scripts/feature_validation.py`

La arquitectura debe incluir `Specification Review` para specs v2. Esa seccion documenta si el Architect encontro contradicciones, criterios no verificables, dependencias faltantes, alcance ambiguo o preguntas criticas.

## Role Guard Y Dominios De Cambio

`change_domain` clasifica la intencion de una feature:

- `product`: cambios normales del producto. Es el default.
- `harness`: mantenimiento controlado del harness.
- `template`: cambios sobre el template o su empaquetado.

Role Guard usa ese dominio para permitir o bloquear rutas. En dominio `harness` se permiten cambios controlados en scripts, agentes, schemas, templates, docs, state y tests. El plano de control externo sigue fuera de alcance.

## Quality Gates

`scripts/quality_gates.py` ejecuta gates configurados en `state/quality-gates.json`.

Fases:

- `implementation_fast`
- `qa_full`
- `finalization`
- `optional_capability`

Cada gate define:

- `id`
- `phase`
- `command`
- `blocking`
- `timeout_seconds`

Los resultados se escriben como JSON estructurado en `artifact_root/quality-gates/<feature>/`. Los logs completos se guardan al lado de la evidencia.

## Mutation Testing

La capability `mutation-testing` usa `scripts/mutation_runner.py`.

El runner:

- detecta codigo Python cambiado
- genera mutantes deterministas
- aplica cada mutante temporalmente
- ejecuta el comando de test
- restaura archivos
- clasifica mutantes como `killed`, `survived` o `invalid`
- escribe evidencia JSON

La revision final la realiza `mutation-reviewer` y se valida con `scripts/mutation_review_validation.py`.

## Evidencias

Evidencias versionadas:

- `evidence/implementations/<feature>.json`
- `evidence/reviews/<feature>.json`
- `evidence/mutation-reviews/<feature>.json`

Artefactos pesados:

- `artifact_root/quality-gates/<feature>/`
- `artifact_root/mutation-tests/<feature>/`
- `artifact_root/git-publish/<feature>/`

## Publicacion Git

La publicacion Git es una capability opcional (`git-publish`) que opera despues de `DONE`.

Componentes:

- `scripts/publish_feature.py`
- agente `repository-publisher`
- configuracion `state/project.json::git_publication`
- evidencia en `artifact_root/git-publish/<feature>/`

El diseño separa integracion local de publicacion remota:

- `finalize_feature.py` integra la feature aprobada en la rama canonica local.
- `publish_feature.py` valida que la feature esta en `DONE` y registra o sube el commit.

Role Guard bloquea `git push` directo. Un push real solo puede ocurrir dentro del script determinista, con repo limpio, feature finalizada y remote configurado.

## Modelo De Sincronizacion

El template no es el harness fuente; es una distribucion. Cuando el harness fuente evoluciona:

1. Sincronizar `core/`.
2. Ajustar perfiles/capacidades si el contrato cambio.
3. Regenerar proyectos de prueba.
4. Ejecutar la suite del template.
5. Completar al menos una feature real si el cambio toca lifecycle, gates o control.
