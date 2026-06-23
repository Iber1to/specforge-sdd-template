#!/usr/bin/env python3
"""Manually validate the Windows evidence for a feature and commit."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from control_common import (
    ControlPlaneError,
    find_feature,
    load_project_config,
    load_queue,
    queue_lock,
    repo_root,
)
from windows_validation import (
    WindowsEvidenceValidationError,
    validate_windows_evidence,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--feature", required=True)
    parser.add_argument("--commit", required=True)

    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    try:
        config = load_project_config()

        with queue_lock(exclusive=False):
            feature = find_feature(load_queue(), arguments.feature)

        evidence = validate_windows_evidence(
            repo_root=repo_root(),
            artifact_root=Path(config["artifact_root"]).expanduser().resolve(),
            feature=feature,
            expected_commit=arguments.commit,
        )

        print(f"[OK] Feature: {feature['id']}")
        print(f"[OK] Commit:  {evidence['tested_commit']}")
        print(f"[OK] Runner:  {evidence['runner_id']}")
        print(f"[OK] Host:    {evidence['host']}")
        print(f"[OK] Checks:  {len(evidence['checks'])}")

        return 0

    except (ControlPlaneError, WindowsEvidenceValidationError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
