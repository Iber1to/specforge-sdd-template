#!/usr/bin/env python3
"""Integra una feature aprobada y realiza la transición exclusiva a DONE."""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from control_common import (
    ControlPlaneError,
    control_paths,
    find_feature,
    load_json,
    load_project_config,
    load_queue,
    load_runtime,
    queue_lock,
    save_queue,
    save_runtime,
    utc_now,
)
from documentation_validation import (
    DocumentationValidationError,
    validate_documentation_requirements,
)
from feature_metrics_snapshot import (
    refresh_feature_metrics_snapshot,
    snapshot_path,
)
from lifecycle_common import apply_lifecycle_transition
from quality_gates import QualityGateError, run_quality_gates
from review_validation import (
    ReviewValidationError,
    validate_review_evidence,
)
from windows_validation import (
    WindowsEvidenceValidationError,
    validate_windows_evidence,
)
from worktree_common import (
    branch_exists,
    current_branch,
    ensure_clean_repository,
    ensure_review_worktree,
    remove_worktree,
    run_git,
)


class FinalizationError(ControlPlaneError):
    """Error controlado durante la finalización."""


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--feature", required=True)
    parser.add_argument(
        "--reason",
        default="Feature validada, integrada y finalizada",
    )

    return parser.parse_args()


def create_operation_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"FINALIZE-{timestamp}-{uuid.uuid4().hex[:8]}"


def git_head(repository: Path) -> str:
    return run_git(repository, "rev-parse", "HEAD").stdout.strip()


def is_ancestor(
    repository: Path,
    ancestor: str,
    descendant: str,
) -> bool:
    result = run_git(
        repository,
        "merge-base",
        "--is-ancestor",
        ancestor,
        descendant,
        check=False,
    )

    return result.returncode == 0


def commits_between(
    repository: Path,
    ancestor: str,
    descendant: str,
) -> int:
    result = run_git(
        repository,
        "rev-list",
        "--count",
        f"{ancestor}..{descendant}",
    )

    return int(result.stdout.strip())


def merge_base(
    repository: Path,
    left: str,
    right: str,
) -> str:
    result = run_git(
        repository,
        "merge-base",
        left,
        right,
    )

    return result.stdout.strip()


def changed_files(
    repository: Path,
    ancestor: str,
    descendant: str,
) -> list[str]:
    result = run_git(
        repository,
        "diff",
        "--name-only",
        ancestor,
        descendant,
    )

    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def validate_qa_chain(
    *,
    worktree: Path,
    feature: dict[str, Any],
    paths: dict[str, Path],
) -> tuple[dict[str, Any], dict[str, Any], str]:
    review = validate_review_evidence(
        worktree,
        feature,
        expected_verdict="APPROVED",
    )

    branch_head = git_head(worktree)
    reviewed_commit = review["reviewed_commit"]

    if not is_ancestor(worktree, reviewed_commit, branch_head):
        raise FinalizationError("El commit revisado por QA no pertenece a la rama actual")

    additional_commits = commits_between(
        worktree,
        reviewed_commit,
        branch_head,
    )

    if additional_commits != 1:
        raise FinalizationError(
            "Después del commit revisado debe existir exactamente "
            "un commit de evidencia QA; "
            f"se detectaron {additional_commits}"
        )

    expected_review_path = f"evidence/reviews/{feature['id']}.json"
    modifications = changed_files(
        worktree,
        reviewed_commit,
        branch_head,
    )

    if modifications != [expected_review_path]:
        raise FinalizationError(
            "La rama contiene cambios posteriores no revisados por QA: " + ", ".join(modifications)
        )

    run_path = paths["runs"] / f"{review['run_id']}.json"
    qa_run = load_json(run_path)

    required_run_values = {
        "feature_id": feature["id"],
        "role": "qa-reviewer",
        "status": "COMPLETED",
        "verdict": "APPROVED",
        "reviewed_commit": reviewed_commit,
        "evidence_commit": branch_head,
    }

    for key, expected in required_run_values.items():
        received = qa_run.get(key)

        if received != expected:
            raise FinalizationError(
                f"El run QA contiene {key}={received!r}; se esperaba {expected!r}"
            )

    return review, qa_run, branch_head


def run_full_verification(
    *,
    repository: Path,
    artifact_root: Path,
    feature_id: str,
    operation_id: str,
    phase: str,
) -> Path:
    try:
        quality_gates = run_quality_gates(
            repo_root=repository,
            artifact_root=artifact_root,
            feature_id=feature_id,
            run_id=operation_id,
            phase="finalization",
        )
    except QualityGateError as exc:
        raise FinalizationError(f"La verificación completa falló durante {phase!r}: {exc}") from exc

    gate_logs = [Path(gate["log"]) for gate in quality_gates["gates"]]
    return gate_logs[0] if gate_logs else Path(quality_gates["evidence"])


