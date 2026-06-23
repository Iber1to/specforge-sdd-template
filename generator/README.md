# Generator

`create_project.py` is the deterministic entrypoint of the template.

## Usage

```bash
python3 create_project.py --config project.yaml
```

Example `project.yaml`:

```yaml
project_id: example-project
name: Example Project
output_path: /srv/agentic/workspace/example-project
profile: python
capabilities: [mutation-testing]
```

## Internal Flow

1. Reads simple YAML.
2. Validates mandatory fields.
3. Copies `core/` to the `output_path`.
4. Writes `state/project.json`.
5. Creates `data/<project_id>/control` and `data/<project_id>/artifacts`.
6. Applies the selected profile.
7. Initializes Git on `main`.
8. Creates the initial commit.

## YAML Parser Limitations

The parser is intentionally small. It supports:

- `key: value`
- booleans `true`/`false`
- inline lists like `[mutation-testing]`
- comments with `#`

It does not support nested YAML. If the template needs complex configuration, it must be added with tests before extending the contract.

## Contracts

Supported profiles:

- `generic`
- `python`
- `node`
- `android`

Supported capabilities:

- `documentation-pack` (included by default)
- `eval-harness`
- `external-runtime`
- `git-publish`
- `mutation-testing`
- `performance-testing`
- `remote-notifications`
- `security-scanning`
- `tool-telemetry`
- `windows-validation`

The generator fails if it receives unknown profiles or capabilities.
