from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_USER_ID, DOMAIN

_SENSITIVE_KEYS = {"apikey", "api_key", "token", "password", "authorization", "secret"}


def _sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _sanitize(item)
            for key, item in value.items()
            if str(key).lower() not in _SENSITIVE_KEYS
        }
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    return value


def _account(user: Any) -> Any:
    if not isinstance(user, dict):
        return None
    return _sanitize(user)


def _history(payload: dict[str, Any]) -> Any:
    for key in ("history", "lockHistory", "logs", "events"):
        value = payload.get(key)
        if isinstance(value, (list, dict)):
            return _sanitize(value)
    return []


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    data = hass.data.get(DOMAIN, {})
    entry_data = data.get("entries", {}).get(entry.entry_id, {})
    coordinator = entry_data.get("coordinator")
    payload = coordinator.data if coordinator and isinstance(coordinator.data, dict) else {}
    session = payload.get("chastitysession") or {}
    return {
        "account": _account(payload.get("user")),
        "current_lock": _sanitize(session),
        "current_lock_history": _history(payload),
        "user_id": entry.data.get(CONF_USER_ID),
        "entry_id": entry.entry_id,
    }
