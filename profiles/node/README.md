# Perfil Node

Perfil para proyectos Node.js ESM con `npm`, `node:test` y gates propios del stack.

## Incluye

- Core completo del harness.
- `package.json` con `type: module`.
- `src/index.js`.
- `tests/index.test.js`.
- Scripts npm:
  - `npm test`
  - `npm run lint`
  - `npm run format:check`
- Gates Node agregados a `state/quality-gates.json`.

## Validacion

```bash
npm test
npm run lint
bash scripts/verify_full.sh
```

## Gates Agregados

El perfil agrega gates bloqueantes:

- `npm test` en `implementation_fast`.
- `npm test` en `qa_full`.
- `npm run lint` en `qa_full`.
- `npm test` en `finalization`.

Esto permite que una feature Node no avance solo porque el harness Python pasa; tambien debe pasar el stack del producto.
