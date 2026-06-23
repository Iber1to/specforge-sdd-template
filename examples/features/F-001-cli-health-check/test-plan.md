# Test Plan — F-001 Local health check CLI

## Test Strategy

The verification combines three levels, aligned with `acceptance.yaml`:

- **Unit:** validate the pure function `build_health_report()` (document
  construction, mandatory fields and the value `"ok"`), without I/O.
- **Integration:** run the full command by subprocess
  (`python -m src.desktop_overlay_assistant.health_check`) and verify the JSON
  on `stdout` and the exit code `0`.
- **Inspection:** static review of the code and the design to confirm the
  absence of network, database and Windows component access.

All tests run in the Linux environment managed by `uv` with `pytest`. No
Windows validation is required: this feature does not define `windows_e2e`
criteria. The tests are deterministic and self-contained.

## Acceptance Traceability

| Criterion | Verification | Concrete evidence |
|----------|--------------|--------------------|
| AC-001 | integration | `tests/integration/test_health_check_cli.py`: the command runs via `uv`/`python -m` and produces output on `stdout`. |
| AC-002 | integration | `tests/integration/test_health_check_cli.py`: `json.loads(stdout)` parses a single valid JSON document without error. |
| AC-003 | integration | `tests/integration/test_health_check_cli.py`: the JSON contains the keys `status`, `application`, `version`, `python_version`. |
| AC-004 | integration | `tests/integration/test_health_check_cli.py`: the JSON on `stdout` has `status == "ok"`. |
| AC-005 | integration | `tests/integration/test_health_check_cli.py`: the process exits with code `0`. |
| AC-006 | inspection | "Failure Modes"/"Windows Runtime Impact" section of `architecture.md` and code review: only `json`, `sys`, `platform` and package metadata are used; no network, database or Windows components. |
| AC-007 | unit | `tests/unit/test_health_check.py`: validates the document construction, the mandatory fields and `status == "ok"`. |
| AC-008 | integration | `tests/integration/test_health_check_cli.py`: runs the full command and verifies the JSON on `stdout` and the exit code `0`. |

## Unit Tests

File: `tests/unit/test_health_check.py`. Imports
`src.desktop_overlay_assistant.health_check`.

- **test_build_report_contains_required_fields (AC-007):**
  `build_health_report()` returns a `dict` whose set of keys includes exactly
  `status`, `application`, `version`, `python_version`.
- **test_build_report_status_is_ok (AC-007):** the `status` field of the built
  document is exactly `"ok"`.
- **test_build_report_fields_are_nonempty_strings (AC-007):** `application`,
  `version` and `python_version` are non-empty strings (`isinstance(v, str)` and
  `v.strip() != ""`).
- **test_build_report_python_version_matches_runtime (AC-007):**
  `python_version` matches `platform.python_version()` of the running
  interpreter.

## Integration Tests

File: `tests/integration/test_health_check_cli.py`. Runs the command by
subprocess from the repository root:
`subprocess.run([sys.executable, "-m",
"src.desktop_overlay_assistant.health_check"], capture_output=True, text=True)`.

- **test_command_runs_and_writes_stdout (AC-001):** the command finishes and
  `stdout` is not empty.
- **test_stdout_is_single_valid_json (AC-002):** `json.loads(result.stdout)`
  does not raise an exception and produces a single JSON object (the output is a
  single parseable line).
- **test_json_has_required_fields (AC-003):** the parsed object contains
  `status`, `application`, `version` and `python_version`.
- **test_status_is_ok (AC-004):** the parsed object satisfies `status == "ok"`.
- **test_exit_code_is_zero (AC-005):** `result.returncode == 0`.
- **test_full_command_contract (AC-008):** integrated case that checks, in a
  single execution, exit code `0` and JSON on `stdout` with mandatory fields
  and `status == "ok"`.

## Windows E2E Tests

None. The feature does not require Windows validation and does not define
`windows_e2e` criteria. The command does not interact with the Windows runtime.

## Performance Tests

None. The command is O(1), without network or database I/O, and its latency is
dominated by the interpreter startup; a dedicated performance test is not
warranted. The integration tests implicitly attest to a fast, non-blocking
execution.

## Exit Criteria

The implementation is considered acceptable when:

- All the described unit and integration tests pass in the Linux environment
  under `uv`/`pytest`.
- Each criterion AC-001..AC-008 is covered by the evidence traced in the
  "Acceptance Traceability" section.
- Inspection confirms the absence of network, database and Windows component
  access (AC-006).
- `ruff check` and `ruff format --check` report no issues in the new files.
- The repository's complete test suite remains green.
