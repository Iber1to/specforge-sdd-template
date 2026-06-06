#!/usr/bin/env python3
"""Regenera el resumen de metricas en docs/90-generated."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from control_common import ControlPlaneError, load_project_config, load_queue, repo_root
from metrics_snapshot_status import summarize_metrics_snapshot


def refresh_metrics_summary(root: Path | None = None) -> Path:
    root = root or repo_root()
    docs_root = root / "docs" / "90-generated"
    docs_root.mkdir(parents=True, exist_ok=True)

    config = load_project_config()
    queue = load_queue()
    summary = summarize_metrics_snapshot(config["control_root"], queue)

    content = f"""# Metrics Summary

Project: {config.get("name", "unknown")}

This file is generated. The metrics snapshot under `control_root` remains
authoritative.

| Field | Value |
| --- | --- |
| Status | {summary.get("status")} |
| Snapshot | `{summary.get("path")}` |
| Generated At | {summary.get("generated_at") or "n/a"} |
| Features | {summary.get("features")} |
| Agent Invocations | {summary.get("agent_invocations")} |
| Runs | {summary.get("runs")} |
| Budget Violations | {summary.get("budget_violations")} |
| Invalid Records | {summary.get("invalid_records")} |
"""

    output = docs_root / "metrics-summary.md"
    output.write_text(content, encoding="utf-8")
    return output


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    try:
        output = refresh_metrics_summary(args.root.resolve() if args.root else None)
        print(f"[OK] Metrics summary refreshed: {output}")
        return 0
    except ControlPlaneError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
