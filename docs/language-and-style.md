# Language and Style Convention

Convention applicable to the template and the generated projects. Its goal is to
avoid mixing languages and to keep a consistent style that both humans and agents
can follow.

## Language

- **Template documentation**: English. Includes the README, the docs under
  `docs/`, the contracts under `docs/architecture/`, conventions and runbooks.
- **Identifiers and machine contracts**: English. Includes JSON schema keys,
  state names (`DRAFT`, `READY_FOR_QA`, ...), capability and gate ids, and
  file/script names.
- **Spec templates** (`specs/templates/`): English, for compatibility with the
  validators and with the content the agents produce.
- Languages are not mixed within a single sentence except for technical terms
  (`worktree`, `lease`, `merge`, `commit`).

## Accents

- Documents under `core/docs/` written in Spanish use correct Spanish accentuation.
- The template root documents, the script messages (`print`) and the `.sh` files
  use ASCII to avoid encoding problems in heterogeneous environments. They are
  not mixed: a file is consistent with itself.

## Technical names

- JSON keys and evidence fields: `snake_case` (`feature_id`, `baseline_p95_ms`).
- Capability, gate and target ids: `kebab-case` (`external-runtime`, `python-smoke`).
- Workflow states: `SCREAMING_SNAKE_CASE` (`READY_FOR_DEVELOPMENT`).
- Python functions and modules: `snake_case`; classes: `PascalCase`.

## Error and output messages

- Script messages in Spanish, with a `[OK]`, `[ERROR]` or `[HOOK_FATAL]` prefix.
- Controlled errors end with exit code `2`; success with `0`.
- Secrets are never printed: samples are redacted (`redacted`,
  `redact_sensitive_text`).

## Commits

- Conventional Commits in English: `type(scope): subject`.
- Common `type`: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`.
- Subject in imperative and lowercase; optional body with bullets.
- One commit per logical unit of change; avoid massive unrelated changes.

## Documentation

- Markdown. Lines <= 100 characters where reasonable.
- One idea per section; prefer brief prose and tables over long paragraphs.
- The generated summaries (`docs/90-generated/`) are not a source of truth.
