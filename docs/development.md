# Guia De Desarrollo Del Template

Esta guia cubre como modificar el template, validar que genera proyectos funcionales y publicar cambios de forma segura.

## Requisitos

- Git
- Python 3.11 o superior
- Bash
- `uv` recomendado para el harness Python
- Node.js y npm para validar el perfil `node`

El template se valida principalmente con `unittest`; los proyectos generados usan los scripts del harness.

## Estructura De Trabajo

Ruta principal en `jarvis`:

```text
/srv/agentic/workspace/agentic-sdd-template        template
```

Los proyectos de prueba deben generarse en directorios temporales o sandboxes
locales. No se conservan como parte estable del workspace.

## Ejecutar Tests Del Template

Desde el repo del template:

```bash
python3 -m unittest discover -s tests -v
```

La suite actual genera proyectos temporales para los tres perfiles y valida que el perfil Node pueda ejecutar `npm test`.

## Crear Un Proyecto Manual

```bash
cat > project.yaml <<'YAML'
project_id: example-project
name: Example Project
output_path: /srv/agentic/workspace/example-project
profile: python
capabilities: [mutation-testing]
YAML

python3 create_project.py --config project.yaml
```

Despues:

```bash
cd /srv/agentic/workspace/example-project
bash scripts/verify_full.sh
python3 scripts/project_status.py
```

## Modificar `core/`

`core/` es ahora la fuente estable del harness dentro del template. Para cambios
de comportamiento:

1. Implementar el cambio en `agentic-sdd-template/core`.
2. Ejecutar tests del template.
3. Generar proyectos temporales si el cambio afecta lifecycle, scripts, specs,
   gates, agentes o state.
4. Completar una feature real en al menos un proyecto generado si el cambio toca
   flujo operativo.

No edites manualmente `data/<project_id>/control` salvo para inspeccion. El estado operativo debe cambiar mediante scripts deterministas.

## Modificar Perfiles

Cada perfil debe cumplir tres reglas:

- El proyecto generado debe tener un primer commit limpio.
- `bash scripts/verify_full.sh` debe poder ejecutarse sin preparacion manual especial.
- Debe existir al menos un smoke test para que los gates tengan una senal real.

Para `node`, si agregas comandos nuevos, actualiza tambien los gates agregados a `state/quality-gates.json`.

## Modificar Capacidades

Una capability debe documentar:

- como se activa
- que archivos o agentes agrega
- que evidencias produce
- si bloquea el lifecycle
- como se valida

Si una capability se activa por feature, verifica que `register_feature.py` acepte el valor y que el control plane lo tenga en cuenta.

## Checklist Antes De Commit

```bash
python3 core/scripts/check_environment.py --profile node
python3 -m unittest discover -s tests -v
git status --short
git diff --check
```

Si se sincronizo `core/`, valida tambien un proyecto generado:

```bash
cd /srv/agentic/workspace/<generated-project>
bash scripts/verify_full.sh
```

## Criterios De Aceptacion Para Cambios Grandes

Un cambio grande del template esta listo cuando:

- La suite del template pasa.
- Al menos un proyecto generado nuevo pasa `verify_full.sh`.
- Los perfiles afectados tienen README actualizado.
- Las capacidades afectadas tienen README actualizado.
- `docs/estado-y-roadmap-harness-agentico.md` o el documento de decision correspondiente refleja el cambio si altera el roadmap o contratos.
- El repo queda limpio antes del commit.

## CI/CD

El ciclo automatizado vive en `.github/workflows/ci-cd.yml` y esta documentado
en `docs/ci-cd.md`.

Resumen:

- PR y push a `main`: preflight, integridad estatica, suite del template y smoke
  de proyectos generados.
- Tags `v*`: los mismos checks y, si pasan, publicacion/actualizacion de GitHub
  Release usando `CHANGELOG.md`.
- No ejecuta Claude Code ni runners Windows reales.

## Convenciones De Documentacion

- Mantener comandos copiables.
- Documentar rutas reales cuando sirven como evidencia.
- Separar estado versionado de estado operativo.
- No esconder limitaciones: si una capability es opcional o parcial, decirlo.
- Preferir ejemplos pequenos que puedan ejecutarse desde un proyecto generado.
