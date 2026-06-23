# Feature Architecture — F-001 Local health check CLI

## Context

Feature F-001 (state `SPEC_READY`) needs a local health check command,
self-contained and deterministic, executable through the project's `uv`
environment. The command must emit on `stdout` a single valid JSON document with
the fields `status`, `application`, `version` and `python_version`, and exit with
code `0` when the state is healthy.

Relevant technical constraints of the repository:

- Canonical structure: `src/`, `tests/`, `pyproject.toml`.
- Existing (empty) application package: `src/desktop_overlay_assistant/`.
- `pyproject.toml` defines `requires-python = ">=3.12,<3.13"`, does not contain
  `[build-system]` and configures `pythonpath = ["."]` with `testpaths = ["tests"]`.
  As a result, the application package is not installed as a distribution and is
  imported by its path from the repository root: `src.desktop_overlay_assistant`.
- No network, no database, no Windows components. Windows validation is **not**
  required by this feature.

This architecture designs the minimal solution that satisfies AC-001..AC-008
without introducing new functional requirements.

## Decision

Implement the health check as a single Python module within the application
package, with two separate, verifiable responsibilities:

1. A **pure function** that builds the health check document (a
   `dict[str, str]`) from the application metadata and the version of the
   running Python interpreter. It is deterministic and performs no I/O.
2. A **CLI entry point** (`main`) that serializes that document to JSON, writes
   it to `stdout` and returns exit code `0` when the state is healthy.

The command is exposed as an **executable module** through an
`if __name__ == "__main__"` block, so that it is invocable through the `uv`
environment:

```
uv run python -m src.desktop_overlay_assistant.health_check
```

Reasons for this decision:

- **Operational simplicity and consistency with the repo.** There is no
  `[build-system]`, so a `console_scripts` would not be installed by
  `uv run <name>`. The `uv run python -m ...` invocation works with the current
  structure without adding packaging or dependencies.
- **Windows/Ubuntu isolation.** The command only uses the standard library
  (`json`, `sys`, `platform`) and project metadata; it does not touch paths,
  network, database or platform-specific APIs, so it is identical on Linux and
  introduces no impact on the Windows runtime.
- **Latency.** Without external I/O or heavy imports, startup and execution are
  in the order of milliseconds.
- **Testability.** Separating the (pure) document construction from
  serialization/output enables direct unit tests (AC-007) and subprocess
  integration tests over the full command (AC-008).

Alternative considered and discarded for this feature: declaring a
`[project.scripts]` + `[build-system]` to expose a `health-check` binary. It is
discarded as the primary mechanism because it would require installing the
package and adding a build backend, expanding the scope unnecessarily. The
implementer may add it optionally (see implementation plan) without breaking the
documented invocation contract.

## Components

- **`src/desktop_overlay_assistant/__init__.py`** (new): marks the directory as
  an importable package and exposes the reusable application metadata:
  - `APPLICATION` (application identifier, non-empty string).
  - `VERSION` (application version, non-empty string), aligned with
    `project.version` in `pyproject.toml` (currently `"0.1.0"`).
- **`src/desktop_overlay_assistant/health_check.py`** (new): command module.
  Contains:
  - `build_health_report() -> dict[str, str]`: pure function that produces the
    health check document.
  - `main(argv: list[str] | None = None) -> int`: CLI entry point that
    serializes the document to JSON, writes it to `stdout` and returns the exit
    code.
  - Guard `if __name__ == "__main__": raise SystemExit(main())`.
- **Tests** (new): unit tests in `tests/unit/` and integration tests in
  `tests/integration/`.

## Interfaces

### Pure function

```
build_health_report() -> dict[str, str]
```

- Inputs: none (reads package metadata and the version of the running
  interpreter).
- Output: dictionary with exactly the mandatory keys:
  - `status`: `"ok"` in a healthy state.
  - `application`: `APPLICATION`, non-empty string.
  - `version`: `VERSION`, non-empty string.
  - `python_version`: version of the active Python interpreter, non-empty string
    (obtained with `platform.python_version()`).
