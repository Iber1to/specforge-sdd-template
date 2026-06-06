#!/usr/bin/env python3
"""Regenera el indice principal de documentacion del proyecto."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from control_common import ControlPlaneError, repo_root

NUMBERED_SECTIONS = [
    ("00-project", "Project context, goals, glossary and roadmap."),
    ("10-architecture", "Consolidated architecture and accepted ADRs."),
    ("20-runtime", "Local development, configuration and runtime matrix."),
    ("30-quality", "Test strategy, quality gates and capability quality docs."),
    ("40-operations", "Runbook, troubleshooting, backup and maintenance."),
    ("50-releases", "Changelog and release notes."),
    ("90-generated", "Regenerated summaries. Not authoritative."),
]


def markdown_list(values: list[str]) -> str:
    if not values:
        return "- none"
    return "\n".join(f"- `{value}`" for value in values)


def load_state(root: Path) -> dict[str, Any]:
    state_path = root / "state" / "project.json"
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ControlPlaneError(f"Missing project state: {state_path}") from exc
    except json.JSONDecodeError as exc:
        raise ControlPlaneError(f"Invalid project state: {state_path}: {exc}") from exc


def project_docs(root: Path) -> list[str]:
    docs_root = root / "docs"
    if not docs_root.is_dir():
        return []
    return sorted(
        str(path.relative_to(docs_root))
        for path in docs_root.rglob("*.md")
        if path.name != "README.md"
    )


def refresh_docs_index(root: Path | None = None) -> Path:
    root = root or repo_root()
    state = load_state(root)
    docs_root = root / "docs"
    docs_root.mkdir(parents=True, exist_ok=True)

    sections = "\n".join(
        f"- `docs/{name}/`: {description}" for name, description in NUMBERED_SECTIONS
    )
    generated_docs = markdown_list(project_docs(root))
    capabilities = markdown_list([str(item) for item in state.get("capabilities", [])])

    content = f"""# Project Documentation

Project: {state.get("name", "unknown")}

Project ID: `{state.get("project_id", "unknown")}`

Profile: `{state.get("profile", "unknown")}`

## Documentation Contract

- `docs/`: stable, living project documentation.
- `specs/features/`: traceable documentation for each feature.
- `evidence/`: lightweight versioned evidence.
- `control_root` and `artifact_root`: operational state and heavy artifacts outside Git.

## Project Sections

{sections}

## Harness Documentation

The generated harness also copies non-numbered documentation directories under
`docs/`, such as `docs/architecture`, `docs/conventions` and
`docs/windows-runner`. These files describe harness contracts used by agents
and scripts.

## Enabled Capabilities

{capabilities}

## Markdown Files

{generated_docs}
"""

    output = docs_root / "README.md"
    output.write_text(content, encoding="utf-8")
    return output


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    try:
        output = refresh_docs_index(args.root.resolve() if args.root else None)
        print(f"[OK] Documentation index refreshed: {output}")
        return 0
    except ControlPlaneError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