def merge_in_progress(repository: Path) -> bool:
    result = run_git(
        repository,
        "rev-parse",
        "--verify",
        "--quiet",
        "MERGE_HEAD",
        check=False,
    )

    return result.returncode == 0


def abort_merge(repository: Path) -> None:
    if merge_in_progress(repository):
        run_git(repository, "merge", "--abort", check=False)


def find_existing_merge_commit(
    repository: Path,
    canonical_branch: str,
    branch_head: str,
) -> str | None:
    commits = run_git(
        repository,
        "rev-list",
        "--first-parent",
        canonical_branch,
    ).stdout.splitlines()

    for commit in commits:
        parents = (
            run_git(
                repository,
                "show",
                "-s",
                "--format=%P",
                commit,
            )
            .stdout.strip()
            .split()
        )

        if branch_head in parents[1:]:
            return commit

    return None


def merge_feature(
    *,
    canonical: Path,
    branch: str,
    branch_head: str,
    canonical_branch: str,
    artifact_root: Path,
    feature_id: str,
    operation_id: str,
) -> tuple[str, Path]:
    if is_ancestor(canonical, branch_head, canonical_branch):
        merge_commit = (
            find_existing_merge_commit(
                canonical,
                canonical_branch,
                branch_head,
            )
            or branch_head
        )

        log_path = run_full_verification(
            repository=canonical,
            artifact_root=artifact_root,
            feature_id=feature_id,
            operation_id=operation_id,
            phase="already-integrated",
        )

        return merge_commit, log_path

    result = run_git(
        canonical,
        "merge",
        "--no-ff",
        "--no-commit",
        branch,
        check=False,
    )

    if result.returncode != 0:
        abort_merge(canonical)

        details = result.stderr.strip() or result.stdout.strip()

        raise FinalizationError("No se pudo preparar el merge sin conflictos:\n" + details)

    try:
        cached_check = run_git(
            canonical,
            "diff",
            "--cached",
            "--check",
            check=False,
        )

        if cached_check.returncode != 0:
            raise FinalizationError(
                "El merge preparado contiene errores de formato:\n" + cached_check.stdout.strip()
            )

        log_path = run_full_verification(
            repository=canonical,
            artifact_root=artifact_root,
            feature_id=feature_id,
            operation_id=operation_id,
            phase="merge-candidate",
        )

        run_git(
            canonical,
            "commit",
            "-m",
            f"merge({feature_id}): integrate approved feature",
        )

        return git_head(canonical), log_path

    except Exception:
        abort_merge(canonical)
        raise


def cleanup_feature_worktree(
    *,
    canonical: Path,
    worktree: Path,
    branch: str,
) -> list[str]:
    warnings: list[str] = []

    try:
        remove_worktree(worktree)
    except ControlPlaneError as exc:
        warnings.append(f"No se pudo eliminar el worktree: {exc}")

    try:
        if branch_exists(canonical, branch):
            run_git(canonical, "branch", "-d", branch)
    except ControlPlaneError as exc:
        warnings.append(f"No se pudo eliminar la rama: {exc}")

    return warnings


