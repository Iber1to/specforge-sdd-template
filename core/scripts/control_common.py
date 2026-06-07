#!/usr/bin/env python3
"""Funciones compartidas del plano de control agéntico."""

from __future__ import annotations

import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

try:  # POSIX
    import fcntl
except ModuleNotFoundError:  # pragma: no cover - Windows u otra plataforma sin fcntl
    fcntl = None  # type: ignore[assignment]

try:  # Windows
    import msvcrt
except ModuleNotFoundError:  # pragma: no cover - plataformas POSIX
    msvcrt = None  # type: ignore[assignment]

FEATURE_ID_PATTERN = re.compile(r"^F-(\d{3,})$")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class ControlPlaneError(RuntimeError):
    """Error controlado del plano de control."""


def repo_root() -> Path:
    override = os.environ.get("DOA_REPO_ROOT")

    if override:
        return Path(override).expanduser().resolve()

    return Path(__file__).resolve().parents[1]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(path: Path) -> dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
    except FileNotFoundError as exc:
        raise ControlPlaneError(f"No existe el archivo requerido: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ControlPlaneError(f"JSON inválido en {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise ControlPlaneError(f"El contenido de {path} debe ser un objeto JSON")

    return data


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        text=True,
    )

    temporary_path = Path(temporary_name)

    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())

        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def resolve_config_path(value: str) -> Path:
    path = Path(value).expanduser()

    if path.is_absolute():
        return path.resolve()

    return (repo_root() / path).resolve()


def load_project_config() -> dict[str, Any]:
    return load_json(repo_root() / "state" / "project.json")


def load_workflow() -> dict[str, Any]:
    return load_json(repo_root() / "state" / "workflow.json")


def control_paths() -> dict[str, Path]:
    config = load_project_config()
    control_root = resolve_config_path(config["control_root"])

    return {
        "control_root": control_root,
        "queue": control_root / "queue.json",
        "runtime": control_root / "runtime.json",
        "locks": control_root / "locks",
        "leases": control_root / "leases",
        "runs": control_root / "runs",
    }


def _acquire_file_lock(handle: Any, *, exclusive: bool) -> None:
    """Adquiere un bloqueo de archivo de forma portable.

    Usa fcntl en POSIX y msvcrt en Windows. En Windows el bloqueo es siempre
    exclusivo (msvcrt no distingue compartido), suficiente para el runner local.
    """

    if fcntl is not None:
        mode = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        fcntl.flock(handle.fileno(), mode)
        return

    if msvcrt is not None:
        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        return

    raise ControlPlaneError("No hay mecanismo de bloqueo de archivos disponible en esta plataforma")


def _release_file_lock(handle: Any) -> None:
    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
        return

    if msvcrt is not None:
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass


@contextmanager
def queue_lock(*, exclusive: bool = True) -> Iterator[None]:
    paths = control_paths()
    paths["locks"].mkdir(parents=True, exist_ok=True)
    lock_path = paths["locks"] / "queue.lock"

    with lock_path.open("a+", encoding="utf-8") as handle:
        _acquire_file_lock(handle, exclusive=exclusive)

        try:
            yield
        finally:
            _release_file_lock(handle)


def load_queue() -> dict[str, Any]:
    queue = load_json(control_paths()["queue"])
    features = queue.get("features")

    if not isinstance(features, list):
        raise ControlPlaneError("queue.json debe contener una lista 'features'")

    return queue


def save_queue(queue: dict[str, Any]) -> None:
    queue["updated_at"] = utc_now()
    atomic_write_json(control_paths()["queue"], queue)


def load_runtime() -> dict[str, Any]:
    return load_json(control_paths()["runtime"])


def save_runtime(runtime: dict[str, Any]) -> None:
    atomic_write_json(control_paths()["runtime"], runtime)


def validate_feature_id(feature_id: str) -> None:
    if not FEATURE_ID_PATTERN.fullmatch(feature_id):
        raise ControlPlaneError(f"Identificador inválido '{feature_id}'. Formato esperado: F-001")


def validate_slug(slug: str) -> None:
    if not SLUG_PATTERN.fullmatch(slug):
        raise ControlPlaneError("El slug solo puede contener minúsculas, números y guiones")


