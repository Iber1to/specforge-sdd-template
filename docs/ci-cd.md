# Ciclo CI/CD

Este documento define el ciclo de integracion y entrega del template
`SpecForge SDD Template`.

El objetivo no es desplegar una aplicacion en servidores. Este repositorio es
un template: la entrega consiste en mantener `main` validado, generar proyectos
reales de prueba y publicar releases versionadas cuando se etiqueta un commit.

## Principios

- `main` debe estar siempre verde.
- Toda PR debe ejecutar la misma validacion determinista que un push a `main`.
- Los tests no dependen de Claude Code, red externa de producto ni runners
  Windows.
- Las capabilities experimentales pueden estar cubiertas offline; la validacion
  real externa vive en runbooks separados.
- La publicacion se hace por tag Git. Para versiones internas, el tag se marca
  como prerelease en GitHub.

## Workflow Automatizado

El workflow vive en:

```text
.github/workflows/ci-cd.yml
```

Se ejecuta en:

- `pull_request`
- `push` a `main`
- `push` de tags `v*`
- `workflow_dispatch`

## Jobs

### Template suite

Valida el propio template.

Pasos:

1. Checkout del repo.
2. Python 3.12.
3. Node 22, necesario para validar el perfil `node`.
4. `uv` fijado a la version usada para validar el template localmente.
5. Identidad Git local para tests que crean commits temporales.
6. Preflight:

```bash
python3 core/scripts/check_environment.py --profile node
```

7. Integridad estatica:

```bash
git diff --check
python3 -m compileall -q create_project.py tests core/scripts capabilities
```

8. Suite determinista:

```bash
python3 -m unittest discover -s tests -v
```

### Generated project smoke

Genera proyectos temporales y ejecuta su verificacion completa.

Matriz:

| Perfil | Capabilities |
|---|---|
| `generic` | `[]` |
| `python` | `[mutation-testing]` |
| `node` | `[]` |

Para cada perfil:

```bash
python3 create_project.py --config "$tmpdir/project.yaml"
cd "$output_path"
python3 scripts/check_environment.py --profile "$profile"
bash scripts/verify_full.sh
```

Esto comprueba que el template no solo pasa sus tests, sino que genera proyectos
operables.

### Publish GitHub release

Solo corre en tags `v*`, y solo despues de que pasen los jobs anteriores.

Acciones:

- crea una GitHub Release si no existe;
- actualiza la Release si ya existe;
- usa `CHANGELOG.md` como notas;
- marca como prerelease si el tag contiene `internal`, `alpha`, `beta` o `rc`.

No necesita secretos propios: usa `GITHUB_TOKEN`.

## Versiones Fijadas

El workflow fija:

| Herramienta | Version |
|---|---|
| Python | `3.12` |
| Node | `22` |
| uv | `0.11.19` |

Tambien define `FORCE_JAVASCRIPT_ACTIONS_TO_NODE24=true` para anticipar la
migracion de GitHub Actions desde Node 20 a Node 24.

## Politica De Ramas

Flujo recomendado:

1. Trabajar en una rama corta.
2. Abrir PR contra `main`.
3. Esperar CI verde.
4. Merge con squash o merge commit, segun politica del repo.
5. Para release, crear tag anotado desde `main`.

Ejemplo:

```bash
git checkout main
git pull --ff-only
git tag -a v1.0.1-internal -m "SpecForge SDD Template v1.0.1-internal"
git push origin main --tags
```

## Protecciones Recomendadas En GitHub

Configura esto manualmente en GitHub si aun no esta activo:

1. `Settings -> Actions -> General`
   - Permitir GitHub Actions.
   - Permitir las acciones usadas por el workflow:
     - `actions/checkout@v4`
     - `actions/setup-python@v5`
     - `actions/setup-node@v4`
     - `astral-sh/setup-uv@v5`
   - Workflow permissions: permitir `Read and write permissions` si quieres que
     el job de release cree/edite GitHub Releases.

2. `Settings -> Branches -> Branch protection rules`
   - Proteger `main`.
   - Require a pull request before merging.
   - Require status checks to pass before merging.
   - Requerir estos checks:
     - `Template suite`
     - `Generated project smoke (generic)`
     - `Generated project smoke (python)`
     - `Generated project smoke (node)`
   - Require branches to be up to date before merging.

3. `Settings -> General`
   - Si el repo debe usarse como plantilla, activar `Template repository`.

4. `Settings -> Tags` o reglas de Rulesets, si estan disponibles en tu plan.
   - Proteger `v*`.
   - Permitir tags de release solo a mantenedores.

## Comandos Locales Equivalentes

Antes de abrir PR:

```bash
python3 core/scripts/check_environment.py --profile node
git diff --check
python3 -m compileall -q create_project.py tests core/scripts capabilities
python3 -m unittest discover -s tests -v
```

Smoke manual de proyecto generado:

```bash
tmpdir="$(mktemp -d)"
cat > "$tmpdir/project.yaml" <<YAML
project_id: ci-python-project
name: CI Python Project
output_path: $tmpdir/ci-python-project
profile: python
capabilities: [mutation-testing]
YAML

python3 create_project.py --config "$tmpdir/project.yaml"
cd "$tmpdir/ci-python-project"
bash scripts/verify_full.sh
```

## Que No Hace El CI

- No ejecuta Claude Code.
- No abre sesiones `tmux`.
- No ejecuta `windows-validation` contra una workstation Windows real.
- No hace push automatico de cambios generados.
- No publica en npm, PyPI ni contenedores.

Estas tareas son deliberadamente manuales o runbook-driven hasta que exista una
necesidad real de entrega externa.

## Diagnostico

Si falla `Template suite`, mira primero:

- version de Python;
- instalacion de `uv`;
- salida de `check_environment.py`;
- errores de `unittest`.

Si falla `Generated project smoke`, el problema suele estar en:

- generador;
- manifest de capability;
- scripts `verify_full.sh`;
- dependencias de perfil, especialmente Node.

Si falla `Publish GitHub release`:

- revisa permisos de `GITHUB_TOKEN`;
- revisa `Settings -> Actions -> Workflow permissions`;
- confirma que el tag empieza por `v`;
- confirma que `CHANGELOG.md` existe en el commit etiquetado.
