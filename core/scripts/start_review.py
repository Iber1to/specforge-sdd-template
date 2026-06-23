#!/usr/bin/env python3
"""Start an exclusive QA review over a feature."""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone

from control_common import (
    ControlPlaneError,
    atomic_write_json,
    control_paths,
    find_feature,
    load_json,
    load_project_config,
    load_queue,
    load_runtime,
    queue_lock,
    save_runtime,
    utc_now,
)
from run_metrics import initialize_run_metrics
from worktree_common import (
    ensure_canonical_repository,
    ensure_review_worktree,
    run_git,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--feature", required=True)
    parser.add_argument("--agent-id", required=True)

    return parser.parse_args()


def create_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]

    return f"RUN-{timestamp}-{suffix}"


def expiration_time(ttl_minutes: int) -> str:
    expiration = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)

    return expiration.isoformat(timespec="seconds")


def git_head(worktree) -> str:
    return run_git(worktree, "rev-parse", "HEAD").stdout.strip()


def main() -> int:
    arguments = parse_arguments()

    try:
        ensure_canonical_repository()

        with queue_lock():
            config = load_project_config()
            paths = control_paths()
            queue = load_queue()
            runtime = load_runtime()

            feature = find_feature(queue, arguments.feature)

            if feature["state"] != "READY_FOR_QA":
                raise ControlPlaneError(
                    f"{feature['id']} cannot be reviewed from state {feature['state']}"
                )

            lease_path = paths["leases"] / f"{feature['id']}.json"

            if lease_path.exists():
                raise ControlPlaneError(
                    f"An active lease already exists for {feature['id']}: {lease_path}"
                )

            worktree, branch, _ = ensure_review_worktree(feature)

            implementation_evidence_path = (
                worktree / "evidence" / "implementations" / f"{feature['id']}.json"
            )

            implementation_evidence = load_json(implementation_evidence_path)

            if implementation_evidence.get("feature_id") != feature["id"]:
                raise ControlPlaneError(
                    f"The implementation evidence does not match {feature['id']}"
                )

            run_id = create_run_id()
            timestamp = utc_now()
            ttl_minutes = int(config.get("lease_ttl_minutes", 720))
            reviewed_commit = git_head(worktree)

            lease = {
                "schema_version": 1,
                "feature_id": feature["id"],
                "run_id": run_id,
                "agent_id": arguments.agent_id,
                "role": "qa-reviewer",
                "branch": branch,
                "worktree": str(worktree),
                "reviewed_commit": reviewed_commit,
                "acquired_at": timestamp,
                "heartbeat_at": timestamp,
                "expires_at": expiration_time(ttl_minutes),
            }

            run = {
                "schema_version": 1,
                "run_id": run_id,
                "feature_id": feature["id"],
                "agent_id": arguments.agent_id,
                "role": "qa-reviewer",
                "status": "ACTIVE",
                "branch": branch,
                "worktree": str(worktree),
                "reviewed_commit": reviewed_commit,
                "started_at": timestamp,
                "updated_at": timestamp,
                "metrics": initialize_run_metrics(
                    runs_root=paths["runs"],
                    feature_id=feature["id"],
                    role="qa-reviewer",
                    started_at=timestamp,
                ),
            }

            atomic_write_json(paths["runs"] / f"{run_id}.json", run)
            atomic_write_json(lease_path, lease)

            runtime.setdefault("active_runs", []).append(run_id)

            save_runtime(runtime)

        print(f"[OK] Feature:         {feature['id']}")
        print(f"[OK] QA Run:          {run_id}")
        print(f"[OK] Reviewed branch: {branch}")
        print(f"[OK] Reviewed commit: {reviewed_commit}")
        print(f"[OK] Worktree:        {worktree}")
        print(f"[OK] Lease:           {lease_path}")

        return 0

    except ControlPlaneError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
