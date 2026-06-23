#!/usr/bin/env python3
"""Inicia una ejecución de implementación y crea su worktree aislado."""

from __future__ import annotations

import argparse
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from control_common import (
    ControlPlaneError,
    apply_transition,
    atomic_write_json,
    control_paths,
    find_feature,
    load_json,
    load_project_config,
    load_queue,
    load_runtime,
    queue_lock,
    save_queue,
    save_runtime,
    utc_now,
    validate_transition,
)
from run_metrics import initialize_run_metrics
from worktree_common import (
    ensure_canonical_repository,
    ensure_implementation_worktree,
    remove_worktree,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--feature", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--reason", default="Implementación iniciada")

    return parser.parse_args()


def create_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    suffix = uuid.uuid4().hex[:8]
    return f"RUN-{timestamp}-{suffix}"


def expiration_time(ttl_minutes: int) -> str:
    expiration = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
    return expiration.isoformat(timespec="seconds")


def find_conflicting_implementer_lease(
    leases_root: Path,
    feature_id: str,
) -> tuple[Path, dict[str, Any]] | None:
    """Devuelve el primer lease de implementer ajeno presente en ``leases_root``.

    Replica la semántica de enumeración de ``role_guard.active_lease()``: itera
    ``sorted(leases_root.glob("F-*.json"))`` (orden determinista), ignora los
    archivos ilegibles o corruptos (ASM-001) y no consulta ``expires_at`` ni el
    estado de la feature propietaria (DEC-001). Un lease cuenta como conflicto
    cuando ``role == "implementer"`` y su ``feature_id`` es distinto del
    solicitado, incluyendo el caso en que ``feature_id`` está ausente
    (conservador). Devuelve ``(ruta, lease)`` del primer conflicto o ``None``.
    """

    for path in sorted(leases_root.glob("F-*.json")):
        try:
            lease = load_json(path)
        except ControlPlaneError:
            continue

        if lease.get("role") == "implementer" and lease.get("feature_id") != feature_id:
            return path, lease

    return None


def main() -> int:
    arguments = parse_arguments()

    worktree = None
    worktree_created = False

    try:
        ensure_canonical_repository()

        with queue_lock():
            config = load_project_config()
            paths = control_paths()
            queue = load_queue()
            runtime = load_runtime()
            feature = find_feature(queue, arguments.feature)

            if feature["state"] not in {
                "READY_FOR_DEVELOPMENT",
                "CHANGES_REQUESTED",
            }:
                raise ControlPlaneError(
                    f"{feature['id']} no puede iniciarse desde el estado {feature['state']}"
                )

            max_qa_attempts = int(config.get("maximum_qa_attempts", 3))
            qa_attempts = int(feature.get("qa_attempts", 0))

            if qa_attempts >= max_qa_attempts:
                raise ControlPlaneError(
                    f"{feature['id']} agoto los {max_qa_attempts} intentos de QA "
                    f"(qa_attempts={qa_attempts}). Escala a decision humana en lugar "
                    "de reintentar: revisa alcance, especificacion o arquitectura."
                )

            lease_path = paths["leases"] / f"{feature['id']}.json"

            if lease_path.exists():
                raise ControlPlaneError(
                    f"Ya existe un lease activo para {feature['id']}: {lease_path}"
                )

            conflict = find_conflicting_implementer_lease(paths["leases"], feature["id"])

            if conflict is not None:
                conflict_path, conflict_lease = conflict
                conflict_feature = conflict_lease.get("feature_id", "desconocida")
                raise ControlPlaneError(
                    f"No se puede iniciar {feature['id']}: existe un lease de "
                    f"implementer activo de {conflict_feature} en {conflict_path}. "
                    "Libera el lease por la vía operativa "
                    "(scripts/recover_stale_leases.py) antes de reintentar."
                )

            validate_transition(feature, "IN_PROGRESS", "implementer")

            worktree, branch, worktree_created, resynced = ensure_implementation_worktree(feature)

            canonical_branch = config.get("canonical_branch", "main")

            run_id = create_run_id()
            timestamp = utc_now()
            ttl_minutes = int(config.get("lease_ttl_minutes", 720))

            lease = {
                "schema_version": 1,
                "feature_id": feature["id"],
                "run_id": run_id,
                "agent_id": arguments.agent_id,
                "role": "implementer",
                "branch": branch,
                "worktree": str(worktree),
                "acquired_at": timestamp,
                "heartbeat_at": timestamp,
                "expires_at": expiration_time(ttl_minutes),
            }

            run = {
                "schema_version": 1,
                "run_id": run_id,
                "feature_id": feature["id"],
                "agent_id": arguments.agent_id,
                "role": "implementer",
                "status": "ACTIVE",
                "branch": branch,
                "worktree": str(worktree),
                "started_at": timestamp,
                "updated_at": timestamp,
                "metrics": initialize_run_metrics(
                    runs_root=paths["runs"],
                    feature_id=feature["id"],
                    role="implementer",
                    started_at=timestamp,
                ),
            }

            atomic_write_json(paths["runs"] / f"{run_id}.json", run)
            atomic_write_json(lease_path, lease)

            apply_transition(
                queue=queue,
                runtime=runtime,
                feature=feature,
                target_state="IN_PROGRESS",
                role="implementer",
                reason=arguments.reason,
            )

            runtime.setdefault("active_runs", []).append(run_id)

            save_queue(queue)
            save_runtime(runtime)

        print(f"[OK] Feature:  {feature['id']}")
        print(f"[OK] Run:      {run_id}")
        print(f"[OK] Rama:     {branch}")
        print(f"[OK] Worktree: {worktree}")
        print(f"[OK] Lease:    {lease_path}")

        if resynced:
            print(f"[INFO] Resync:  merge de '{canonical_branch}' en '{branch}' aplicado")

        return 0

    except ControlPlaneError as exc:
        if worktree_created and worktree is not None:
            try:
                remove_worktree(worktree)
            except ControlPlaneError:
                pass

        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
