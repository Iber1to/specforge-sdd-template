# Python Profile

Profile for Python projects with a `src/` layout, tests and harness gates.

## Includes

- Complete harness core.
- Python package under `src/<project_name>/`.
- `tests/unit/test_profile_smoke.py`.
- `tests/unit/test_harness_smoke.py`.
- `pyproject.toml` and `uv.lock` inherited from the core.

## Toolchain

- Python 3.11+
- `pytest`
- `ruff`
- `compileall`
- `uv` recommended, with a fallback to `.venv/bin` in verification scripts.

## Validation

```bash
bash scripts/verify_fast.sh
bash scripts/verify_full.sh
```

## Mutation Testing

This profile is the initial target of `mutation-testing`.

Example:

```bash
python3 scripts/mutation_runner.py \
  --feature F-001 \
  --output /srv/agentic/workspace/data/<project_id>/artifacts/mutation-tests/F-001/latest.json \
  --test-command python3 -m pytest -q
```

The runner applies Python mutants, runs tests and restores the modified files.
