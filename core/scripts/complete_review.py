#!/usr/bin/env python3
"""Complete a QA review and apply its verdict."""

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
    mutation_testing_required,
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
    # Only used when the feature declares the mutation-testing capability and the
    # verdict is APPROVED; the mutation report is folded into the single QA commit.
    parser.add_argument("--mutation-reviewer-id", default=None)
    parser.add_argument("--mutation-summary", default=None)
    parser.add_argument(
        "--mutation-evidence",
        default=None,
        help=(
            "Path to the mutation_runner evidence "
            "(defaults to artifact_root/mutation-tests/<F>/latest.json)."
        ),
    )
    parser.add_argument(
        "--mutation-classification",
        action="append",
        default=[],
        help=(
            "Classification of a survivor: "
            "MUT-XXX=equivalent|out_of_scope|invalid|test_gap:reason."
        ),
    )

    return parser.parse_args()


def current_worktree() -> Path:
    result = run_git(Path.cwd(), "rev-parse", "--show-toplevel")
    return Path(result.stdout.strip()).resolve()


def git_head(worktree: Path) -> str:
    return run_git(worktree, "rev-parse", "HEAD").stdout.strip()


def validate_arguments(arguments: argparse.Namespace) -> None:
    if len(arguments.summary.strip()) < 10:
        raise ControlPlaneError("The QA summary must contain at least 10 characters")

    if arguments.verdict == "APPROVED" and arguments.required_change:
        raise ControlPlaneError("An APPROVED report cannot contain required changes")

    if arguments.verdict == "CHANGES_REQUESTED" and not arguments.required_change:
        raise ControlPlaneError("CHANGES_REQUESTED requires at least one --required-change")


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


def render_review_report(review: dict) -> str:
    """Readable, diffable render of the QA report, with fixed fields, alongside the JSON."""

    changes = review.get("required_changes") or []
    if changes:
        changes_block = "\n".join(f"- {item}" for item in changes)
    else:
        changes_block = "None."

    verification = review.get("verification", {})

    return (
        f"# QA Review Report - {review['feature_id']}\n\n"
        "| Field | Value |\n"
        "| --- | --- |\n"
        f"| Feature | {review['feature_id']} |\n"
        f"| Verdict | {review['verdict']} |\n"
        f"| Reviewer | {review['reviewer_id']} |\n"
        f"| Run | {review['run_id']} |\n"
        f"| Reviewed commit | {review['reviewed_commit']} |\n"
        f"| Verification | {verification.get('command', '')} "
        f"(exit {verification.get('exit_code', '')}) |\n"
        f"| Date | {review['created_at']} |\n\n"
        "## Summary\n\n"
        f"{review['summary']}\n\n"
        "## Required changes\n\n"
        f"{changes_block}\n\n"
        "## Verification log\n\n"
        f"`{verification.get('log', '')}`\n"
    )


