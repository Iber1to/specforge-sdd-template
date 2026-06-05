#!/usr/bin/env python3
"""Completa una revisión QA y aplica su veredicto."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from control_common import (
    ControlPlaneError,
    apply_transition,
    atomic_write_json,
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
from quality_gates import run_quality_gates
from review_validation import ReviewValidationError, validate_review_evidence
from run_metrics import finalize_run_metrics
from worktree_common import ensure_clean_repository, run_git


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--feature", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument(
        "--verdict",
        required=True,
        choices=["APPROVED", "CHANGES_REQUESTED"],
    )
    parser.add_argument("--summary", required=True)
    parser.add_argument(
        "--required-change",
        action="append",
        default=[],
    )

    return parser.parse_args()


def current_worktree() -> Path:
    result = run_git(Path.cwd(), "rev-parse", "--show-toplevel")
    return Path(result.stdout.strip()).resolve()


def git_head(worktree: Path) -> str:
    return run_git(worktree, "rev-parse", "HEAD").stdout.strip()


def validate_arguments(arguments: argparse.Namespace) -> None:
    if len(arguments.summary.strip()) < 10:
        raise ControlPlaneError("El resumen QA debe contener al menos 10 caracteres")

    if arguments.verdict == "APPROVED" and arguments.required_change:
        raise ControlPlaneError("Un informe APPROVED no puede contener cambios requeridos")

    if arguments.verdict == "CHANGES_REQUESTED" and not arguments.required_change:
        raise ControlPlaneError("CHANGES_REQUESTED requiere al menos un --required-change")


def run_full_verification(
    worktree: Path,
    artifact_root: Path,
    feature_id: str,
    run_id: str,
) -> tuple[subprocess.CompletedProcess[str], Path, str, dict]:
    quality_gates = run_quality_gates(
        repo_root=worktree,
        artifact_root=artifact_root,
        feature_id=feature_id,
        run_id=run_id,
        phase="qa_full",
        raise_on_blocking=False,
    )

    gate_logs = [Path(gate["log"]) for gate in quality_gates["gates"]]
    log_path = gate_logs[0] if gate_logs else Path(quality_gates["evidence"])
    exit_code = 0 if quality_gates["status"] in {"PASS", "WARN"} else 1

    result = subprocess.CompletedProcess(
        args=["quality-gates", "qa_full"],
        returncode=exit_code,
        stdout="",
        stderr="",
    )

    return result, log_path, "quality-gates:qa_full", quality_gates


def create_and_commit_review(
    worktree: Path,
    feature: dict,
    lease: dict,
    verdict: str,
    summary: str,
    required_changes: list[str],
    verification_result: subprocess.CompletedProcess[str],
    verification_log: Path,
    verification_command: str,
) -> tuple[Path, str]:
    review_path = worktree / "evidence" / "reviews" / f"{feature['id']}.json"

    review = {
        "schema_version": 1,
        "feature_id": feature["id"],
        "run_id": lease["run_id"],
        "reviewer_id": lease["agent_id"],
        "verdict": verdict,
        "reviewed_commit": lease["reviewed_commit"],
        "verification": {
            "command": verification_command,
            "exit_code": verification_result.returncode,
            "log": str(verification_log),
        },
        "summary": summary.strip(),
        "required_changes": required_changes,
        "created_at": utc_now(),
    }

    atomic_write_json(review_path, review)

    validate_review_evidence(
        worktree,
        feature,
        expected_verdict=verdict,
    )

    relative_path = review_path.relative_to(worktree)

    run_git(worktree, "add", str(relative_path))
    run_git(
        worktree,
        "commit",
        "-m",
        f"chore({feature['id']}): record QA verdict {verdict}",
    )

    ensure_clean_repository(worktree)

    return review_path, git_head(worktree)


def main() -> int:
    arguments = parse_arguments()

    try:
        validate_arguments(arguments)

        worktree = current_worktree()
        config = load_project_config()
        paths = control_paths()
        lease_path = paths["leases"] / f"{arguments.feature}.json"

        with queue_lock(exclusive=False):
            queue = load_queue()
            feature = find_feature(queue, arguments.feature)

            if feature["state"] != "READY_FOR_QA":
                raise ControlPlaneError(f"{feature['id']} no está en READY_FOR_QA")

            lease = load_json(lease_path)

            if lease.get("role") != "qa-reviewer":
                raise ControlPlaneError("El lease activo no pertenece a QA")

            if lease.get("agent_id") != arguments.agent_id:
                raise ControlPlaneError(
                    f"El lease pertenece a {lease.get('agent_id')}, no a {arguments.agent_id}"
                )

            if Path(lease["worktree"]).resolve() != worktree:
                raise ControlPlaneError("La revisión debe completarse desde el worktree asignado")

        ensure_clean_repository(worktree)

        if git_head(worktree) != lease["reviewed_commit"]:
            raise ControlPlaneError("El commit del worktree cambió desde el inicio de la revisión")

        result, log_path, command, quality_gates = run_full_verification(
            worktree=worktree,
            artifact_root=Path(config["artifact_root"]).resolve(),
            feature_id=feature["id"],
            run_id=lease["run_id"],
        )

        ensure_clean_repository(worktree)

        if git_head(worktree) != lease["reviewed_commit"]:
            raise ControlPlaneError("La verificación modificó el commit revisado")

        if arguments.verdict == "APPROVED" and result.returncode != 0:
            raise ControlPlaneError(
                f"No puede emitirse APPROVED con la suite completa fallida. Revisa: {log_path}"
            )

        review_path, evidence_commit = create_and_commit_review(
            worktree=worktree,
            feature=feature,
            lease=lease,
            verdict=arguments.verdict,
            summary=arguments.summary,
            required_changes=arguments.required_change,
            verification_result=result,
            verification_log=log_path,
            verification_command=command,
        )

        with queue_lock():
            queue = load_queue()
            runtime = load_runtime()
            feature = find_feature(queue, arguments.feature)
            current_lease = load_json(lease_path)

            if current_lease.get("run_id") != lease["run_id"]:
                raise ControlPlaneError("El lease cambió durante la revisión")

            apply_transition(
                queue=queue,
                runtime=runtime,
                feature=feature,
                target_state=arguments.verdict,
                role="qa-reviewer",
                reason=arguments.summary.strip(),
            )

            run_path = paths["runs"] / f"{lease['run_id']}.json"
            run = load_json(run_path)

            completion_timestamp = utc_now()

            run["status"] = "COMPLETED"
            run["verdict"] = arguments.verdict
            run["verification_exit_code"] = result.returncode
            run["verification_log"] = str(log_path)
            run["quality_gates"] = {
                "status": quality_gates["status"],
                "phase": quality_gates["phase"],
                "evidence": quality_gates["evidence"],
            }
            run["review_evidence"] = str(review_path)
            run["evidence_commit"] = evidence_commit
            run["updated_at"] = completion_timestamp
            run["completed_at"] = completion_timestamp

            finalize_run_metrics(
                run,
                result=arguments.verdict,
                completed_at=completion_timestamp,
            )

            runtime["active_runs"] = [
                run_id for run_id in runtime.get("active_runs", []) if run_id != lease["run_id"]
            ]
            runtime["last_completed_run"] = lease["run_id"]

            save_queue(queue)
            save_runtime(runtime)
            atomic_write_json(run_path, run)

            lease_path.unlink()

        print(f"[OK] Feature:          {feature['id']}")
        print(f"[OK] Veredicto:        {arguments.verdict}")
        print(f"[OK] Commit revisado:  {lease['reviewed_commit']}")
        print(f"[OK] Commit evidencia: {evidence_commit}")
        print(f"[OK] Evidencia:        {review_path}")
        print(f"[OK] Log:              {log_path}")

        return 0

    except (ControlPlaneError, ReviewValidationError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
