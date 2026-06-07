#!/usr/bin/env python3
"""Valida estructura documental, enlaces locales y frontmatter YAML."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Iterable
from urllib.parse import unquote, urlparse

import yaml
from control_common import repo_root

REQUIRED_DOCS = {
    "docs/README.md": ("Project Documentation",),
    "docs/00-project/overview.md": ("Name", "Identifier", "Status"),
    "docs/00-project/goals-and-scope.md": ("Functional Goals", "System Boundaries"),
    "docs/00-project/source-of-truth.md": ("Source Of Truth",),
    "docs/00-project/glossary.md": ("Glossary",),
    "docs/00-project/roadmap.md": ("Current Phase", "Planned Features"),
    "docs/10-architecture/architecture-overview.md": ("Overview",),
    "docs/20-runtime/configuration.md": ("Versioned Configuration",),
    "docs/30-quality/quality-gates.md": ("Phases",),
    "docs/40-operations/runbook.md": ("Validate",),
    "docs/50-releases/changelog.md": ("Unreleased",),
}

LINK_PATTERN = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


class DocumentationStructureError(RuntimeError):
    """Error controlado de estructura documental."""


def markdown_headings(content: str) -> set[str]:
    headings = set()
    for line in content.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if match:
            headings.add(match.group(1).strip())
    return headings


def validate_frontmatter(path: Path, content: str) -> None:
    if not content.startswith("---\n"):
        return

    parts = content.split("---", 2)
    if len(parts) < 3:
        raise DocumentationStructureError(f"Frontmatter sin cierre: {path}")

    try:
        value = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        raise DocumentationStructureError(f"Frontmatter YAML invalido en {path}: {exc}") from exc

    if not isinstance(value, dict):
        raise DocumentationStructureError(f"Frontmatter debe ser objeto YAML: {path}")


def local_link_target(root: Path, source: Path, target: str) -> Path | None:
    parsed = urlparse(target)
    if parsed.scheme or target.startswith("#"):
        return None

    raw_path = unquote(parsed.path)
    if not raw_path or raw_path.startswith("#"):
        return None

    if raw_path.startswith("/"):
        return root / raw_path.lstrip("/")

    return source.parent / raw_path


def validate_links(root: Path, path: Path, content: str) -> None:
    for match in LINK_PATTERN.finditer(content):
        target = match.group(1).strip()
        resolved = local_link_target(root, path, target)
        if resolved is None:
            continue

        if not resolved.exists():
            relative = path.relative_to(root)
            raise DocumentationStructureError(f"Enlace local roto en {relative}: {target}")


def validate_required_docs(root: Path) -> None:
    for relative, required_headings in REQUIRED_DOCS.items():
        path = root / relative
        if not path.is_file():
            raise DocumentationStructureError(f"Falta documento requerido: {relative}")

        content = path.read_text(encoding="utf-8")
        if not re.search(r"^#\s+\S", content, flags=re.MULTILINE):
            raise DocumentationStructureError(f"{relative} no contiene H1")

        headings = markdown_headings(content)
        missing = [heading for heading in required_headings if heading not in headings]
        if missing:
            raise DocumentationStructureError(
                f"{relative} no contiene secciones requeridas: {', '.join(missing)}"
            )


def markdown_files(root: Path) -> Iterable[Path]:
    docs_root = root / "docs"
    if not docs_root.is_dir():
        return []
    return docs_root.rglob("*.md")


def validate_documentation_structure(root: Path | None = None) -> None:
    root = root or repo_root()
    validate_required_docs(root)

    for path in markdown_files(root):
        content = path.read_text(encoding="utf-8")
        validate_frontmatter(path, content)
        validate_links(root, path, content)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    try:
        validate_documentation_structure(args.root.resolve() if args.root else None)
        print("[OK] Documentacion tecnica valida")
        return 0
    except DocumentationStructureError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
