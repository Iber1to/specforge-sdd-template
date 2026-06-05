#!/usr/bin/env python3
"""Ejecución determinista de Quality Gates configurables."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_PHASE_COMMANDS = {
    "implementation_fast": ["bash", "scripts/verify_fast.sh"],
    "qa_full": ["bash", "scripts/verify_full.sh"],
    "finalization": ["bash", "scripts/verify_full.sh"],
}


class QualityGateError(RuntimeError):
    """Un quality gate bloqueante falló."""


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_quality_gate_config(repo_root: Path) -> dict[str, Any]:
    config_path = repo_root / "state" / "quality-gates.json"

    if config_path.is_file():
        config = _load_json(config_path)
    else:
        config = {
            "schema_version": 1,
            "gates": [
                {
                    "id": f"GATE-{index:03d}",
                    "phase": phase,
                    "command": command,
                    "blocking": True,
                    "timeout_seconds": 900,
                }
                for index, (phase, command) in enumerate(DEFAULT_PHASE_COMMANDS.items(), start=1)
            ],
        }

    if not isinstance(config, dict):
        raise QualityGateError("quality-gates.json debe contener un objeto JSON")

    gates = config.get("gates", [])
    if not isinstance(gates, list):
        raise QualityGateError("quality-gates.json debe contener una lista gates")

    return config


def _phase_gates(config: dict[str, Any], phase: str) -> list[dict[str, Any]]:
    gates = [gate for gate in config.get("gates", []) if gate.get("phase") == phase]

    if gates:
        return gates

    default_command = DEFAULT_PHASE_COMMANDS.get(phase)
    if default_command is None:
        return []

    return [
        {
            "id": "GATE-001",
            "phase": phase,
            "command": default_command,
            "blocking": True,
            "timeout_seconds": 900,
        }
    ]


def _validate_gate(gate: dict[str, Any]) -> None:
    command = gate.get("command")

    if not isinstance(gate.get("id"), str) or not gate["id"]:
        raise QualityGateError("Cada gate requiere id")

    if (
        not isinstance(command, list)
        or not command
        or not all(isinstance(part, str) and part for part in command)
    ):
        raise QualityGateError(f"{gate['id']} requiere command como lista de strings")

    if not isinstance(gate.get("blocking", True), bool):
        raise QualityGateError(f"{gate['id']} requiere blocking booleano")

    timeout = gate.get("timeout_seconds", 900)
    if not isinstance(timeout, int) or timeout < 1:
        raise QualityGateError(f"{gate['id']} requiere timeout_seconds positivo")


def run_quality_gates(
    *,
    repo_root: Path,
    artifact_root: Path,
    feature_id: str,
    run_id: str,
    phase: str,
    raise_on_blocking: bool = True,
) -> dict[str, Any]:
    """Ejecuta los gates de una fase y escribe evidencia estructurada."""

    root = repo_root.resolve()
    output_root = artifact_root.resolve() / "quality-gates" / feature_id
    output_root.mkdir(parents=True, exist_ok=True)

    config = load_quality_gate_config(root)
    gates = _phase_gates(config, phase)
    results: list[dict[str, Any]] = []

    for gate in gates:
        _validate_gate(gate)
        gate_id = gate["id"]
        log_path = output_root / f"{run_id}-{phase}-{gate_id}.log"

        try:
            completed = subprocess.run(
                gate["command"],
                cwd=root,
                text=True,
                capture_output=True,
                timeout=gate.get("timeout_seconds", 900),
                check=False,
            )
            exit_code = completed.returncode
            stdout = completed.stdout
            stderr = completed.stderr
            timed_out = False
        except subprocess.TimeoutExpired as exc:
            exit_code = 124
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            timed_out = True

        log_path.write_text(stdout + "\n--- STDERR ---\n" + stderr, encoding="utf-8")

        results.append(
            {
                "id": gate_id,
                "phase": phase,
                "command": gate["command"],
                "blocking": gate.get("blocking", True),
                "exit_code": exit_code,
                "timed_out": timed_out,
                "log": str(log_path),
                "status": "PASS" if exit_code == 0 else "FAIL",
            }
        )

    blocking_failures = [
        result for result in results if result["blocking"] is True and result["exit_code"] != 0
    ]
    nonblocking_failures = [
        result for result in results if result["blocking"] is False and result["exit_code"] != 0
    ]

    status = "PASS"
    if blocking_failures:
        status = "FAIL"
    elif nonblocking_failures:
        status = "WARN"

    evidence_path = output_root / f"{run_id}-{phase}.json"

    evidence = {
        "schema_version": 1,
        "feature_id": feature_id,
        "run_id": run_id,
        "phase": phase,
        "status": status,
        "generated_at": utc_now(),
        "evidence": str(evidence_path),
        "gates": results,
    }

    evidence_path.write_text(
        json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    if blocking_failures and raise_on_blocking:
        failed_ids = ", ".join(result["id"] for result in blocking_failures)
        raise QualityGateError(f"Quality gates bloqueantes fallidos: {failed_ids}")

    return evidence
