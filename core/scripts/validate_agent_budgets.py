#!/usr/bin/env python3
"""Validate the budget policy and its consistency with the agents."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml

REQUIRED_ROLES = {
    "leader",
    "specifier",
    "architect",
    "implementer",
    "qa-reviewer",
    "mutation-reviewer",
    "repository-publisher",
}


class BudgetValidationError(RuntimeError):
    """Invalid budget policy."""


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise BudgetValidationError(f"Does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise BudgetValidationError(f"Invalid JSON in {path}: {exc}") from exc

    if not isinstance(value, dict):
        raise BudgetValidationError(f"{path} must contain a JSON object")

    return value


def load_agent(path: Path) -> dict[str, Any]:
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise BudgetValidationError(f"Agent does not exist: {path}") from exc

    if not content.startswith("---\n"):
        raise BudgetValidationError(f"Invalid frontmatter: {path}")

    try:
        _, frontmatter, _ = content.split("---", 2)
    except ValueError as exc:
        raise BudgetValidationError(f"Incomplete frontmatter: {path}") from exc

    value = yaml.safe_load(frontmatter)

    if not isinstance(value, dict):
        raise BudgetValidationError(f"Invalid frontmatter: {path}")

    return value


def validate_policy(root: Path) -> None:
    policy = load_json(root / "state" / "agent-budgets.json")

    if policy.get("schema_version") != 1:
        raise BudgetValidationError("schema_version must be 1")

    if policy.get("mode") != "observe":
        raise BudgetValidationError("The initial policy must remain in observe mode")

    roles = policy.get("roles")

    if not isinstance(roles, dict):
        raise BudgetValidationError("roles must be an object")

    detected_roles = set(roles)

    if detected_roles != REQUIRED_ROLES:
        raise BudgetValidationError(
            f"Incorrect roles: expected={sorted(REQUIRED_ROLES)}, received={sorted(detected_roles)}"
        )

    for role in sorted(REQUIRED_ROLES):
        budget = roles[role]

        if not isinstance(budget, dict):
            raise BudgetValidationError(f"Invalid budget for {role}")

        for field in (
            "max_turns",
            "max_duration_seconds",
            "max_total_tokens",
        ):
            value = budget.get(field)

            if not isinstance(value, int) or value <= 0:
                raise BudgetValidationError(f"{role}.{field} must be a positive integer")

        agent = load_agent(root / ".claude" / "agents" / f"{role}.md")

        comparisons = {
            "name": role,
            "model": budget.get("model"),
            "effort": budget.get("effort"),
            "maxTurns": budget["max_turns"],
        }

        for field, expected in comparisons.items():
            received = agent.get(field)

            if received != expected:
                raise BudgetValidationError(
                    f"{role}.{field}: expected={expected!r}, received={received!r}"
                )

        print(
            f"[OK] {role:<14} "
            f"turns={budget['max_turns']:<3} "
            f"duration={budget['max_duration_seconds']:<4}s "
            f"tokens={budget['max_total_tokens']}"
        )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_arguments()

    try:
        validate_policy(arguments.repo_root.resolve())
        print("[OK] Agent policy consistent")
        return 0

    except BudgetValidationError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
