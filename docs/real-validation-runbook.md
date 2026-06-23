# Real Validation Runbook (Windows and SSH)

These validations require real hardware or services that the offline suites do
not cover. The code is already ready (`F2`, `T-007C`, SSH BatchMode/ConnectTimeout);
here are the procedures for QA to complete `T-008E` and `T-008F`.

## T-008E — Real Windows

Prerequisites: a Windows workstation with Python 3.12 and access to the
project's `artifact_root` (shared folder, `external-runtime` SSH/SCP, or manual
copy).

1. On the orchestration host (Linux), finalize the feature and note the
   QA-reviewed commit (`reviewed_commit`).
2. On the Windows workstation, inside the generated project, run the runner
   **without** `--allow-non-windows` (the platform check must pass because it is
   real Windows):

   ```
   python scripts\collect_windows_evidence.py --feature F-XXX --commit <commit>
   ```

3. Publish `artifact_root/windows-tests/F-XXX/latest.json` (and `runner.log` /
   `environment.json`) to the `artifact_root` accessible from Linux.
4. On the Linux host, validate:

   ```
   python3 scripts/validate_windows_evidence.py --feature F-XXX --commit <commit>
   ```

Acceptance criteria:

- The runner executes on real Windows without an override.
- It does not import POSIX modules (fixed in `control_common`, portable locking).
- The evidence is valid; commit and feature match.
- An incorrect commit is rejected with exit code 2.

The equivalent offline coverage (`collect --allow-non-windows` + `validate`) is
in `tests/test_generator.py::test_windows_evidence_collect_and_validate_offline`.

## T-008F — Real SSH

Prerequisites: an accessible SSH target (VM or remote host) with key-based
authentication (compatible with `BatchMode=yes`, no interactive password) and
the declared command's binary available on the remote.

1. In `state/capabilities/external-runtime.json`, enable a real SSH target
   (`enabled: true`, `host`, `user`, `port`) and declare
   `allowed_command_templates` with the permitted `command-id`s.
2. Run a job:

   ```
   uv run python scripts/run_external_runtime.py \
     --feature F-XXX --target <ssh-target> --command-id <id>
   ```

3. Review the evidence in
   `artifact_root/capabilities/external-runtime/F-XXX/latest.json`.

Acceptance criteria:

- A valid SSH job produces a `PASSED` result with evidence.
- An inaccessible target fails with a clear error (BatchMode + ConnectTimeout
  prevent hanging or asking for a password) and is recorded in the evidence.
- Only commands declared by `command-id` are run; free commands over SSH are not
  allowed.

The equivalent offline coverage (unknown command-id rejected, inaccessible
target fails cleanly) is in
`tests/test_generator.py::test_external_runtime_ssh_guards_offline`.
