# CI/CD Cycle

This document defines the integration and delivery cycle of the
`SpecForge SDD Template`.

The goal is not to deploy an application to servers. This repository is a
template: delivery consists of keeping `main` validated, generating real test
projects and publishing versioned releases when a commit is tagged.

## Principles

- `main` must always be green.
- Every PR must run the same deterministic validation as a push to `main`.
- The tests do not depend on Claude Code, external product networks or Windows
  runners.
- Experimental capabilities may be covered offline; the real external
  validation lives in separate runbooks.
- Publishing is done by Git tag. For internal versions, the tag is marked as a
  prerelease on GitHub.

## Automated Workflow

The workflow lives in:

```text
.github/workflows/ci-cd.yml
```

It runs on:

- `pull_request`
- `push` to `main`
- `push` of `v*` tags
- `workflow_dispatch`

## Jobs

### Template suite

Validates the template itself.

Steps:

1. Checkout of the repo.
2. Python 3.12.
3. Node 22, needed to validate the `node` profile.
4. `uv` pinned to the version used to validate the template locally.
5. Local Git identity for tests that create temporary commits.
6. Preflight:

```bash
python3 core/scripts/check_environment.py --profile node
```

7. Static integrity:

```bash
git diff --check
python3 -m compileall -q create_project.py tests core/scripts capabilities
```

8. Deterministic suite:

```bash
python3 -m unittest discover -s tests -v
```

On GitHub Actions it runs via an embedded `unittest` runner that preserves the
same semantics and, on failure, writes the test and a summarized traceback to
the job summary and emits `::error` annotations.

### Generated project smoke

Generates temporary projects and runs their full verification.

Matrix:

| Profile | Capabilities |
|---|---|
| `generic` | `[]` |
| `python` | `[mutation-testing]` |
| `node` | `[]` |

For each profile:

```bash
python3 create_project.py --config "$tmpdir/project.yaml"
cd "$output_path"
python3 scripts/check_environment.py --profile "$profile"
bash scripts/verify_full.sh
```

This checks that the template not only passes its tests but also generates
operable projects.

### Publish GitHub release

Runs only on `v*` tags, and only after the previous jobs pass.

Actions:

- creates a GitHub Release if it does not exist;
- updates the Release if it already exists;
- uses `CHANGELOG.md` as notes;
- marks as prerelease if the tag contains `internal`, `alpha`, `beta` or `rc`.

It needs no secrets of its own: it uses `GITHUB_TOKEN`.

## Pinned Versions

The workflow pins:

| Tool | Version |
|---|---|
| Python | `3.12` |
| Node | `22` |
| uv | `0.11.19` |

It also defines `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` to anticipate the
migration of GitHub Actions from Node 20 to Node 24.

## Branch Policy

Recommended flow:

1. Work on a short-lived branch.
2. Open a PR against `main`.
3. Wait for green CI.
4. Merge with squash or merge commit, depending on repo policy.
5. For a release, create an annotated tag from `main`.

Example:

```bash
git checkout main
git pull --ff-only
git tag -a v1.0.1-internal -m "SpecForge SDD Template v1.0.1-internal"
git push origin main --tags
```

## Recommended Protections On GitHub

Configure this manually on GitHub if it is not active yet:

1. `Settings -> Actions -> General`
   - Allow GitHub Actions.
   - Allow the actions used by the workflow:
     - `actions/checkout@v4`
     - `actions/setup-python@v5`
     - `actions/setup-node@v4`
     - `astral-sh/setup-uv@v5`
   - Workflow permissions: allow `Read and write permissions` if you want the
     release job to create/edit GitHub Releases.

2. `Settings -> Branches -> Branch protection rules`
   - Protect `main`.
   - Require a pull request before merging.
   - Require status checks to pass before merging.
   - Require these checks:
     - `Template suite`
     - `Generated project smoke (generic)`
     - `Generated project smoke (python)`
     - `Generated project smoke (node)`
   - Require branches to be up to date before merging.

3. `Settings -> General`
   - If the repo is to be used as a template, enable `Template repository`.

4. `Settings -> Tags` or Rulesets rules, if available in your plan.
   - Protect `v*`.
   - Allow release tags only to maintainers.

## Equivalent Local Commands

Before opening a PR:

```bash
python3 core/scripts/check_environment.py --profile node
git diff --check
python3 -m compileall -q create_project.py tests core/scripts capabilities
python3 -m unittest discover -s tests -v
```

Manual smoke of a generated project:

```bash
tmpdir="$(mktemp -d)"
cat > "$tmpdir/project.yaml" <<YAML
project_id: ci-python-project
name: CI Python Project
output_path: $tmpdir/ci-python-project
profile: python
capabilities: [mutation-testing]
YAML

python3 create_project.py --config "$tmpdir/project.yaml"
cd "$tmpdir/ci-python-project"
bash scripts/verify_full.sh
```

## What The CI Does Not Do

- It does not run Claude Code.
- It does not open `tmux` sessions.
- It does not run `windows-validation` against a real Windows workstation.
- It does not auto-push generated changes.
- It does not publish to npm, PyPI or containers.

These tasks are deliberately manual or runbook-driven until there is a real need
for external delivery.

## Diagnostics

If `Template suite` fails, look first at:

- the Python version;
- the `uv` installation;
- the output of `check_environment.py`;
- `unittest` errors.

If `Generated project smoke` fails, the problem is usually in:

- the generator;
- a capability manifest;
- the `verify_full.sh` scripts;
- profile dependencies, especially Node.

If `Publish GitHub release` fails:

- check `GITHUB_TOKEN` permissions;
- check `Settings -> Actions -> Workflow permissions`;
- confirm the tag starts with `v`;
- confirm `CHANGELOG.md` exists in the tagged commit.
