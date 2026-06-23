#!/usr/bin/env python3
"""Regenerate docs/00-project/glossary.md from glossary.yaml."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml
from control_common import ControlPlaneError, repo_root
from jsonschema import Draft202012Validator


def read_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ControlPlaneError(f"YAML glossary does not exist: {path}") from exc
    except yaml.YAMLError as exc:
        raise ControlPlaneError(f"Invalid YAML in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ControlPlaneError("glossary.yaml must contain a YAML object")

    return data


def validate_glossary(root: Path, glossary: dict[str, Any]) -> None:
    schema_path = root / "specs" / "schemas" / "glossary.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    errors = sorted(
        validator.iter_errors(glossary),
        key=lambda error: list(error.absolute_path),
    )

    if errors:
        error = errors[0]
        location = ".".join(str(part) for part in error.absolute_path) or "<root>"
        raise ControlPlaneError(f"Invalid glossary.yaml at {location}: {error.message}")


def join_values(values: list[str]) -> str:
    return ", ".join(values) if values else "none"


def render_glossary(glossary: dict[str, Any]) -> str:
    rows = []
    for term in glossary["terms"]:
        rows.append(
            "| {term} | {definition} | {context} | {aliases} | {relations} |".format(
                term=term["term"],
                definition=term["definition"],
                context=term["context"],
                aliases=join_values(term.get("aliases", [])),
                relations=join_values(term.get("relations", [])),
            )
        )

    return (
        "---\n"
        "owner: template\n"
        "last_verified: 2026-06-07\n"
        "---\n\n"
        "# Glossary\n\n"
        "This file is generated from `docs/00-project/glossary.yaml`.\n\n"
        "| Term | Definition | Context | Aliases | Relations |\n"
        "| --- | --- | --- | --- | --- |\n" + "\n".join(rows) + "\n"
    )


def refresh_glossary(root: Path | None = None) -> Path:
    root = root or repo_root()
    glossary_path = root / "docs" / "00-project" / "glossary.yaml"
    output_path = root / "docs" / "00-project" / "glossary.md"
    glossary = read_yaml(glossary_path)
    validate_glossary(root, glossary)
    output_path.write_text(render_glossary(glossary), encoding="utf-8")
    return output_path


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    try:
        output = refresh_glossary(args.root.resolve() if args.root else None)
        print(f"[OK] Refreshed: {output}")
        return 0
    except ControlPlaneError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
