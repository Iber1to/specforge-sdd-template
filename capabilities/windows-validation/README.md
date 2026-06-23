# Capability: Windows Validation

Optional capability for projects that require Windows validation evidence.

## Activation

In `project.yaml`:

```yaml
capabilities: [windows-validation]
```

The generator will mark:

```json
{
  "windows_validation_available": true
}
```

in `state/project.json`. The mandatory nature of Windows evidence is per feature
(declared with `--capability windows-validation` or `--windows-validation-required`
when registering the feature); installing the capability only makes it available.

## Components

- `scripts/collect_windows_evidence.py`
- `scripts/windows_validation.py`
- `scripts/validate_windows_evidence.py`
- `specs/schemas/windows-evidence.schema.json`
- `docs/windows-runner/evidence-contract.md`

## Evidence

Windows evidence must follow the contract documented in:

```text
docs/windows-runner/evidence-contract.md
```

Minimal runner:

```bash
python3 scripts/collect_windows_evidence.py \
  --feature F-001 \
  --commit <commit>
```

Non-Windows smoke to validate the infrastructure on Jarvis:

```bash
python3 scripts/collect_windows_evidence.py \
  --feature F-001 \
  --allow-non-windows
```

## Operational Note

Windows validation is not a dependency of the core. Projects that do not activate this capability can complete features without Windows evidence.
