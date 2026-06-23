#!/usr/bin/env python3
"""Display the current status of the control plane."""

from __future__ import annotations

import argparse
import json
import sys

from control_common import (
    ControlPlaneError,
    load_project_config,
    load_queue,
    load_runtime,
    queue_lock,
)
from lifecycle_common import current_lifecycle_phase
from metrics_snapshot_status import (
    format_metrics_snapshot_status,
    summarize_metrics_snapshot,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json",
        action="store_true",
        help="Return the full status as JSON.",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    try:
        with queue_lock(exclusive=False):
            project = load_project_config()
            queue = load_queue()
            runtime = load_runtime()

        lifecycle_phase = current_lifecycle_phase(project, runtime)

        metrics_snapshot = summarize_metrics_snapshot(
            project["control_root"],
            queue,
        )

        if arguments.json:
            print(
                json.dumps(
                    {
                        "project": project,
                        "queue": queue,
                        "runtime": runtime,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )
            return 0

        print("=== CONTROL PLANE ===")
        print(f"Project:        {project['name']}")
        print(f"Phase:          {lifecycle_phase}")
        print(f"Active feature: {runtime.get('active_feature') or 'none'}")
        print(f"Features:       {len(queue['features'])}")
        print("Metrics:        " + format_metrics_snapshot_status(metrics_snapshot))
        print()

        if not queue["features"]:
            print("No features registered.")
            return 0

        print(f"{'ID':<8} {'STATE':<24} {'PRIO':<6} {'WIN':<5} TITLE")
        print("-" * 90)

        for feature in queue["features"]:
            windows = "yes" if feature.get("windows_validation_required", False) else "no"

            print(
                f"{feature['id']:<8} "
                f"{feature['state']:<24} "
                f"{feature['priority']:<6} "
                f"{windows:<5} "
                f"{feature['title']}"
            )

        return 0

    except ControlPlaneError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
