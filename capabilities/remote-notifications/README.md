# Capability: Remote Notifications

Optional capability for remote notification and interaction with the leader.

## What It Provides

- The leader notifies via Telegram when a feature becomes `BLOCKED`, when it
  needs human intervention or when it completes the work and stops
  (`scripts/notify.py`, instructed in `leader.md`).
- Deterministic safety net: Claude Code `Stop` and `Notification` hooks
  notify even if the model omits the explicit call
  (`scripts/notify_hook.py` via `hook_entrypoint.sh notify`).
- Optional bidirectional gateway (`scripts/telegram_gateway.py`): from the
  phone, `/status`, `/tail` and free text injected as a prompt into the leader's
  tmux session. Long-polling: no public endpoint or tunnel.

## Activation

In the generator configuration:

```yaml
capabilities: [remote-notifications]
```

Credentials setup and usage: `docs/notifications/setup.md`.

## Transport

`telegram` (only one supported). The transport is abstracted in
`scripts/notify_common.py`; a WhatsApp Cloud API adapter or other channel is
added there without changing `notify.py`, the hook or the gateway.

## Guarantees

- Fail-soft: a failed notification never blocks the harness (exit 0 except with
  `--strict`).
- Projects without the capability: the `notify` hook is a no-op.
- Secrets outside Git (`~/.config/agentic-harness/telegram.env`); the token
  is redacted in errors.
- Only the authorized `chat_id` can talk to the gateway.
