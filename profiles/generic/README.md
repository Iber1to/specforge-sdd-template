# Perfil Generic

Perfil stack-neutral para proyectos que necesitan el harness SDD sin asumir lenguaje o framework principal.

## Incluye

- Core completo del harness.
- `src/` vacio preparado para codigo futuro.
- `tests/unit/test_harness_smoke.py`.
- README minimo del proyecto generado.

## Uso Recomendado

Usalo para:

- repos de documentacion tecnica
- proyectos mixtos
- prototipos donde el stack aun no esta decidido
- productos que quieren adoptar el workflow antes de fijar toolchain

## Validacion

El proyecto generado debe pasar:

```bash
bash scripts/verify_full.sh
```

Como no hay stack propio, los gates validan el harness, schemas, formato Python, tests y estado versionado.
