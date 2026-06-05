#!/usr/bin/env python3
"""Regenera el snapshot derivado de métricas por feature."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from control_common import (
    ControlPlaneError,
    load_project_config,
    load_queue,
    queue_lock,
)
from feature_metrics_snapshot import (
    refresh_feature_metrics_snapshot,
    snapshot_path,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--feature")
    parser.add_argument("--json", action="store_true")

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    try:
        config = load_project_config()
        control_root = Path(config["control_root"]).resolve()

        with queue_lock(exclusive=False):
            queue = load_queue()

        snapshot = refresh_feature_metrics_snapshot(
            control_root=control_root,
            queue=queue,
        )

        selected = snapshot

        if arguments.feature:
            selected = snapshot["features"].get(arguments.feature)

            if selected is None:
                raise ControlPlaneError(f"No existe la feature {arguments.feature}")

        if arguments.json:
            print(
                json.dumps(
                    selected,
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            print(f"[OK] Snapshot regenerado: {snapshot_path(control_root)}")
            print(f"[OK] Features incluidas: {len(snapshot['features'])}")
            print(
                "[OK] Registros inválidos: "
                f"agentes={snapshot['invalid_records']['agent_metrics']}; "
                f"runs={snapshot['invalid_records']['runs']}"
            )

        return 0

    except ControlPlaneError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
