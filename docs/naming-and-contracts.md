# Naming and JSON Contracts

Canonical vocabulary of the harness contracts. Its goal is that similar fields
are not confused and that naming is predictable across capabilities.

## Canonical vocabulary

| Concept | Field | Meaning |
|---|---|---|
| Installed capability | `enabled` (policy) / `*_available` (project) | The capability is installed and available. Does not imply it is required. |
| Requirement | `*_required` (feature) | A concrete feature requires that evidence to advance. Declared per feature. |
| Blocking policy | `mode`: `observe` \| `enforce` | `observe` records evidence without blocking; `enforce` can block the phase. |
| Gate/runner result | `status` | Result of a deterministic run (see values below). |
| Human/agent verdict | `verdict` | QA decision: `APPROVED` \| `CHANGES_REQUESTED`. Different from `status`. |

Rules:

- **`available` vs `required`**: installing a capability leaves it *available*
  (project); a feature requiring it is *required* (feature). Separated since
  `windows_validation_available` / `windows_validation_required`.
- **`enabled` vs `required`**: `enabled` belongs to the capability's policy;
  `required_for_done` / `required_for_qa_approval` are independent requirement
  flags.
- **`observe` vs `enforce`**: the single blocking axis. Every capability starts in
  `observe` unless an explicit decision is made.
- **`status` vs `verdict`**: `status` is machine (gates/runners); `verdict` is the
  QA decision. They are not interchanged.

## Evidence field convention

All evidence includes: `schema_version`, `feature_id`, `status`, `started_at`,
`completed_at`. Paths and commands go as explicit lists/strings; secrets are
redacted or published as a hash (`remote_url_hash`).

## Known inconsistency: `PASS`/`PASSED`

Today two vocabularies coexist for `status`:

- Capability evidence (`external-runtime`, `performance-testing`,
  `security-scanning`): `PASSED` / `FAILED` (see `capability_common.CAPABILITY_STATUSES`).
- Windows evidence and `git-publish`: `PASS` / `FAIL`.

Both values are clear, but they are not unified. The unification (e.g. everything
to `PASSED`/`FAILED`) touches schemas, validators and tests, so it is left as a
**follow-up with its own tested change**, not as part of the v1 polish.

Recommended migration when addressed:

1. Choose the canonical vocabulary (`PASSED`/`FAILED`).
2. Update `windows-evidence.schema.json`, `windows_validation.py`,
   `collect_windows_evidence.py` and `publish_feature.py`.
3. Update the tests that assert `PASS`/`FAIL`.
4. Document the contract change in the changelog.
