# Generator

`create_project.py` es el entrypoint determinista del template.

## Uso

```bash
python3 create_project.py --config project.yaml
```

Ejemplo de `project.yaml`:

```yaml
project_id: example-project
name: Example Project
output_path: /srv/agentic/workspace/example-project
profile: python
capabilities: [mutation-testing]
```

## Flujo Interno

1. Lee YAML simple.
2. Valida campos obligatorios.
3. Copia `core/` al `output_path`.
4. Escribe `state/project.json`.
5. Crea `data/<project_id>/control` y `data/<project_id>/artifacts`.
6. Aplica el perfil seleccionado.
7. Inicializa Git en `main`.
8. Crea el commit inicial.

## Limitaciones Del Parser YAML

El parser es intencionadamente pequeno. Soporta:

- `key: value`
- booleanos `true`/`false`
- listas inline como `[mutation-testing]`
- comentarios con `#`

No soporta YAML anidado. Si el template necesita configuracion compleja, debe agregarse con tests antes de ampliar el contrato.

## Contratos

Perfiles soportados:

- `generic`
- `python`
- `node`
- `android`

Capacidades soportadas:

- `documentation-pack` (incluida por defecto)
- `eval-harness`
- `external-runtime`
- `git-publish`
- `mutation-testing`
- `performance-testing`
- `remote-notifications`
- `security-scanning`
- `tool-telemetry`
- `windows-validation`

El generador falla si recibe perfiles o capacidades desconocidos.
