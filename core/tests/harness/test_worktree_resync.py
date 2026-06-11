"""Tests herméticos de la resincronización de worktrees reutilizados (F-011).

Cubre AC-001..AC-008 / SCN-001..SCN-006 en dos niveles:

- Tests unitarios de ``resync_branch_with_canonical`` sobre repos Git
  temporales (sin plano de control).
- Tests E2E que ejecutan ``scripts/start_implementation.py`` por subproceso con
  ``DOA_REPO_ROOT`` apuntando a un repositorio canónico temporal y un plano de
  control temporal.

Hermeticidad (NFR-1): repositorios Git y plano de control en ``tmp_path``, sin
red, sin tmux, sin tocar el repositorio canónico real ni el plano de control
real. La identidad Git se fija por repositorio y se aísla la configuración
global/sistema (``GIT_CONFIG_GLOBAL`` vacío, ``GIT_CONFIG_NOSYSTEM=1``).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from control_common import ControlPlaneError
from worktree_common import resync_branch_with_canonical

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = REPO_ROOT / "scripts"
START_SCRIPT = SCRIPTS / "start_implementation.py"
WORKFLOW_SOURCE = REPO_ROOT / "state" / "workflow.json"

FEATURE_ID = "F-101"
FEATURE_SLUG = "sample"
FEATURE_BRANCH = "feature/F-101-sample"


# ---------------------------------------------------------------------------
# Infraestructura de sandbox hermético
# ---------------------------------------------------------------------------


def _git_env(home: Path) -> dict[str, str]:
    """Entorno con identidad/configuración Git aislada del host."""

    global_config = home / ".gitconfig-empty"
    global_config.touch()

    env = dict(os.environ)
    env.pop("TELEGRAM_BOT_TOKEN", None)
    env.pop("TELEGRAM_CHAT_ID", None)
    env.update(
        {
            "GIT_CONFIG_GLOBAL": str(global_config),
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "F011 Test",
            "GIT_AUTHOR_EMAIL": "f011@example.test",
            "GIT_COMMITTER_NAME": "F011 Test",
            "GIT_COMMITTER_EMAIL": "f011@example.test",
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
            f"git {' '.join(args)} falló en {repo}:\n{result.stderr}\n{result.stdout}"
        )
    return result


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _init_canonical_repo(tmp_path: Path, env: dict[str, str]) -> Path:
    """Crea un repositorio canónico de prueba con base commit en main."""

    canonical = tmp_path / "canonical"
    canonical.mkdir()
    _git(canonical, "init", "-b", "main", env=env)
    _git(canonical, "config", "user.name", "F011 Test", env=env)
    _git(canonical, "config", "user.email", "f011@example.test", env=env)

    _write(canonical / "tool.txt", "base\n")
    _git(canonical, "add", "tool.txt", env=env)
    _git(canonical, "commit", "-m", "base commit", env=env)
    return canonical


def _make_feature_branch(
    canonical: Path,
    env: dict[str, str],
    *,
    file_name: str = "feature.txt",
    content: str = "feature work\n",
    commit_message: str = "feature commit",
) -> str:
    """Crea la rama de feature con un commit propio mediante un worktree temporal.

    Devuelve el head de la rama de feature.
    """

    tmp_wt = canonical.parent / "_seed_feature_wt"
    _git(canonical, "worktree", "add", "-b", FEATURE_BRANCH, str(tmp_wt), "main", env=env)
    _write(tmp_wt / file_name, content)
    _git(tmp_wt, "add", file_name, env=env)
    _git(tmp_wt, "commit", "-m", commit_message, env=env)
    head = _git(tmp_wt, "rev-parse", "HEAD", env=env).stdout.strip()
    _git(canonical, "worktree", "remove", "--force", str(tmp_wt), env=env)
    return head


def _advance_main(
    canonical: Path,
    env: dict[str, str],
    *,
    file_name: str = "tool.txt",
    content: str = "advanced on main\n",
    commit_message: str = "advance main",
) -> str:
    """Avanza la rama main con un commit directo en el repo canónico.

    ``main`` está checked out en el repo canónico, por lo que se commitea allí
    directamente; el repo queda limpio tras el commit.
    """

    _write(canonical / file_name, content)
    _git(canonical, "add", file_name, env=env)
    _git(canonical, "commit", "-m", commit_message, env=env)
    return _git(canonical, "rev-parse", "HEAD", env=env).stdout.strip()


def _build_control_plane(
    tmp_path: Path,
    canonical: Path,
    *,
    state: str = "READY_FOR_DEVELOPMENT",
) -> tuple[Path, Path]:
    """Crea project.json/workflow.json en el repo canónico y el plano de control.

    Devuelve ``(control_root, worktree_root)``.
    """

    control_root = tmp_path / "control"
    for sub in ("leases", "runs", "locks"):
        (control_root / sub).mkdir(parents=True, exist_ok=True)
    worktree_root = tmp_path / "worktrees"
    worktree_root.mkdir(parents=True, exist_ok=True)

    project = {
        "schema_version": 1,
        "project_id": "f011-test",
        "name": "F011 Test",
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
                "id": FEATURE_ID,
                "slug": FEATURE_SLUG,
                "title": "Sample feature",
                "state": state,
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
                "history": [],
            }
        ],
    }
    _write(control_root / "queue.json", json.dumps(queue, indent=2) + "\n")

    runtime = {"schema_version": 1, "active_feature": None, "active_runs": []}
    _write(control_root / "runtime.json", json.dumps(runtime, indent=2) + "\n")

    return control_root, worktree_root


def _commit_canonical_state(canonical: Path, env: dict[str, str]) -> None:
    """Commitea state/ en el repo canónico para que esté limpio."""

    _git(canonical, "add", "state", env=env)
    _git(canonical, "commit", "-m", "add harness state", env=env)


def _run_start(canonical: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    run_env = dict(env)
    run_env["DOA_REPO_ROOT"] = str(canonical)
    return subprocess.run(
        [
            sys.executable,
            str(START_SCRIPT),
            "--feature",
            FEATURE_ID,
            "--agent-id",
            "impl-test-r1",
        ],
        cwd=canonical,
        env=run_env,
        text=True,
        capture_output=True,
        check=False,
    )


def _add_existing_worktree(
    canonical: Path,
    worktree_root: Path,
    env: dict[str, str],
) -> Path:
    """Crea el worktree de la feature desde su rama existente."""

    worktree = worktree_root / f"{FEATURE_ID}-{FEATURE_SLUG}"
    _git(canonical, "worktree", "add", str(worktree), FEATURE_BRANCH, env=env)
    return worktree


# ---------------------------------------------------------------------------
# Helpers de aserción del contrato de salida
# ---------------------------------------------------------------------------

OK_PREFIXES = [
    "[OK] Feature:  ",
    "[OK] Run:      ",
    "[OK] Rama:     ",
    "[OK] Worktree: ",
    "[OK] Lease:    ",
]


def _assert_ok_contract(stdout: str) -> None:
    lines = stdout.splitlines()
    ok_lines = [line for line in lines if line.startswith("[OK]")]
    assert len(ok_lines) == 5, f"se esperaban 5 líneas [OK], stdout:\n{stdout}"
    for line, prefix in zip(ok_lines, OK_PREFIXES):
        assert line.startswith(prefix), f"línea '{line}' no usa el prefijo '{prefix}'"


def _is_ancestor(repo: Path, ancestor: str, descendant: str, env: dict[str, str]) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repo,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


# ===========================================================================
# Tests unitarios de resync_branch_with_canonical
# ===========================================================================


@pytest.fixture()
def unit_sandbox(tmp_path: Path):
    env = _git_env(tmp_path)
    canonical = _init_canonical_repo(tmp_path, env)
    worktree_root = tmp_path / "worktrees"
    worktree_root.mkdir()
    return canonical, worktree_root, env


def test_resync_noop_when_canonical_is_ancestor(unit_sandbox) -> None:
    """AC-004: rama ya sincronizada es un no-op (acepta worktree sucio, DEC-003)."""

    canonical, worktree_root, env = unit_sandbox
    _make_feature_branch(canonical, env)  # nace de main, contiene su head
    worktree = worktree_root / "wt"
    _git(canonical, "worktree", "add", str(worktree), FEATURE_BRANCH, env=env)

    head_before = _git(worktree, "rev-parse", "HEAD", env=env).stdout.strip()
    # Ensucia el worktree: el no-op no debe exigir limpieza.
    (worktree / "dirty.txt").write_text("dirty\n", encoding="utf-8")

    resynced = resync_branch_with_canonical(
        canonical=canonical,
        worktree=worktree,
        branch=FEATURE_BRANCH,
        canonical_branch="main",
        feature_id=FEATURE_ID,
    )

    assert resynced is False
    head_after = _git(worktree, "rev-parse", "HEAD", env=env).stdout.strip()
    assert head_after == head_before
    assert (worktree / "dirty.txt").exists()


def test_resync_merges_when_divergent(unit_sandbox) -> None:
    """AC-001: divergencia → merge; head canónico ancestro; commit previo alcanzable."""

    canonical, worktree_root, env = unit_sandbox
    feature_head = _make_feature_branch(canonical, env)
    main_head = _advance_main(canonical, env)
    worktree = worktree_root / "wt"
    _git(canonical, "worktree", "add", str(worktree), FEATURE_BRANCH, env=env)

    resynced = resync_branch_with_canonical(
        canonical=canonical,
        worktree=worktree,
        branch=FEATURE_BRANCH,
        canonical_branch="main",
        feature_id=FEATURE_ID,
    )

    assert resynced is True
    assert _is_ancestor(canonical, main_head, FEATURE_BRANCH, env)
    assert _is_ancestor(canonical, feature_head, FEATURE_BRANCH, env)


def test_resync_fast_forward_when_no_feature_commits(unit_sandbox) -> None:
    """Fast-forward: rama sin commits propios → head feature == head canónico."""

    canonical, worktree_root, env = unit_sandbox
    # Rama de feature creada en el head base, sin commits propios.
    base_wt = canonical.parent / "_ff_seed"
    _git(canonical, "worktree", "add", "-b", FEATURE_BRANCH, str(base_wt), "main", env=env)
    _git(canonical, "worktree", "remove", "--force", str(base_wt), env=env)
    main_head = _advance_main(canonical, env)

    worktree = worktree_root / "wt"
    _git(canonical, "worktree", "add", str(worktree), FEATURE_BRANCH, env=env)

    resynced = resync_branch_with_canonical(
        canonical=canonical,
        worktree=worktree,
        branch=FEATURE_BRANCH,
        canonical_branch="main",
        feature_id=FEATURE_ID,
    )

    assert resynced is True
    feature_head = _git(canonical, "rev-parse", FEATURE_BRANCH, env=env).stdout.strip()
    assert feature_head == main_head


def test_resync_dirty_worktree_raises_before_merge(unit_sandbox) -> None:
    """AC-007: worktree sucio con integración requerida → error sin iniciar merge."""

    canonical, worktree_root, env = unit_sandbox
    _make_feature_branch(canonical, env)
    _advance_main(canonical, env)
    worktree = worktree_root / "wt"
    _git(canonical, "worktree", "add", str(worktree), FEATURE_BRANCH, env=env)

    dirty = worktree / "feature.txt"
    dirty.write_text("uncommitted change\n", encoding="utf-8")

    with pytest.raises(ControlPlaneError) as excinfo:
        resync_branch_with_canonical(
            canonical=canonical,
            worktree=worktree,
            branch=FEATURE_BRANCH,
            canonical_branch="main",
            feature_id=FEATURE_ID,
        )

    message = str(excinfo.value)
    assert FEATURE_ID in message
    assert FEATURE_BRANCH in message
    assert "main" in message
    assert not (worktree / ".git" / "MERGE_HEAD").exists()
    assert dirty.read_text(encoding="utf-8") == "uncommitted change\n"


def test_resync_conflict_raises_and_restores(unit_sandbox) -> None:
    """AC-002: conflicto → error, worktree limpio, head previo, sin MERGE_HEAD."""

    canonical, worktree_root, env = unit_sandbox
    # Conflicto garantizado: ambas ramas modifican tool.txt de forma incompatible.
    _make_feature_branch(
        canonical,
        env,
        file_name="tool.txt",
        content="feature side\n",
        commit_message="feature edits tool",
    )
    _advance_main(canonical, env, file_name="tool.txt", content="main side\n")

    worktree = worktree_root / "wt"
    _git(canonical, "worktree", "add", str(worktree), FEATURE_BRANCH, env=env)
    head_before = _git(worktree, "rev-parse", "HEAD", env=env).stdout.strip()

    with pytest.raises(ControlPlaneError) as excinfo:
        resync_branch_with_canonical(
            canonical=canonical,
            worktree=worktree,
            branch=FEATURE_BRANCH,
            canonical_branch="main",
            feature_id=FEATURE_ID,
        )

    message = str(excinfo.value)
    assert FEATURE_ID in message
    assert FEATURE_BRANCH in message

    status = _git(worktree, "status", "--porcelain", env=env).stdout.strip()
    assert status == ""
    assert not (worktree / ".git" / "MERGE_HEAD").exists()
    head_after = _git(worktree, "rev-parse", "HEAD", env=env).stdout.strip()
    assert head_after == head_before


def test_resync_invalid_canonical_ref_raises(unit_sandbox) -> None:
    """Ref canónica inexistente → ControlPlaneError (merge-base ≠ 0/1)."""

    canonical, worktree_root, env = unit_sandbox
    _make_feature_branch(canonical, env)
    worktree = worktree_root / "wt"
    _git(canonical, "worktree", "add", str(worktree), FEATURE_BRANCH, env=env)

    with pytest.raises(ControlPlaneError):
        resync_branch_with_canonical(
            canonical=canonical,
            worktree=worktree,
            branch=FEATURE_BRANCH,
            canonical_branch="nonexistent-branch",
            feature_id=FEATURE_ID,
        )


# ===========================================================================
# Tests E2E del script start_implementation.py
# ===========================================================================


def _list_dir(path: Path) -> set[str]:
    return {p.name for p in path.iterdir()} if path.exists() else set()


def test_reuse_existing_worktree_divergent_merges_and_succeeds(tmp_path: Path) -> None:
    """SCN-001 / AC-001, AC-006: worktree existente divergente → merge + éxito."""

    env = _git_env(tmp_path)
    canonical = _init_canonical_repo(tmp_path, env)
    control_root, worktree_root = _build_control_plane(tmp_path, canonical)
    _commit_canonical_state(canonical, env)

    feature_head = _make_feature_branch(canonical, env)
    main_head = _advance_main(canonical, env)
    _add_existing_worktree(canonical, worktree_root, env)

    result = _run_start(canonical, env)

    assert result.returncode == 0, result.stderr
    _assert_ok_contract(result.stdout)
    assert "[INFO] Resync:" in result.stdout

    assert _is_ancestor(canonical, main_head, FEATURE_BRANCH, env)
    assert _is_ancestor(canonical, feature_head, FEATURE_BRANCH, env)

    assert (control_root / "leases" / f"{FEATURE_ID}.json").exists()
    assert any((control_root / "runs").glob("RUN-*.json"))
    queue = json.loads((control_root / "queue.json").read_text(encoding="utf-8"))
    assert queue["features"][0]["state"] == "IN_PROGRESS"


def test_reuse_branch_without_worktree_recreates_and_merges(tmp_path: Path) -> None:
    """SCN-002 / AC-001: rama existe, worktree no → se recrea y resincroniza."""

    env = _git_env(tmp_path)
    canonical = _init_canonical_repo(tmp_path, env)
    control_root, worktree_root = _build_control_plane(
        tmp_path, canonical, state="CHANGES_REQUESTED"
    )
    _commit_canonical_state(canonical, env)

    feature_head = _make_feature_branch(canonical, env)
    main_head = _advance_main(canonical, env)
    # No se crea el worktree: solo existe la rama.

    worktree = worktree_root / f"{FEATURE_ID}-{FEATURE_SLUG}"
    assert not worktree.exists()

    result = _run_start(canonical, env)

    assert result.returncode == 0, result.stderr
    _assert_ok_contract(result.stdout)
    assert "[INFO] Resync:" in result.stdout
    assert worktree.exists()

    assert _is_ancestor(canonical, main_head, FEATURE_BRANCH, env)
    assert _is_ancestor(canonical, feature_head, FEATURE_BRANCH, env)
    queue = json.loads((control_root / "queue.json").read_text(encoding="utf-8"))
    assert queue["features"][0]["state"] == "IN_PROGRESS"


def test_merge_conflict_aborts_clean_with_exit_2(tmp_path: Path) -> None:
    """SCN-003 / AC-002, AC-003: conflicto → exit 2, limpio, sin escrituras."""

    env = _git_env(tmp_path)
    canonical = _init_canonical_repo(tmp_path, env)
    control_root, worktree_root = _build_control_plane(tmp_path, canonical)
    _commit_canonical_state(canonical, env)

    _make_feature_branch(
        canonical,
        env,
        file_name="tool.txt",
        content="feature side\n",
        commit_message="feature edits tool",
    )
    _advance_main(canonical, env, file_name="tool.txt", content="main side\n")
    worktree = _add_existing_worktree(canonical, worktree_root, env)
    head_before = _git(worktree, "rev-parse", "HEAD", env=env).stdout.strip()

    queue_before = (control_root / "queue.json").read_bytes()
    leases_before = _list_dir(control_root / "leases")
    runs_before = _list_dir(control_root / "runs")

    result = _run_start(canonical, env)

    assert result.returncode == 2
    assert "[ERROR]" in result.stderr
    assert FEATURE_ID in result.stderr
    assert FEATURE_BRANCH in result.stderr
    assert "main" in result.stderr

    status = _git(worktree, "status", "--porcelain", env=env).stdout.strip()
    assert status == ""
    assert not (worktree / ".git" / "MERGE_HEAD").exists()
    head_after = _git(worktree, "rev-parse", "HEAD", env=env).stdout.strip()
    assert head_after == head_before

    # AC-003: cero escrituras de control.
    assert _list_dir(control_root / "leases") == leases_before
    assert _list_dir(control_root / "runs") == runs_before
    assert (control_root / "queue.json").read_bytes() == queue_before


def test_already_synced_reuse_is_noop(tmp_path: Path) -> None:
    """SCN-004 / AC-004, AC-006: ya sincronizada → no-op, sin línea Resync."""

    env = _git_env(tmp_path)
    canonical = _init_canonical_repo(tmp_path, env)
    control_root, worktree_root = _build_control_plane(tmp_path, canonical)
    _commit_canonical_state(canonical, env)

    # Rama de feature nacida tras commitear state: contiene el head de main.
    _make_feature_branch(canonical, env)
    _add_existing_worktree(canonical, worktree_root, env)
    head_before = _git(canonical, "rev-parse", FEATURE_BRANCH, env=env).stdout.strip()

    result = _run_start(canonical, env)

    assert result.returncode == 0, result.stderr
    _assert_ok_contract(result.stdout)
    assert "[INFO] Resync:" not in result.stdout

    head_after = _git(canonical, "rev-parse", FEATURE_BRANCH, env=env).stdout.strip()
    assert head_after == head_before

    assert (control_root / "leases" / f"{FEATURE_ID}.json").exists()
    assert any((control_root / "runs").glob("RUN-*.json"))
    queue = json.loads((control_root / "queue.json").read_text(encoding="utf-8"))
    assert queue["features"][0]["state"] == "IN_PROGRESS"


def test_fresh_creation_unchanged(tmp_path: Path) -> None:
    """SCN-005 / AC-005, AC-006: rama inexistente → creación desde main, sin merge."""

    env = _git_env(tmp_path)
    canonical = _init_canonical_repo(tmp_path, env)
    control_root, worktree_root = _build_control_plane(tmp_path, canonical)
    _commit_canonical_state(canonical, env)

    main_head = _git(canonical, "rev-parse", "main", env=env).stdout.strip()

    result = _run_start(canonical, env)

    assert result.returncode == 0, result.stderr
    _assert_ok_contract(result.stdout)
    assert "[INFO] Resync:" not in result.stdout

    feature_head = _git(canonical, "rev-parse", FEATURE_BRANCH, env=env).stdout.strip()
    assert feature_head == main_head
    queue = json.loads((control_root / "queue.json").read_text(encoding="utf-8"))
    assert queue["features"][0]["state"] == "IN_PROGRESS"


def test_dirty_worktree_with_required_integration_aborts(tmp_path: Path) -> None:
    """SCN-006 / AC-007: divergencia + worktree sucio → exit 2 sin merge ni control."""

    env = _git_env(tmp_path)
    canonical = _init_canonical_repo(tmp_path, env)
    control_root, worktree_root = _build_control_plane(tmp_path, canonical)
    _commit_canonical_state(canonical, env)

    _make_feature_branch(canonical, env)
    _advance_main(canonical, env)
    worktree = _add_existing_worktree(canonical, worktree_root, env)

    dirty = worktree / "feature.txt"
    dirty.write_text("local uncommitted edit\n", encoding="utf-8")

    queue_before = (control_root / "queue.json").read_bytes()
    leases_before = _list_dir(control_root / "leases")
    runs_before = _list_dir(control_root / "runs")

    result = _run_start(canonical, env)

    assert result.returncode == 2
    assert "[ERROR]" in result.stderr
    assert FEATURE_ID in result.stderr

    assert dirty.read_text(encoding="utf-8") == "local uncommitted edit\n"
    assert not (worktree / ".git" / "MERGE_HEAD").exists()

    assert _list_dir(control_root / "leases") == leases_before
    assert _list_dir(control_root / "runs") == runs_before
    assert (control_root / "queue.json").read_bytes() == queue_before
