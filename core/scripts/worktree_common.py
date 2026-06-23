#!/usr/bin/env python3
"""Deterministic operations on Git branches and worktrees."""

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

        raise ControlPlaneError(f"Git failed in {repository}: git {' '.join(arguments)}\n{details}")

    return result


def canonical_repository() -> Path:
    config = load_project_config()
    return Path(config["canonical_repository"]).resolve()


def ensure_canonical_repository() -> Path:
    canonical = canonical_repository()

    if repo_root() != canonical:
        raise ControlPlaneError("This operation can only be executed from the canonical repository")

    return canonical


def ensure_clean_repository(repository: Path) -> None:
    result = run_git(repository, "status", "--porcelain")

    if result.stdout.strip():
        raise ControlPlaneError(f"The repository contains pending changes: {repository}")


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
    """Resynchronizes the reused feature branch with the canonical branch.

    Integrates ``canonical_branch`` into ``branch`` via ``git merge --no-edit``
    inside ``worktree``, without rewriting history (DEC-001). It is an
    idempotent no-op when the branch already contains the canonical head
    (FR-3). Faced with a dirty worktree that has a pending integration (FR-4)
    or a merge conflict/failure (FR-5), it raises ``ControlPlaneError``, leaving
    the worktree clean at its previous head, with no writes to the control plane
    (the caller aborts before any persistence).

    Returns ``True`` if a merge was applied and ``False`` if it was a no-op.
    """

    # 1. Ancestry check (idempotent no-op, FR-3).
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
            f"Could not check the ancestry of '{canonical_branch}' in "
            f"'{branch}' for {feature_id}: {details}"
        )

    # 2. Cleanliness precondition (FR-4): only if integration is required.
    status = run_git(worktree, "status", "--porcelain")

    if status.stdout.strip():
        raise ControlPlaneError(
            f"The worktree for {feature_id} contains uncommitted changes and "
            f"requires integrating '{canonical_branch}' into '{branch}': {worktree}. "
            f"Commit or discard the changes before restarting."
        )

    # 3. Capture the previous head (to verify restoration on failure).
    previous_head = run_git(worktree, "rev-parse", "HEAD").stdout.strip()

    # 4. Integration via merge (FR-2, DEC-001): allows fast-forward.
    merge = run_git(
        worktree,
        "merge",
        "--no-edit",
        canonical_branch,
        check=False,
    )

    if merge.returncode != 0:
        cause = merge.stderr.strip() or merge.stdout.strip()

        # 6. Failure (FR-5, DEC-004): abort merge and verify restoration.
        run_git(worktree, "merge", "--abort", check=False)

        restored_status = run_git(worktree, "status", "--porcelain")
        restored_head = run_git(worktree, "rev-parse", "HEAD").stdout.strip()

        if restored_status.stdout.strip() or restored_head != previous_head:
            raise ControlPlaneError(
                f"The integration of '{canonical_branch}' into '{branch}' for "
                f"{feature_id} failed and the worktree could not be restored "
                f"automatically: {worktree}. Manual intervention required. "
                f"Cause: {cause}"
            )

        raise ControlPlaneError(
            f"The integration of '{canonical_branch}' into '{branch}' for "
            f"{feature_id} produced a conflict and was aborted; the worktree was "
            f"left clean at its previous head: {worktree}. Cause: {cause}"
        )

    # 5. Success: ancestry sanity check.
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
            f"After integrating '{canonical_branch}' into '{branch}' for "
            f"{feature_id}, the canonical head was not left as an ancestor: {details}"
        )

    return True


def ensure_implementation_worktree(
    feature: dict[str, Any],
) -> tuple[Path, str, bool, bool]:
    """Creates or recovers the worktree assigned to a feature.

    Returns ``(worktree, branch, created, resynced)`` where ``created``
    indicates whether the worktree was created in this invocation and
    ``resynced`` whether a resynchronization merge with the canonical branch
    was applied.
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
                f"The worktree path exists but is not a Git worktree: {worktree}"
            )

        detected_branch = current_branch(worktree)

        if detected_branch != branch:
            raise ControlPlaneError(
                f"The worktree {worktree} uses branch '{detected_branch}', "
                f"but '{branch}' was expected"
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
            f"The branch required to reprocess {feature['id']} does not exist: {branch}"
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
    """Returns the expected path and branch for a feature."""

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
    """Recovers the existing worktree that QA must review."""

    canonical = ensure_canonical_repository()
    ensure_clean_repository(canonical)

    worktree, branch = implementation_coordinates(feature)

    run_git(canonical, "worktree", "prune")

    if not branch_exists(canonical, branch):
        raise ControlPlaneError(f"The required implementation branch does not exist: {branch}")

    created = False

    if worktree.exists():
        if not worktree.joinpath(".git").exists():
            raise ControlPlaneError(f"The path exists but is not a Git worktree: {worktree}")

        detected_branch = current_branch(worktree)

        if detected_branch != branch:
            raise ControlPlaneError(
                f"The worktree uses '{detected_branch}', but '{branch}' was expected"
            )
    else:
        worktree.parent.mkdir(parents=True, exist_ok=True)
        run_git(canonical, "worktree", "add", str(worktree), branch)
        created = True

    ensure_clean_repository(worktree)

    return worktree, branch, created
