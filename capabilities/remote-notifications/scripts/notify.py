#!/usr/bin/env python3
"""Notificacion remota explicita del harness (capability remote-notifications).

Pensado para que el leader (u otro operador) avise por Telegram cuando una
feature queda BLOCKED, cuando el trabajo solicitado termina o cuando se
necesita atencion humana.

Uso:

    uv run python scripts/notify.py --event blocked --feature F-001 \
        --message "Spec ambigua: falta criterio de aceptacion"

Por defecto es fail-soft (exit 0 aunque falle el envio) para no bloquear el
workflow; con --strict devuelve exit 2 si el envio falla.
"""

from __future__ import annotations

import argparse
import sys

from notify_common import (
    NotificationError,
    event_enabled,
    format_event_text,
    load_policy,
    policy_enabled,
    send_message,
)

VALID_EVENTS = ("blocked", "completed", "attention", "info")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", required=True, choices=VALID_EVENTS)
    parser.add_argument("--message", required=True)
    parser.add_argument("--feature", default=None)
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Devuelve exit 2 si la notificacion no puede enviarse",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    try:
        policy = load_policy()

        if not policy_enabled(policy):
            print("[OK] Notificaciones deshabilitadas por politica; no se envia nada")
            return 0

        if not event_enabled(policy, args.event):
            print(f"[OK] Evento {args.event} deshabilitado por politica; no se envia nada")
            return 0

        text = format_event_text(args.event, args.message, feature=args.feature)
        send_message(policy, text)
    except NotificationError as exc:
        print(f"[ERROR] Notificacion no enviada: {exc}", file=sys.stderr)
        return 2 if args.strict else 0

    print(f"[OK] Notificacion enviada ({args.event})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
