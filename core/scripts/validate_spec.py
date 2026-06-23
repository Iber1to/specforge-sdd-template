#!/usr/bin/env python3
"""Validate the specification and acceptance criteria of a feature."""

from __future__ import annotations

import argparse
import sys

from control_common import ControlPlaneError, find_feature, load_queue, queue_lock, repo_root
from feature_validation import FeatureValidationError, validate_specification


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature", required=True)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    try:
        with queue_lock(exclusive=False):
            feature = find_feature(load_queue(), arguments.feature)

        acceptance = validate_specification(repo_root(), feature)

        print(
            f"[OK] {feature['id']}: specification valid ({len(acceptance['criteria'])} criteria)"
        )
        return 0

    except (ControlPlaneError, FeatureValidationError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
