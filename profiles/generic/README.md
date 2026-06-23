# Generic Profile

Stack-neutral profile for projects that need the SDD harness without assuming a main language or framework.

## Includes

- Complete harness core.
- Empty `src/` prepared for future code.
- `tests/unit/test_harness_smoke.py`.
- Minimal README for the generated project.

## Recommended Usage

Use it for:

- technical documentation repos
- mixed projects
- prototypes where the stack is not yet decided
- products that want to adopt the workflow before locking in a toolchain

## Validation

The generated project must pass:

```bash
bash scripts/verify_full.sh
```

Since there is no dedicated stack, the gates validate the harness, schemas, Python formatting, tests and versioned state.
