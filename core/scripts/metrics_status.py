#!/usr/bin/env python3
"""Query aggregated metrics for the project, role, or feature."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from control_common import ControlPlaneError, load_project_config
from metrics_common import aggregate_metrics


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--feature")
    selection.add_argument("--role")

    parser.add_argument("--json", action="store_true")

    return parser.parse_args()


def print_scope(label: str, scope: dict[str, Any]) -> None:
    agents = scope["agents"]
    runs = scope["runs"]

    print(f"=== {label} ===")
    print(
        "Agents: "
        f"{agents['invocations']} invocations; "
        f"{agents['completed']} completed; "
        f"{agents['active']} active; "
        f"{agents['blocked_results']} blocked"
    )
    print(
        "Observed usage: "
        f"{agents['total_tokens_observed']} raw tokens; "
        f"{agents['assistant_turns_observed']} turns; "
        f"{agents['duration_seconds']} seconds"
    )
    print(
        "Cache: "
        f"{agents['cache_creation_input_tokens']} creation; "
        f"{agents['cache_read_input_tokens']} read"
    )
    print(f"Budget overruns: {agents['budget_violations']}")
    print(
        "Runs: "
        f"{runs['runs']} total; "
        f"{runs['completed']} completed; "
        f"{runs['active']} active; "
        f"{runs['expired']} expired; "
        f"{runs['retries']} retries"
    )
    print(
        "Observed runs: "
        f"{runs['duration_seconds']} seconds; "
        f"{runs['heartbeat_count']} heartbeats"
    )

    if runs["results"]:
        print(
            "Results: "
            + ", ".join(f"{name}={amount}" for name, amount in sorted(runs["results"].items()))
        )


def main() -> int:
    arguments = parse_arguments()

    try:
        config = load_project_config()
        control_root = Path(config["control_root"]).resolve()
        summary = aggregate_metrics(control_root)

        selected: dict[str, Any]
        label: str

        if arguments.feature:
            selected = summary["features"].get(arguments.feature)

            if selected is None:
                raise ControlPlaneError(f"No metrics exist for {arguments.feature}")

            label = f"FEATURE {arguments.feature}"

        elif arguments.role:
            selected = summary["roles"].get(arguments.role)

            if selected is None:
                raise ControlPlaneError(f"No metrics exist for role {arguments.role}")

            label = f"ROLE {arguments.role}"

        else:
            selected = summary["project"]
            label = "PROJECT"

        if arguments.json:
            print(
                json.dumps(
                    selected if arguments.feature or arguments.role else summary,
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            print_scope(label, selected)

        return 0

    except ControlPlaneError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
