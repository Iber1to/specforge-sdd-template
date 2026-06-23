#!/usr/bin/env python3
"""Regenerate the feature index in docs/90-generated."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

from control_common import (
    ControlPlaneError,
    control_paths,
    load_project_config,
    load_queue,
    repo_root,
)


def feature_row(feature: dict[str, Any]) -> str:
    return (
        f"| {feature.get('id', '')} "
        f"| {feature.get('state', '')} "
        f"| {feature.get('priority', '')} "
        f"| {feature.get('change_domain', 'product')} "
        f"| {feature.get('title', '')} "
        f"| `{feature.get('spec_path', '')}` |"
    )


def refresh_feature_index(root: Path | None = None) -> Path:
    root = root or repo_root()
    docs_root = root / "docs" / "90-generated"
    docs_root.mkdir(parents=True, exist_ok=True)

    config = load_project_config()
    queue = load_queue()
    features = [item for item in queue.get("features", []) if isinstance(item, dict)]

    rows = "\n".join(feature_row(feature) for feature in features)
    if not rows:
        rows = "| none | none | none | none | No features registered | none |"

    content = f"""# Feature Index

Project: {config.get("name", "unknown")}

Source: `{control_paths()["queue"]}`

This file is generated. The queue and feature specs remain authoritative.

| ID | State | Priority | Domain | Title | Spec |
| --- | --- | --- | --- | --- | --- |
{rows}
"""

    output = docs_root / "feature-index.md"
    output.write_text(content, encoding="utf-8")
    return output


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    try:
        output = refresh_feature_index(args.root.resolve() if args.root else None)
        print(f"[OK] Feature index refreshed: {output}")
        return 0
    except ControlPlaneError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
