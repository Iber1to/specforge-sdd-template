#!/usr/bin/env python3
"""Runner determinista mínimo de Mutation Testing para código Python."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

MUTATION_PATTERNS = (
    ("==", "!="),
    ("!=", "=="),
    (">=", "<"),
    ("<=", ">"),
    (">", "<="),
    ("<", ">="),
    ("and", "or"),
    ("or", "and"),
    ("True", "False"),
    ("False", "True"),
    ("+", "-"),
    ("-", "+"),
    ("*", "//"),
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _token_pattern(token: str) -> re.Pattern[str]:
    if token.isidentifier():
        return re.compile(rf"\b{re.escape(token)}\b")

    return re.compile(re.escape(token))


def generate_mutants(path: str, source: str, *, max_mutants: int) -> list[dict[str, Any]]:
    """Genera mutantes deterministas por orden de línea y patrón."""

    mutants: list[dict[str, Any]] = []

    for line_number, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        for original, replacement in MUTATION_PATTERNS:
            match = _token_pattern(original).search(line)
            if match is None:
                continue

            mutant_id = f"MUT-{len(mutants) + 1:03d}"
            mutants.append(
                {
                    "id": mutant_id,
                    "file": path,
                    "line": line_number,
                    "column": match.start() + 1,
                    "operator": f"{original}->{replacement}",
                    "original": original,
                    "replacement": replacement,
                    "status": "not_run",
                }
            )

            if len(mutants) >= max_mutants:
                return mutants

    return mutants


def collect_python_mutants(repo_root: Path, *, max_mutants: int) -> list[dict[str, Any]]:
    mutants: list[dict[str, Any]] = []

    for path in sorted((repo_root / "src").rglob("*.py")):
        relative = path.relative_to(repo_root).as_posix()
        remaining = max_mutants - len(mutants)
        if remaining <= 0:
            break
        mutants.extend(
            generate_mutants(relative, path.read_text(encoding="utf-8"), max_mutants=remaining)
        )

    return mutants


def build_evidence(repo_root: Path, feature_id: str, *, max_mutants: int) -> dict[str, Any]:
    mutants = collect_python_mutants(repo_root, max_mutants=max_mutants)

    return {
        "schema_version": 1,
        "feature_id": feature_id,
        "scope": "changed_code",
        "max_mutants": max_mutants,
        "generated_at": utc_now(),
        "summary": {
            "generated": len(mutants),
            "survived": len([mutant for mutant in mutants if mutant["status"] == "survived"]),
        },
        "mutants": mutants,
    }


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-mutants", type=int, default=100)
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    evidence = build_evidence(
        Path.cwd(),
        arguments.feature,
        max_mutants=arguments.max_mutants,
    )

    output_path = Path(arguments.output).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"[OK] Mutantes generados: {evidence['summary']['generated']}")
    print(f"[OK] Evidencia: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
