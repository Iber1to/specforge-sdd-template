#!/usr/bin/env python3
"""Run a deterministic local security scan and produce normalized evidence."""

from __future__ import annotations

import argparse
import fnmatch
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from capability_common import (
    CapabilityError,
    capability_policy,
    duration_seconds,
    ensure_policy_enabled,
    load_project_config,
    monotonic_seconds,
    operation_id,
    repo_root,
    utc_now,
    write_capability_evidence,
)

CAPABILITY = "security-scanning"

DEFAULT_EXCLUDES = {
    ".git",
    ".venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
}

SECRET_PATTERNS = (
    (
        "SEC-SECRET-PRIVATE-KEY",
        "critical",
        "secret",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ),
    ("SEC-SECRET-AWS", "critical", "secret", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "SEC-SECRET-GENERIC",
        "high",
        "secret",
        re.compile(r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"][^'\"]{12,}['\"]"),
    ),
)

SENSITIVE_PATTERNS = (
    ".env",
    "*.pem",
    "*.key",
    "id_rsa",
)

# Adapters per profile (T-009D). Rules apply only to the project profile.
PROFILE_CODE_PATTERNS = {
    "python": (
        ("SEC-PY-EVAL", "high", "code-exec", re.compile(r"(?<![\w.])eval\s*\(")),
        ("SEC-PY-EXEC", "high", "code-exec", re.compile(r"(?<![\w.])exec\s*\(")),
        ("SEC-PY-PICKLE", "medium", "deserialization", re.compile(r"\bpickle\.loads?\s*\(")),
        ("SEC-PY-OS-SYSTEM", "high", "command-injection", re.compile(r"\bos\.system\s*\(")),
        ("SEC-PY-SHELL-TRUE", "high", "command-injection", re.compile(r"shell\s*=\s*True\b")),
    ),
}

NODE_INSTALL_HOOK = re.compile(
    r"\"(?:preinstall|install|postinstall)\"\s*:\s*\"[^\"]*(?:curl|wget|\|\s*sh)[^\"]*\""
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feature", required=True)
    parser.add_argument("--path", type=Path, default=Path("."))
    parser.add_argument("--scope", default="repository")
    return parser.parse_args()


def should_exclude(path: Path, root: Path, policy: dict) -> bool:
    relative = path.relative_to(root)
    parts = set(relative.parts)

    if parts & DEFAULT_EXCLUDES:
        return True

    for pattern in policy.get("exclude_globs", []):
        if fnmatch.fnmatch(str(relative), pattern):
            return True

    return False


def text_files(root: Path, scan_root: Path, policy: dict) -> list[Path]:
    files: list[Path] = []

    for path in scan_root.rglob("*"):
        if path.is_dir() or should_exclude(path, root, policy):
            continue

        if path.stat().st_size > int(policy.get("max_file_bytes", 1_000_000)):
            continue

        files.append(path)

    return files


def redacted(value: str) -> str:
    if len(value) <= 8:
        return "***"
    return value[:4] + "***" + value[-4:]


def finding(
    *,
    finding_id: str,
    severity: str,
    category: str,
    path: Path,
    line: int,
    description: str,
    recommendation: str,
    sample: str | None = None,
) -> dict:
    result = {
        "id": finding_id,
        "severity": severity,
        "category": category,
        "path": str(path),
        "line": line,
        "description": description,
        "recommendation": recommendation,
    }

    if sample is not None:
        result["sample"] = redacted(sample.strip())

    return result


def accepted_finding(policy: dict, item: dict) -> dict | None:
    accepted = policy.get("accepted_findings", [])
    if not isinstance(accepted, list):
        return None

    for entry in accepted:
        if not isinstance(entry, dict):
            continue

        if entry.get("id") != item.get("id"):
            continue

        if entry.get("path") != item.get("path"):
            continue

        if "line" in entry and entry.get("line") != item.get("line"):
            continue

        return entry

    return None


def acceptance_expired(entry: dict) -> bool:
    expires_at = entry.get("expires_at")
    if not isinstance(expires_at, str) or not expires_at:
        return False

    try:
        moment = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return True

    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)

    return moment <= datetime.now(timezone.utc)


def apply_baseline(policy: dict, findings: list[dict]) -> list[dict]:
    classified: list[dict] = []

    for item in findings:
        result = dict(item)
        accepted = accepted_finding(policy, result)

        if accepted is None:
            result["baseline_status"] = "new"
        elif acceptance_expired(accepted):
            result["baseline_status"] = "expired"
            result["classification"] = str(accepted.get("classification", "accepted"))
            result["accepted_reason"] = str(accepted.get("reason", "expired baseline acceptance"))
        else:
            result["baseline_status"] = "accepted"
            result["classification"] = str(accepted.get("classification", "accepted"))
            result["accepted_reason"] = str(accepted.get("reason", "accepted baseline finding"))

        classified.append(result)

    return classified


