# Feature Specification — F-001 Local health check CLI

## Problem

There is no local, fast and deterministic way to verify that the application
and its Python environment start up correctly. Without an observable,
structured signal, an operator or an automated process cannot reliably confirm
that the installation is in a valid state before starting downstream tasks. The
current manual verification is ambiguous and does not produce machine-consumable
output.

## Goal

Provide a local health check command that can be run through the `uv`
environment, that validates that the application and its Python environment
start up correctly, that emits a valid, structured JSON document on standard
output and that exits with code `0` when the state is healthy. The result must
be observable and consumable by both humans and automation without depending on
network, database or Windows-specific components.

## Scope

- An executable health check command invocable through the `uv` environment.
- Emission on standard output (`stdout`) of a single valid JSON document.
- Mandatory inclusion in the JSON of the fields `status`, `application`,
  `version` and `python_version`.
- Value `"ok"` in the `status` field when execution is correct.
- Exit code `0` when the health check state is healthy.
- Coverage through unit tests and integration tests that validate the
  observable behavior of the command.

## Out of Scope

- Any check that requires network access.
- Any check that requires a database.
- Any behavior or validation specific to Windows components.
- End-to-end Windows validation (not required for this feature).
- Graphical interface, overlay or any user surface other than the CLI.
- Advanced environment diagnostics beyond confirming correct startup.
- Definition of the internal architecture, module names or technical design
  decisions.

## User Scenarios

- As an operator, I run the health check command through `uv` and obtain on
  `stdout` a JSON with `status` equal to `"ok"` and an exit code `0`, so that I
  confirm the application starts up correctly.
- As an automated process, I invoke the command, parse the JSON from `stdout`
  and read the fields `status`, `application`, `version` and `python_version`
  to decide deterministically whether the environment is valid.
- As an operator in an environment without network or database, I run the
  command and obtain the same correct result, because the health check does not
  depend on those resources.

## Functional Requirements

- FR-001: The system must expose a health check command executable through the
  `uv` environment.
- FR-002: The command must write a single syntactically valid JSON document to
  `stdout`.
- FR-003: The JSON document must include, at minimum, the fields `status`,
  `application`, `version` and `python_version`.
- FR-004: The `status` field must contain the value `"ok"` when execution is
  correct.
- FR-005: The `application` field must contain an application identifier as a
  non-empty string.
- FR-006: The `version` field must contain the application version as a
  non-empty string.
- FR-007: The `python_version` field must reflect the version of the running
  Python interpreter as a non-empty string.
- FR-008: The command must exit with code `0` when the health check state is
  healthy.
- FR-009: The command must not access network, database or Windows-specific
  components during its execution.

## Non-Functional Requirements

- The command must run locally and self-contained, without external network or
  database dependencies.
- The command must be deterministic: for the same environment, the JSON keys
  and the exit code must be stable across executions.
- The JSON output must be parseable by standard automated consumers.
- The command must run in the project's Linux environment without requiring
  Windows components.

## Assumptions

- The command is invoked within the `uv`-managed environment defined by the
  project.
- The values of `application` and `version` come from the project metadata and
  are considered non-empty strings.
- The `python_version` field corresponds to the version of the Python
  interpreter active during execution.
- The JSON output is emitted on `stdout`; diagnostics or errors unrelated to
  the JSON document, if any, are not mixed into `stdout`.
- "Healthy state" means that the application and its Python environment start
  up without error and that all mandatory fields can be produced.

## Acceptance Summary

The acceptance criteria in `acceptance.yaml` cover: the existence of a command
executable through `uv` (AC-001); the emission of a valid JSON on `stdout`
(AC-002); the presence of the mandatory fields `status`, `application`,
`version` and `python_version` (AC-003); the value `"ok"` of the `status` field
on correct execution (AC-004); the exit code `0` in a healthy state (AC-005);
the absence of network, database and Windows component dependencies (AC-006);
and coverage through unit tests (AC-007) and integration tests (AC-008) of the
observable behavior.

## Open Questions

None
