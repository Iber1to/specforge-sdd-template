#!/usr/bin/env python3
"""Recovers expired leases and blocks their features."""

from __future__ import annotations

import argparse
import sys

from control_common import (
    ControlPlaneError,
    apply_transition,
    atomic_write_json,
    control_paths,
    find_feature,
    lease_is_expired,
    load_json,
    load_queue,
    load_runtime,
    queue_lock,
    save_queue,
    save_runtime,
    utc_now,
)
from run_metrics import finalize_run_metrics
from worktree_common import ensure_canonical_repository


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--feature")
    selection.add_argument("--all", action="store_true")

    parser.add_argument(
        "--reason",
        default="Lease expired and recovered",
    )

    return parser.parse_args()


def recover_feature(
    feature_id: str,
    reason: str,
    queue: dict,
    runtime: dict,
) -> bool:
    paths = control_paths()
    lease_path = paths["leases"] / f"{feature_id}.json"

    if not lease_path.exists():
        raise ControlPlaneError(f"No lease exists for {feature_id}")

    lease = load_json(lease_path)

    if not lease_is_expired(lease):
        return False

    feature = find_feature(queue, feature_id)

    # An expired lease may belong to an implementer (feature in IN_PROGRESS) or
    # to a QA reviewer (feature in READY_FOR_QA). In both cases the feature must
    # be left BLOCKED so it is not orphaned without an active lease.
    if feature["state"] in {"IN_PROGRESS", "READY_FOR_QA"}:
        apply_transition(
            queue=queue,
            runtime=runtime,
            feature=feature,
            target_state="BLOCKED",
            role="leader",
            reason=reason,
        )

    run_path = paths["runs"] / f"{lease['run_id']}.json"
    run = load_json(run_path)

    completion_timestamp = utc_now()

    run["status"] = "EXPIRED"
    run["updated_at"] = completion_timestamp
    run["completed_at"] = completion_timestamp
    run["recovery_reason"] = reason

    finalize_run_metrics(
        run,
        result="EXPIRED",
        completed_at=completion_timestamp,
    )

    runtime["active_runs"] = [
        run_id for run_id in runtime.get("active_runs", []) if run_id != lease["run_id"]
    ]

    if runtime.get("active_feature") == feature_id:
        runtime["active_feature"] = None

    atomic_write_json(run_path, run)
    lease_path.unlink()

    return True


def main() -> int:
    arguments = parse_arguments()

    try:
        ensure_canonical_repository()

        with queue_lock():
            paths = control_paths()
            queue = load_queue()
            runtime = load_runtime()

            if arguments.all:
                feature_ids = sorted(path.stem for path in paths["leases"].glob("F-*.json"))
            else:
                feature_ids = [arguments.feature]

            recovered: list[str] = []

            for feature_id in feature_ids:
                if recover_feature(
                    feature_id=feature_id,
                    reason=arguments.reason,
                    queue=queue,
                    runtime=runtime,
                ):
                    recovered.append(feature_id)

            save_queue(queue)
            save_runtime(runtime)

        if recovered:
            for feature_id in recovered:
                print(f"[OK] Lease recovered: {feature_id}")
        else:
            print("[OK] No expired leases exist.")

        return 0

    except ControlPlaneError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