def find_feature(queue: dict[str, Any], feature_id: str) -> dict[str, Any]:
    validate_feature_id(feature_id)

    for feature in queue["features"]:
        if feature.get("id") == feature_id:
            return feature

    raise ControlPlaneError(f"No existe la feature {feature_id}")


def ensure_nonempty_file(path: Path, label: str) -> None:
    if not path.is_file():
        raise ControlPlaneError(f"Falta {label}: {path}")

    if path.stat().st_size == 0:
        raise ControlPlaneError(f"{label} está vacío: {path}")


def mutation_testing_required(feature: dict[str, Any]) -> bool:
    capabilities = feature.get("capabilities", [])
    return isinstance(capabilities, list) and "mutation-testing" in capabilities


def validate_evidence_for_transition(
    feature: dict[str, Any],
    current_state: str,
    target_state: str,
) -> None:
    if __package__:
        from .feature_validation import (
            FeatureValidationError,
            validate_architecture,
            validate_development_readiness,
            validate_specification,
        )
        from .review_validation import (
            ReviewValidationError,
            validate_review_evidence,
        )
    else:
        from feature_validation import (
            FeatureValidationError,
            validate_architecture,
            validate_development_readiness,
            validate_specification,
        )
        from review_validation import (
            ReviewValidationError,
            validate_review_evidence,
        )

    root = repo_root()
    feature_id = feature["id"]
    transition = (current_state, target_state)

    try:
        if transition == ("DRAFT", "SPEC_READY"):
            validate_specification(root, feature)

        elif transition == ("SPEC_READY", "DESIGN_READY"):
            validate_architecture(root, feature)

        elif transition == ("DESIGN_READY", "READY_FOR_DEVELOPMENT"):
            validate_development_readiness(root, feature)

    except FeatureValidationError as exc:
        raise ControlPlaneError(str(exc)) from exc

    if transition == ("IN_PROGRESS", "READY_FOR_QA"):
        evidence_path = root / "evidence" / "implementations" / f"{feature_id}.json"

        ensure_nonempty_file(evidence_path, "evidencia de implementación")
        evidence = load_json(evidence_path)

        if evidence.get("feature_id") != feature_id:
            raise ControlPlaneError(f"La evidencia de implementación no corresponde a {feature_id}")

    if transition in {
        ("READY_FOR_QA", "APPROVED"),
        ("READY_FOR_QA", "CHANGES_REQUESTED"),
    }:
        try:
            review = validate_review_evidence(
                root,
                feature,
                expected_verdict=target_state,
            )
        except ReviewValidationError as exc:
            raise ControlPlaneError(str(exc)) from exc

        lease_path = control_paths()["leases"] / f"{feature_id}.json"
        lease = load_json(lease_path)

        if lease.get("role") != "qa-reviewer":
            raise ControlPlaneError(f"El lease activo de {feature_id} no pertenece a QA")

        if review.get("run_id") != lease.get("run_id"):
            raise ControlPlaneError("El informe QA no corresponde al run activo")

        if review.get("reviewer_id") != lease.get("agent_id"):
            raise ControlPlaneError("El informe QA no corresponde al revisor asignado")

        if review.get("reviewed_commit") != lease.get("reviewed_commit"):
            raise ControlPlaneError("El informe QA no corresponde al commit asignado")

        if target_state == "APPROVED" and mutation_testing_required(feature):
            if __package__:
                from .mutation_review_validation import (
                    MutationReviewValidationError,
                    validate_mutation_review_evidence,
                )
            else:
                from mutation_review_validation import (
                    MutationReviewValidationError,
                    validate_mutation_review_evidence,
                )

            try:
                validate_mutation_review_evidence(root, feature)
            except MutationReviewValidationError as exc:
                raise ControlPlaneError(str(exc)) from exc


