#!/usr/bin/env python3
"""Operaciones deterministas sobre ramas y worktrees Git."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from control_common import ControlPlaneError, load_project_config, repo_root


def run_git(
    repository: Path,
    *arguments: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *arguments],
        cwd=repository,
        text=True,
        capture_output=True,
        check=False,
    )

    if check and result.returncode != 0:
        details = result.stderr.strip() or result.stdout.strip()

        raise ControlPlaneError(f"Git falló en {repository}: git {' '.join(arguments)}\n{details}")

    return result


def canonical_repository() -> Path:
    config = load_project_config()
    return Path(config["canonical_repository"]).resolve()


def ensure_canonical_repository() -> Path:
    canonical = canonical_repository()

    if repo_root() != canonical:
        raise ControlPlaneError(
            "Esta operación solo puede ejecutarse desde el repositorio canónico"
        )

    return canonical


def ensure_clean_repository(repository: Path) -> None:
    result = run_git(repository, "status", "--porcelain")

    if result.stdout.strip():
        raise ControlPlaneError(f"El repositorio contiene cambios pendientes: {repository}")


def branch_exists(repository: Path, branch: str) -> bool:
    result = run_git(
        repository,
        "show-ref",
        "--verify",
        "--quiet",
        f"refs/heads/{branch}",
        check=False,
    )

    return result.returncode == 0


def current_branch(repository: Path) -> str:
    result = run_git(repository, "branch", "--show-current")
    return result.stdout.strip()


def resync_branch_with_canonical(
    canonical: Path,
    worktree: Path,
    branch: str,
    canonical_branch: str,
    feature_id: str,
) -> bool:
    """Resincroniza la rama de feature reutilizada con la rama canónica.

    Integra ``canonical_branch`` en ``branch`` mediante ``git merge --no-edit``
    dentro de ``worktree``, sin reescribir la historia (DEC-001). Es un no-op
    idempotente cuando la rama ya contiene el head canónico (FR-3). Ante
    worktree sucio con integración pendiente (FR-4) o conflicto/fallo de merge
    (FR-5) lanza ``ControlPlaneError``, dejando el worktree limpio en su head
    previo, sin escrituras en el plano de control (el caller aborta antes de
    cualquier persistencia).

    Devuelve ``True`` si se aplicó un merge y ``False`` si fue un no-op.
    """

    # 1. Comprobación de ancestría (no-op idempotente, FR-3).
    ancestry = run_git(
        canonical,
        "merge-base",
        "--is-ancestor",
        canonical_branch,
        branch,
        check=False,
    )

    if ancestry.returncode == 0:
        return False

    if ancestry.returncode != 1:
        details = ancestry.stderr.strip() or ancestry.stdout.strip()
        raise ControlPlaneError(
            f"No se pudo comprobar la ancestría de '{canonical_branch}' en "
            f"'{branch}' para {feature_id}: {details}"
        )

    # 2. Precondición de limpieza (FR-4): solo si se requiere integración.
    status = run_git(worktree, "status", "--porcelain")

    if status.stdout.strip():
        raise ControlPlaneError(
            f"El worktree de {feature_id} contiene cambios sin commitear y "
            f"requiere integrar '{canonical_branch}' en '{branch}': {worktree}. "
            f"Commitea o descarta los cambios antes de reiniciar."
        )

    # 3. Captura del head previo (para verificar restauración ante fallo).
    previous_head = run_git(worktree, "rev-parse", "HEAD").stdout.strip()

    # 4. Integración por merge (FR-2, DEC-001): permite fast-forward.
    merge = run_git(
        worktree,
        "merge",
        "--no-edit",
        canonical_branch,
        check=False,
    )

    if merge.returncode != 0:
        cause = merge.stderr.strip() or merge.stdout.strip()

        # 6. Fallo (FR-5, DEC-004): abortar merge y verificar restauración.
        run_git(worktree, "merge", "--abort", check=False)

        restored_status = run_git(worktree, "status", "--porcelain")
        restored_head = run_git(worktree, "rev-parse", "HEAD").stdout.strip()

        if restored_status.stdout.strip() or restored_head != previous_head:
            raise ControlPlaneError(
                f"La integración de '{canonical_branch}' en '{branch}' para "
                f"{feature_id} falló y el worktree no pudo restaurarse "
                f"automáticamente: {worktree}. Requiere intervención manual. "
                f"Causa: {cause}"
            )

        raise ControlPlaneError(
            f"La integración de '{canonical_branch}' en '{branch}' para "
            f"{feature_id} produjo un conflicto y se abortó; el worktree quedó "
            f"limpio en su head previo: {worktree}. Causa: {cause}"
        )

    # 5. Éxito: sanity check de ancestría.
    confirm = run_git(
        canonical,
        "merge-base",
        "--is-ancestor",
        canonical_branch,
        branch,
        check=False,
    )

    if confirm.returncode != 0:
        details = confirm.stderr.strip() or confirm.stdout.strip()
        raise ControlPlaneError(
            f"Tras integrar '{canonical_branch}' en '{branch}' para "
            f"{feature_id}, el head canónico no quedó como ancestro: {details}"
        )

    return True


def ensure_implementation_worktree(
    feature: dict[str, Any],
) -> tuple[Path, str, bool, bool]:
    """Crea o recupera el worktree asignado a una feature.

    Devuelve ``(worktree, branch, created, resynced)`` donde ``created``
    indica si el worktree se creó en esta invocación y ``resynced`` si se
    aplicó un merge de resincronización con la rama canónica.
    """

    config = load_project_config()
    canonical = ensure_canonical_repository()
    ensure_clean_repository(canonical)

    worktree_root = Path(config["worktree_root"]).resolve()
    worktree_root.mkdir(parents=True, exist_ok=True)

    branch_prefix = config.get("implementation_branch_prefix", "feature")
    canonical_branch = config.get("canonical_branch", "main")

    worktree_name = f"{feature['id']}-{feature['slug']}"
    branch = f"{branch_prefix}/{worktree_name}"
    worktree = worktree_root / worktree_name

    run_git(canonical, "worktree", "prune")

    if worktree.exists():
        if not worktree.joinpath(".git").exists():
            raise ControlPlaneError(
                f"La ruta del worktree existe pero no es un worktree Git: {worktree}"
            )

        detected_branch = current_branch(worktree)

        if detected_branch != branch:
            raise ControlPlaneError(
                f"El worktree {worktree} utiliza la rama '{detected_branch}', "
                f"pero se esperaba '{branch}'"
            )

        resynced = resync_branch_with_canonical(
            canonical=canonical,
            worktree=worktree,
            branch=branch,
            canonical_branch=canonical_branch,
            feature_id=feature["id"],
        )

        return worktree, branch, False, resynced

    if branch_exists(canonical, branch):
        run_git(canonical, "worktree", "add", str(worktree), branch)

        resynced = resync_branch_with_canonical(
            canonical=canonical,
            worktree=worktree,
            branch=branch,
            canonical_branch=canonical_branch,
            feature_id=feature["id"],
        )

        return worktree, branch, True, resynced

    if feature["state"] == "CHANGES_REQUESTED":
        raise ControlPlaneError(
            f"La rama requerida para reprocesar {feature['id']} no existe: {branch}"
        )

    run_git(
        canonical,
        "worktree",
        "add",
        "-b",
        branch,
        str(worktree),
        canonical_branch,
    )

    return worktree, branch, True, False


def remove_worktree(worktree: Path) -> None:
    canonical = canonical_repository()

    if not worktree.exists():
        return

    run_git(canonical, "worktree", "remove", "--force", str(worktree))


def implementation_coordinates(
    feature: dict[str, Any],
) -> tuple[Path, str]:
    """Devuelve la ruta y rama esperadas para una feature."""

    config = load_project_config()

    branch_prefix = config.get("implementation_branch_prefix", "feature")
    worktree_root = Path(config["worktree_root"]).resolve()

    name = f"{feature['id']}-{feature['slug']}"

    return (
        worktree_root / name,
        f"{branch_prefix}/{name}",
    )


def ensure_review_worktree(
    feature: dict[str, Any],
) -> tuple[Path, str, bool]:
    """Recupera el worktree existente que debe revisar QA."""

    canonical = ensure_canonical_repository()
    ensure_clean_repository(canonical)

    worktree, branch = implementation_coordinates(feature)

    run_git(canonical, "worktree", "prune")

    if not branch_exists(canonical, branch):
        raise ControlPlaneError(f"No existe la rama de implementación requerida: {branch}")

    created = False

    if worktree.exists():
        if not worktree.joinpath(".git").exists():
            raise ControlPlaneError(f"La ruta existe pero no es un worktree Git: {worktree}")

        detected_branch = current_branch(worktree)

        if detected_branch != branch:
            raise ControlPlaneError(
                f"El worktree utiliza '{detected_branch}', pero se esperaba '{branch}'"
            )
    else:
        worktree.parent.mkdir(parents=True, exist_ok=True)
        run_git(canonical, "worktree", "add", str(worktree), branch)
        created = True

    ensure_clean_repository(worktree)

    return worktree, branch, created
