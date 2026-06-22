# Matriz de Perfiles y Capabilities

Combinaciones soportadas por `create_project.py`. `documentation-pack` esta
activa por defecto en todos los perfiles.

| Perfil | documentation-pack | mutation-testing | external-runtime | windows-validation | performance-testing | security-scanning | git-publish | remote-notifications | eval-harness | tool-telemetry |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| generic | si (defecto) | no | si | opcional | si | si | si | opcional | si | opcional |
| python | si (defecto) | si | si | opcional | si | si | si | opcional | si | opcional |
| node | si (defecto) | no (futuro) | si | opcional | si | si | si | opcional | si | opcional |
| android | si (defecto) | no | si | opcional | si | si | si | opcional | si | opcional |

## Reglas aplicadas por el generador

- `mutation-testing` solo es compatible con el perfil `python`. El generador
  rechaza la combinacion con otros perfiles (`PROFILE_CAPABILITY_RULES`).
- `documentation-pack` se incluye siempre, aunque no se declare.
- El resto de capabilities son opcionales y validas en cualquier perfil.
- `eval-harness` es opcional y compatible con cualquier perfil. Convierte los
  escenarios `SCN-XXX` de cada feature en graders ejecutables; su gate
  `EVAL-001` se instala en `qa_full` en modo `observe`.
- `tool-telemetry` es opcional y compatible con cualquier perfil. Registra cada
  llamada a herramienta (`PreToolUse`/`PostToolUse`) como JSONL determinista con
  scrubbing de secretos; es telemetria/evidencia, no un gate. Sin la capability,
  los hooks son no-op.
- `windows-validation` deja la validacion Windows **disponible**; la
  obligatoriedad de evidencia es por feature, no global.
- El perfil `android` (Kotlin + Gradle) instala sus gates (`ANDROID-001`,
  `ANDROID-002`) en modo `observe` (no bloqueante): se ejecutan via
  `scripts/verify_android.sh` y se omiten con exito cuando Gradle o el Android
  SDK no estan presentes. Los gates bloqueantes siguen siendo los de Python. Se
  recomienda `external-runtime` para ejecutar el build Android real en un runner
  provisto. `mutation-testing` sigue siendo exclusivo de `python`.

## Validacion

`create_project.py` aborta con error si se declara una capability incompatible
con el perfil. Cubierto por
`tests/test_generator.py::test_rejects_incompatible_profile_capability`.
