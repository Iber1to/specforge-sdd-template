#!/usr/bin/env python3
"""Inicia una ejecución de implementación y crea su worktree aislado."""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone

from control_common import (
    ControlPlaneError,
    apply_transition,
    atomic_write_json,
    control_paths,
    find_feature,
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
    parser.add_argument("--reason", default="Implementación iniciada")

    return parser.parse_args()


def create_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    return f"RUN-{timestamp}-{suffix}"


def expiration_time(ttl_minutes: int) -> str:
    expiration = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    return expiration.isoformat(timespec="seconds")


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
                    f"{feature['id']} no puede iniciarse desde el estado {feature['state']}"
                )

            lease_path = paths["leases"] / f"{feature['id']}.json"

            if lease_path.exists():
                raise ControlPlaneError(
                    f"Ya existe un lease activo para {feature['id']}: {lease_path}"
                )

            validate_transition(feature, "IN_PROGRESS", "implementer")

            worktree, branch, worktree_created = ensure_implementation_worktree(feature)

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
        print(f"[OK] Rama:     {branch}")
        print(f"[OK] Worktree: {worktree}")
        print(f"[OK] Lease:    {lease_path}")

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
