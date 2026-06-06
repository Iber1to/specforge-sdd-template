# Perfil Python

Perfil para proyectos Python con layout `src/`, tests y gates del harness.

## Incluye

- Core completo del harness.
- Paquete Python bajo `src/<project_name>/`.
- `tests/unit/test_profile_smoke.py`.
- `tests/unit/test_harness_smoke.py`.
- `pyproject.toml` y `uv.lock` heredados del core.

## Toolchain

- Python 3.11+
- `pytest`
- `ruff`
- `compileall`
- `uv` recomendado, con fallback a `.venv/bin` en scripts de verificacion.

## Validacion

```bash
bash scripts/verify_fast.sh
bash scripts/verify_full.sh
```

## Mutation Testing

Este perfil es el objetivo inicial de `mutation-testing`.

Ejemplo:

```bash
python3 scripts/mutation_runner.py \
  --feature F-001 \
  --output /srv/agentic/workspace/data/<project_id>/artifacts/mutation-tests/F-001/latest.json \
  --test-command python3 -m pytest -q
```

El runner aplica mutantes Python, ejecuta tests y restaura los archivos modificados.
