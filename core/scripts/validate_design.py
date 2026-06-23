#!/usr/bin/env python3
"""Validate the architecture or full readiness for development."""

from __future__ import annotations

import argparse
import sys

from control_common import ControlPlaneError, find_feature, load_queue, queue_lock, repo_root
from feature_validation import (
    FeatureValidationError,
    validate_architecture,
    validate_development_readiness,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature", required=True)
    parser.add_argument(
        "--level",
        choices=["architecture", "ready"],
        default="ready",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    try:
        with queue_lock(exclusive=False):
            feature = find_feature(load_queue(), arguments.feature)

        if arguments.level == "architecture":
            validate_architecture(repo_root(), feature)
            print(f"[OK] {feature['id']}: architecture valid")
        else:
            validate_development_readiness(repo_root(), feature)
            print(f"[OK] {feature['id']}: ready for development")

        return 0

    except (ControlPlaneError, FeatureValidationError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
