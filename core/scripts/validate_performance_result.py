#!/usr/bin/env python3
"""Valida evidencia de performance-testing."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from capability_common import CapabilityError, load_evidence, validate_capability_evidence

CAPABILITY = "performance-testing"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature", required=True)
    parser.add_argument("--evidence", required=True, type=Path)
    parser.add_argument("--require-pass", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    try:
        evidence = load_evidence(args.evidence)
        validate_capability_evidence(evidence, CAPABILITY, args.feature)

        statistics = evidence.get("statistics")
        if not isinstance(statistics, dict) or "p95_ms" not in statistics:
            raise CapabilityError("La evidencia performance no contiene statistics.p95_ms")

        if args.require_pass and evidence["status"] != "PASSED":
            raise CapabilityError("La evidencia performance no esta en PASSED")

        print(f"[OK] Performance evidence valid: {args.evidence}")
        return 0

    except CapabilityError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
