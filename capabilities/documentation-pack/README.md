# Capability: Documentation Pack

`documentation-pack` is enabled by default for generated projects. It makes
technical documentation part of the template contract instead of a manual task
after implementation.

## What It Adds

- Stable project documentation under numbered `docs/` sections.
- Feature traceability remains under `specs/features/`.
- Lightweight evidence remains under `evidence/`.
- Heavy artifacts and operational state remain outside Git in `artifact_root`
  and `control_root`.
- Generated summaries live under `docs/90-generated/` and are not
  authoritative.

## Generated Structure

```text
docs/
  README.md
  00-project/
  10-architecture/
  20-runtime/
  30-quality/
  40-operations/
  50-releases/
  90-generated/
```

The generated harness may also copy non-numbered directories under `docs/`,
such as `docs/architecture` and `docs/conventions`. Those files describe the
harness contracts used by agents and scripts.

## Scripts

```bash
python3 scripts/generate_docs_index.py
python3 scripts/refresh_project_docs.py
python3 scripts/refresh_feature_index.py
python3 scripts/refresh_quality_summary.py
python3 scripts/refresh_metrics_summary.py
```

`refresh_project_docs.py` runs the full documentation refresh.

## Policy

Policy is stored in:

```text
state/capabilities/documentation-pack.json
```

Schema:

```text
specs/schemas/documentation-policy.schema.json
```

Generated documentation is explicitly non-authoritative. The source of truth
remains `state/`, `control_root`, `specs/features/`, `evidence/` and Git.

## Source Of Truth Matrix

Generated projects include:

```text
docs/00-project/source-of-truth.md
```

That file declares which source owns each kind of information:

| Information | Authoritative Source |
| --- | --- |
| Current feature state | `control_root/queue.json` |
| Feature requirements | `specs/features/<FEATURE>/` |
| Stable architecture decisions | `docs/10-architecture/adr/` |
| Runtime configuration | `state/project.json` |
| Quality gates | `state/quality-gates.json` |
| Capability policy | `state/capabilities/*.json` |
| Lightweight evidence | `evidence/` |
| Heavy artifacts | `artifact_root` |
| Exact code changes | Git history |
| Generated summaries | `docs/90-generated/` |

`docs/90-generated/` is regenerable and must never be treated as the source of
truth.

## Finalization Gate

Features can declare documentation requirements in `acceptance.yaml`:

```yaml
documentation:
  requires_adr: true
  requires_runtime_update: false
  requires_operations_update: true
  requires_quality_update: false
```

`scripts/finalize_feature.py` validates the reviewed diff before moving a
feature to `DONE`. Required documentation updates must be present in the
reviewed changes, not added after QA.
