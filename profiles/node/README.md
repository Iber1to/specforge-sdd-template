# Node Profile

Profile for Node.js ESM projects with `npm`, `node:test` and stack-specific gates.
For v1 it uses a simple toolchain: it does not install external dependencies, does not require
a lockfile and validates syntax with `node --check`.

## Includes

- Complete harness core.
- `package.json` with `type: module`.
- `src/index.js`.
- `tests/index.test.js`.
- npm scripts:
  - `npm test`
  - `npm run lint`
- Node gates added to `state/quality-gates.json`.

## Validation

```bash
npm test
npm run lint
bash scripts/verify_full.sh
```

`npm run lint` runs `node --check src/index.js tests/index.test.js`.

## Added Gates

The profile adds blocking gates:

- `npm test` in `implementation_fast`.
- `npm test` in `qa_full`.
- `npm run lint` in `qa_full`.
- `npm test` in `finalization`.

This ensures a Node feature does not advance just because the Python harness passes; the product stack must pass too.
