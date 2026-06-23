#!/usr/bin/env python3
"""Preflight: verify that the local environment meets the harness requirements.

Exit code 0 if everything is correct; 2 if a mandatory requirement is missing.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

REQUIRED_PYTHON = (3, 12)


class CheckResult:
    def __init__(self) -> None:
        self.failures: list[str] = []
        self.lines: list[str] = []

    def record(self, ok: bool, label: str, detail: str = "") -> None:
        mark = "OK   " if ok else "MISS "
        suffix = f" - {detail}" if detail else ""
        self.lines.append(f"[{mark}] {label}{suffix}")
        if not ok:
            self.failures.append(label)

    def note(self, label: str, present: bool) -> None:
        mark = "OK  " if present else "n/a "
        self.lines.append(f"[{mark}] {label} (optional)")


def check_python(result: CheckResult) -> None:
    actual = sys.version_info[:2]
    detected = f"{actual[0]}.{actual[1]}"
    result.record(actual >= REQUIRED_PYTHON, "Python >= 3.12", f"detected {detected}")


def check_required_tool(result: CheckResult, tool: str) -> None:
    path = shutil.which(tool)
    result.record(path is not None, tool, path or "not found in PATH")


def check_optional_tool(result: CheckResult, tool: str) -> None:
    result.note(tool, shutil.which(tool) is not None)


def check_writable(result: CheckResult, label: str, path: Path) -> None:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".preflight-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        result.record(True, label, str(path))
    except OSError as exc:
        result.record(False, label, f"{path}: {exc}")


def check_project_paths(result: CheckResult, root: Path) -> None:
    config_path = root / "state" / "project.json"

    if not config_path.is_file():
        result.lines.append("[n/a ] state/project.json not present; operational paths skipped")
        return

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        result.record(False, "state/project.json readable", str(exc))
        return

    for key in ("data_root", "control_root", "artifact_root", "worktree_root"):
        value = config.get(key)
        if value:
            check_writable(result, f"write access to {key}", Path(str(value)).expanduser())


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=["generic", "python", "node"])
    parser.add_argument("--require-claude", action="store_true")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    result = CheckResult()

    check_python(result)
    for tool in ("git", "bash", "uv"):
        check_required_tool(result, tool)

    if args.profile == "node":
        check_required_tool(result, "node")
        check_required_tool(result, "npm")
    else:
        check_optional_tool(result, "node")

    if args.require_claude:
        check_required_tool(result, "claude")
    else:
        check_optional_tool(result, "claude")

    check_project_paths(result, args.root.expanduser().resolve())

    for line in result.lines:
        print(line)

    if result.failures:
        print(f"\n[ERROR] Missing requirements: {', '.join(result.failures)}", file=sys.stderr)
        return 2

    print("\n[OK] Environment ready.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
