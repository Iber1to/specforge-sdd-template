"""Hermetic tests for the lease invariant in start_implementation (F-009).

Covers AC-001..AC-005 / SCN-001..SCN-005 at two levels:

- Unit tests of ``find_conflicting_implementer_lease`` over temporary lease
  directories (``tmp_path``), importing the ``start_implementation`` module
  via the ``sys.path`` configured by ``tests/harness/conftest.py``.
- E2E tests that run ``scripts/start_implementation.py`` as a subprocess with
  ``DOA_REPO_ROOT`` pointing at a temporary canonical repository and a
  temporary control plane with two queued features (``F-100`` owning the
  foreign lease, ``F-101`` requested).

Hermeticity (NFR-1): Git repositories and control plane in ``tmp_path``, with
no network, no tmux, and without touching the real canonical repository or the
real control plane. Git identity is pinned per repository and the global/system
configuration is isolated (empty ``GIT_CONFIG_GLOBAL``, ``GIT_CONFIG_NOSYSTEM=1``).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from start_implementation import find_conflicting_implementer_lease

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
START_SCRIPT = SCRIPTS / "start_implementation.py"
WORKFLOW_SOURCE = REPO_ROOT / "state" / "workflow.json"

OWNER_ID = "F-100"
OWNER_SLUG = "owner"
OWNER_BRANCH = "feature/F-100-owner"

REQUEST_ID = "F-101"
REQUEST_SLUG = "request"
REQUEST_BRANCH = "feature/F-101-request"


# ---------------------------------------------------------------------------
# Hermetic sandbox infrastructure
# ---------------------------------------------------------------------------


def _git_env(home: Path) -> dict[str, str]:
    """Environment with Git identity/configuration isolated from the host."""

    global_config = home / ".gitconfig-empty"
    global_config.touch()

    env = dict(os.environ)
    env.pop("TELEGRAM_BOT_TOKEN", None)
    env.pop("TELEGRAM_CHAT_ID", None)
    env.update(
        {
            "GIT_CONFIG_GLOBAL": str(global_config),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "F009 Test",
            "GIT_AUTHOR_EMAIL": "f009@example.test",
            "GIT_COMMITTER_NAME": "F009 Test",
            "GIT_COMMITTER_EMAIL": "f009@example.test",
        }
    )
    return env


def _git(repo: Path, *args: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed in {repo}:\n{result.stderr}\n{result.stdout}"
        )
    return result


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _init_canonical_repo(tmp_path: Path, env: dict[str, str]) -> Path:
    """Create a test canonical repository with a base commit on main."""

    canonical = tmp_path / "canonical"
    canonical.mkdir()
    _git(canonical, "init", "-b", "main", env=env)
    _git(canonical, "config", "user.name", "F009 Test", env=env)
    _git(canonical, "config", "user.email", "f009@example.test", env=env)

    _write(canonical / "tool.txt", "base\n")
    _git(canonical, "add", "tool.txt", env=env)
    _git(canonical, "commit", "-m", "base commit", env=env)
    return canonical


def _build_control_plane(
    tmp_path: Path,
    canonical: Path,
    *,
    owner_state: str = "BLOCKED",
    request_state: str = "READY_FOR_DEVELOPMENT",
) -> tuple[Path, Path]:
    """Create project.json/workflow.json in the canonical repo and the control plane.

    The queue contains two features: ``F-100`` (owner of the foreign lease) and
    ``F-101`` (requested). Returns ``(control_root, worktree_root)``.
    """

    control_root = tmp_path / "control"
    for sub in ("leases", "runs", "locks"):
        (control_root / sub).mkdir(parents=True, exist_ok=True)
    worktree_root = tmp_path / "worktrees"
    worktree_root.mkdir(parents=True, exist_ok=True)

    project = {
        "schema_version": 1,
        "project_id": "f009-test",
        "name": "F009 Test",
        "workflow": "spec-driven-development",
        "canonical_repository": str(canonical),
        "worktree_root": str(worktree_root),
        "control_root": str(control_root),
        "artifact_root": str(tmp_path / "artifacts"),
        "maximum_active_implementers": 1,
        "canonical_branch": "main",
        "implementation_branch_prefix": "feature",
        "lease_ttl_minutes": 720,
        "profile": "python",
    }
    _write(canonical / "state" / "project.json", json.dumps(project, indent=2) + "\n")

    workflow_text = WORKFLOW_SOURCE.read_text(encoding="utf-8")
    _write(canonical / "state" / "workflow.json", workflow_text)

    queue = {
        "schema_version": 1,
        "updated_at": "2026-01-01T00:00:00+00:00",
        "features": [
            {
                "id": OWNER_ID,
                "slug": OWNER_SLUG,
                "title": "Owner feature",
                "state": owner_state,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "history": [],
            },
            {
                "id": REQUEST_ID,
                "slug": REQUEST_SLUG,
                "title": "Requested feature",
                "state": request_state,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "history": [],
            },
        ],
    }
    _write(control_root / "queue.json", json.dumps(queue, indent=2) + "\n")

    runtime = {"schema_version": 1, "active_feature": None, "active_runs": []}
    _write(control_root / "runtime.json", json.dumps(runtime, indent=2) + "\n")

    return control_root, worktree_root


def _commit_canonical_state(canonical: Path, env: dict[str, str]) -> None:
    """Commit state/ in the canonical repo so it is clean."""

    _git(canonical, "add", "state", env=env)
    _git(canonical, "commit", "-m", "add harness state", env=env)


def _write_lease(
    control_root: Path,
    feature_id: str,
    role: str,
    *,
    expires_at: str = "2099-01-01T00:00:00+00:00",
    branch: str | None = None,
) -> Path:
    """Write a ``schema_version: 1`` lease with the real schema's fields."""

    lease = {
        "schema_version": 1,
        "feature_id": feature_id,
        "run_id": f"RUN-{feature_id}",
        "agent_id": f"agent-{feature_id}",
        "role": role,
        "branch": branch or f"feature/{feature_id}-x",
        "worktree": str(control_root / "worktrees" / feature_id),
        "acquired_at": "2026-01-01T00:00:00+00:00",
        "heartbeat_at": "2026-01-01T00:00:00+00:00",
        "expires_at": expires_at,
    }
    path = control_root / "leases" / f"{feature_id}.json"
    _write(path, json.dumps(lease, indent=2) + "\n")
    return path


