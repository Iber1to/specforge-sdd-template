# Perfil Android

Perfil para apps Android nativas en Kotlin construidas con Gradle. Para v1 usa
un toolchain mínimo: el generador no descarga el Android SDK ni Gradle y no
instala dependencias externas (misma filosofía que el perfil Node v1).

## Incluye

- Core completo del harness.
- Proyecto Gradle (`settings.gradle.kts`, `build.gradle.kts`, `gradle.properties`).
- Módulo `app/` con Kotlin DSL (`app/build.gradle.kts`).
- `app/src/main/AndroidManifest.xml` con permisos de cámara e internet.
- `app/src/main/java/<paquete>/MainActivity.kt`.
- Test unitario JVM en `app/src/test/java/<paquete>/ExampleUnitTest.kt`.
- Recursos localizados en `app/src/main/res/values{,-es,-ja,-ko}/strings.xml`
  (inglés por defecto, más castellano, japonés y coreano).
- `scripts/verify_android.sh`.
- Gates Android (`ANDROID-001`, `ANDROID-002`) en `state/quality-gates.json`.

## Toolchain

- Kotlin (compilado por el plugin de Android).
- Gradle 8.x (Kotlin DSL).
- Android SDK (compileSdk 34, minSdk 24).
- JDK 17.

El generador no provee el wrapper binario de Gradle ni el SDK. En una máquina de
desarrollo inicializa el wrapper con `gradle wrapper` o abre el proyecto en
Android Studio.

## Validación

```bash
./gradlew testDebugUnitTest
./gradlew lintDebug
bash scripts/verify_full.sh
```

`scripts/verify_android.sh` detecta `./gradlew` o `gradle`; si no encuentra
ninguno, informa `[SKIP]` y termina con éxito.

## Gates Agregados

El perfil agrega gates **no bloqueantes** en modo `observe`:

- `ANDROID-001` en `implementation_fast`.
- `ANDROID-002` en `qa_full`.

Ambos ejecutan `scripts/verify_android.sh`. Son `observe` porque el harness se
orquesta con Python y su entorno (p. ej. el host de orquestación) no siempre
tiene el Android SDK. Los gates **bloqueantes** siguen siendo los de Python
(`verify_fast.sh` / `verify_full.sh`): Python 3.12, `uv`, `ruff` y `pytest`
deben estar disponibles para pasar `qa_full` y `finalization`.

Para ejecutar el build Android real de forma reproducible en un runner provisto,
combina este perfil con la capability `external-runtime`.

## Mutation Testing

No soportado en este perfil. `mutation-testing` sigue siendo exclusivo del
perfil `python`.
