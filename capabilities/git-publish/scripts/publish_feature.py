#!/usr/bin/env python3
"""Publica una feature finalizada en Git local o remoto con evidencia auditada."""

from __future__ import annotations

import argparse
import hashlib
import re
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from control_common import (
    ControlPlaneError,
    atomic_write_json,
    find_feature,
    load_project_config,
    load_queue,
    queue_lock,
    repo_root,
    save_queue,
    utc_now,
)
from worktree_common import current_branch, ensure_clean_repository, run_git

PUBLICATION_MODES = {"configured", "disabled", "local", "dry_run", "push"}


class GitPublicationError(ControlPlaneError):
    """Error controlado durante la publicacion Git."""


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--feature", required=True)
    parser.add_argument(
        "--mode",
        choices=sorted(PUBLICATION_MODES),
        default="configured",
        help="Modo de publicacion. 'configured' usa state/project.json.",
    )
    parser.add_argument("--remote", help="Remote Git a usar para dry_run o push.")
    parser.add_argument("--branch", help="Rama remota/canonica a publicar.")
    parser.add_argument(
        "--reason",
        default="Feature finalizada publicada por el harness",
    )

    return parser.parse_args()


def create_operation_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"GIT-PUBLISH-{timestamp}-{uuid.uuid4().hex[:8]}"


def git_head(repository: Path) -> str:
    return run_git(repository, "rev-parse", "HEAD").stdout.strip()


def is_ancestor(repository: Path, ancestor: str, descendant: str) -> bool:
    result = run_git(
        repository,
        "merge-base",
        "--is-ancestor",
        ancestor,
        descendant,
        check=False,
    )

    return result.returncode == 0


def sanitize_remote_url(remote_url: str) -> str:
    return re.sub(r"://[^/@]+@", "://***@", remote_url)


def redact_sensitive_text(value: str) -> str:
    redacted = re.sub(r"://[^/@\s]+@", "://***@", value)
    redacted = re.sub(r"\bAKIA[0-9A-Z]{16}\b", "AKIA***REDACTED", redacted)
    redacted = re.sub(
        r"(?i)\b(api[_-]?key|secret|token|password)\b\s*[:=]\s*['\"]?[^'\"\s]{8,}",
        r"\1=***",
        redacted,
    )
    return redacted


def hash_remote_url(value: str | None) -> str | None:
    """Hash estable del remote para auditar sin exponer la URL ni credenciales."""

    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def publication_config(
    project: dict[str, Any],
    *,
    mode_override: str,
    remote_override: str | None,
    branch_override: str | None,
) -> dict[str, Any]:
    configured = project.get("git_publication", {})

    if configured is None:
        configured = {}

    if not isinstance(configured, dict):
        raise GitPublicationError("state/project.json contiene git_publication invalido")

    capabilities = project.get("capabilities", [])
    capability_enabled = isinstance(capabilities, list) and "git-publish" in capabilities

    enabled = bool(configured.get("enabled", capability_enabled))
    configured_mode = str(configured.get("mode", "local" if enabled else "disabled"))
    mode = configured_mode if mode_override == "configured" else mode_override

    if mode not in PUBLICATION_MODES - {"configured"}:
        raise GitPublicationError(f"Modo de publicacion Git no soportado: {mode}")

    if not enabled and mode_override == "configured":
        mode = "disabled"

    return {
        "enabled": enabled,
        "mode": mode,
        "remote": remote_override or str(configured.get("remote", "origin")),
        "branch": branch_override
        or str(configured.get("branch", project.get("canonical_branch", "main"))),
        "require_merged_head": bool(configured.get("require_merged_head", True)),
    }


def validate_feature_ready(
    *,
    repository: Path,
    canonical_branch: str,
    feature: dict[str, Any],
    require_merged_head: bool,
) -> tuple[str, str]:
    if feature.get("state") != "DONE":
        raise GitPublicationError(
            f"{feature.get('id')} debe estar en DONE antes de publicar; "
            f"estado actual: {feature.get('state')}"
        )

    merged_commit = str(feature.get("merged_commit", "")).strip()
    if not merged_commit:
        raise GitPublicationError(f"{feature.get('id')} no contiene merged_commit")

    head = git_head(repository)

    if not is_ancestor(repository, merged_commit, head):
        raise GitPublicationError("El merged_commit de la feature no pertenece al HEAD canonico")

    if require_merged_head and head != merged_commit:
        raise GitPublicationError(
            "El HEAD canonico contiene commits posteriores a la feature; "
            "publica la ultima feature o desactiva require_merged_head"
        )

    branch = current_branch(repository)
    if branch != canonical_branch:
        raise GitPublicationError(
            f"El repositorio canonico debe estar en {canonical_branch}; rama actual: {branch}"
        )

    return merged_commit, head


def remote_url(repository: Path, remote: str) -> str:
    result = run_git(repository, "remote", "get-url", remote, check=False)

    if result.returncode != 0:
        raise GitPublicationError(f"No existe el remote Git requerido: {remote}")

    return sanitize_remote_url(result.stdout.strip())


