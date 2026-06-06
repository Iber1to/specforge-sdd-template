#!/usr/bin/env python3
"""Deterministic project generator for the Agentic SDD template."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent
PROFILES = {"generic", "python", "node"}
CAPABILITIES = {
    "external-runtime",
    "git-publish",
    "mutation-testing",
    "performance-testing",
    "security-scanning",
    "windows-validation",
}
GIT_PUBLICATION_MODES = {"disabled", "local", "dry_run", "push"}


def parse_scalar(value: str) -> Any:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        raw_items = value[1:-1].strip()
        if not raw_items:
            return []
        return [item.strip().strip("'\"") for item in raw_items.split(",")]
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False
    return value.strip("'\"")


def load_simple_yaml(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = {}

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line:
            continue
        if ":" not in line:
            raise ValueError(f"Invalid config line: {raw_line}")
        key, value = line.split(":", 1)
        data[key.strip()] = parse_scalar(value)

    return data


def validate_config(config: dict[str, Any]) -> dict[str, Any]:
    required = {"project_id", "name", "output_path", "profile"}
    missing = sorted(required - set(config))
    if missing:
        raise ValueError("Missing required config keys: " + ", ".join(missing))

    profile = str(config["profile"])
    if profile not in PROFILES:
        raise ValueError(f"Unsupported profile: {profile}")

    capabilities = config.get("capabilities", [])
    if not isinstance(capabilities, list):
        raise ValueError("capabilities must be an inline list")

    unknown = sorted(set(capabilities) - CAPABILITIES)
    if unknown:
        raise ValueError("Unsupported capabilities: " + ", ".join(unknown))

    return {
        "project_id": str(config["project_id"]),
        "name": str(config["name"]),
        "output_path": str(config["output_path"]),
        "profile": profile,
        "capabilities": capabilities,
        "git_publish_mode": str(config.get("git_publish_mode", "local")),
        "git_publish_remote": str(config.get("git_publish_remote", "origin")),
        "git_publish_branch": str(config.get("git_publish_branch", "main")),
        "git_publish_auto": bool(config.get("git_publish_auto", False)),
    }


def ignore_generated(directory: str, names: list[str]) -> set[str]:
    return {
        name
        for name in names
        if name == "__pycache__" or name.endswith(".pyc") or name in {".pytest_cache", ".ruff_cache"}
    }


def copy_core(output: Path) -> None:
    core = ROOT / "core"

    for child in core.iterdir():
        destination = output / child.name
        if child.is_dir():
            shutil.copytree(child, destination, ignore=ignore_generated)
        else:
            shutil.copy2(child, destination)

    (output / ".gitignore").write_text(
        "__pycache__/\n*.pyc\n.pytest_cache/\n.ruff_cache/\n.venv/\nnode_modules/\n",
        encoding="utf-8",
    )


def write_project_state(output: Path, config: dict[str, Any]) -> None:
    project_id = config["project_id"]
    data_root = output.parent / "data" / project_id
    git_publish_enabled = "git-publish" in config["capabilities"]
    git_publish_mode = config["git_publish_mode"]

    if git_publish_mode not in GIT_PUBLICATION_MODES:
        raise ValueError(f"Unsupported git_publish_mode: {git_publish_mode}")

    if not git_publish_enabled:
        git_publish_mode = "disabled"

    state = {
        "schema_version": 1,
        "project_id": project_id,
        "name": config["name"],
        "workflow": "spec-driven-development",
        "lifecycle_phase": "BOOTSTRAP",
        "canonical_host": "generated",
        "canonical_repository": str(output),
        "worktree_root": str(output.parent / "worktrees" / project_id),
        "data_root": str(data_root),
        "control_root": str(data_root / "control"),
        "artifact_root": str(data_root / "artifacts"),
        "maximum_active_implementers": 1,
        "windows_validation_required": "windows-validation" in config["capabilities"],
        "canonical_branch": "main",
        "implementation_branch_prefix": "feature",
        "lease_ttl_minutes": 720,
        "profile": config["profile"],
        "capabilities": config["capabilities"],
        "git_publication": {
            "enabled": git_publish_enabled,
            "mode": git_publish_mode,
            "remote": config["git_publish_remote"],
            "branch": config["git_publish_branch"],
            "auto_publish_on_done": config["git_publish_auto"],
            "require_merged_head": True,
        },
    }

    (output / "state" / "project.json").write_text(
        json.dumps(state, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    control_root = Path(state["control_root"])
    for directory in ("locks", "leases", "runs", "agent-metrics", "role-sessions"):
        (control_root / directory).mkdir(parents=True, exist_ok=True)

    (control_root / "queue.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_id": project_id,
                "updated_at": None,
                "features": [],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (control_root / "runtime.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "project_id": project_id,
                "active_feature": None,
                "active_runs": [],
                "last_completed_run": None,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    Path(state["artifact_root"]).mkdir(parents=True, exist_ok=True)


def write_python_smoke(output: Path) -> None:
    (output / "src").mkdir(exist_ok=True)
    (output / "tests" / "unit").mkdir(parents=True, exist_ok=True)
    (output / "tests" / "unit" / "test_harness_smoke.py").write_text(
        "def test_generated_project_has_harness() -> None:\n    assert True\n",
        encoding="utf-8",
    )


def apply_profile(output: Path, profile: str) -> None:
    write_python_smoke(output)

    if profile == "generic":
        (output / "README.md").write_text("# Generated Generic Project\n", encoding="utf-8")
        return

    if profile == "python":
        package = output.name.replace("-", "_")
        (output / "src" / package).mkdir(parents=True)
        (output / "src" / package / "__init__.py").write_text('VERSION = "0.1.0"\n', encoding="utf-8")
        (output / "tests" / "unit" / "test_profile_smoke.py").write_text(
            f"from src.{package} import VERSION\n\n\ndef test_version() -> None:\n    assert VERSION\n",
            encoding="utf-8",
        )
        return

    if profile == "node":
        (output / "src").mkdir(exist_ok=True)
        (output / "tests").mkdir(exist_ok=True)
        (output / "package.json").write_text(
            json.dumps(
                {
                    "type": "module",
                    "scripts": {
                        "test": "node --test",
                        "lint": "node --check src/index.js tests/index.test.js",
                        "format:check": "node --check src/index.js tests/index.test.js"
                    },
                    "devDependencies": {
                        "eslint": "^9.0.0",
                        "prettier": "^3.0.0"
                    }
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (output / "src" / "index.js").write_text("export const version = '0.1.0';\n", encoding="utf-8")
        (output / "tests" / "index.test.js").write_text(
            "import test from 'node:test';\nimport assert from 'node:assert/strict';\nimport { version } from '../src/index.js';\n\ntest('exports version', () => {\n  assert.equal(version, '0.1.0');\n});\n",
            encoding="utf-8",
        )
        gates_path = output / "state" / "quality-gates.json"
        gates = json.loads(gates_path.read_text(encoding="utf-8"))
        gates["gates"].extend(
            [
                {
                    "id": "GATE-004",
                    "phase": "implementation_fast",
                    "command": ["npm", "test"],
                    "blocking": True,
                    "timeout_seconds": 300,
                },
                {
                    "id": "GATE-005",
                    "phase": "qa_full",
                    "command": ["npm", "test"],
                    "blocking": True,
                    "timeout_seconds": 300,
                },
                {
                    "id": "GATE-006",
                    "phase": "qa_full",
                    "command": ["npm", "run", "lint"],
                    "blocking": True,
                    "timeout_seconds": 300,
                },
                {
                    "id": "GATE-007",
                    "phase": "finalization",
                    "command": ["npm", "test"],
                    "blocking": True,
                    "timeout_seconds": 300,
                },
            ]
        )
        gates_path.write_text(json.dumps(gates, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def initialize_git(output: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=output, check=True, text=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Agentic Template"], cwd=output, check=True)
    subprocess.run(["git", "config", "user.email", "agentic-template@example.invalid"], cwd=output, check=True)
    subprocess.run(["git", "add", "."], cwd=output, check=True)
    subprocess.run(["git", "commit", "-m", "chore: initialize generated project"], cwd=output, check=True, text=True, capture_output=True)


def create_project(config: dict[str, Any]) -> Path:
    output = Path(config["output_path"]).expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"Output path already exists: {output}")
    output.mkdir(parents=True)

    copy_core(output)
    write_project_state(output, config)
    apply_profile(output, config["profile"])
    initialize_git(output)
    return output


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    config = validate_config(load_simple_yaml(Path(args.config)))
    output = create_project(config)
    print(f"[OK] Created project: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
