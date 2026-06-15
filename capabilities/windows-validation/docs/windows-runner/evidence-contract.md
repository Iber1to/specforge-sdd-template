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

### Rutas de `log` y `artifacts` (portabilidad Windows/POSIX)

El runner se ejecuta en Windows y emite inevitablemente rutas nativas
(`J:\...`, UNC `\\host\share\...`), mientras que la validación corre en Linux.
Por eso el esquema **no** impone formato POSIX en `log` ni en `artifacts`
(solo `minLength: 1`), y la validación re-enraíza cada ruta por su *basename*
bajo el directorio canónico `<artifact_root>/windows-tests/<FEATURE>/`. La
confianza se ancla en el directorio canónico, no en la cadena emitida por el
runner:

- Se acepta cualquier ruta cuyo último componente (basename) exista como
  fichero real dentro del directorio canónico.
- Se rechazan basenames inseguros o ambiguos (`.`, `..`, vacío, o con
  separadores residuales), de modo que ninguna ruta declarada pueda escapar
  del canónico.
- La existencia real se sigue comprobando contra el canónico: una ruta nativa
  no resuelve nunca contra el sistema de ficheros local arbitrario.
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
