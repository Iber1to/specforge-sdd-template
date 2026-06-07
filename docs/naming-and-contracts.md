# Naming y Contratos JSON

Vocabulario canonico de los contratos del harness. Su objetivo es que campos
parecidos no se confundan y que el naming sea predecible entre capabilities.

## Vocabulario canonico

| Concepto | Campo | Significado |
|---|---|---|
| Capacidad instalada | `enabled` (policy) / `*_available` (project) | La capability esta instalada y disponible. No implica obligatoriedad. |
| Obligatoriedad | `*_required` (feature) | Una feature concreta exige esa evidencia para avanzar. Se declara por feature. |
| Politica de bloqueo | `mode`: `observe` \| `enforce` | `observe` registra evidencia sin bloquear; `enforce` puede bloquear la fase. |
| Resultado de gate/runner | `status` | Resultado de una ejecucion determinista (ver valores abajo). |
| Veredicto humano/agente | `verdict` | Decision de QA: `APPROVED` \| `CHANGES_REQUESTED`. Distinto de `status`. |

Reglas:

- **`available` vs `required`**: instalar una capability la deja *available*
  (proyecto); que una feature la exija es *required* (feature). Separados desde
  `windows_validation_available` / `windows_validation_required`.
- **`enabled` vs `required`**: `enabled` es de la policy de la capability;
  `required_for_done` / `required_for_qa_approval` son banderas de obligatoriedad
  independientes.
- **`observe` vs `enforce`**: unico eje de bloqueo. Toda capability arranca en
  `observe` salvo decision explicita.
- **`status` vs `verdict`**: `status` es maquina (gates/runners); `verdict` es la
  decision de QA. No se intercambian.

## Convencion de campos de evidencia

Toda evidencia incluye: `schema_version`, `feature_id`, `status`, `started_at`,
`completed_at`. Las rutas y comandos van como listas/strings explicitos; los
secretos se redactan o se publican como hash (`remote_url_hash`).

## Inconsistencia conocida: `PASS`/`PASSED`

Hoy conviven dos vocabularios para `status`:

- Evidencia de capabilities (`external-runtime`, `performance-testing`,
  `security-scanning`): `PASSED` / `FAILED` (ver `capability_common.CAPABILITY_STATUSES`).
- Evidencia Windows y `git-publish`: `PASS` / `FAIL`.

Ambos valores son claros, pero no estan unificados. La unificacion (p. ej. todo a
`PASSED`/`FAILED`) toca esquemas, validadores y tests, por lo que se deja como
**follow-up con su propio cambio testeado**, no como parte del pulido v1.

Migracion recomendada cuando se aborde:

1. Elegir el vocabulario canonico (`PASSED`/`FAILED`).
2. Actualizar `windows-evidence.schema.json`, `windows_validation.py`,
   `collect_windows_evidence.py` y `publish_feature.py`.
3. Actualizar los tests que afirman `PASS`/`FAIL`.
4. Documentar el cambio de contrato en el changelog.
