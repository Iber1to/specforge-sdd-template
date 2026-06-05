#!/usr/bin/env python3
"""Completa una implementación validada y la envía a READY_FOR_QA."""

from __future__ import annotations

import argparse
import json
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
from quality_gates import QualityGateError, run_quality_gates
from run_metrics import finalize_run_metrics
from worktree_common import ensure_clean_repository, run_git


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--feature", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument(
        "--reason",
        default="Implementación completada y verificada",
    )

    return parser.parse_args()


def current_worktree() -> Path:
    result = run_git(Path.cwd(), "rev-parse", "--show-toplevel")
    return Path(result.stdout.strip()).resolve()


def git_head(repository: Path) -> str:
    return run_git(repository, "rev-parse", "HEAD").stdout.strip()


def commits_ahead(repository: Path, canonical_branch: str) -> int:
    result = run_git(
        repository,
        "rev-list",
        "--count",
        f"{canonical_branch}..HEAD",
    )

    return int(result.stdout.strip())


def run_verification(
    worktree: Path,
    artifact_root: Path,
    feature_id: str,
    run_id: str,
) -> tuple[Path, str, dict]:
    try:
        quality_gates = run_quality_gates(
            repo_root=worktree,
            artifact_root=artifact_root,
            feature_id=feature_id,
            run_id=run_id,
            phase="implementation_fast",
        )
    except QualityGateError as exc:
        raise ControlPlaneError(str(exc)) from exc

    gate_logs = [Path(gate["log"]) for gate in quality_gates["gates"]]
    log_path = gate_logs[0] if gate_logs else Path(quality_gates["evidence"])

    return log_path, "quality-gates:implementation_fast", quality_gates


def create_and_commit_evidence(
    worktree: Path,
    feature: dict,
    lease: dict,
    tested_commit: str,
    verification_log: Path,
    verification_command: str,
    quality_gates: dict,
) -> tuple[Path, str]:
    evidence_path = worktree / "evidence" / "implementations" / f"{feature['id']}.json"

    evidence_path.parent.mkdir(parents=True, exist_ok=True)

    evidence = {
        "schema_version": 1,
        "feature_id": feature["id"],
        "run_id": lease["run_id"],
        "agent_id": lease["agent_id"],
        "branch": lease["branch"],
        "worktree": lease["worktree"],
        "tested_commit": tested_commit,
        "verification_command": verification_command,
        "verification_exit_code": 0,
        "verification_log": str(verification_log),
        "quality_gates": {
            "status": quality_gates["status"],
            "phase": quality_gates["phase"],
            "evidence": quality_gates["evidence"],
        },
        "completed_at": utc_now(),
    }

    evidence_path.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    relative_path = evidence_path.relative_to(worktree)

    run_git(worktree, "add", str(relative_path))

    status = run_git(worktree, "status", "--porcelain").stdout.strip()

    if status:
        run_git(
            worktree,
            "commit",
            "-m",
            f"chore({feature['id']}): record implementation evidence",
        )

    ensure_clean_repository(worktree)

    return evidence_path, git_head(worktree)


def main() -> int:
    arguments = parse_arguments()

    try:
        worktree = current_worktree()
        config = load_project_config()
        paths = control_paths()

        with queue_lock(exclusive=False):
            queue = load_queue()
            feature = find_feature(queue, arguments.feature)

            if feature["state"] != "IN_PROGRESS":
                raise ControlPlaneError(f"{feature['id']} no está en estado IN_PROGRESS")

            lease_path = paths["leases"] / f"{feature['id']}.json"
            lease = load_json(lease_path)

            if lease.get("agent_id") != arguments.agent_id:
                raise ControlPlaneError(
                    f"El lease pertenece a {lease.get('agent_id')}, no a {arguments.agent_id}"
                )

            if Path(lease["worktree"]).resolve() != worktree:
                raise ControlPlaneError("El cierre debe ejecutarse desde el worktree asignado")

        ensure_clean_repository(worktree)

        canonical_branch = config.get("canonical_branch", "main")

        if commits_ahead(worktree, canonical_branch) < 1:
            raise ControlPlaneError("La rama de implementación no contiene commits propios")

        tested_commit = git_head(worktree)

        log_path, verification_command, quality_gates = run_verification(
            worktree=worktree,
            artifact_root=Path(config["artifact_root"]).resolve(),
            feature_id=feature["id"],
            run_id=lease["run_id"],
        )

        evidence_path, evidence_commit = create_and_commit_evidence(
            worktree=worktree,
            feature=feature,
            lease=lease,
            tested_commit=tested_commit,
            verification_log=log_path,
            verification_command=verification_command,
            quality_gates=quality_gates,
        )

        with queue_lock():
            queue = load_queue()
            runtime = load_runtime()
            feature = find_feature(queue, arguments.feature)

            current_lease = load_json(lease_path)

            if current_lease.get("run_id") != lease["run_id"]:
                raise ControlPlaneError("El lease cambió durante el cierre de implementación")

            apply_transition(
                queue=queue,
                runtime=runtime,
                feature=feature,
                target_state="READY_FOR_QA",
                role="implementer",
                reason=arguments.reason,
            )

            run_path = paths["runs"] / f"{lease['run_id']}.json"
            run = load_json(run_path)

            completion_timestamp = utc_now()

            run["status"] = "COMPLETED"
            run["tested_commit"] = tested_commit
            run["evidence_commit"] = evidence_commit
            run["implementation_evidence"] = str(evidence_path)
            run["verification_log"] = str(log_path)
            run["quality_gates"] = {
                "status": quality_gates["status"],
                "phase": quality_gates["phase"],
                "evidence": quality_gates["evidence"],
            }
            run["updated_at"] = completion_timestamp
            run["completed_at"] = completion_timestamp

            finalize_run_metrics(
                run,
                result="READY_FOR_QA",
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
        print("[OK] Estado:           READY_FOR_QA")
        print(f"[OK] Commit probado:   {tested_commit}")
        print(f"[OK] Commit evidencia: {evidence_commit}")
        print(f"[OK] Evidencia:        {evidence_path}")
        print(f"[OK] Log:              {log_path}")

        return 0

    except ControlPlaneError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