ROLE_TRANSITIONS: dict[str, set[tuple[str, str]]] = {
    "specifier": {
        ("DRAFT", "SPEC_READY"),
        ("SPEC_READY", "DRAFT"),
    },
    "architect": {
        ("SPEC_READY", "DESIGN_READY"),
        ("DESIGN_READY", "SPEC_READY"),
        ("DESIGN_READY", "READY_FOR_DEVELOPMENT"),
    },
    "implementer": {
        ("READY_FOR_DEVELOPMENT", "IN_PROGRESS"),
        ("IN_PROGRESS", "READY_FOR_QA"),
        ("CHANGES_REQUESTED", "IN_PROGRESS"),
    },
    "qa-reviewer": {
        ("READY_FOR_QA", "CHANGES_REQUESTED"),
        ("READY_FOR_QA", "APPROVED"),
        ("APPROVED", "CHANGES_REQUESTED"),
    },
}


def validate_role_for_transition(
    role: str,
    current_state: str,
    target_state: str,
) -> None:
    if role == "leader":
        if target_state == "BLOCKED" or current_state == "BLOCKED":
            return

        raise ControlPlaneError("El leader solo puede bloquear o recuperar features bloqueadas")

    permitted = ROLE_TRANSITIONS.get(role, set())

    if (current_state, target_state) not in permitted:
        raise ControlPlaneError(
            f"El rol '{role}' no puede realizar {current_state} -> {target_state}"
        )


def validate_transition(
    feature: dict[str, Any],
    target_state: str,
    role: str,
) -> None:
    current_state = feature["state"]

    if target_state == "DONE":
        raise ControlPlaneError("La transición a DONE está reservada a scripts/finalize_feature.py")

    workflow = load_workflow()
    transitions = workflow.get("transitions", {})
    allowed_targets = transitions.get(current_state, [])

    if target_state not in allowed_targets:
        raise ControlPlaneError(f"Transición no permitida: {current_state} -> {target_state}")

    validate_role_for_transition(role, current_state, target_state)
    validate_evidence_for_transition(feature, current_state, target_state)


def apply_transition(
    queue: dict[str, Any],
    runtime: dict[str, Any],
    feature: dict[str, Any],
    target_state: str,
    role: str,
    reason: str,
) -> None:
    """Aplica en memoria una transición previamente validada."""

    validate_transition(feature, target_state, role)

    current_state = feature["state"]
    config = load_project_config()

    if target_state == "IN_PROGRESS":
        active_implementations = [
            item
            for item in queue["features"]
            if item["state"] == "IN_PROGRESS" and item["id"] != feature["id"]
        ]

        maximum = int(config["maximum_active_implementers"])

        if len(active_implementations) >= maximum:
            raise ControlPlaneError("Se ha alcanzado el máximo de implementadores activos")

    timestamp = utc_now()

    feature["state"] = target_state
    feature["updated_at"] = timestamp
    feature.setdefault("history", []).append(
        {
            "timestamp": timestamp,
            "action": "TRANSITION",
            "actor_role": role,
            "from": current_state,
            "to": target_state,
            "reason": reason,
        }
    )

    if target_state == "BLOCKED":
        feature["blocked_from"] = current_state

    if current_state == "BLOCKED":
        feature.pop("blocked_from", None)

    if target_state == "IN_PROGRESS":
        runtime["active_feature"] = feature["id"]

    if (
        current_state == "IN_PROGRESS"
        and target_state != "IN_PROGRESS"
        and runtime.get("active_feature") == feature["id"]
    ):
        runtime["active_feature"] = None

    if target_state == "BLOCKED" and runtime.get("active_feature") == feature["id"]:
        runtime["active_feature"] = None


def parse_utc_timestamp(value: str) -> datetime:
    """Convierte un timestamp ISO-8601 en datetime UTC."""

    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ControlPlaneError(f"Timestamp inválido: {value}") from exc

    if timestamp.tzinfo is None:
        raise ControlPlaneError(f"El timestamp no contiene zona horaria: {value}")

    return timestamp.astimezone(timezone.utc)


def lease_is_expired(lease: dict[str, Any]) -> bool:
    """Indica si un lease ha superado su fecha de expiración."""

    expires_at = lease.get("expires_at")

    if not isinstance(expires_at, str):
        raise ControlPlaneError("El lease no contiene expires_at válido")

    return parse_utc_timestamp(expires_at) <= datetime.now(timezone.utc)
