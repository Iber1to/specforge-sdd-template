# Profile and Capability Matrix

Combinations supported by `create_project.py`. `documentation-pack` is
active by default in all profiles.

| Profile | documentation-pack | mutation-testing | external-runtime | windows-validation | performance-testing | security-scanning | git-publish | remote-notifications | eval-harness | tool-telemetry |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| generic | yes (default) | no | yes | optional | yes | yes | yes | optional | yes | optional |
| python | yes (default) | yes | yes | optional | yes | yes | yes | optional | yes | optional |
| node | yes (default) | no (future) | yes | optional | yes | yes | yes | optional | yes | optional |
| android | yes (default) | no | yes | optional | yes | yes | yes | optional | yes | optional |

## Rules applied by the generator

- `mutation-testing` is only compatible with the `python` profile. The generator
  rejects the combination with other profiles (`PROFILE_CAPABILITY_RULES`).
- `documentation-pack` is always included, even if not declared.
- The remaining capabilities are optional and valid in any profile.
- `eval-harness` is optional and compatible with any profile. It converts the
  `SCN-XXX` scenarios of each feature into executable graders; its `EVAL-001`
  gate is installed in `qa_full` in `observe` mode.
- `tool-telemetry` is optional and compatible with any profile. It records each
  tool call (`PreToolUse`/`PostToolUse`) as deterministic JSONL with
  secret scrubbing; it is telemetry/evidence, not a gate. Without the capability,
  the hooks are no-ops.
- `windows-validation` makes Windows validation **available**; the
  mandatory nature of evidence is per feature, not global.
- The `android` profile (Kotlin + Gradle) installs its gates (`ANDROID-001`,
  `ANDROID-002`) in `observe` mode (non-blocking): they run via
  `scripts/verify_android.sh` and are skipped successfully when Gradle or the Android
  SDK are not present. The blocking gates remain the Python ones. It is
  recommended to use `external-runtime` to run the real Android build on a provided
  runner. `mutation-testing` remains exclusive to `python`.

## Validation

`create_project.py` aborts with an error if a capability incompatible
with the profile is declared. Covered by
`tests/test_generator.py::test_rejects_incompatible_profile_capability`.
