#!/usr/bin/env python3
"""Runner minimo para generar evidencia Windows compatible con el harness."""

from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

from control_common import ControlPlaneError, atomic_write_json, load_project_config, repo_root
from windows_validation import WindowsEvidenceValidationError, validate_windows_evidence


def utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature", required=True)
    parser.add_argument("--commit")
    parser.add_argument("--runner-id", default="windows-runner-minimal")
    parser.add_argument("--workspace", type=Path, default=Path.cwd())
    parser.add_argument(
        "--allow-non-windows",
        action="store_true",
        help="Permite ejecutar smoke tests de infraestructura fuera de Windows.",
    )
    return parser.parse_args()


def git_head(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )

    if result.returncode != 0:
        raise ControlPlaneError(result.stderr.strip() or result.stdout.strip())

    return result.stdout.strip()


def check(status: bool, check_id: str, name: str, details: str | None = None) -> dict:
    result = {
        "id": check_id,
        "name": name,
        "status": "PASS" if status else "FAIL",
    }

    if details:
        result["details"] = details

    return result


def main() -> int:
    args = parse_arguments()

    try:
        root = repo_root()
        config = load_project_config()
        commit = args.commit or git_head(root)
        artifact_root = Path(config["artifact_root"]).resolve()
        evidence_root = artifact_root / "windows-tests" / args.feature
        evidence_root.mkdir(parents=True, exist_ok=True)

        log_path = evidence_root / "runner.log"
        artifact_path = evidence_root / "environment.json"

        system = platform.system()
        is_windows = system == "Windows"
        platform_ok = is_windows or args.allow_non_windows
        workspace = args.workspace.resolve()

        started_at = utc_now()
        checks = [
            check(
                platform_ok,
                "WIN-001",
                "Windows platform available",
                f"platform={system}; allow_non_windows={args.allow_non_windows}",
            ),
            check(True, "WIN-002", "Python available", sys.version.split()[0]),
            check(workspace.exists(), "WIN-003", "Workspace exists", str(workspace)),
        ]

        environment = {
            "platform": system,
            "python": sys.version,
            "workspace": str(workspace),
            "tested_commit": commit,
        }
        artifact_path.write_text(json.dumps(environment, indent=2) + "\n", encoding="utf-8")
        checks.append(check(artifact_path.is_file(), "WIN-004", "Artifact write"))

        status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
        log_path.write_text(
            "\n".join(
                [
                    f"runner_id={args.runner_id}",
                    f"feature_id={args.feature}",
                    f"tested_commit={commit}",
                    f"status={status}",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        evidence = {
            "schema_version": 1,
            "feature_id": args.feature,
            "runner_id": args.runner_id,
            "host": platform.node() or "unknown-host",
            "status": status,
            "tested_commit": commit,
            "started_at": started_at,
            "completed_at": utc_now(),
            "checks": checks,
            "log": str(log_path),
            "artifacts": [str(artifact_path)],
            "metrics": {
                "checks": len(checks),
            },
        }

        evidence_path = evidence_root / "latest.json"
        atomic_write_json(evidence_path, evidence)

        validate_windows_evidence(
            repo_root=root,
            artifact_root=artifact_root,
            feature={"id": args.feature, "windows_validation_required": True},
            expected_commit=commit,
            evidence_path=evidence_path,
        )

        print(f"[OK] Windows evidence: {status}")
        print(f"[OK] Evidencia:        {evidence_path}")
        return 0 if status == "PASS" else 2

    except (ControlPlaneError, WindowsEvidenceValidationError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
