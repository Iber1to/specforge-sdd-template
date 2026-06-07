# Contrato de evidencias del Windows Test Runner

## Ubicación

El Windows Test Runner debe publicar atómicamente el resultado final en:

`<artifact_root>/windows-tests/<FEATURE>/latest.json`

Los logs, capturas y otros artefactos también deben almacenarse fuera del
repositorio Git.

## Requisitos obligatorios

- La evidencia debe cumplir `specs/schemas/windows-evidence.schema.json`.
- `feature_id` debe coincidir con la feature probada.
- `tested_commit` debe coincidir exactamente con el commit solicitado.
- El estado global debe ser `PASS`.
- Todos los checks deben estar en `PASS`.
- Los checks deben estar numerados secuencialmente desde `WIN-001`.
- El log debe existir.
- Todos los artefactos declarados deben existir.
- Los timestamps deben incluir zona horaria.
- El archivo `latest.json` solo debe reemplazarse cuando la ejecución haya
  concluido completamente.

## Publicación atómica recomendada

1. Crear el resultado en `latest.json.tmp`.
2. Escribir y cerrar completamente el archivo.
3. Renombrar `latest.json.tmp` a `latest.json`.

## Validación desde Ubuntu

```bash
uv run python scripts/validate_windows_evidence.py \
  --feature F-001 \
  --commit <commit>
```

## Commit solicitado por el finalizador

La evidencia requerida para finalizar una feature debe utilizar como
`tested_commit` el campo `reviewed_commit` del informe QA aprobado.

El commit posterior que almacena el propio informe QA no modifica el código
funcional y no necesita una nueva ejecución Windows.