def profile_findings(profile: str, relative: Path, content: str) -> list[dict]:
    results: list[dict] = []

    if profile == "python" and relative.suffix == ".py" and relative.parts[:1] == ("src",):
        for line_number, line in enumerate(content.splitlines(), start=1):
            for finding_id, severity, category, pattern in PROFILE_CODE_PATTERNS["python"]:
                if pattern.search(line):
                    results.append(
                        finding(
                            finding_id=finding_id,
                            severity=severity,
                            category=category,
                            path=relative,
                            line=line_number,
                            description="Profile-specific risky pattern detected",
                            recommendation="Review and avoid the risky construct",
                        )
                    )

    if profile == "node" and relative.name == "package.json":
        for line_number, line in enumerate(content.splitlines(), start=1):
            if NODE_INSTALL_HOOK.search(line):
                results.append(
                    finding(
                        finding_id="SEC-NODE-INSTALL-HOOK",
                        severity="high",
                        category="supply-chain",
                        path=relative,
                        line=line_number,
                        description="Suspicious npm lifecycle hook detected",
                        recommendation="Review preinstall/install/postinstall scripts",
                    )
                )

    return results


def scan_file(path: Path, relative: Path, profile: str) -> list[dict]:
    findings: list[dict] = []

    if any(fnmatch.fnmatch(relative.name, pattern) for pattern in SENSITIVE_PATTERNS):
        findings.append(
            finding(
                finding_id="SEC-SENSITIVE-FILE",
                severity="critical",
                category="secret",
                path=relative,
                line=1,
                description="Sensitive file is present in the repository",
                recommendation="Remove the file from Git and rotate any contained credentials",
            )
        )

    try:
        content = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return findings

    for line_number, line in enumerate(content.splitlines(), start=1):
        for finding_id, severity, category, pattern in SECRET_PATTERNS:
            match = pattern.search(line)
            if match:
                findings.append(
                    finding(
                        finding_id=finding_id,
                        severity=severity,
                        category=category,
                        path=relative,
                        line=line_number,
                        description="Potential secret detected by deterministic pattern",
                        recommendation="Remove the secret and rotate the credential if real",
                        sample=match.group(0),
                    )
                )

    findings.extend(profile_findings(profile, relative, content))

    return findings


def summarize(findings: list[dict]) -> dict[str, int]:
    summary = {
        "critical": 0,
        "high": 0,
        "medium": 0,
        "low": 0,
        "accepted": 0,
        "new": 0,
        "expired": 0,
    }

    for item in findings:
        severity = item.get("severity")
        if severity in summary:
            summary[severity] += 1
        baseline_status = item.get("baseline_status")
        if baseline_status in {"accepted", "new", "expired"}:
            summary[baseline_status] += 1

    return summary


def main() -> int:
    args = parse_arguments()
    operation = operation_id("SEC")

    try:
        policy = capability_policy(CAPABILITY)
        ensure_policy_enabled(policy, CAPABILITY)

        root = repo_root()
        scan_root = (root / args.path).resolve()

        if not scan_root.exists():
            raise CapabilityError(f"Security scan scope does not exist: {scan_root}")

        profile = str(load_project_config().get("profile", "generic"))
        started_at = utc_now()
        started = monotonic_seconds()
        findings: list[dict] = []

        for path in text_files(root, scan_root, policy):
            findings.extend(scan_file(path, path.relative_to(root), profile))

        findings = apply_baseline(policy, findings)
        summary = summarize(findings)
        fail_on = set(policy.get("fail_on", []))
        new_findings = [item for item in findings if item.get("baseline_status") != "accepted"]
        blocked = any(item.get("severity") in fail_on for item in new_findings)
        status = "FAILED" if blocked and policy.get("mode") == "enforce" else "PASSED"

        evidence = {
            "schema_version": 1,
            "feature_id": args.feature,
            "gate_id": CAPABILITY,
            "status": status,
            "started_at": started_at,
            "completed_at": utc_now(),
            "duration_seconds": duration_seconds(started),
            "scope": args.scope,
            "summary": "Security scan completed",
            "checks": [
                {
                    "id": "SEC-001",
                    "name": "deterministic secret scan",
                    "status": status,
                    "findings": len(findings),
                    "new_findings": len(new_findings),
                    "accepted_findings": summary["accepted"],
                    "mode": policy.get("mode"),
                }
            ],
            "artifacts": [],
            "security_summary": summary,
            "findings": findings,
            "mode": policy.get("mode"),
            "fail_on": sorted(fail_on),
            "blocked_by_new_findings": blocked,
        }

        evidence_path = write_capability_evidence(
            capability=CAPABILITY,
            feature_id=args.feature,
            operation=operation,
            evidence=evidence,
        )

        print(f"[OK] Security scan: {evidence['status']}")
        print(f"[OK] Findings:      {len(findings)}")
        print(f"[OK] Evidence:      {evidence_path}")
        return 0 if status == "PASSED" else 2

    except CapabilityError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
