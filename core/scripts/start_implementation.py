#!/usr/bin/env python3
"""Start an implementation run and create its isolated worktree."""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

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
    validate_transition,
)
from run_metrics import initialize_run_metrics
from worktree_common import (
    ensure_canonical_repository,
    ensure_implementation_worktree,
    remove_worktree,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--feature", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--reason", default="Implementation started")

    return parser.parse_args()


def create_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    return f"RUN-{timestamp}-{suffix}"


def expiration_time(ttl_minutes: int) -> str:
    expiration = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    return expiration.isoformat(timespec="seconds")


def find_conflicting_implementer_lease(
    leases_root: Path,
    feature_id: str,
) -> tuple[Path, dict[str, Any]] | None:
    """Return the first foreign implementer lease present in ``leases_root``.

    Replicates the enumeration semantics of ``role_guard.active_lease()``: it
    iterates ``sorted(leases_root.glob("F-*.json"))`` (deterministic order),
    ignores unreadable or corrupt files (ASM-001) and does not consult
    ``expires_at`` nor the state of the owning feature (DEC-001). A lease counts
    as a conflict when ``role == "implementer"`` and its ``feature_id`` differs
    from the requested one, including the case where ``feature_id`` is absent
    (conservative). Returns ``(path, lease)`` of the first conflict or ``None``.
    """

    for path in sorted(leases_root.glob("F-*.json")):
        try:
            lease = load_json(path)
        except ControlPlaneError:
            continue

        if lease.get("role") == "implementer" and lease.get("feature_id") != feature_id:
            return path, lease

    return None


def main() -> int:
    arguments = parse_arguments()

    worktree = None
    worktree_created = False

    try:
        ensure_canonical_repository()

        with queue_lock():
            config = load_project_config()
            paths = control_paths()
            queue = load_queue()
            runtime = load_runtime()
            feature = find_feature(queue, arguments.feature)

            if feature["state"] not in {
                "READY_FOR_DEVELOPMENT",
                "CHANGES_REQUESTED",
            }:
                raise ControlPlaneError(
                    f"{feature['id']} cannot be started from state {feature['state']}"
                )

            max_qa_attempts = int(config.get("maximum_qa_attempts", 3))
            qa_attempts = int(feature.get("qa_attempts", 0))

            if qa_attempts >= max_qa_attempts:
                raise ControlPlaneError(
                    f"{feature['id']} exhausted the {max_qa_attempts} QA attempts "
                    f"(qa_attempts={qa_attempts}). Escalate to a human decision instead "
                    "of retrying: review scope, specification or architecture."
                )

            lease_path = paths["leases"] / f"{feature['id']}.json"

            if lease_path.exists():
                raise ControlPlaneError(
                    f"An active lease already exists for {feature['id']}: {lease_path}"
                )

            conflict = find_conflicting_implementer_lease(paths["leases"], feature["id"])

            if conflict is not None:
                conflict_path, conflict_lease = conflict
                conflict_feature = conflict_lease.get("feature_id", "unknown")
                raise ControlPlaneError(
                    f"Cannot start {feature['id']}: an active implementer lease "
                    f"from {conflict_feature} exists at {conflict_path}. "
                    "Release the lease through the operational path "
                    "(scripts/recover_stale_leases.py) before retrying."
                )

            validate_transition(feature, "IN_PROGRESS", "implementer")

            worktree, branch, worktree_created, resynced = ensure_implementation_worktree(feature)

            canonical_branch = config.get("canonical_branch", "main")

            run_id = create_run_id()
            timestamp = utc_now()
            ttl_minutes = int(config.get("lease_ttl_minutes", 720))

            lease = {
                "schema_version": 1,
                "feature_id": feature["id"],
                "run_id": run_id,
                "agent_id": arguments.agent_id,
                "role": "implementer",
                "branch": branch,
                "worktree": str(worktree),
                "acquired_at": timestamp,
                "heartbeat_at": timestamp,
                "expires_at": expiration_time(ttl_minutes),
            }

            run = {
                "schema_version": 1,
                "run_id": run_id,
                "feature_id": feature["id"],
                "agent_id": arguments.agent_id,
                "role": "implementer",
                "status": "ACTIVE",
                "branch": branch,
                "worktree": str(worktree),
                "started_at": timestamp,
                "updated_at": timestamp,
                "metrics": initialize_run_metrics(
                    runs_root=paths["runs"],
                    feature_id=feature["id"],
                    role="implementer",
                    started_at=timestamp,
                ),
            }

            atomic_write_json(paths["runs"] / f"{run_id}.json", run)
            atomic_write_json(lease_path, lease)

            apply_transition(
                queue=queue,
                runtime=runtime,
                feature=feature,
                target_state="IN_PROGRESS",
                role="implementer",
                reason=arguments.reason,
            )

            runtime.setdefault("active_runs", []).append(run_id)

            save_queue(queue)
            save_runtime(runtime)

        print(f"[OK] Feature:  {feature['id']}")
        print(f"[OK] Run:      {run_id}")
        print(f"[OK] Branch:   {branch}")
        print(f"[OK] Worktree: {worktree}")
        print(f"[OK] Lease:    {lease_path}")

        if resynced:
            print(f"[INFO] Resync:  merge of '{canonical_branch}' into '{branch}' applied")

        return 0

    except ControlPlaneError as exc:
        if worktree_created and worktree is not None:
            try:
                remove_worktree(worktree)
            except ControlPlaneError:
                pass

        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
