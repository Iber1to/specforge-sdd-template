# Template Development Guide

This guide covers how to modify the template, validate that it generates
functional projects and publish changes safely.

## Requirements

- Git
- Python 3.11 or higher
- Bash
- `uv` recommended for the Python harness
- Node.js and npm to validate the `node` profile

The template is validated mainly with `unittest`; the generated projects use the
harness scripts.

## Work Structure

Main path on `jarvis`:

```text
/srv/agentic/workspace/agentic-sdd-template        template
```

Test projects must be generated in temporary directories or local sandboxes.
They are not kept as a stable part of the workspace.

## Run Template Tests

From the template repo:

```bash
python3 -m unittest discover -s tests -v
```

The current suite generates temporary projects for the three profiles and
validates that the Node profile can run `npm test`.

## Create A Manual Project

```bash
cat > project.yaml <<'YAML'
project_id: example-project
name: Example Project
output_path: /srv/agentic/workspace/example-project
profile: python
capabilities: [mutation-testing]
YAML

python3 create_project.py --config project.yaml
```

Afterwards:

```bash
cd /srv/agentic/workspace/example-project
bash scripts/verify_full.sh
python3 scripts/project_status.py
```

## Modify `core/`

`core/` is now the stable source of the harness within the template. For
behavior changes:

1. Implement the change in `agentic-sdd-template/core`.
2. Run the template tests.
3. Generate temporary projects if the change affects the lifecycle, scripts,
   specs, gates, agents or state.
4. Complete a real feature in at least one generated project if the change
   touches the operational flow.

Do not manually edit `data/<project_id>/control` except for inspection. The
operational state must change through deterministic scripts.

## Modify Profiles

Each profile must meet three rules:

- The generated project must have a clean first commit.
- `bash scripts/verify_full.sh` must be able to run without special manual
  preparation.
- There must be at least one smoke test so the gates have a real signal.

For `node`, if you add new commands, also update the gates added to
`state/quality-gates.json`.

## Modify Capabilities

A capability must document:

- how it is activated
- which files or agents it adds
- which evidence it produces
- whether it blocks the lifecycle
- how it is validated

If a capability is activated per feature, verify that `register_feature.py`
accepts the value and that the control plane takes it into account.

## Pre-Commit Checklist

```bash
python3 core/scripts/check_environment.py --profile node
python3 -m unittest discover -s tests -v
git status --short
git diff --check
```

If `core/` was synchronized, also validate a generated project:

```bash
cd /srv/agentic/workspace/<generated-project>
bash scripts/verify_full.sh
```

## Acceptance Criteria For Large Changes

A large template change is ready when:

- The template suite passes.
- At least one new generated project passes `verify_full.sh`.
- The affected profiles have an updated README.
- The affected capabilities have an updated README.
- `docs/estado-y-roadmap-harness-agentico.md` or the corresponding decision
  document reflects the change if it alters the roadmap or contracts.
- The repo is clean before the commit.

## CI/CD

The automated cycle lives in `.github/workflows/ci-cd.yml` and is documented in
`docs/ci-cd.md`.

Summary:

- PR and push to `main`: preflight, static integrity, template suite and smoke
  of generated projects.
- `v*` tags: the same checks and, if they pass, publication/update of the GitHub
  Release using `CHANGELOG.md`.
- It does not run Claude Code or real Windows runners.

## Documentation Conventions

- Keep commands copy-pasteable.
- Document real paths when they serve as evidence.
- Separate versioned state from operational state.
- Do not hide limitations: if a capability is optional or partial, say so.
- Prefer small examples that can be run from a generated project.
