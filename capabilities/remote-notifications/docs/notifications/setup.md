# Notificaciones Remotas (Telegram)

Capability `remote-notifications`: el leader avisa al operador cuando necesita
intervención humana o cuando termina y se detiene, y un gateway opcional
permite responder al leader desde el móvil.

## Arquitectura

| Pieza | Función |
| --- | --- |
| `scripts/notify.py` | Notificación explícita del leader (`blocked`, `completed`, `attention`, `info`). |
| `scripts/notify_hook.py` | Red de seguridad: hooks `Stop`/`Notification` de Claude Code (vía `hook_entrypoint.sh notify`). |
| `scripts/telegram_gateway.py` | Daemon long-polling: `/status`, `/tail`, y texto libre → prompt al leader (tmux). |
| `scripts/notify_common.py` | Transporte abstraído. Hoy `telegram`; un adapter WhatsApp Cloud API encaja aquí sin tocar a los llamantes. |
| `state/capabilities/remote-notifications.json` | Política versionada (eventos, debounce, sesión tmux, gateway). |

Las credenciales viven **fuera del repositorio**. Nunca se versionan.

## Setup (una vez, ~5 minutos)

1. Crea el bot: habla con `@BotFather` en Telegram → `/newbot` → guarda el token.
2. Abre un chat con tu bot y envíale cualquier mensaje (p. ej. `hola`).
3. Obtén tu `chat_id`:

```bash
curl -s "https://api.telegram.org/bot<TOKEN>/getUpdates" | jq '.result[-1].message.chat.id'
```

4. Crea el archivo de credenciales en la máquina donde corre el leader (las
   variables de entorno `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID` tienen prioridad
   sobre el archivo; la ruta es configurable vía `credentials_file` en la política):

```bash
mkdir -p ~/.config/agentic-harness
cat > ~/.config/agentic-harness/telegram.env <<'EOF'
TELEGRAM_BOT_TOKEN=123456:ABC-tu-token
TELEGRAM_CHAT_ID=123456789
EOF
chmod 600 ~/.config/agentic-harness/telegram.env
```

5. Prueba el envío:

```bash
uv run python scripts/notify.py --event info --message "Prueba de notificaciones" --strict
```

## Gateway bidireccional (opcional)

```bash
bash scripts/run_gateway.sh
```

El gateway corre en su propia sesión tmux (`notify-gateway`; configurable con
la variable `GATEWAY_TMUX_SESSION`). Reconecta con `tmux attach -t notify-gateway`.

Desde Telegram: `/ping`, `/status`, `/tail 60`, `/help`. Cualquier otro texto
se inyecta como prompt en la sesión tmux del leader (`tmux_session` en la
política). Solo se atiende el `chat_id` autorizado; el resto se ignora y se
registra en stderr. Al arrancar se descarta el backlog de mensajes pendientes
para no reprocesar mensajes antiguos.

## Política

`state/capabilities/remote-notifications.json`:

- `enabled`: interruptor global.
- `transport`: canal de envío; hoy solo `telegram`.
- `roles`: roles cuyos hooks notifican (defecto `["leader"]`).
- `events`: activa/desactiva por tipo (`stop` y `notification` son los
  automáticos de hooks; `blocked`/`completed`/`attention`/`info` los explícitos).
- `debounce_seconds`: silencio mínimo entre eventos automáticos (defecto 60).
- `credentials_file`: ruta del archivo de credenciales (defecto
  `~/.config/agentic-harness/telegram.env`).
- `tmux_session`: sesión tmux del leader donde `/tail` lee y se inyectan prompts
  (defecto `leader`).
- `gateway.enabled`: interruptor del gateway bidireccional.
- `gateway.poll_timeout_seconds`: timeout del long-polling (defecto 50).
- `gateway.allow_text_injection`: permite o no inyectar prompts vía tmux.

## Garantías

- Fail-soft: ni `notify.py` (sin `--strict`) ni el hook devuelven error; una
  caída de Telegram nunca bloquea el harness.
- Sin la capability instalada, `hook_entrypoint.sh notify` es un no-op.
- El token se redacta en todos los mensajes de error.
- Role Guard: `notify.py` está en la allowlist Bash del leader.
