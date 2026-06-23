---
owner: alejandro
last_verified: 2026-06-21
---

# ADR-0002 - Eval-Harness como puerta de verificación trazable

## Status

Accepted

## Context

El contrato de feature del harness ya produce criterios de aceptación
trazables `AC-XXX` y escenarios estructurados `SCN-XXX` (`acceptance.yaml`,
`schema_version: 2`). Sin embargo, esos escenarios son hoy un **contrato
documental**: describen `given`/`when`/`then`, pero no se ejecutan. La
verificación efectiva recae en la lectura humana del QA y en las quality
gates genéricas, sin un vínculo máquina-comprobable entre cada `SCN-XXX` y
una comprobación que pase o falle de forma determinista.

Esto deja un hueco en la cadena de trazabilidad:

`AC-XXX` (qué) → `SCN-XXX` (cómo se observa) → **¿?** (cómo se comprueba)

Se ha evaluado el patrón `eval-harness` del proyecto externo `affaan-m/ECC`
(MIT). Sus dos aportes útiles son (1) una taxonomía de *graders* y (2) las
métricas `pass@k` / `pass^k` como umbral de release. El loop operativo de ECC
(`verification-loop`) está escrito como prosa para el LLM y es no
determinista; **no se adopta tal cual**. Lo que se incorpora es el modelo de
graders y métricas, reexpresado como capability determinista del template,
coherente con el resto de capabilities (`security-scanning`,
`performance-testing`, etc.).

Restricciones del harness que esta decisión debe respetar:

- Las transiciones de estado pasan por scripts deterministas.
- El role-guard limita qué ficheros edita cada rol.
- La evidencia ligera vive en `evidence/`; los artefactos pesados, en
  `artifact_root`.
- Las capabilities son modulares y se activan por proyecto
  (`state/capabilities/*.json`), instaladas por `create_project.py` vía
  `manifest.json`.

## Decision

Introducir una capability `eval-harness` que convierte cada `SCN-XXX` en uno o
más *graders* ejecutables y exige su resultado como evidencia de gate.

1. **Capability modular.** Nueva capability `eval-harness` con su directorio
   `capabilities/eval-harness/` (manifest, runner, validador, schema y
   política), registrada en `create_project.py` (`CAPABILITIES`) y en
   `register_feature.py` (`--capability`). Inactiva por defecto.

2. **Taxonomía de graders.** Cuatro tipos, dos elegibles para gate y dos solo
   consultivos:
   - `code` — ejecuta un comando; pasa si exit code `0`. **Gate.**
   - `rule` — restricción determinista sobre ficheros (existe / contiene
     regex / ausente). **Gate.**
   - `model` — LLM-as-judge con rúbrica. **Consultivo, nunca bloquea el gate
     automático.**
   - `human` — adjudicación manual. **Consultivo.**

   Solo `code` y `rule` deciden una transición automática. Esto preserva el
   determinismo del harness.

3. **Definición junto a la feature.** Cada grader se declara en
   `specs/features/<FEATURE>/evals.json`, referenciando el `SCN-XXX` que
   verifica. Un escenario sin al menos un grader `code` o `rule` se reporta
   como no verificable.

4. **Métricas y umbrales (vía política).**
   - `runs` repeticiones por grader; `pass_at_k` (al menos una pasa) y
     `pass_caret_k` (todas pasan).
   - `pass_at_k_min` para criterios de capacidad.
   - `require_pass_caret_k_for_release_critical` exige `pass_caret_k = 1.00`
     en los graders marcados `release_critical`.

5. **Gate y evidencia.** El runner `run_evals.py` ejecuta los graders elegibles
   y deposita evidencia normalizada en
   `artifact_root/capabilities/eval-harness/<feature>/latest.json`, validada por
   `validate_eval_result.py` contra `specs/schemas/eval-result.schema.json`. El
   quality gate `EVAL-001` se instala en fase `qa_full`, en modo `observe` por
   defecto.

El loop de 6 fases de `verification-loop` (build, typecheck, lint,
test+cobertura, security, diff) **no entra en este ADR**: la verificación rápida
ya está cubierta por `verify_fast.sh` / `verify_full.sh` y las capabilities
existentes; mezclarlas sería otra decisión.

## Consequences

- La trazabilidad se cierra de extremo a extremo:
  `AC-XXX → SCN-XXX → grader ejecutable → evidencia`.
- El gate de calidad pasa a ser determinista y reproducible, alineado con el
  modelo de capabilities y transiciones por script.
- Los graders `release_critical` con `pass_caret_k = 1.00` protegen los caminos
  críticos.
- Coste de autoría: cada escenario verificable exige al menos un grader
  `code` o `rule`; aumenta el trabajo del `specifier`/`architect`.
- Nueva superficie a mantener: runner, validador, schema, política y el bloque
  de registro en el generador y sus tests.
- Riesgo de no-determinismo si se usaran graders `model`/`human` en el gate;
  mitigado por diseño al excluirlos de la decisión automática.

## Alternatives Considered

- **Adoptar `verification-loop` de ECC tal cual.** Rechazado: es prosa para el
  LLM, depende del juicio del modelo y reintroduce no-determinismo en el gate.
- **Adoptar el sistema de instintos / continuous-learning de ECC.** Rechazado:
  muta el comportamiento del agente a posteriori y rompe la reproducibilidad
  que sostiene el flujo dirigido por especificación.
- **Dejar `SCN-XXX` como contrato solo documental.** Rechazado: mantiene el
  hueco de verificación y deja la aceptación a lectura humana no trazable.
- **Graders embebidos en los tests del proyecto sin capability.** Rechazado:
  rompe la modularidad y la activación por proyecto.

## Related Features

Implementación entregada como capability `eval-harness` del template:
`capabilities/eval-harness/` (manifest, `run_evals.py`,
`validate_eval_result.py`, `eval-result.schema.json`, política), registro en
`create_project.py` y `register_feature.py`, documentación en
`docs/quality-and-capabilities.md` y `docs/profile-capability-matrix.md`, y test
E2E en `tests/test_generator.py`. Capability source: `affaan-m/ECC`
(`skills/eval-harness/SKILL.md`), adaptado a ejecución determinista.