def run_publication(
    *,
    repository: Path,
    mode: str,
    remote: str,
    branch: str,
) -> tuple[int, str, str, str | None]:
    if mode == "disabled":
        return 0, "git-publish disabled", "", None

    if mode == "local":
        return 0, "local Git integration recorded", "", None

    sanitized_remote = remote_url(repository, remote)
    target = f"HEAD:refs/heads/{branch}"
    command = ["push", remote, target]

    if mode == "dry_run":
        command.insert(1, "--dry-run")

    result = run_git(repository, *command, check=False)
    return result.returncode, result.stdout, result.stderr, sanitized_remote


def status_for_mode(mode: str) -> str:
    return {
        "disabled": "DISABLED",
        "local": "LOCAL_RECORDED",
        "dry_run": "DRY_RUN",
        "push": "PUBLISHED",
    }[mode]


def write_publication_evidence(
    *,
    artifact_root: Path,
    feature_id: str,
    operation_id: str,
    evidence: dict[str, Any],
) -> Path:
    output_root = artifact_root / "git-publish" / feature_id
    output_root.mkdir(parents=True, exist_ok=True)

    evidence_path = output_root / f"{operation_id}.json"
    latest_path = output_root / "latest.json"

    atomic_write_json(evidence_path, evidence)
    shutil.copy2(evidence_path, latest_path)

    return evidence_path


def main() -> int:
    args = parse_arguments()
    operation_id = create_operation_id()
    started_at = utc_now()

    try:
        project = load_project_config()
        root = repo_root()
        canonical = Path(project["canonical_repository"]).resolve()
        canonical_branch = str(project.get("canonical_branch", "main"))
        artifact_root = Path(project["artifact_root"]).resolve()

        if root != canonical or Path.cwd().resolve() != canonical:
            raise GitPublicationError(
                "La publicacion debe ejecutarse desde el repositorio canonico"
            )

        ensure_clean_repository(canonical)

        config = publication_config(
            project,
            mode_override=args.mode,
            remote_override=args.remote,
            branch_override=args.branch,
        )

        with queue_lock(exclusive=False):
            queue = load_queue()
            feature = find_feature(queue, args.feature)
            merged_commit, published_commit = validate_feature_ready(
                repository=canonical,
                canonical_branch=canonical_branch,
                feature=feature,
                require_merged_head=config["require_merged_head"],
            )

        exit_code, stdout, stderr, remote = run_publication(
            repository=canonical,
            mode=config["mode"],
            remote=config["remote"],
            branch=config["branch"],
        )

        status = "PASS" if exit_code == 0 else "FAIL"
        timestamp = utc_now()

        evidence = {
            "schema_version": 1,
            "operation_id": operation_id,
            "feature_id": args.feature,
            "source_branch": canonical_branch,
            "status": status,
            "publication_status": status_for_mode(config["mode"]) if status == "PASS" else "FAILED",
            "mode": config["mode"],
            "remote": config["remote"],
            "remote_url": redact_sensitive_text(remote or "") if remote is not None else None,
            "remote_url_hash": hash_remote_url(remote),
            "branch": config["branch"],
            "merged_commit": merged_commit,
            "published_commit": published_commit,
            "exit_code": exit_code,
            "stdout": redact_sensitive_text(stdout),
            "stderr": redact_sensitive_text(stderr),
            "reason": args.reason,
            "started_at": started_at,
            "completed_at": timestamp,
            "created_at": timestamp,
        }

        evidence_path = write_publication_evidence(
            artifact_root=artifact_root,
            feature_id=args.feature,
            operation_id=operation_id,
            evidence=evidence,
        )

        if status != "PASS":
            raise GitPublicationError(f"La publicacion Git fallo. Evidencia: {evidence_path}")

        with queue_lock():
            queue = load_queue()
            feature = find_feature(queue, args.feature)

            if feature.get("state") != "DONE":
                raise GitPublicationError("El estado cambio durante la publicacion")

            feature["git_publication"] = {
                "status": evidence["publication_status"],
                "mode": config["mode"],
                "remote": config["remote"],
                "branch": config["branch"],
                "published_commit": published_commit,
                "evidence": str(evidence_path),
                "updated_at": timestamp,
            }
            feature.setdefault("history", []).append(
                {
                    "timestamp": timestamp,
                    "action": "GIT_PUBLISHED",
                    "actor_role": "repository-publisher",
                    "publication_status": evidence["publication_status"],
                    "mode": config["mode"],
                    "remote": config["remote"],
                    "branch": config["branch"],
                    "reason": args.reason,
                    "evidence": str(evidence_path),
                }
            )

            save_queue(queue)

        print(f"[OK] Feature:             {args.feature}")
        print(f"[OK] Publicacion Git:     {evidence['publication_status']}")
        print(f"[OK] Commit publicado:    {published_commit}")
        print(f"[OK] Evidencia:           {evidence_path}")

        return 0

    except (ControlPlaneError, GitPublicationError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
