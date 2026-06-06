# Capability: Git Publish

Capacidad opcional para publicar features completadas en Git local o remoto mediante un script determinista y evidencia auditada.

## Por Que Existe

El harness ya integra una feature aprobada en la rama canonica local durante `finalize_feature.py`. Esta capability agrega el paso posterior: registrar o subir esa feature completada al repositorio configurado sin permitir que un agente ejecute `git push` directamente.

## Activacion

En `project.yaml`:

```yaml
capabilities: [git-publish]
git_publish_mode: local
git_publish_remote: origin
git_publish_branch: main
git_publish_auto: false
```

Modos:

- `local`: registra evidencia de que la feature quedo integrada en Git local.
- `dry_run`: ejecuta `git push --dry-run` contra el remote configurado.
- `push`: ejecuta `git push <remote> HEAD:refs/heads/<branch>`.
- `disabled`: desactiva la publicacion.

El modo por defecto al activar la capability es `local`.

## Agente

Agente especializado:

```text
repository-publisher
```

El agente solo puede ejecutar:

```bash
uv run python scripts/publish_feature.py --feature <FEATURE>
```

Role Guard bloquea `git push` directo. El push real, cuando se configura, ocurre dentro del script validado.

## Requisitos

- La feature debe estar en `DONE`.
- El repo canonico debe estar limpio.
- La rama actual debe ser la rama canonica.
- `merged_commit` debe pertenecer al HEAD canonico.
- Por defecto, `merged_commit` debe ser exactamente `HEAD` para evitar publicar commits posteriores no atribuidos a esa feature.
- Para `dry_run` o `push`, el remote configurado debe existir.

## Evidencia

Artefactos:

```text
artifact_root/git-publish/<feature>/<operation>.json
artifact_root/git-publish/<feature>/latest.json
```

La cola de features registra:

```json
{
  "git_publication": {
    "status": "LOCAL_RECORDED",
    "mode": "local",
    "remote": "origin",
    "branch": "main",
    "published_commit": "...",
    "evidence": "..."
  }
}
```

Estados:

- `LOCAL_RECORDED`
- `DRY_RUN`
- `PUBLISHED`
- `DISABLED`

## Seguridad

- No se guardan credenciales en evidencia; URLs con credenciales embebidas se redactan.
- El script falla si hay cambios pendientes.
- El script falla si la feature no esta en `DONE`.
- El script falla si el HEAD contiene commits posteriores y `require_merged_head` esta activo.
