#!/usr/bin/env python3
"""Consulta métricas agregadas del proyecto, rol o feature."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from control_common import ControlPlaneError, load_project_config
from metrics_common import aggregate_metrics


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--feature")
    selection.add_argument("--role")

    parser.add_argument("--json", action="store_true")

    return parser.parse_args()


def print_scope(label: str, scope: dict[str, Any]) -> None:
    agents = scope["agents"]
    runs = scope["runs"]

    print(f"=== {label} ===")
    print(
        "Agentes: "
        f"{agents['invocations']} invocaciones; "
        f"{agents['completed']} completadas; "
        f"{agents['active']} activas; "
        f"{agents['blocked_results']} bloqueadas"
    )
    print(
        "Consumo observado: "
        f"{agents['total_tokens_observed']} tokens brutos; "
        f"{agents['assistant_turns_observed']} turnos; "
        f"{agents['duration_seconds']} segundos"
    )
    print(
        "Caché: "
        f"{agents['cache_creation_input_tokens']} creación; "
        f"{agents['cache_read_input_tokens']} lectura"
    )
    print(f"Presupuestos excedidos: {agents['budget_violations']}")
    print(
        "Runs: "
        f"{runs['runs']} totales; "
        f"{runs['completed']} completados; "
        f"{runs['active']} activos; "
        f"{runs['expired']} caducados; "
        f"{runs['retries']} reintentos"
    )
    print(
        "Runs observados: "
        f"{runs['duration_seconds']} segundos; "
        f"{runs['heartbeat_count']} heartbeats"
    )

    if runs["results"]:
        print(
            "Resultados: "
            + ", ".join(f"{name}={amount}" for name, amount in sorted(runs["results"].items()))
        )


def main() -> int:
    arguments = parse_arguments()

    try:
        config = load_project_config()
        control_root = Path(config["control_root"]).resolve()
        summary = aggregate_metrics(control_root)

        selected: dict[str, Any]
        label: str

        if arguments.feature:
            selected = summary["features"].get(arguments.feature)

            if selected is None:
                raise ControlPlaneError(f"No existen métricas para {arguments.feature}")

            label = f"FEATURE {arguments.feature}"

        elif arguments.role:
            selected = summary["roles"].get(arguments.role)

            if selected is None:
                raise ControlPlaneError(f"No existen métricas para el rol {arguments.role}")

            label = f"ROL {arguments.role}"

        else:
            selected = summary["project"]
            label = "PROYECTO"

        if arguments.json:
            print(
                json.dumps(
                    selected if arguments.feature or arguments.role else summary,
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            print_scope(label, selected)

        return 0

    except ControlPlaneError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
