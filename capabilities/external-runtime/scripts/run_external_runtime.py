#!/usr/bin/env python3
"""Run or validate an external-runtime job and produce evidence."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from capability_common import (
    CapabilityError,
    artifact_root,
    capability_policy,
    duration_seconds,
    ensure_policy_enabled,
    load_evidence,
    monotonic_seconds,
    operation_id,
    utc_now,
    validate_capability_evidence,
    write_capability_evidence,
)

CAPABILITY = "external-runtime"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature", required=True)
    parser.add_argument("--target", default="local")
    parser.add_argument("--scope", default="local-command")
    parser.add_argument("--result", type=Path, help="External manual-drop result to normalize.")
    parser.add_argument("--fetch-artifact", help="Optional remote path to copy with scp.")
    parser.add_argument(
        "--command-id",
        help="Identifier of a command template declared in the target policy.",
    )
    return parser.parse_args()


def target_policy(policy: dict, target_id: str) -> dict:
    for target in policy.get("targets", []):
        if target.get("id") == target_id:
            if target.get("enabled") is not True:
                raise CapabilityError(f"Disabled external-runtime target: {target_id}")
            return target

    raise CapabilityError(f"Unregistered external-runtime target: {target_id}")


def resolve_command_template(target: dict, command_id: str) -> tuple[list[str], int]:
    """Resolve a command template declared in the target policy."""

    templates = target.get("allowed_command_templates")

    if not isinstance(templates, list) or not templates:
        raise CapabilityError(f"Target '{target.get('id')}' defines no allowed_command_templates")

    for template in templates:
        if not isinstance(template, dict) or template.get("id") != command_id:
            continue

        command = template.get("command")
        if not isinstance(command, list) or not command:
            raise CapabilityError(f"Command template '{command_id}' defines no valid command")

        timeout = template.get("timeout_seconds", 60)
        if not isinstance(timeout, int) or timeout <= 0:
            raise CapabilityError(f"Command template '{command_id}' has an invalid timeout")

        return [str(part) for part in command], timeout

    raise CapabilityError(f"command-id not registered in target '{target.get('id')}': {command_id}")


def resolve_command(args: argparse.Namespace, target: dict) -> tuple[list[str], int, str | None]:
    """Determine the command to run.

    The only mode is --command-id against allowed_command_templates. There is no
    free-form command execution.
    """

    if not args.command_id:
        raise CapabilityError("You must provide --command-id; free-form commands are not allowed")

    command, timeout = resolve_command_template(target, args.command_id)
    return command, timeout, args.command_id


def normalize_manual_result(feature_id: str, result_path: Path) -> dict:
    result = load_evidence(result_path)
    status = result.get("status", "BLOCKED")

    evidence = {
        "schema_version": 1,
        "feature_id": feature_id,
        "gate_id": CAPABILITY,
        "status": status,
        "started_at": result.get("started_at") or utc_now(),
        "completed_at": result.get("completed_at") or utc_now(),
        "duration_seconds": int(result.get("duration_seconds", 0)),
        "scope": str(result.get("scope", "manual-drop")),
        "summary": str(result.get("summary", "External runtime manual result collected")),
        "checks": result.get("checks", []),
        "artifacts": result.get("artifacts", [str(result_path)]),
        "target": result.get("target"),
        "job_id": result.get("job_id"),
    }
    validate_capability_evidence(evidence, CAPABILITY, feature_id)
    return evidence


def run_local_command(
    *,
    feature_id: str,
    target: dict,
    command: list[str],
    timeout_seconds: int,
    scope: str,
    command_id: str | None,
) -> dict:
    if not command:
        raise CapabilityError("--command is required for local targets")

    started_at = utc_now()
    started = monotonic_seconds()

    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        timed_out = False
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = 124
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""

    status = "PASSED" if exit_code == 0 else "FAILED"

    return {
        "schema_version": 1,
        "feature_id": feature_id,
        "gate_id": CAPABILITY,
        "status": status,
        "started_at": started_at,
        "completed_at": utc_now(),
        "duration_seconds": duration_seconds(started),
        "scope": scope,
        "summary": "External runtime local command passed"
        if status == "PASSED"
        else "External runtime local command failed",
        "checks": [
            {
                "id": "EXT-LOCAL-001",
                "name": "local command",
                "status": status,
                "exit_code": exit_code,
                "timed_out": timed_out,
            }
        ],
        "artifacts": [],
        "target": target["id"],
        "target_type": target.get("type"),
        "command_id": command_id,
        "runtime_job_id": operation_id("EXT-JOB"),
        "command": command,
        "stdout": stdout[-4000:],
        "stderr": stderr[-4000:],
    }


def ssh_destination(target: dict) -> str:
    user = str(target.get("user", "")).strip()
    host = str(target.get("host", "")).strip()
    if not host:
        raise CapabilityError("SSH target requires host")
    return f"{user}@{host}" if user else host


def run_ssh_command(
    *,
    feature_id: str,
    target: dict,
    command: list[str],
    timeout_seconds: int,
    scope: str,
    fetch_artifact: str | None,
    command_id: str | None,
) -> dict:
    if not command:
        raise CapabilityError("--command is required for SSH targets")

    if shutil.which("ssh") is None:
        raise CapabilityError("The ssh binary does not exist in PATH")

    port = str(target.get("port", 22))
    destination = ssh_destination(target)
    connect_timeout = str(min(int(target.get("connect_timeout_seconds", 10)), timeout_seconds))
    ssh_command = [
        "ssh",
        "-p",
        port,
        "-o",
        "BatchMode=yes",
        "-o",
        f"ConnectTimeout={connect_timeout}",
        destination,
        *command,
    ]
    started_at = utc_now()
    started = monotonic_seconds()
    runtime_job_id = operation_id("EXT-JOB")

    try:
        completed = subprocess.run(
            ssh_command,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        timed_out = False
        exit_code = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = 124
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""

    artifacts = []
    if fetch_artifact and exit_code == 0:
        if shutil.which("scp") is None:
            raise CapabilityError("The scp binary does not exist in PATH")
        output_dir = artifact_root() / "capabilities" / CAPABILITY / feature_id / "remote-artifacts"
        output_dir.mkdir(parents=True, exist_ok=True)
        local_artifact = output_dir / f"{runtime_job_id}-{Path(fetch_artifact).name}"
        scp_result = subprocess.run(
            ["scp", "-P", port, f"{destination}:{fetch_artifact}", str(local_artifact)],
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        if scp_result.returncode != 0:
            status = "FAILED"
            stderr += "\nSCP failed:\n" + scp_result.stderr
            exit_code = scp_result.returncode
        else:
            artifacts.append(str(local_artifact))

    status = "PASSED" if exit_code == 0 else "FAILED"

    return {
        "schema_version": 1,
        "feature_id": feature_id,
        "gate_id": CAPABILITY,
        "status": status,
        "started_at": started_at,
        "completed_at": utc_now(),
        "duration_seconds": duration_seconds(started),
        "scope": scope,
        "summary": "External runtime SSH command passed"
        if status == "PASSED"
        else "External runtime SSH command failed",
        "checks": [
            {
                "id": "EXT-SSH-001",
                "name": "ssh command",
                "status": status,
                "exit_code": exit_code,
                "timed_out": timed_out,
            }
        ],
        "artifacts": artifacts,
        "target": target["id"],
        "target_type": target.get("type"),
        "command_id": command_id,
        "runtime_job_id": runtime_job_id,
        "command": ssh_command,
        "stdout": stdout[-4000:],
        "stderr": stderr[-4000:],
    }


def main() -> int:
    args = parse_arguments()
    operation = operation_id("EXT")

    try:
        policy = capability_policy(CAPABILITY)
        ensure_policy_enabled(policy, CAPABILITY)
        target = target_policy(policy, args.target)

        if args.result is not None:
            evidence = normalize_manual_result(args.feature, args.result)
        elif target.get("type") == "local":
            command, timeout_seconds, command_id = resolve_command(args, target)
            evidence = run_local_command(
                feature_id=args.feature,
                target=target,
                command=command,
                timeout_seconds=timeout_seconds,
                scope=args.scope,
                command_id=command_id,
            )
        elif target.get("type") == "ssh":
            command, timeout_seconds, command_id = resolve_command(args, target)
            evidence = run_ssh_command(
                feature_id=args.feature,
                target=target,
                command=command,
                timeout_seconds=timeout_seconds,
                scope=args.scope,
                fetch_artifact=args.fetch_artifact,
                command_id=command_id,
            )
        else:
            raise CapabilityError(f"Target {args.target} requires a manual result with --result")

        evidence_path = write_capability_evidence(
            capability=CAPABILITY,
            feature_id=args.feature,
            operation=operation,
            evidence=evidence,
        )

        print(f"[OK] External runtime: {evidence['status']}")
        print(f"[OK] Evidence:         {evidence_path}")
        return 0 if evidence["status"] == "PASSED" else 2

    except CapabilityError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
