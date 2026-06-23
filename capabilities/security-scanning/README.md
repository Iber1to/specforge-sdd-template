# Capability: Security Scanning

Optional capability to detect secrets and sensitive configurations with low-noise local checks.

## MVP Scope

- Versioned policy in `state/capabilities/security-scanning.json`.
- Deterministic scanner of secrets and sensitive files.
- Redaction of sensitive samples.
- Normalized output with severities.
- Deterministic validator.
- Evidence in `artifact_root/capabilities/security-scanning/<feature>/`.

## Usage

```bash
python3 scripts/run_security_scan.py --feature F-001
```

Validation:

```bash
python3 scripts/validate_security_result.py \
  --feature F-001 \
  --evidence <artifact_root>/capabilities/security-scanning/F-001/latest.json \
  --require-pass
```

## Status

Initial mode: `observe`. Findings are recorded and normalized; blocking on critical severity is activated by changing the policy to `enforce`.