def _run_start(
    canonical: Path,
    env: dict[str, str],
    feature_id: str = REQUEST_ID,
) -> subprocess.CompletedProcess[str]:
    run_env = dict(env)
    run_env["DOA_REPO_ROOT"] = str(canonical)
    return subprocess.run(
        [
            sys.executable,
            str(START_SCRIPT),
            "--feature",
            feature_id,
            "--agent-id",
            "impl-test-r1",
        ],
        cwd=canonical,
        env=run_env,
        text=True,
        capture_output=True,
        check=False,
    )


def _list_dir(path: Path) -> set[str]:
    return {p.name for p in path.iterdir()} if path.exists() else set()


def _control_snapshot(control_root: Path) -> dict[str, object]:
    """Capture queue/runtime bytes and lease/run names."""

    return {
        "queue": (control_root / "queue.json").read_bytes(),
        "runtime": (control_root / "runtime.json").read_bytes(),
        "leases": _list_dir(control_root / "leases"),
        "runs": _list_dir(control_root / "runs"),
    }


OK_PREFIXES = [
    "[OK] Feature:  ",
    "[OK] Run:      ",
    "[OK] Branch:   ",
    "[OK] Worktree: ",
    "[OK] Lease:    ",
]


def _assert_ok_contract(stdout: str) -> None:
    lines = stdout.splitlines()
    ok_lines = [line for line in lines if line.startswith("[OK]")]
    assert len(ok_lines) == 5, f"expected 5 [OK] lines, stdout:\n{stdout}"
    for line, prefix in zip(ok_lines, OK_PREFIXES):
        assert line.startswith(prefix), f"line '{line}' does not use the prefix '{prefix}'"


# ===========================================================================
# Unit tests of find_conflicting_implementer_lease
# ===========================================================================


def _bare_lease(leases_root: Path, feature_id: str, role: str, **extra) -> Path:
    lease = {"schema_version": 1, "role": role, **extra}
    if feature_id is not None:
        lease["feature_id"] = feature_id
    path = leases_root / f"{feature_id or 'F-999'}.json"
    _write(path, json.dumps(lease, indent=2) + "\n")
    return path


def test_detects_foreign_implementer_lease(tmp_path: Path) -> None:
    """U1: foreign implementer lease -> returns the correct (path, lease)."""

    leases = tmp_path / "leases"
    leases.mkdir()
    path = _bare_lease(leases, OWNER_ID, "implementer")

    result = find_conflicting_implementer_lease(leases, REQUEST_ID)

    assert result is not None
    found_path, found_lease = result
    assert found_path == path
    assert found_lease["feature_id"] == OWNER_ID


def test_expired_foreign_lease_still_conflicts(tmp_path: Path) -> None:
    """U2: foreign implementer lease with a past expires_at -> still conflicts."""

    leases = tmp_path / "leases"
    leases.mkdir()
    _bare_lease(
        leases,
        OWNER_ID,
        "implementer",
        expires_at="2000-01-01T00:00:00+00:00",
    )

    result = find_conflicting_implementer_lease(leases, REQUEST_ID)

    assert result is not None
    assert result[1]["feature_id"] == OWNER_ID


