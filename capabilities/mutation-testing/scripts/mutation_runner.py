#!/usr/bin/env python3
"""Runner determinista mínimo de Mutation Testing para código Python."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
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


def _mutate_source(source: str, mutant: dict[str, Any]) -> str:
    lines = source.splitlines(keepends=True)
    index = int(mutant["line"]) - 1
    line = lines[index]
    column = int(mutant["column"]) - 1
    original = str(mutant["original"])
    replacement = str(mutant["replacement"])

    if line[column : column + len(original)] != original:
        raise ValueError(f"Mutant {mutant['id']} no longer matches source")

    lines[index] = line[:column] + replacement + line[column + len(original) :]
    return "".join(lines)


def run_mutation_testing(
    *,
    repo_root: Path,
    feature_id: str,
    test_command: list[str],
    max_mutants: int,
    max_duration_seconds: int,
) -> dict[str, Any]:
    """Genera mutantes, ejecuta tests por mutante y restaura archivos."""

    root = repo_root.resolve()
    mutants = collect_python_mutants(root, max_mutants=max_mutants)

    for mutant in mutants:
        path = root / str(mutant["file"])
        original_source = path.read_text(encoding="utf-8")

        try:
            path.write_text(_mutate_source(original_source, mutant), encoding="utf-8")
            completed = subprocess.run(
                test_command,
                cwd=root,
                text=True,
                capture_output=True,
                timeout=max_duration_seconds,
                check=False,
            )
            mutant["test_command"] = test_command
            mutant["test_exit_code"] = completed.returncode
            mutant["status"] = "survived" if completed.returncode == 0 else "killed"
        except (subprocess.TimeoutExpired, ValueError) as exc:
            mutant["test_command"] = test_command
            mutant["test_exit_code"] = 124 if isinstance(exc, subprocess.TimeoutExpired) else 2
            mutant["status"] = "invalid"
            mutant["error"] = str(exc)
        finally:
            path.write_text(original_source, encoding="utf-8")

    return {
        "schema_version": 1,
        "feature_id": feature_id,
        "scope": "changed_code",
        "max_mutants": max_mutants,
        "max_duration_seconds": max_duration_seconds,
        "test_command": test_command,
        "generated_at": utc_now(),
        "summary": {
            "generated": len(mutants),
            "killed": len([mutant for mutant in mutants if mutant["status"] == "killed"]),
            "survived": len([mutant for mutant in mutants if mutant["status"] == "survived"]),
            "invalid": len([mutant for mutant in mutants if mutant["status"] == "invalid"]),
        },
        "mutants": mutants,
    }


def build_evidence(repo_root: Path, feature_id: str, *, max_mutants: int) -> dict[str, Any]:
    return run_mutation_testing(
        repo_root=repo_root,
        feature_id=feature_id,
        test_command=["python3", "-m", "pytest", "-q"],
        max_mutants=max_mutants,
        max_duration_seconds=600,
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-mutants", type=int, default=100)
    parser.add_argument("--max-duration-seconds", type=int, default=600)
    parser.add_argument(
        "--test-command",
        nargs="+",
        default=["python3", "-m", "pytest", "-q"],
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    evidence = run_mutation_testing(
        repo_root=Path.cwd(),
        feature_id=arguments.feature,
        test_command=arguments.test_command,
        max_mutants=arguments.max_mutants,
        max_duration_seconds=arguments.max_duration_seconds,
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
