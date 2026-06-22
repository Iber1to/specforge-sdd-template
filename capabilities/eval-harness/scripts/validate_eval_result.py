#!/usr/bin/env python3
"""Valida evidencia de eval-harness."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from capability_common import CapabilityError, load_evidence, validate_capability_evidence

CAPABILITY = "eval-harness"


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

        summary = evidence.get("eval_summary")
        graders = evidence.get("graders")

        if not isinstance(summary, dict):
            raise CapabilityError("La evidencia eval no contiene eval_summary")
        if not isinstance(graders, list):
            raise CapabilityError("La evidencia eval no contiene graders")
        if args.require_pass and evidence["status"] != "PASSED":
            raise CapabilityError("La evidencia eval no esta en PASSED")

        print(f"[OK] Eval evidence valid: {args.evidence}")
        return 0

    except CapabilityError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
