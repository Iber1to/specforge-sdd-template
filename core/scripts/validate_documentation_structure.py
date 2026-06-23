#!/usr/bin/env python3
"""Validate documentation structure, local links and YAML frontmatter."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import date, datetime
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
STABLE_DOC_PATTERN = re.compile(
    r"^docs/(README\.md|"
    r"(00-project|10-architecture|20-runtime|30-quality|40-operations|50-releases)/.*\.md)$"
)


class DocumentationStructureError(RuntimeError):
    """Controlled documentation structure error."""


def markdown_headings(content: str) -> set[str]:
    headings = set()
    for line in content.splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*$", line)
        if match:
            headings.add(match.group(1).strip())
    return headings


def is_stable_doc(root: Path, path: Path) -> bool:
    relative = path.relative_to(root).as_posix()
    if relative.startswith("docs/90-generated/"):
        return False
    return STABLE_DOC_PATTERN.fullmatch(relative) is not None


def validate_last_verified(path: Path, value: object) -> None:
    if isinstance(value, date):
        return

    if not isinstance(value, str):
        raise DocumentationStructureError(f"last_verified must be an ISO date in {path}")

    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError as exc:
        raise DocumentationStructureError(f"last_verified must use YYYY-MM-DD in {path}") from exc


def validate_frontmatter(root: Path, path: Path, content: str) -> None:
    requires_frontmatter = is_stable_doc(root, path)

    if not content.startswith("---\n"):
        if requires_frontmatter:
            raise DocumentationStructureError(f"Missing owner/last_verified frontmatter: {path}")
        return

    parts = content.split("---", 2)
    if len(parts) < 3:
        raise DocumentationStructureError(f"Unclosed frontmatter: {path}")

    try:
        value = yaml.safe_load(parts[1])
    except yaml.YAMLError as exc:
        raise DocumentationStructureError(f"Invalid YAML frontmatter in {path}: {exc}") from exc

    if not isinstance(value, dict):
        raise DocumentationStructureError(f"Frontmatter must be a YAML object: {path}")

    if requires_frontmatter:
        owner = value.get("owner")
        if not isinstance(owner, str) or not owner.strip():
            raise DocumentationStructureError(f"Frontmatter requires owner in {path}")

        if "last_verified" not in value:
            raise DocumentationStructureError(f"Frontmatter requires last_verified in {path}")

        validate_last_verified(path, value["last_verified"])


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
            raise DocumentationStructureError(f"Broken local link in {relative}: {target}")


def validate_required_docs(root: Path) -> None:
    for relative, required_headings in REQUIRED_DOCS.items():
        path = root / relative
        if not path.is_file():
            raise DocumentationStructureError(f"Missing required document: {relative}")

        content = path.read_text(encoding="utf-8")
        if not re.search(r"^#\s+\S", content, flags=re.MULTILINE):
            raise DocumentationStructureError(f"{relative} does not contain an H1")

        headings = markdown_headings(content)
        missing = [heading for heading in required_headings if heading not in headings]
        if missing:
            raise DocumentationStructureError(
                f"{relative} does not contain required sections: {', '.join(missing)}"
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
        validate_frontmatter(root, path, content)
        validate_links(root, path, content)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    try:
        validate_documentation_structure(args.root.resolve() if args.root else None)
        print("[OK] Technical documentation valid")
        return 0
    except DocumentationStructureError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
