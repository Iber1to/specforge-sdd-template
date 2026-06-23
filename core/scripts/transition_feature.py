#!/usr/bin/env python3
"""Perform a validated transition of a feature."""

from __future__ import annotations

import argparse
import sys

from control_common import (
    ControlPlaneError,
    apply_transition,
    find_feature,
    load_queue,
    load_runtime,
    queue_lock,
    save_queue,
    save_runtime,
)

VALID_ROLES = [
    "leader",
    "specifier",
    "architect",
    "implementer",
    "qa-reviewer",
]


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--feature", required=True)
    parser.add_argument("--to", required=True)
    parser.add_argument("--role", required=True, choices=VALID_ROLES)
    parser.add_argument("--reason", required=True)

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    try:
        with queue_lock():
            queue = load_queue()
            runtime = load_runtime()
            feature = find_feature(queue, arguments.feature)
            current_state = feature["state"]

            apply_transition(
                queue=queue,
                runtime=runtime,
                feature=feature,
                target_state=arguments.to,
                role=arguments.role,
                reason=arguments.reason,
            )

            save_queue(queue)
            save_runtime(runtime)

        print(f"[OK] {feature['id']}: {current_state} -> {arguments.to} by {arguments.role}")

        return 0

    except ControlPlaneError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
