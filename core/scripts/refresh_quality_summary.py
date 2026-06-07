#!/usr/bin/env python3
"""Regenera el resumen de calidad en docs/90-generated."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml
from control_common import ControlPlaneError, load_project_config, repo_root

STALE_AFTER_DAYS = 180


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


def stable_markdown_files(root: Path) -> list[Path]:
    docs_root = root / "docs"
    if not docs_root.is_dir():
        return []

    prefixes = (
        docs_root / "00-project",
        docs_root / "10-architecture",
        docs_root / "20-runtime",
        docs_root / "30-quality",
        docs_root / "40-operations",
        docs_root / "50-releases",
    )

    files = [docs_root / "README.md"]
    for prefix in prefixes:
        if prefix.is_dir():
            files.extend(prefix.rglob("*.md"))
    return sorted(path for path in files if path.is_file())


def document_frontmatter(path: Path) -> dict[str, Any]:
    content = path.read_text(encoding="utf-8")
    if not content.startswith("---\n"):
        return {}

    parts = content.split("---", 2)
    if len(parts) < 3:
        return {}

    value = yaml.safe_load(parts[1])
    return value if isinstance(value, dict) else {}


def parse_verified_date(value: object) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def summarize_document_freshness(root: Path) -> list[str]:
    today = date.today()
    rows: list[str] = []

    for path in stable_markdown_files(root):
        frontmatter = document_frontmatter(path)
        owner = str(frontmatter.get("owner") or "missing")
        verified = parse_verified_date(frontmatter.get("last_verified"))

        if verified is None:
            status = "missing-last_verified"
            age = ""
        else:
            age_days = (today - verified).days
            age = str(age_days)
            status = "stale" if age_days > STALE_AFTER_DAYS else "fresh"

        rows.append(
            f"| `{path.relative_to(root)}` | {owner} | {frontmatter.get('last_verified', '')} | {age} | {status} |"
        )

    return rows or ["| none | none | none | none | no stable docs found |"]


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

    freshness_rows = summarize_document_freshness(root)

    content = f"""# Quality Summary

Project: {config.get("name", "unknown")}

This file is generated. `state/quality-gates.json` and artifact evidence remain
authoritative.

## Configured Gates

| ID | Phase | Blocking | Command |
| --- | --- | --- | --- |
{chr(10).join(gate_rows)}

## Documentation Freshness

Stable docs are expected to expose `owner` and `last_verified` frontmatter.
Documents older than {STALE_AFTER_DAYS} days are reported as stale.

| Document | Owner | Last Verified | Age Days | Status |
| --- | --- | --- | --- | --- |
{chr(10).join(freshness_rows)}

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
