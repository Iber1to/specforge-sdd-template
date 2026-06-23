# Spec Driven Development Conventions

## Mandatory documents per feature

Each feature is stored in:

`specs/features/<feature-id>-<slug>/`

And must contain:

- `specification.md`
- `acceptance.yaml`
- `architecture.md`
- `implementation-plan.md`
- `test-plan.md`

## Rules for acceptance criteria

- Each criterion has a sequential identifier: `AC-001`, `AC-002`, etc.
- Identifiers cannot be repeated.
- All criteria must be objectively verifiable.
- All criteria must appear in `test-plan.md`.
- No properties other than those defined in the schema are allowed.
- Features that require Windows validation must include at least one criterion
  verified through `windows_e2e`.

## Markdown rules

- Every document must have an H1 title.
- All mandatory sections must exist.
- Mandatory sections cannot be left empty.
- No `<!-- REQUIRED: ... -->` markers may remain.
- The corresponding validators must be run before requesting a transition.

## Manual validation

```bash
uv run python scripts/validate_spec.py --feature F-001
uv run python scripts/validate_design.py --feature F-001 --level architecture
uv run python scripts/validate_design.py --feature F-001 --level ready
```

## Autonomous Spec Partner

New features use `acceptance.yaml` with `schema_version: 2`.

The technical agent `specifier` acts as an autonomous Spec Partner:

- analyzes and hardens the initial functional idea;
- documents assumptions through `ASM-XXX`;
- documents functional decisions through `DEC-XXX`;
- records open questions through `Q-XXX`;
- blocks only when a critical question cannot be resolved safely;
- generates structured scenarios `SCN-XXX` with `given`, `when` and `then`;
- ensures coverage of all mandatory `AC-XXX` criteria.

Scenarios are not executable Gherkin and do not imply TDD. They constitute a
structured, traceable contract for architecture, implementation and QA.

Legacy features declared in
`state/specification-policy.json::legacy_v1_features` may retain
`schema_version: 1` contracts.
