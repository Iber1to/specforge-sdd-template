# Capability: Git Publish

Optional capability to publish completed features to a local or remote Git repository through a deterministic script and audited evidence.

## Why It Exists

The harness already integrates an approved feature into the local canonical branch during `finalize_feature.py`. This capability adds the subsequent step: recording or pushing that completed feature to the configured repository without allowing an agent to run `git push` directly.

## Activation

In `project.yaml`:

```yaml
capabilities: [git-publish]
git_publish_mode: local
git_publish_remote: origin
git_publish_branch: main
git_publish_auto: false
```

Modes:

- `local`: records evidence that the feature was integrated into local Git.
- `dry_run`: runs `git push --dry-run` against the configured remote.
- `push`: runs `git push <remote> HEAD:refs/heads/<branch>`.
- `disabled`: disables publication.

The default mode when activating the capability is `local`.

## Agent

Specialized agent:

```text
repository-publisher
```

The agent may only run:

```bash
uv run python scripts/publish_feature.py --feature <FEATURE>
```

The Role Guard blocks direct `git push`. The real push, when configured, happens inside the validated script.

## Requirements

- The feature must be in `DONE`.
- The canonical repo must be clean.
- The current branch must be the canonical branch.
- `merged_commit` must belong to the canonical HEAD.
- By default, `merged_commit` must be exactly `HEAD` to avoid publishing subsequent commits not attributed to that feature.
- For `dry_run` or `push`, the configured remote must exist.

## Evidence

Artifacts:

```text
artifact_root/git-publish/<feature>/<operation>.json
artifact_root/git-publish/<feature>/latest.json
```

The feature queue records:

```json
{
  "git_publication": {
    "status": "LOCAL_RECORDED",
    "mode": "local",
    "remote": "origin",
    "branch": "main",
    "published_commit": "...",
    "evidence": "..."
  }
}
```

States:

- `LOCAL_RECORDED`
- `DRY_RUN`
- `PUBLISHED`
- `DISABLED`

## Security

- No credentials are stored in evidence; URLs with embedded credentials are redacted.
- The script fails if there are pending changes.
- The script fails if the feature is not in `DONE`.
- The script fails if HEAD contains subsequent commits and `require_merged_head` is active.
