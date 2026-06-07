# CLAUDE.md - Specs Router

Use this directory for traceable product and feature truth.

## Routes

| Need | Read |
| --- | --- |
| Product context | `product/` |
| Feature specification | `features/<FEATURE>/specification.md` |
| Acceptance criteria | `features/<FEATURE>/acceptance.yaml` |
| Semantic review | `features/<FEATURE>/semantic-review.md` |
| Architecture proposal | `features/<FEATURE>/architecture.md` |
| Implementation plan | `features/<FEATURE>/implementation-plan.md` |
| Test plan | `features/<FEATURE>/test-plan.md` |
| Reusable templates | `templates/` |
| Schemas | `schemas/` |

Feature files are authoritative for that feature until finalization. Stable
architecture decisions should be consolidated into `docs/10-architecture/adr/`
only when the feature is approved.