def main() -> int:
    arguments = parse_arguments()
    operation_id = create_operation_id()
    metrics_snapshot_file: Path | None = None
    metrics_snapshot_warning: str | None = None

    try:
        config = load_project_config()
        canonical = Path(config["canonical_repository"]).resolve()
        canonical_branch = config.get("canonical_branch", "main")
        artifact_root = Path(config["artifact_root"]).resolve()
        paths = control_paths()

        if Path.cwd().resolve() != canonical:
            raise FinalizationError("La finalización debe ejecutarse desde el repositorio canónico")

        ensure_clean_repository(canonical)

        if current_branch(canonical) != canonical_branch:
            raise FinalizationError(f"El repositorio canónico debe estar en {canonical_branch}")

        with queue_lock(exclusive=False):
            queue = load_queue()
            feature = find_feature(queue, arguments.feature)

            if feature["state"] == "DONE":
                print(f"[OK] {feature['id']} ya está finalizada.")
                print(f"[OK] Commit integrado: {feature.get('merged_commit', 'desconocido')}")
                return 0

            if feature["state"] != "APPROVED":
                raise FinalizationError(
                    f"{feature['id']} no puede finalizarse desde {feature['state']}"
                )

            lease_path = paths["leases"] / f"{feature['id']}.json"

            if lease_path.exists():
                raise FinalizationError(
                    f"Existe un lease activo para {feature['id']}: {lease_path}"
                )

        worktree, branch, _ = ensure_review_worktree(feature)
        ensure_clean_repository(worktree)

        review, _, branch_head = validate_qa_chain(
            worktree=worktree,
            feature=feature,
            paths=paths,
        )

        reviewed_commit = review["reviewed_commit"]

        documentation_base = merge_base(
            worktree,
            canonical_branch,
            reviewed_commit,
        )
        documentation_changes = changed_files(
            worktree,
            documentation_base,
            reviewed_commit,
        )
        validate_documentation_requirements(
            worktree,
            feature,
            changed_files=documentation_changes,
        )

        branch_log = run_full_verification(
            repository=worktree,
            artifact_root=artifact_root,
            feature_id=feature["id"],
            operation_id=operation_id,
            phase="approved-branch",
        )

        windows_evidence_path: str | None = None

        if feature.get("windows_validation_required", False):
            windows_evidence = validate_windows_evidence(
                repo_root=worktree,
                artifact_root=artifact_root,
                feature=feature,
                expected_commit=reviewed_commit,
            )

            windows_evidence_path = str(
                artifact_root / "windows-tests" / feature["id"] / "latest.json"
            )

            if windows_evidence["status"] != "PASS":
                raise FinalizationError("La evidencia Windows no tiene estado PASS")

        with queue_lock():
            queue = load_queue()
            runtime = load_runtime()
            feature = find_feature(queue, arguments.feature)

            if feature["state"] != "APPROVED":
                raise FinalizationError(
                    f"El estado cambió durante la finalización: {feature['state']}"
                )

            lease_path = paths["leases"] / f"{feature['id']}.json"

            if lease_path.exists():
                raise FinalizationError("Se creó un lease durante la finalización")

            ensure_clean_repository(canonical)
            ensure_clean_repository(worktree)

            if git_head(worktree) != branch_head:
                raise FinalizationError("La rama cambió durante la finalización")

            merge_commit, merge_log = merge_feature(
                canonical=canonical,
                branch=branch,
                branch_head=branch_head,
                canonical_branch=canonical_branch,
                artifact_root=artifact_root,
                feature_id=feature["id"],
                operation_id=operation_id,
            )

            timestamp = utc_now()

            feature["state"] = "DONE"
            feature["updated_at"] = timestamp
            feature["completed_at"] = timestamp
            feature["reviewed_commit"] = reviewed_commit
            feature["feature_branch_head"] = branch_head
            feature["merged_commit"] = merge_commit
            feature["windows_evidence"] = windows_evidence_path
            feature.setdefault("history", []).append(
                {
                    "timestamp": timestamp,
                    "action": "FINALIZED",
                    "actor_role": "finalizer",
                    "from": "APPROVED",
                    "to": "DONE",
                    "reason": arguments.reason,
                    "merged_commit": merge_commit,
                }
            )

            apply_lifecycle_transition(
                project=config,
                queue=queue,
                runtime=runtime,
                target_phase="ACTIVE_DEVELOPMENT",
                actor="finalizer",
                reason=f"Primera feature finalizada: {feature['id']}",
            )

            runtime["last_completed_run"] = operation_id

            save_queue(queue)
            save_runtime(runtime)

            try:
                control_root = Path(config["control_root"]).resolve()

                refresh_feature_metrics_snapshot(
                    control_root=control_root,
                    queue=queue,
                )

                metrics_snapshot_file = snapshot_path(control_root)

            except Exception as exc:
                metrics_snapshot_warning = str(exc)

        warnings = cleanup_feature_worktree(
            canonical=canonical,
            worktree=worktree,
            branch=branch,
        )

        print(f"[OK] Feature:             {feature['id']}")
        print("[OK] Estado:              DONE")
        print(f"[OK] Commit revisado:     {reviewed_commit}")
        print(f"[OK] Head de feature:     {branch_head}")
        print(f"[OK] Commit integrado:    {merge_commit}")
        print(f"[OK] Log rama aprobada:   {branch_log}")
        print(f"[OK] Log integración:     {merge_log}")

        if metrics_snapshot_file is not None:
            print(f"[OK] Snapshot métricas:    {metrics_snapshot_file}")

        if metrics_snapshot_warning is not None:
            print(
                "[WARN] No se pudo regenerar el snapshot de métricas: " + metrics_snapshot_warning,
                file=sys.stderr,
            )

        for warning in warnings:
            print(f"[WARN] {warning}", file=sys.stderr)

        return 0

    except (
        ControlPlaneError,
        FinalizationError,
        DocumentationValidationError,
        ReviewValidationError,
        WindowsEvidenceValidationError,
    ) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
