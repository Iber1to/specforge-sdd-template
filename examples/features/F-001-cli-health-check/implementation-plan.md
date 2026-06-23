# Implementation Plan — F-001 Local health check CLI

## Strategy

Implement the health check command with the minimal possible surface,
respecting the repository structure (`src/`, `tests/`, `pyproject.toml`) and the
F-001 architecture. The work is divided into:

1. Expose application metadata in the package (`__init__.py`).
2. Create the command module with a pure document-building function and a CLI
   entry point executable as a module (`python -m`).
3. Cover the behavior with unit tests (pure function) and integration tests
   (subprocess execution of the full command).

The command only uses the standard library (`json`, `sys`, `platform`) and the
package metadata. No runtime dependencies are added. There is no access to
network, database or Windows components.

The stable invocation contract is:

```
uv run python -m src.desktop_overlay_assistant.health_check
```

## Work Breakdown

1. **Package metadata** — `src/desktop_overlay_assistant/__init__.py`:
   - Define `APPLICATION: str` with the application identifier, a non-empty
     string (for example `"desktop-overlay-assistant"`, matching
     `project.name`).
   - Define `VERSION: str` with the application version, aligned with
     `project.version` in `pyproject.toml` (currently `"0.1.0"`).
   - Keep both values as non-empty strings.

2. **Command module** — `src/desktop_overlay_assistant/health_check.py`:
   - Import `json`, `sys`, `platform` and the package metadata
     (`APPLICATION`, `VERSION`).
   - Define the healthy-state constant `OK_STATUS = "ok"`.
   - Implement `build_health_report() -> dict[str, str]` that returns a
     dictionary with the mandatory keys, in this order:
     `{"status": OK_STATUS, "application": APPLICATION, "version": VERSION,
     "python_version": platform.python_version()}`. Pure function, no I/O.
   - Implement `main(argv: list[str] | None = None) -> int`:
     - Build the document with `build_health_report()`.
     - Serialize it with `json.dumps(report)` (a single JSON document).
     - Write it to `stdout` via `print(...)` or
       `sys.stdout.write(... + "\n")` (a single line, nothing else on `stdout`).
     - Return `0` when `report["status"] == OK_STATUS`.
   - Add the guard `if __name__ == "__main__": raise SystemExit(main())`.

3. **Unit tests** — `tests/unit/test_health_check.py`:
   - Verify that `build_health_report()` returns the four mandatory keys and
     that `status == "ok"`.
   - Verify that `application`, `version` and `python_version` are non-empty
     strings and that `python_version` matches `platform.python_version()`.

4. **Integration tests** — `tests/integration/test_health_check_cli.py`:
   - Run the full command by subprocess with
     `subprocess.run([sys.executable, "-m",
     "src.desktop_overlay_assistant.health_check"], ...)` from the repo root,
     capturing `stdout` and the exit code.
   - Verify exit code `0`.
   - Parse `stdout` with `json.loads` (single, valid JSON) and check the
     mandatory fields and `status == "ok"`.

5. **Local pre-delivery verification** (without changing states):
   - `uv run ruff check` and `uv run ruff format --check` on the new files.
   - `uv run pytest tests/unit/test_health_check.py
     tests/integration/test_health_check_cli.py`.
   - Manual command:
     `uv run python -m src.desktop_overlay_assistant.health_check`.

Note on the entry point: the primary and mandatory mechanism is the executable
module (`python -m ...`), consistent with the absence of `[build-system]` in
`pyproject.toml`. **Optionally**, if the implementer decides to also expose a
named script (`health-check`), they must add `[build-system]` and
`[project.scripts]` in `pyproject.toml` and install the package; this is
optional and must not break the documented `python -m` contract nor introduce
network/database dependencies.

## Files Expected to Change

- `src/desktop_overlay_assistant/__init__.py` (new): metadata `APPLICATION`,
  `VERSION`.
- `src/desktop_overlay_assistant/health_check.py` (new): pure function, `main`
  and `__main__` guard.
- `tests/unit/test_health_check.py` (new): unit tests of the pure function.
- `tests/integration/test_health_check_cli.py` (new): integration tests of the
  full command.
- `pyproject.toml` (optional, only if the implementer adds the named script):
  `[build-system]` and `[project.scripts]` blocks.

No other file is modified. `runtime/windows-runner/`, `state/`, `scripts/` and
the control plane are not touched.

## Dependencies

None. The command relies exclusively on the Python standard library
(`json`, `sys`, `platform`) and the package metadata. The required development
dependencies (`pytest`, `ruff`) are already declared in the `dev` group of
`pyproject.toml`.

## Risks

- **Package import path:** without `[build-system]`, the module is imported as
  `src.desktop_overlay_assistant.health_check`. Mitigation: use exactly that
  path both in the `python -m` invocation and in the unit test imports, and run
  the integration subprocess from the repo root (where `pythonpath = ["."]`
  applies).
- **`stdout` contamination:** writing additional traces to `stdout` would break
  JSON parsing (AC-002). Mitigation: emit only the JSON document on `stdout`;
  any diagnostic goes to `stderr`.
- **`version` misalignment:** the exposed version could diverge from
  `project.version`. Mitigation: document and keep `VERSION` aligned with
  `pyproject.toml`; in any case it must be a non-empty string.
- **Overscope:** adding packaging or advanced diagnostic logic would exceed the
  scope. Mitigation: keep the solution minimal; the named script is strictly
  optional.

## Rollback

The changes are purely additive and isolated in new files. To revert it is
enough to delete the created files
(`src/desktop_overlay_assistant/health_check.py`,
`src/desktop_overlay_assistant/__init__.py`, `tests/unit/test_health_check.py`,
`tests/integration/test_health_check_cli.py`) and, if it had been added, undo
the optional edit of `pyproject.toml`. There are no data migrations, persistent
state or external side effects to clean up; reverting the corresponding commit
leaves the repository in its previous state.