def test_qa_lease_does_not_conflict(tmp_path: Path) -> None:
    """U3: sole foreign qa-reviewer lease -> None."""

    leases = tmp_path / "leases"
    leases.mkdir()
    _bare_lease(leases, OWNER_ID, "qa-reviewer")

    assert find_conflicting_implementer_lease(leases, REQUEST_ID) is None


def test_own_lease_is_not_a_conflict(tmp_path: Path) -> None:
    """U4: own implementer lease (same feature_id) -> None."""

    leases = tmp_path / "leases"
    leases.mkdir()
    _bare_lease(leases, REQUEST_ID, "implementer")

    assert find_conflicting_implementer_lease(leases, REQUEST_ID) is None


def test_corrupt_lease_file_is_ignored(tmp_path: Path) -> None:
    """U5: corrupt file next to a valid non-conflicting lease -> None."""

    leases = tmp_path / "leases"
    leases.mkdir()
    _write(leases / "F-050.json", "{ not valid json")
    _bare_lease(leases, REQUEST_ID, "implementer")  # own, no conflict

    assert find_conflicting_implementer_lease(leases, REQUEST_ID) is None


def test_empty_or_missing_leases_dir_returns_none(tmp_path: Path) -> None:
    """U6: empty and nonexistent directory -> None in both cases."""

    empty = tmp_path / "empty"
    empty.mkdir()
    assert find_conflicting_implementer_lease(empty, REQUEST_ID) is None

    missing = tmp_path / "missing"
    assert find_conflicting_implementer_lease(missing, REQUEST_ID) is None


def test_implementer_lease_without_feature_id_conflicts(tmp_path: Path) -> None:
    """U7: implementer lease without a feature_id field -> conflict (conservative)."""

    leases = tmp_path / "leases"
    leases.mkdir()
    lease = {"schema_version": 1, "role": "implementer"}
    _write(leases / "F-100.json", json.dumps(lease, indent=2) + "\n")

    result = find_conflicting_implementer_lease(leases, REQUEST_ID)

    assert result is not None
    assert "feature_id" not in result[1]


# ===========================================================================
# E2E tests of the start_implementation.py script
# ===========================================================================


def test_foreign_lease_blocked_owner_rejects_with_descriptive_error(
    tmp_path: Path,
) -> None:
    """E1 (SCN-001/AC-001): BLOCKED owner with a lease -> exit 2 and descriptive [ERROR]."""

    env = _git_env(tmp_path)
    canonical = _init_canonical_repo(tmp_path, env)
    control_root, _ = _build_control_plane(tmp_path, canonical, owner_state="BLOCKED")
    _commit_canonical_state(canonical, env)

    lease_path = _write_lease(control_root, OWNER_ID, "implementer")

    result = _run_start(canonical, env, REQUEST_ID)

    assert result.returncode == 2
    assert "[ERROR]" in result.stderr
    assert REQUEST_ID in result.stderr
    assert OWNER_ID in result.stderr
    assert str(lease_path) in result.stderr


