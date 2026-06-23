#!/usr/bin/env python3
"""Explicit harness remote notification (remote-notifications capability).

Intended for the leader (or another operator) to send a Telegram alert when a
feature becomes BLOCKED, when the requested work finishes, or when human
attention is needed.

Usage:

    uv run python scripts/notify.py --event blocked --feature F-001 \
        --message "Ambiguous spec: missing acceptance criterion"

By default it is fail-soft (exit 0 even if the send fails) so the workflow is
not blocked; with --strict it returns exit 2 if the send fails.
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
        help="Returns exit 2 if the notification cannot be sent",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()

    try:
        policy = load_policy()

        if not policy_enabled(policy):
            print("[OK] Notifications disabled by policy; nothing is sent")
            return 0

        if not event_enabled(policy, args.event):
            print(f"[OK] Event {args.event} disabled by policy; nothing is sent")
            return 0

        text = format_event_text(args.event, args.message, feature=args.feature)
        send_message(policy, text)
    except NotificationError as exc:
        print(f"[ERROR] Notification not sent: {exc}", file=sys.stderr)
        return 2 if args.strict else 0

    print(f"[OK] Notification sent ({args.event})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
