# Android Profile

Profile for native Android apps in Kotlin built with Gradle. For v1 it uses
a minimal toolchain: the generator does not download the Android SDK or Gradle and does not
install external dependencies (same philosophy as the Node v1 profile).

## Includes

- Complete harness core.
- Gradle project (`settings.gradle.kts`, `build.gradle.kts`, `gradle.properties`).
- `app/` module with Kotlin DSL (`app/build.gradle.kts`).
- `app/src/main/AndroidManifest.xml` with camera and internet permissions.
- `app/src/main/java/<package>/MainActivity.kt`.
- JVM unit test in `app/src/test/java/<package>/ExampleUnitTest.kt`.
- Localized resources in `app/src/main/res/values{,-es,-ja,-ko}/strings.xml`
  (English by default, plus Spanish, Japanese and Korean).
- `scripts/verify_android.sh`.
- Android gates (`ANDROID-001`, `ANDROID-002`) in `state/quality-gates.json`.

## Toolchain

- Kotlin (compiled by the Android plugin).
- Gradle 8.x (Kotlin DSL).
- Android SDK (compileSdk 34, minSdk 24).
- JDK 17.

The generator does not provide the Gradle binary wrapper or the SDK. On a
development machine, initialize the wrapper with `gradle wrapper` or open the project in
Android Studio.

## Validation

```bash
./gradlew testDebugUnitTest
./gradlew lintDebug
bash scripts/verify_full.sh
```

`scripts/verify_android.sh` detects `./gradlew` or `gradle`; if it finds
neither, it reports `[SKIP]` and exits successfully.

## Added Gates

The profile adds **non-blocking** gates in `observe` mode:

- `ANDROID-001` in `implementation_fast`.
- `ANDROID-002` in `qa_full`.

Both run `scripts/verify_android.sh`. They are `observe` because the harness is
orchestrated with Python and its environment (e.g. the orchestration host) does not always
have the Android SDK. The **blocking** gates remain the Python ones
(`verify_fast.sh` / `verify_full.sh`): Python 3.12, `uv`, `ruff` and `pytest`
must be available to pass `qa_full` and `finalization`.

To run the real Android build reproducibly on a provided runner,
combine this profile with the `external-runtime` capability.

## Mutation Testing

Not supported in this profile. `mutation-testing` remains exclusive to the
`python` profile.