def test_rejection_leaves_no_effects_fresh_feature(tmp_path: Path) -> None:
    """E2 (SCN-002/AC-002): rejection with no prior worktree -> zero effects."""

    env = _git_env(tmp_path)
    canonical = _init_canonical_repo(tmp_path, env)
    control_root, worktree_root = _build_control_plane(tmp_path, canonical)
    _commit_canonical_state(canonical, env)

    _write_lease(control_root, OWNER_ID, "implementer")

    worktree = worktree_root / f"{REQUEST_ID}-{REQUEST_SLUG}"
    assert not worktree.exists()
    before = _control_snapshot(control_root)

    result = _run_start(canonical, env, REQUEST_ID)

    assert result.returncode == 2
    assert _control_snapshot(control_root) == before
    assert not worktree.exists()

    # The requested feature's branch has not been created.
    branch_check = subprocess.run(
        ["git", "rev-parse", "--verify", REQUEST_BRANCH],
        cwd=canonical,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    assert branch_check.returncode != 0


def test_rejection_leaves_reused_worktree_untouched(tmp_path: Path) -> None:
    """E3 (SCN-002/AC-002): divergent reusable worktree -> head untouched."""

    env = _git_env(tmp_path)
    canonical = _init_canonical_repo(tmp_path, env)
    control_root, worktree_root = _build_control_plane(tmp_path, canonical)
    _commit_canonical_state(canonical, env)

    # F-101 branch with its own commit, via a temporary seed worktree.
    seed = tmp_path / "_seed_request_wt"
    _git(canonical, "worktree", "add", "-b", REQUEST_BRANCH, str(seed), "main", env=env)
    _write(seed / "request.txt", "request work\n")
    _git(seed, "add", "request.txt", env=env)
    _git(seed, "commit", "-m", "request commit", env=env)
    _git(canonical, "worktree", "remove", "--force", str(seed), env=env)

    # main advances to force divergence (resync would require a merge).
    _write(canonical / "tool.txt", "advanced\n")
    _git(canonical, "add", "tool.txt", env=env)
    _git(canonical, "commit", "-m", "advance main", env=env)

    # Existing worktree for the feature.
    worktree = worktree_root / f"{REQUEST_ID}-{REQUEST_SLUG}"
    _git(canonical, "worktree", "add", str(worktree), REQUEST_BRANCH, env=env)
    head_before = _git(worktree, "rev-parse", "HEAD", env=env).stdout.strip()

    _write_lease(control_root, OWNER_ID, "implementer")
    before = _control_snapshot(control_root)

    result = _run_start(canonical, env, REQUEST_ID)

    assert result.returncode == 2
    head_after = _git(worktree, "rev-parse", "HEAD", env=env).stdout.strip()
    assert head_after == head_before
    assert not (worktree / ".git" / "MERGE_HEAD").exists()
    assert _control_snapshot(control_root) == before


def test_expired_foreign_lease_rejects_identically(tmp_path: Path) -> None:
    """E4 (SCN-003/AC-003): expired foreign lease -> exit 2, zero effects."""

    env = _git_env(tmp_path)
    canonical = _init_canonical_repo(tmp_path, env)
    control_root, _ = _build_control_plane(tmp_path, canonical)
    _commit_canonical_state(canonical, env)

    lease_path = _write_lease(
        control_root,
        OWNER_ID,
        "implementer",
        expires_at="2000-01-01T00:00:00+00:00",
    )
    before = _control_snapshot(control_root)

    result = _run_start(canonical, env, REQUEST_ID)

    assert result.returncode == 2
    assert "[ERROR]" in result.stderr
    assert REQUEST_ID in result.stderr
    assert OWNER_ID in result.stderr
    assert str(lease_path) in result.stderr
    assert _control_snapshot(control_root) == before


def test_qa_lease_does_not_block_start(tmp_path: Path) -> None:
    """E5 (SCN-004/AC-004): sole foreign qa-reviewer lease -> successful start."""

    env = _git_env(tmp_path)
    canonical = _init_canonical_repo(tmp_path, env)
    control_root, _ = _build_control_plane(tmp_path, canonical)
    _commit_canonical_state(canonical, env)

    _write_lease(control_root, OWNER_ID, "qa-reviewer")

    result = _run_start(canonical, env, REQUEST_ID)

    assert result.returncode == 0, result.stderr
    _assert_ok_contract(result.stdout)

    assert (control_root / "leases" / f"{REQUEST_ID}.json").exists()
    assert any((control_root / "runs").glob("RUN-*.json"))
    queue = json.loads((control_root / "queue.json").read_text(encoding="utf-8"))
    request = next(f for f in queue["features"] if f["id"] == REQUEST_ID)
    assert request["state"] == "IN_PROGRESS"


def test_success_path_and_own_lease_rejection_preserved(tmp_path: Path) -> None:
    """E6 (SCN-005/AC-005): no leases -> success; rerun with own lease -> exit 2."""

    env = _git_env(tmp_path)
    canonical = _init_canonical_repo(tmp_path, env)
    control_root, _ = _build_control_plane(tmp_path, canonical)
    _commit_canonical_state(canonical, env)

    first = _run_start(canonical, env, REQUEST_ID)

    assert first.returncode == 0, first.stderr
    _assert_ok_contract(first.stdout)
    assert "[INFO] Resync:" not in first.stdout
    assert (control_root / "leases" / f"{REQUEST_ID}.json").exists()
    assert any((control_root / "runs").glob("RUN-*.json"))
    queue = json.loads((control_root / "queue.json").read_text(encoding="utf-8"))
    request = next(f for f in queue["features"] if f["id"] == REQUEST_ID)
    assert request["state"] == "IN_PROGRESS"


def test_own_lease_rejection_preserved(tmp_path: Path) -> None:
    """E6 (SCN-005/AC-005): own lease already present in an eligible state -> exit 2.

    Rejection due to an own lease is evaluated before the foreign-lease guard and
    must preserve the current message ("An active lease already exists"). To exercise
    that branch the own lease is created manually while the feature remains in an
    eligible state (not IN_PROGRESS).
    """

    env = _git_env(tmp_path)
    canonical = _init_canonical_repo(tmp_path, env)
    control_root, _ = _build_control_plane(tmp_path, canonical)
    _commit_canonical_state(canonical, env)

    _write_lease(control_root, REQUEST_ID, "implementer")

    result = _run_start(canonical, env, REQUEST_ID)

    assert result.returncode == 2
    assert "An active lease already exists" in result.stderr
