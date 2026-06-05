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


def ensure_implementation_worktree(
    feature: dict[str, Any],
) -> tuple[Path, str, bool]:
    """Crea o recupera el worktree asignado a una feature."""

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

        return worktree, branch, False

    if branch_exists(canonical, branch):
        run_git(canonical, "worktree", "add", str(worktree), branch)
        return worktree, branch, True

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

    return worktree, branch, True


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
