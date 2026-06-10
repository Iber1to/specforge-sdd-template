# Capability: Remote Notifications

Capacidad opcional de notificacion remota e interaccion con el leader.

## Que aporta

- El leader avisa por Telegram cuando una feature queda `BLOCKED`, cuando
  necesita intervencion humana o cuando completa el trabajo y se detiene
  (`scripts/notify.py`, instruido en `leader.md`).
- Red de seguridad determinista: hooks `Stop` y `Notification` de Claude Code
  notifican aunque el modelo omita la llamada explicita
  (`scripts/notify_hook.py` via `hook_entrypoint.sh notify`).
- Gateway bidireccional opcional (`scripts/telegram_gateway.py`): desde el
  movil, `/status`, `/tail` y texto libre inyectado como prompt en la sesion
  tmux del leader. Long-polling: sin endpoint publico ni tunel.

## Activacion

En la configuracion del generador:

```yaml
capabilities: [remote-notifications]
```

Setup de credenciales y uso: `docs/notifications/setup.md`.

## Transporte

`telegram` (unico soportado). El transporte esta abstraido en
`scripts/notify_common.py`; un adapter WhatsApp Cloud API u otro canal se
anade ahi sin cambiar `notify.py`, el hook ni el gateway.

## Garantias

- Fail-soft: una notificacion fallida nunca bloquea el harness (exit 0 salvo
  `--strict`).
- Proyectos sin la capability: el hook `notify` es un no-op.
- Secretos fuera de Git (`~/.config/agentic-harness/telegram.env`); el token
  se redacta en errores.
- Solo el `chat_id` autorizado puede hablar con el gateway.
