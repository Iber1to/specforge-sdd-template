#!/usr/bin/env python3
"""Regenerate the documents derived from project state."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from control_common import (
    ControlPlaneError,
    load_project_config,
    load_queue,
    load_runtime,
    repo_root,
)
from generate_docs_index import refresh_docs_index
from refresh_feature_index import refresh_feature_index
from refresh_glossary import refresh_glossary
from refresh_metrics_summary import refresh_metrics_summary
from refresh_quality_summary import refresh_quality_summary


def state_rows(features: list[dict[str, Any]]) -> str:
    counts = Counter(str(feature.get("state", "UNKNOWN")) for feature in features)
    if not counts:
        return "| none | 0 |"
    return "\n".join(f"| {state} | {count} |" for state, count in sorted(counts.items()))


def refresh_project_status(root: Path | None = None) -> Path:
    root = root or repo_root()
    docs_root = root / "docs" / "90-generated"
    docs_root.mkdir(parents=True, exist_ok=True)

    config = load_project_config()
    queue = load_queue()
    runtime = load_runtime()
    features = [item for item in queue.get("features", []) if isinstance(item, dict)]

    content = f"""# Project Status

Project: {config.get("name", "unknown")}

Project ID: `{config.get("project_id", "unknown")}`

Profile: `{config.get("profile", "unknown")}`

Lifecycle Phase: `{config.get("lifecycle_phase", "unknown")}`

Active Feature: `{runtime.get("active_feature") or "none"}`

This file is generated. `state/`, `control_root`, `specs/features/` and Git
remain authoritative.

## Feature States

| State | Count |
| --- | --- |
{state_rows(features)}
"""

    output = docs_root / "project-status.md"
    output.write_text(content, encoding="utf-8")
    return output


def refresh_project_docs(root: Path | None = None) -> list[Path]:
    root = root or repo_root()
    outputs = [
        refresh_docs_index(root),
        refresh_glossary(root),
        refresh_project_status(root),
        refresh_feature_index(root),
        refresh_quality_summary(root),
        refresh_metrics_summary(root),
    ]
    return outputs


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    try:
        outputs = refresh_project_docs(args.root.resolve() if args.root else None)
        for output in outputs:
            print(f"[OK] Refreshed: {output}")
        return 0
    except ControlPlaneError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
