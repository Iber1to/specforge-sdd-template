# Contrato de finalización de features

## Autoridad exclusiva

Solo `scripts/finalize_feature.py` puede realizar la transición:

`APPROVED -> DONE`

Ningún agente ni script genérico puede marcar directamente una feature como
finalizada.

## Commit validado

El commit funcional validado es `reviewed_commit`, incluido en el informe QA.

Después de `reviewed_commit`, la rama de la feature solo puede contener un
commit adicional (el commit de evidencia de QA); dicho commit solo puede
modificar:

- `evidence/reviews/<FEATURE>.json` (obligatorio)
- `evidence/reviews/<FEATURE>.md`
- `evidence/mutation-reviews/<FEATURE>.json` (solo si la feature declara la
  capability `mutation-testing`; el informe de mutación se pliega en este mismo
  commit, no en uno adicional)

La evidencia Windows, cuando sea obligatoria, debe corresponder exactamente a
`reviewed_commit`.

## Condiciones previas

- La feature está en estado `APPROVED`.
- No existe ningún lease activo para la feature.
- El repositorio canónico está limpio y sobre la rama `main`.
- El worktree de implementación está limpio.
- El informe QA es válido y tiene veredicto `APPROVED`.
- El run QA está cerrado correctamente.
- No existen commits o archivos posteriores no revisados.
- La suite Linux completa pasa en la rama.
- La evidencia Windows es válida cuando sea requerida.

## Integración

La rama se integra mediante un merge commit.

Antes de crear el merge commit:

1. Se prepara el merge mediante `--no-ff --no-commit`.
2. Se valida el contenido preparado.
3. Se ejecuta la suite Linux completa sobre el resultado integrado.
4. Si cualquier validación falla, se aborta el merge.

## Resultado

Después de integrar correctamente:

- Se registra el commit de integración.
- La feature pasa a `DONE`.
- Se elimina el worktree.
- Se elimina la rama de feature.
