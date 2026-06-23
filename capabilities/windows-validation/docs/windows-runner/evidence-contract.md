# Windows Test Runner evidence contract

## Location

The Windows Test Runner must atomically publish the final result to:

`<artifact_root>/windows-tests/<FEATURE>/latest.json`

Logs, screenshots and other artifacts must also be stored outside the
Git repository.

## Mandatory requirements

- The evidence must comply with `specs/schemas/windows-evidence.schema.json`.
- `feature_id` must match the tested feature.
- `tested_commit` must match exactly the requested commit.
- The global status must be `PASS`.
- All checks must be `PASS`.
- Checks must be numbered sequentially starting from `WIN-001`.
- The log must exist.
- All declared artifacts must exist.
- Timestamps must include a time zone.

### `log` and `artifacts` paths (Windows/POSIX portability)

The runner runs on Windows and inevitably emits native paths
(`J:\...`, UNC `\\host\share\...`), while validation runs on Linux.
For this reason the schema does **not** impose a POSIX format on `log` or `artifacts`
(only `minLength: 1`), and validation re-roots each path by its *basename*
under the canonical directory `<artifact_root>/windows-tests/<FEATURE>/`. Trust
is anchored in the canonical directory, not in the string emitted by the
runner:

- Any path whose last component (basename) exists as a real
  file inside the canonical directory is accepted.
- Unsafe or ambiguous basenames are rejected (`.`, `..`, empty, or with
  residual separators), so that no declared path can escape
  the canonical one.
- Real existence is still checked against the canonical directory: a native path
  never resolves against the arbitrary local file system.
- The `latest.json` file should only be replaced when the run has
  completed fully.

## Recommended atomic publication

1. Create the result in `latest.json.tmp`.
2. Write and fully close the file.
3. Rename `latest.json.tmp` to `latest.json`.

## Validation from Ubuntu

```bash
uv run python scripts/validate_windows_evidence.py \
  --feature F-001 \
  --commit <commit>
```

## Commit requested by the finalizer

The evidence required to finalize a feature must use as
`tested_commit` the `reviewed_commit` field of the approved QA report.

The subsequent commit that stores the QA report itself does not modify the
functional code and does not need a new Windows run.
