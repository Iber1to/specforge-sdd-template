#!/usr/bin/env python3
"""Renews an active lease from the assigned worktree."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from control_common import (
    ControlPlaneError,
    atomic_write_json,
    control_paths,
    find_feature,
    load_json,
    load_project_config,
    load_queue,
    queue_lock,
    utc_now,
)
from run_metrics import record_run_heartbeat
from worktree_common import run_git

ROLE_STATES = {
    "implementer": "IN_PROGRESS",
    "qa-reviewer": "READY_FOR_QA",
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--feature", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--ttl-minutes", type=int)

    return parser.parse_args()


def current_worktree() -> Path:
    result = run_git(Path.cwd(), "rev-parse", "--show-toplevel")
    return Path(result.stdout.strip()).resolve()


def main() -> int:
    arguments = parse_arguments()

    try:
        with queue_lock():
            config = load_project_config()
            paths = control_paths()
            queue = load_queue()
            feature = find_feature(queue, arguments.feature)

            lease_path = paths["leases"] / f"{feature['id']}.json"
            lease = load_json(lease_path)

            role = lease.get("role")
            expected_state = ROLE_STATES.get(role)

            if expected_state is None:
                raise ControlPlaneError(f"Unsupported lease role: {role}")

            if feature["state"] != expected_state:
                raise ControlPlaneError(
                    f"{feature['id']} must be in {expected_state} "
                    f"to renew a {role} lease"
                )

            if lease.get("agent_id") != arguments.agent_id:
                raise ControlPlaneError(
                    f"The lease belongs to {lease.get('agent_id')}, not to {arguments.agent_id}"
                )

            expected_worktree = Path(lease["worktree"]).resolve()
            detected_worktree = current_worktree()

            if detected_worktree != expected_worktree:
                raise ControlPlaneError(
                    "The heartbeat must be executed from the assigned worktree. "
                    f"Expected: {expected_worktree}; detected: {detected_worktree}"
                )

            ttl_minutes = (
                arguments.ttl_minutes
                if arguments.ttl_minutes is not None
                else int(config.get("lease_ttl_minutes", 720))
            )

            if ttl_minutes <= 0:
                raise ControlPlaneError("ttl-minutes must be greater than zero")

            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(minutes=ttl_minutes)

            lease["heartbeat_at"] = now.isoformat(timespec="seconds")
            lease["expires_at"] = expires_at.isoformat(timespec="seconds")

            run_path = paths["runs"] / f"{lease['run_id']}.json"
            run = load_json(run_path)
            run["updated_at"] = utc_now()
            record_run_heartbeat(
                run,
                timestamp=lease["heartbeat_at"],
            )

            atomic_write_json(lease_path, lease)
            atomic_write_json(run_path, run)

        print(f"[OK] Lease renewed: {feature['id']} ({role})")
        print(f"[OK] Expires: {lease['expires_at']}")

        return 0

    except ControlPlaneError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
