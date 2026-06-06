#!/usr/bin/env python3
"""Regenera el resumen de calidad en docs/90-generated."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from control_common import ControlPlaneError, load_project_config, repo_root


def load_json_or_none(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def summarize_latest_artifacts(artifact_root: Path) -> list[str]:
    if not artifact_root.is_dir():
        return []

    rows: list[str] = []
    for path in sorted(artifact_root.rglob("latest.json")):
        data = load_json_or_none(path)
        if data is None:
            status = "invalid-json"
            feature = ""
            gate = ""
        else:
            status = str(data.get("status") or data.get("overall_status") or "unknown")
            feature = str(data.get("feature_id") or data.get("feature") or "")
            gate = str(data.get("gate_id") or data.get("phase") or data.get("operation") or "")

        rows.append(f"| `{path.relative_to(artifact_root)}` | {feature} | {gate} | {status} |")

    return rows


def refresh_quality_summary(root: Path | None = None) -> Path:
    root = root or repo_root()
    docs_root = root / "docs" / "90-generated"
    docs_root.mkdir(parents=True, exist_ok=True)

    config = load_project_config()
    gates_path = root / "state" / "quality-gates.json"
    gates = load_json_or_none(gates_path) or {}
    gate_rows = []

    for gate in gates.get("gates", []):
        if not isinstance(gate, dict):
            continue
        command = " ".join(str(part) for part in gate.get("command", []))
        gate_rows.append(
            f"| {gate.get('id', '')} | {gate.get('phase', '')} | "
            f"{gate.get('blocking', '')} | `{command}` |"
        )

    if not gate_rows:
        gate_rows.append("| none | none | none | none |")

    artifact_root = Path(str(config.get("artifact_root", ""))).expanduser()
    artifact_rows = summarize_latest_artifacts(artifact_root)
    if not artifact_rows:
        artifact_rows.append("| none | none | none | no latest evidence found |")

    content = f"""# Quality Summary

Project: {config.get("name", "unknown")}

This file is generated. `state/quality-gates.json` and artifact evidence remain
authoritative.

## Configured Gates

| ID | Phase | Blocking | Command |
| --- | --- | --- | --- |
{chr(10).join(gate_rows)}

## Latest Evidence

Artifact root: `{artifact_root}`

| Evidence | Feature | Gate | Status |
| --- | --- | --- | --- |
{chr(10).join(artifact_rows)}
"""

    output = docs_root / "quality-summary.md"
    output.write_text(content, encoding="utf-8")
    return output


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    try:
        output = refresh_quality_summary(args.root.resolve() if args.root else None)
        print(f"[OK] Quality summary refreshed: {output}")
        return 0
    except ControlPlaneError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
