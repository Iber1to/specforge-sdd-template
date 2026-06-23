# Feature finalization contract

## Exclusive authority

Only `scripts/finalize_feature.py` may perform the transition:

`APPROVED -> DONE`

No agent or generic script may directly mark a feature as
finalized.

## Validated commit

The validated functional commit is `reviewed_commit`, included in the QA report.

After `reviewed_commit`, the feature branch may only contain one
additional commit (the QA evidence commit); that commit may only
modify:

- `evidence/reviews/<FEATURE>.json` (mandatory)
- `evidence/reviews/<FEATURE>.md`
- `evidence/mutation-reviews/<FEATURE>.json` (only if the feature declares the
  `mutation-testing` capability; the mutation report is folded into this same
  commit, not into an additional one)

Windows evidence, when mandatory, must correspond exactly to
`reviewed_commit`.

## Preconditions

- The feature is in `APPROVED` state.
- No active lease exists for the feature.
- The canonical repository is clean and on the `main` branch.
- The implementation worktree is clean.
- The QA report is valid and has verdict `APPROVED`.
- The QA run is closed correctly.
- No subsequent unreviewed commits or files exist.
- The full Linux suite passes on the branch.
- Windows evidence is valid when required.

## Integration

The branch is integrated through a merge commit.

Before creating the merge commit:

1. The merge is prepared with `--no-ff --no-commit`.
2. The prepared content is validated.
3. The full Linux suite runs over the integrated result.
4. If any validation fails, the merge is aborted.

## Result

After integrating successfully:

- The integration commit is recorded.
- The feature moves to `DONE`.
- The worktree is removed.
- The feature branch is removed.