def write_mutation_review_evidence(
    worktree: Path,
    feature: dict,
    arguments: argparse.Namespace,
    artifact_root: Path,
) -> Path:
    """Build, write, and validate the Mutation Reviewer report.

    Only invoked when the feature declares mutation-testing and the verdict is
    APPROVED. The file is folded into the single QA evidence commit.
    """

    if __package__:
        from .mutation_review_validation import (
            MutationReviewValidationError,
            build_mutation_review,
            validate_mutation_review_evidence,
        )
    else:
        from mutation_review_validation import (
            MutationReviewValidationError,
            build_mutation_review,
            validate_mutation_review_evidence,
        )

    reviewer_id = (arguments.mutation_reviewer_id or "").strip()
    if len(reviewer_id) < 3:
        raise ControlPlaneError(
            "The feature requires mutation-testing: provide --mutation-reviewer-id"
        )

    mutation_summary = (arguments.mutation_summary or "").strip()
    if len(mutation_summary) < 10:
        raise ControlPlaneError(
            "The feature requires mutation-testing: provide --mutation-summary (>=10 characters)"
        )

    evidence_ref = arguments.mutation_evidence or str(
        artifact_root / "mutation-tests" / feature["id"] / "latest.json"
    )

    try:
        review = build_mutation_review(
            feature_id=feature["id"],
            reviewer_id=reviewer_id,
            mutation_evidence=evidence_ref,
            classifications=arguments.mutation_classification,
            summary=mutation_summary,
            created_at=utc_now(),
        )
    except MutationReviewValidationError as exc:
        raise ControlPlaneError(str(exc)) from exc

    review_path = worktree / "evidence" / "mutation-reviews" / f"{feature['id']}.json"
    review_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_json(review_path, review)

    try:
        validate_mutation_review_evidence(worktree, feature)
    except MutationReviewValidationError as exc:
        raise ControlPlaneError(str(exc)) from exc

    return review_path


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
    arguments: argparse.Namespace,
    artifact_root: Path,
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

    report_path = worktree / "evidence" / "reviews" / f"{feature['id']}.md"
    report_path.write_text(render_review_report(review), encoding="utf-8")

    # Only features with mutation-testing and an APPROVED verdict: the mutation
    # report travels in this same (single) QA evidence commit.
    mutation_review_path: Path | None = None
    if verdict == "APPROVED" and mutation_testing_required(feature):
        mutation_review_path = write_mutation_review_evidence(
            worktree, feature, arguments, artifact_root
        )

    validate_review_evidence(
        worktree,
        feature,
        expected_verdict=verdict,
    )

    run_git(worktree, "add", str(review_path.relative_to(worktree)))
    run_git(worktree, "add", str(report_path.relative_to(worktree)))
    if mutation_review_path is not None:
        run_git(worktree, "add", str(mutation_review_path.relative_to(worktree)))
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
                raise ControlPlaneError(f"{feature['id']} is not in READY_FOR_QA")

            lease = load_json(lease_path)

            if lease.get("role") != "qa-reviewer":
                raise ControlPlaneError("The active lease does not belong to QA")

            if lease.get("agent_id") != arguments.agent_id:
                raise ControlPlaneError(
                    f"The lease belongs to {lease.get('agent_id')}, not to {arguments.agent_id}"
                )

            if Path(lease["worktree"]).resolve() != worktree:
                raise ControlPlaneError("The review must be completed from the assigned worktree")

        ensure_clean_repository(worktree)

        if git_head(worktree) != lease["reviewed_commit"]:
            raise ControlPlaneError("The worktree commit changed since the review started")

        result, log_path, command, quality_gates = run_full_verification(
            worktree=worktree,
            artifact_root=Path(config["artifact_root"]).resolve(),
            feature_id=feature["id"],
            run_id=lease["run_id"],
        )

        ensure_clean_repository(worktree)

        if git_head(worktree) != lease["reviewed_commit"]:
            raise ControlPlaneError("Verification modified the reviewed commit")

        if arguments.verdict == "APPROVED" and result.returncode != 0:
            raise ControlPlaneError(
                f"APPROVED cannot be issued with the full suite failing. Check: {log_path}"
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
            arguments=arguments,
            artifact_root=Path(config["artifact_root"]).resolve(),
        )

        with queue_lock():
            queue = load_queue()
            runtime = load_runtime()
            feature = find_feature(queue, arguments.feature)
            current_lease = load_json(lease_path)

            if current_lease.get("run_id") != lease["run_id"]:
                raise ControlPlaneError("The lease changed during the review")

            apply_transition(
                queue=queue,
                runtime=runtime,
                feature=feature,
                target_state=arguments.verdict,
                role="qa-reviewer",
                reason=arguments.summary.strip(),
            )

            if arguments.verdict == "CHANGES_REQUESTED":
                feature["qa_attempts"] = int(feature.get("qa_attempts", 0)) + 1

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
        print(f"[OK] Verdict:          {arguments.verdict}")
        print(f"[OK] Reviewed commit:  {lease['reviewed_commit']}")
        print(f"[OK] Evidence commit:  {evidence_commit}")
        print(f"[OK] Evidence:         {review_path}")
        print(f"[OK] Log:              {log_path}")

        return 0

    except (ControlPlaneError, ReviewValidationError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
