#!/usr/bin/env python3
"""Realiza una transición determinista del ciclo de vida del proyecto."""

from __future__ import annotations

import argparse
import sys

from control_common import (
    ControlPlaneError,
    load_project_config,
    load_queue,
    load_runtime,
    queue_lock,
    save_runtime,
)
from lifecycle_common import (
    apply_lifecycle_transition,
    current_lifecycle_phase,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument(
        "--to",
        required=True,
        choices=["ACTIVE_DEVELOPMENT"],
    )
    parser.add_argument("--actor", default="leader")
    parser.add_argument("--reason", required=True)

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    try:
        with queue_lock():
            project = load_project_config()
            queue = load_queue()
            runtime = load_runtime()

            previous = current_lifecycle_phase(project, runtime)

            changed = apply_lifecycle_transition(
                project=project,
                queue=queue,
                runtime=runtime,
                target_phase=arguments.to,
                actor=arguments.actor,
                reason=arguments.reason,
            )

            if changed:
                save_runtime(runtime)

        if changed:
            print(f"[OK] Ciclo de vida: {previous} -> {arguments.to}")
        else:
            print(f"[OK] El ciclo de vida ya está en {arguments.to}")

        return 0

    except ControlPlaneError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
