# Remote Notifications (Telegram)

Capability `remote-notifications`: the leader notifies the operator when it needs
human intervention or when it finishes and stops, and an optional gateway
allows replying to the leader from the phone.

## Architecture

| Piece | Function |
| --- | --- |
| `scripts/notify.py` | Explicit notification from the leader (`blocked`, `completed`, `attention`, `info`). |
| `scripts/notify_hook.py` | Safety net: Claude Code `Stop`/`Notification` hooks (via `hook_entrypoint.sh notify`). |
| `scripts/telegram_gateway.py` | Long-polling daemon: `/status`, `/tail`, and free text -> prompt to the leader (tmux). |
| `scripts/notify_common.py` | Abstracted transport. Today `telegram`; a WhatsApp Cloud API adapter fits here without touching the callers. |
| `state/capabilities/remote-notifications.json` | Versioned policy (events, debounce, tmux session, gateway). |

Credentials live **outside the repository**. They are never versioned.

## Setup (once, ~5 minutes)

1. Create the bot: talk to `@BotFather` on Telegram -> `/newbot` -> save the token.
2. Open a chat with your bot and send it any message (e.g. `hola`).
3. Get your `chat_id`:

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | jq '.result[-1].message.chat.id'
```

4. Create the credentials file on the machine where the leader runs (the
   environment variables `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` take precedence
   over the file; the path is configurable via `credentials_file` in the policy):

```bash
mkdir -p ~/.config/agentic-harness
cat > ~/.config/agentic-harness/telegram.env <<'EOF'
TELEGRAM_BOT_TOKEN=123456:ABC-tu-token
TELEGRAM_CHAT_ID=123456789
EOF
chmod 600 ~/.config/agentic-harness/telegram.env
```

5. Test sending:

```bash
uv run python scripts/notify.py --event info --message "Prueba de notificaciones" --strict
```

## Bidirectional gateway (optional)

```bash
bash scripts/run_gateway.sh
```

The gateway runs in its own tmux session (`notify-gateway`; configurable with
the `GATEWAY_TMUX_SESSION` variable). Reconnect with `tmux attach -t notify-gateway`.

From Telegram: `/ping`, `/status`, `/tail 60`, `/help`. Any other text
is injected as a prompt into the leader's tmux session (`tmux_session` in the
policy). Only the authorized `chat_id` is served; the rest is ignored and
logged to stderr. On startup the backlog of pending messages is discarded
so old messages are not reprocessed.

## Policy

`state/capabilities/remote-notifications.json`:

- `enabled`: global switch.
- `transport`: sending channel; today only `telegram`.
- `roles`: roles whose hooks notify (default `["leader"]`).
- `events`: enables/disables by type (`stop` and `notification` are the
  automatic hook events; `blocked`/`completed`/`attention`/`info` the explicit ones).
- `debounce_seconds`: minimum silence between automatic events (default 60).
- `credentials_file`: path of the credentials file (default
  `~/.config/agentic-harness/telegram.env`).
- `tmux_session`: the leader's tmux session where `/tail` reads and prompts are
  injected (default `leader`).
- `gateway.enabled`: switch for the bidirectional gateway.
- `gateway.poll_timeout_seconds`: long-polling timeout (default 50).
- `gateway.allow_text_injection`: allows or not injecting prompts via tmux.

## Guarantees

- Fail-soft: neither `notify.py` (without `--strict`) nor the hook returns an error; a
  Telegram outage never blocks the harness.
- Without the capability installed, `hook_entrypoint.sh notify` is a no-op.
- The token is redacted in all error messages.
- Role Guard: `notify.py` is in the leader's Bash allowlist.
