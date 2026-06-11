"""Tests herméticos del invariante de leases en start_implementation (F-009).

Cubre AC-001..AC-005 / SCN-001..SCN-005 en dos niveles:

- Tests unitarios de ``find_conflicting_implementer_lease`` sobre directorios
  de leases temporales (``tmp_path``), importando el módulo
  ``start_implementation`` vía el ``sys.path`` que configura
  ``tests/harness/conftest.py``.
- Tests E2E que ejecutan ``scripts/start_implementation.py`` por subproceso con
  ``DOA_REPO_ROOT`` apuntando a un repositorio canónico temporal y un plano de
  control temporal con dos features en cola (``F-100`` propietaria del lease
  ajeno, ``F-101`` solicitada).

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
    """Crea project.json/workflow.json en el repo canónico y el plano de control.

    La cola contiene dos features: ``F-100`` (propietaria del lease ajeno) y
    ``F-101`` (solicitada). Devuelve ``(control_root, worktree_root)``.
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
    """Commitea state/ en el repo canónico para que esté limpio."""

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
    """Escribe un lease ``schema_version: 1`` con los campos del esquema real."""

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
    """Captura bytes de queue/runtime y nombres de leases/runs."""

    return {
        "queue": (control_root / "queue.json").read_bytes(),
        "runtime": (control_root / "runtime.json").read_bytes(),
        "leases": _list_dir(control_root / "leases"),
        "runs": _list_dir(control_root / "runs"),
    }


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


# ===========================================================================
# Tests unitarios de find_conflicting_implementer_lease
# ===========================================================================


def _bare_lease(leases_root: Path, feature_id: str, role: str, **extra) -> Path:
    lease = {"schema_version": 1, "role": role, **extra}
    if feature_id is not None:
        lease["feature_id"] = feature_id
    path = leases_root / f"{feature_id or 'F-999'}.json"
    _write(path, json.dumps(lease, indent=2) + "\n")
    return path


def test_detects_foreign_implementer_lease(tmp_path: Path) -> None:
    """U1: lease implementer ajeno → devuelve (path, lease) correctos."""

    leases = tmp_path / "leases"
    leases.mkdir()
    path = _bare_lease(leases, OWNER_ID, "implementer")

    result = find_conflicting_implementer_lease(leases, REQUEST_ID)

    assert result is not None
    found_path, found_lease = result
    assert found_path == path
    assert found_lease["feature_id"] == OWNER_ID


def test_expired_foreign_lease_still_conflicts(tmp_path: Path) -> None:
    """U2: lease implementer ajeno con expires_at pasado → conflicto igual."""

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
    """U3: único lease qa-reviewer ajeno → None."""

    leases = tmp_path / "leases"
    leases.mkdir()
    _bare_lease(leases, OWNER_ID, "qa-reviewer")

    assert find_conflicting_implementer_lease(leases, REQUEST_ID) is None


def test_own_lease_is_not_a_conflict(tmp_path: Path) -> None:
    """U4: lease implementer propio (mismo feature_id) → None."""

    leases = tmp_path / "leases"
    leases.mkdir()
    _bare_lease(leases, REQUEST_ID, "implementer")

    assert find_conflicting_implementer_lease(leases, REQUEST_ID) is None


def test_corrupt_lease_file_is_ignored(tmp_path: Path) -> None:
    """U5: archivo corrupto junto a un lease válido no conflictivo → None."""

    leases = tmp_path / "leases"
    leases.mkdir()
    _write(leases / "F-050.json", "{ not valid json")
    _bare_lease(leases, REQUEST_ID, "implementer")  # propio, no conflicto

    assert find_conflicting_implementer_lease(leases, REQUEST_ID) is None


def test_empty_or_missing_leases_dir_returns_none(tmp_path: Path) -> None:
    """U6: directorio vacío e inexistente → None en ambos casos."""

    empty = tmp_path / "empty"
    empty.mkdir()
    assert find_conflicting_implementer_lease(empty, REQUEST_ID) is None

    missing = tmp_path / "missing"
    assert find_conflicting_implementer_lease(missing, REQUEST_ID) is None


def test_implementer_lease_without_feature_id_conflicts(tmp_path: Path) -> None:
    """U7: lease implementer sin campo feature_id → conflicto (conservador)."""

    leases = tmp_path / "leases"
    leases.mkdir()
    lease = {"schema_version": 1, "role": "implementer"}
    _write(leases / "F-100.json", json.dumps(lease, indent=2) + "\n")

    result = find_conflicting_implementer_lease(leases, REQUEST_ID)

    assert result is not None
    assert "feature_id" not in result[1]


# ===========================================================================
# Tests E2E del script start_implementation.py
# ===========================================================================


def test_foreign_lease_blocked_owner_rejects_with_descriptive_error(
    tmp_path: Path,
) -> None:
    """E1 (SCN-001/AC-001): owner BLOCKED con lease → exit 2 y [ERROR] descriptivo."""

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
    """E2 (SCN-002/AC-002): rechazo sin worktree previo → cero efectos."""

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

    # La rama de la feature solicitada no se ha creado.
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
    """E3 (SCN-002/AC-002): worktree reutilizable divergente → head intacto."""

    env = _git_env(tmp_path)
    canonical = _init_canonical_repo(tmp_path, env)
    control_root, worktree_root = _build_control_plane(tmp_path, canonical)
    _commit_canonical_state(canonical, env)

    # Rama de F-101 con commit propio, mediante un worktree semilla temporal.
    seed = tmp_path / "_seed_request_wt"
    _git(canonical, "worktree", "add", "-b", REQUEST_BRANCH, str(seed), "main", env=env)
    _write(seed / "request.txt", "request work\n")
    _git(seed, "add", "request.txt", env=env)
    _git(seed, "commit", "-m", "request commit", env=env)
    _git(canonical, "worktree", "remove", "--force", str(seed), env=env)

    # main avanza para forzar divergencia (resync requeriría merge).
    _write(canonical / "tool.txt", "advanced\n")
    _git(canonical, "add", "tool.txt", env=env)
    _git(canonical, "commit", "-m", "advance main", env=env)

    # Worktree existente de la feature.
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
    """E4 (SCN-003/AC-003): lease ajeno caducado → exit 2, cero efectos."""

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
    """E5 (SCN-004/AC-004): único lease qa-reviewer ajeno → inicio con éxito."""

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
    """E6 (SCN-005/AC-005): sin leases → éxito; reejecución con lease propio → exit 2."""

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
    """E6 (SCN-005/AC-005): lease propio ya presente en estado elegible → exit 2.

    El rechazo por lease propio se evalúa antes que el guard de lease ajeno y
    debe conservar el mensaje actual ("Ya existe un lease activo"). Para
    ejercitar esa rama el lease propio se crea manualmente mientras la feature
    permanece en un estado elegible (no IN_PROGRESS).
    """

    env = _git_env(tmp_path)
    canonical = _init_canonical_repo(tmp_path, env)
    control_root, _ = _build_control_plane(tmp_path, canonical)
    _commit_canonical_state(canonical, env)

    _write_lease(control_root, REQUEST_ID, "implementer")

    result = _run_start(canonical, env, REQUEST_ID)

    assert result.returncode == 2
    assert "Ya existe un lease activo" in result.stderr
