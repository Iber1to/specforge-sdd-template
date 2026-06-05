#!/usr/bin/env python3
"""Registra una nueva feature en estado DRAFT."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from control_common import (
    FEATURE_ID_PATTERN,
    ControlPlaneError,
    load_project_config,
    load_queue,
    queue_lock,
    repo_root,
    save_queue,
    utc_now,
    validate_slug,
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    parser.add_argument("--title", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--description", required=True)
    parser.add_argument("--priority", type=int, default=100)
    parser.add_argument("--requested-by", default="user")
    parser.add_argument(
        "--change-domain",
        choices=["product", "harness", "template"],
        default="product",
        help="Dominio de cambio que controla permisos de mantenimiento.",
    )
    parser.add_argument(
        "--capability",
        action="append",
        choices=["mutation-testing"],
        default=[],
        help="Capability opcional requerida por la feature.",
    )
    parser.add_argument(
        "--windows-validation-required",
        action=argparse.BooleanOptionalAction,
        default=None,
    )

    return parser.parse_args()


def ensure_canonical_repository() -> None:
    config = load_project_config()
    canonical = Path(config["canonical_repository"]).resolve()

    if repo_root() != canonical:
        raise ControlPlaneError(
            "Las features solo pueden registrarse desde el repositorio canónico"
        )


def next_feature_id(features: list[dict]) -> str:
    numbers: list[int] = []

    for feature in features:
        match = FEATURE_ID_PATTERN.fullmatch(str(feature.get("id", "")))

        if match:
            numbers.append(int(match.group(1)))

    return f"F-{max(numbers, default=0) + 1:03d}"


def main() -> int:
    arguments = parse_arguments()

    try:
        ensure_canonical_repository()
        validate_slug(arguments.slug)

        if arguments.priority < 0:
            raise ControlPlaneError("La prioridad no puede ser negativa")

        config = load_project_config()

        windows_required = arguments.windows_validation_required

        if windows_required is None:
            windows_required = bool(config["windows_validation_required"])

        with queue_lock():
            queue = load_queue()

            if any(feature.get("slug") == arguments.slug for feature in queue["features"]):
                raise ControlPlaneError(f"Ya existe una feature con slug '{arguments.slug}'")

            feature_id = next_feature_id(queue["features"])
            timestamp = utc_now()

            feature = {
                "id": feature_id,
                "slug": arguments.slug,
                "title": arguments.title,
                "description": arguments.description,
                "priority": arguments.priority,
                "change_domain": arguments.change_domain,
                "capabilities": sorted(set(arguments.capability)),
                "state": "DRAFT",
                "spec_path": f"specs/features/{feature_id}-{arguments.slug}",
                "windows_validation_required": windows_required,
                "created_at": timestamp,
                "updated_at": timestamp,
                "history": [
                    {
                        "timestamp": timestamp,
                        "action": "REGISTERED",
                        "actor": arguments.requested_by,
                        "to": "DRAFT",
                    }
                ],
            }

            queue["features"].append(feature)
            queue["features"].sort(key=lambda item: (item["priority"], item["id"]))

            save_queue(queue)

        print(f"[OK] Registrada {feature_id}: {arguments.title} (estado DRAFT)")
        print(f"[OK] Ruta de especificación: {feature['spec_path']}")

        return 0

    except ControlPlaneError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
