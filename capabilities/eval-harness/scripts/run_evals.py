#!/usr/bin/env python3
"""Run a feature's graders (eval-harness) and produce normalized evidence."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from capability_common import (
    CapabilityError,
    capability_policy,
    duration_seconds,
    ensure_policy_enabled,
    monotonic_seconds,
    operation_id,
    repo_root,
    utc_now,
    write_capability_evidence,
)

CAPABILITY = "eval-harness"
GATE_TYPES = {"code", "rule"}
ADVISORY_TYPES = {"model", "human"}
RULE_KINDS = {"file_exists", "file_absent", "file_contains"}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature", required=True)
    parser.add_argument("--scope", default="repository")
    parser.add_argument("--evals", type=Path, default=None)
    return parser.parse_args()


def load_graders(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise CapabilityError(f"Graders file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise CapabilityError(f"Invalid graders JSON in {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise CapabilityError(f"The graders file must be a JSON object: {path}")

    graders = data.get("graders")
    if not isinstance(graders, list):
        raise CapabilityError("The graders file must contain 'graders' as a list")

    return graders


def run_code_grader(command: list, runs: int, timeout: int, root: Path) -> int:
    if not all(isinstance(part, str) for part in command):
        raise CapabilityError("The grader command must be a list of strings")

    successes = 0
    for _ in range(runs):
        try:
            result = subprocess.run(
                command,
                cwd=str(root),
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except FileNotFoundError as exc:
            raise CapabilityError(f"Grader command not found: {command[0]}") from exc
        except subprocess.TimeoutExpired:
            continue
        if result.returncode == 0:
            successes += 1

    return successes


def evaluate_rule(rule: dict, root: Path) -> bool:
    kind = rule.get("kind")
    path = rule.get("path")

    if kind not in RULE_KINDS:
        raise CapabilityError(f"unsupported rule kind: {kind}")
    if not isinstance(path, str) or not path:
        raise CapabilityError("rule requires 'path' as a string")

    target = root / path

    if kind == "file_exists":
        return target.is_file()
    if kind == "file_absent":
        return not target.exists()

    pattern = rule.get("pattern")
    if not isinstance(pattern, str) or not pattern:
        raise CapabilityError("file_contains requires 'pattern'")
    if not target.is_file():
        return False
    try:
        content = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    return re.search(pattern, content) is not None


def main() -> int:
    args = parse_arguments()
    operation = operation_id("EVAL")

    try:
        policy = capability_policy(CAPABILITY)
        ensure_policy_enabled(policy, CAPABILITY)

        root = repo_root()
        mode = policy.get("mode")
        runs = max(1, int(policy.get("runs", 1)))
        timeout = int(policy.get("grader_timeout_seconds", 300))
        pass_at_k_min = float(policy.get("pass_at_k_min", 1.0))
        require_caret_release = bool(
            policy.get("require_pass_caret_k_for_release_critical", True)
        )

        evals_path = args.evals or (
            root / "specs" / "features" / args.feature / "evals.json"
        )
        graders = load_graders(evals_path)

        started_at = utc_now()
        started = monotonic_seconds()

        checks: list[dict] = []
        passed = 0
        failed = 0
        advisory = 0
        gate_failures = 0
        scenarios_all: set = set()
        scenarios_gated: set = set()

        for grader in graders:
            grader_id = grader.get("id")
            if not grader_id:
                raise CapabilityError("Each grader requires 'id'")

            grader_type = grader.get("type")
            scenario = grader.get("scenario")
            gate = bool(grader.get("gate", grader_type in GATE_TYPES))
            release_critical = bool(grader.get("release_critical", False))

            if isinstance(scenario, str) and scenario:
                scenarios_all.add(scenario)

            if grader_type in ADVISORY_TYPES:
                advisory += 1
                checks.append(
                    {
                        "id": grader_id,
                        "scenario": scenario,
                        "type": grader_type,
                        "status": "SKIPPED",
                        "gate": False,
                        "release_critical": release_critical,
                        "runs": 0,
                        "successes": 0,
                        "pass_at_k": None,
                        "pass_caret_k": None,
                        "note": "advisory: does not decide the automatic gate",
                    }
                )
                continue

            if grader_type == "code":
                command = grader.get("command")
                if not isinstance(command, list) or not command:
                    raise CapabilityError(
                        f"{grader_id}: code grader requires 'command' as a list"
                    )
                runs_executed = runs
                successes = run_code_grader(command, runs, timeout, root)
            elif grader_type == "rule":
                rule = grader.get("rule")
                if not isinstance(rule, dict):
                    raise CapabilityError(
                        f"{grader_id}: rule grader requires 'rule' as an object"
                    )
                runs_executed = 1
                successes = 1 if evaluate_rule(rule, root) else 0
            else:
                raise CapabilityError(
                    f"{grader_id}: unsupported grader type: {grader_type}"
                )

            pass_at_k = successes >= 1
            pass_caret_k = runs_executed > 0 and successes == runs_executed
            ratio = successes / runs_executed if runs_executed else 0.0

            if gate:
                if release_critical and require_caret_release:
                    required_ok = pass_caret_k
                else:
                    required_ok = pass_at_k and ratio >= pass_at_k_min
                if isinstance(scenario, str) and scenario:
                    scenarios_gated.add(scenario)
                if required_ok:
                    passed += 1
                else:
                    failed += 1
                    gate_failures += 1
                status = "PASSED" if required_ok else "FAILED"
            else:
                advisory += 1
                status = "PASSED" if pass_at_k else "FAILED"

            checks.append(
                {
                    "id": grader_id,
                    "scenario": scenario,
                    "type": grader_type,
                    "status": status,
                    "gate": gate,
                    "release_critical": release_critical,
                    "runs": runs_executed,
                    "successes": successes,
                    "pass_at_k": pass_at_k,
                    "pass_caret_k": pass_caret_k,
                }
            )

        unverifiable = sorted(scenarios_all - scenarios_gated)
        blocked = gate_failures > 0
        status = "FAILED" if blocked and mode == "enforce" else "PASSED"

        evidence = {
            "schema_version": 1,
            "feature_id": args.feature,
            "gate_id": CAPABILITY,
            "status": status,
            "started_at": started_at,
            "completed_at": utc_now(),
            "duration_seconds": duration_seconds(started),
            "scope": args.scope,
            "summary": "Eval harness completed",
            "checks": checks,
            "artifacts": [],
            "graders": checks,
            "eval_summary": {
                "total": len(graders),
                "gate_eligible": passed + failed,
                "passed": passed,
                "failed": failed,
                "advisory": advisory,
                "unverifiable_scenarios": unverifiable,
            },
            "metrics": {
                "runs_per_grader": runs,
                "pass_at_k_min": pass_at_k_min,
                "require_pass_caret_k_for_release_critical": require_caret_release,
            },
            "mode": mode,
            "blocked_by_gate_failures": blocked,
        }

        evidence_path = write_capability_evidence(
            capability=CAPABILITY,
            feature_id=args.feature,
            operation=operation,
            evidence=evidence,
        )

        print(f"[OK] Eval harness:  {status}")
        print(f"[OK] Graders gate:  {passed} passed / {failed} failed")
        print(f"[OK] Advisory:      {advisory}")
        if unverifiable:
            print(f"[WARN] Scenarios without a gate grader: {', '.join(unverifiable)}")
        print(f"[OK] Evidence:      {evidence_path}")
        return 0 if status == "PASSED" else 2

    except CapabilityError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
