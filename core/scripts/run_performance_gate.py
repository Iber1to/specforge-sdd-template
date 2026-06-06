#!/usr/bin/env python3
"""Ejecuta benchmarks simples y produce evidencia de performance-testing."""

from __future__ import annotations

import argparse
import statistics
import subprocess
import sys
import time

from capability_common import (
    CapabilityError,
    capability_policy,
    duration_seconds,
    ensure_policy_enabled,
    monotonic_seconds,
    operation_id,
    utc_now,
    write_capability_evidence,
)

CAPABILITY = "performance-testing"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature", required=True)
    parser.add_argument("--benchmark", required=True)
    parser.add_argument("--warmup-runs", type=int)
    parser.add_argument("--measured-runs", type=int)
    parser.add_argument("--timeout-seconds", type=int)
    parser.add_argument("--max-p95-ms", type=float)
    parser.add_argument("--command", nargs=argparse.REMAINDER)
    return parser.parse_args()


def benchmark_policy(policy: dict, benchmark_id: str) -> dict:
    for benchmark in policy.get("benchmarks", []):
        if benchmark.get("id") == benchmark_id:
            return benchmark

    raise CapabilityError(f"Benchmark no registrado: {benchmark_id}")


def percentile_95(values: list[float]) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    index = min(len(ordered) - 1, int(round((len(ordered) - 1) * 0.95)))
    return ordered[index]


def run_once(command: list[str], timeout_seconds: int) -> tuple[int, float, bool, str, str]:
    started = time.perf_counter()

    try:
        completed = subprocess.run(
            command,
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
        elapsed_ms = (time.perf_counter() - started) * 1000
        return completed.returncode, elapsed_ms, False, completed.stdout, completed.stderr
    except subprocess.TimeoutExpired as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000
        return 124, elapsed_ms, True, exc.stdout or "", exc.stderr or ""


def main() -> int:
    args = parse_arguments()
    operation = operation_id("PERF")

    try:
        policy = capability_policy(CAPABILITY)
        ensure_policy_enabled(policy, CAPABILITY)
        benchmark = benchmark_policy(policy, args.benchmark)

        command = args.command or benchmark.get("command")
        if not isinstance(command, list) or not command:
            raise CapabilityError("El benchmark requiere command como lista")

        warmup_runs = args.warmup_runs
        if warmup_runs is None:
            warmup_runs = int(benchmark.get("warmup_runs", 0))

        measured_runs = args.measured_runs
        if measured_runs is None:
            measured_runs = int(benchmark.get("measured_runs", 3))

        timeout_seconds = args.timeout_seconds
        if timeout_seconds is None:
            timeout_seconds = int(benchmark.get("timeout_seconds", 30))

        max_p95_ms = args.max_p95_ms
        if max_p95_ms is None and benchmark.get("max_p95_ms") is not None:
            max_p95_ms = float(benchmark["max_p95_ms"])

        if warmup_runs < 0 or measured_runs < 1:
            raise CapabilityError("warmup_runs debe ser >= 0 y measured_runs >= 1")

        started_at = utc_now()
        started = monotonic_seconds()
        checks: list[dict] = []

        for _ in range(warmup_runs):
            run_once(command, timeout_seconds)

        durations: list[float] = []
        failed_runs = 0
        timed_out_runs = 0
        last_stdout = ""
        last_stderr = ""

        for index in range(measured_runs):
            exit_code, elapsed_ms, timed_out, stdout, stderr = run_once(command, timeout_seconds)
            durations.append(elapsed_ms)
            last_stdout = stdout
            last_stderr = stderr

            if exit_code != 0:
                failed_runs += 1
            if timed_out:
                timed_out_runs += 1

            checks.append(
                {
                    "id": f"PERF-RUN-{index + 1:03d}",
                    "name": "measured run",
                    "status": "PASSED" if exit_code == 0 else "FAILED",
                    "exit_code": exit_code,
                    "duration_ms": round(elapsed_ms, 3),
                    "timed_out": timed_out,
                }
            )

        stats = {
            "runs": measured_runs,
            "min_ms": round(min(durations), 3),
            "median_ms": round(statistics.median(durations), 3),
            "p95_ms": round(percentile_95(durations), 3),
            "max_ms": round(max(durations), 3),
        }

        budget_failed = max_p95_ms is not None and stats["p95_ms"] > max_p95_ms
        status = "PASSED"
        if failed_runs or timed_out_runs or (budget_failed and policy.get("mode") == "enforce"):
            status = "FAILED"

        evidence = {
            "schema_version": 1,
            "feature_id": args.feature,
            "gate_id": CAPABILITY,
            "status": status,
            "started_at": started_at,
            "completed_at": utc_now(),
            "duration_seconds": duration_seconds(started),
            "scope": args.benchmark,
            "summary": "Performance benchmark completed",
            "checks": checks,
            "artifacts": [],
            "benchmark_id": args.benchmark,
            "command": command,
            "warmup_runs": warmup_runs,
            "measured_runs": measured_runs,
            "timeout_seconds": timeout_seconds,
            "max_p95_ms": max_p95_ms,
            "statistics": stats,
            "budget_failed": budget_failed,
            "failed_runs": failed_runs,
            "timed_out_runs": timed_out_runs,
            "stdout": last_stdout[-4000:],
            "stderr": last_stderr[-4000:],
        }

        evidence_path = write_capability_evidence(
            capability=CAPABILITY,
            feature_id=args.feature,
            operation=operation,
            evidence=evidence,
        )

        print(f"[OK] Performance: {evidence['status']}")
        print(f"[OK] p95_ms:      {stats['p95_ms']}")
        print(f"[OK] Evidencia:   {evidence_path}")
        return 0 if status == "PASSED" else 2

    except CapabilityError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