- No side effects, no I/O, no network, no database.

### CLI entry point

```
main(argv: list[str] | None = None) -> int
```

- Builds the document with `build_health_report()`.
- Serializes with `json.dumps(report)` producing a single JSON document.
- Writes the JSON to `stdout` (a single line, followed by a line break).
- Returns `0` when the state is healthy (`status == "ok"`).
- Does not write the JSON document to `stderr`; any diagnostics unrelated to the
  JSON, if any, would go to `stderr` so as not to contaminate `stdout`.

### Invocation contract (external boundary)

- Stable health check command:
  `uv run python -m src.desktop_overlay_assistant.health_check`.
- Observable output: a single JSON line on `stdout`; exit code `0`.

## Data Flow

1. The operator or automated process invokes
   `uv run python -m src.desktop_overlay_assistant.health_check`.
2. `uv` activates the managed environment and runs the module.
3. The `__main__` guard calls `main()`.
4. `main()` invokes `build_health_report()`.
5. `build_health_report()` reads `APPLICATION` and `VERSION` from the package and
   obtains `platform.python_version()`, and returns the `dict` with the four keys.
6. `main()` serializes the `dict` to JSON with `json.dumps` and writes it to
   `stdout`.
7. `main()` returns `0`; the guard propagates it as the process exit code.
8. The consumer parses the JSON from `stdout` and/or evaluates the exit code.

There is no network, database, application file system or platform-specific path
in any step.

## Data Model

Health check document (JSON object with string-typed values):

| Field            | Type   | Source                              | Constraint           |
|------------------|--------|-------------------------------------|----------------------|
| `status`         | string | Healthy-state constant              | `== "ok"`            |
| `application`    | string | Package `APPLICATION`               | non-empty            |
| `version`        | string | Package `VERSION`                   | non-empty            |
| `python_version` | string | `platform.python_version()`         | non-empty            |

Representative example of the output:

```json
{"status": "ok", "application": "desktop-overlay-assistant", "version": "0.1.0", "python_version": "3.12.x"}
```

The set of keys is stable across executions for the same environment
(determinism required by the specification). `python_version` may vary
depending on the active interpreter, but it is always a non-empty string.

## Performance Considerations

- **Latency:** execution dominated by the interpreter startup under `uv`. The
  command's own work (building a four-key `dict` and serializing it) is O(1) and
  in the order of microseconds; the total cost is a few milliseconds after the
  interpreter startup.
- **Memory:** negligible; fixed-size structures and only standard-library modules
  (`json`, `sys`, `platform`).
- **Concurrency:** not applicable; single-process execution, with no shared
  state or external resources, idempotent and reentrant.
- **Bottlenecks:** none relevant; there is no network or database I/O. Imports
  are kept minimal so as not to penalize startup.

## Failure Modes

- **Missing or empty metadata** (`APPLICATION`/`VERSION`): they are defined as
  non-empty constants within the package, so under normal conditions they cannot
  be missing. If the implementer were to derive the version from an external
  source and it were not available, it must fall back to the package constant as
  the fallback value to guarantee a non-empty string and `status == "ok"`.
- **Interpreter/environment import failure:** if the Python environment does not
  start, the process fails before producing JSON and exits with a non-zero code;
  this is exactly the "unhealthy" signal that the feature intends to make
  observable. It is not masked with a `0`.
- **`stdout` contamination:** so as not to break JSON parsing, the command does
  not write anything else to `stdout`. Any diagnostic trace goes to `stderr`.
- **Recovery:** the command is stateless and idempotent; in the face of a
  transient environment failure, simply retrying the execution is enough. It
  leaves no side effects that require cleanup.

## Windows Runtime Impact

None. The command uses exclusively the Python standard library
(`json`, `sys`, `platform`) and project metadata; it does not invoke Windows
APIs, does not touch `runtime/windows-runner/` and does not depend on
platform-specific paths or components. The feature does not require Windows
validation and does not introduce any `windows_e2e` criterion.

## Open Questions

None
