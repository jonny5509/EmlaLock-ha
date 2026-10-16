"""Opt-in 24-hour session reminders and session-ended notifications."""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.event import async_track_time_interval
from datetime import timedelta

from .const import (
    CONF_ENABLE_NOTIFICATIONS,
    CONF_ENABLE_PHONE_NOTIFICATIONS,
    CONF_ENABLE_HA_NOTIFICATIONS,
    CONF_NOTIFICATION_SERVICE,
    CONF_NOTIFY_DAILY,
    CONF_NOTIFY_COMPLETION,
    CONF_NOTIFY_HA_DAILY,
    CONF_NOTIFY_HA_COMPLETION,
    DEFAULT_NOTIFICATION_SERVICE,
    DOMAIN,
    CONF_NOTIFICATION_DESTINATION,
    CONF_NOTIFICATION_TARGETS,
)

_LOGGER = logging.getLogger(__name__)
_CHECK_INTERVAL = timedelta(minutes=1)


def _timestamp(value: Any) -> float | None:
    if value is None or value == "" or isinstance(value, bool):
        return None
    try:
        if isinstance(value, (int, float)):
            result = float(value)
            if result > 10_000_000_000:
                result /= 1000
            return result
        text = str(value).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError, OverflowError, OSError):
        return None


class EmlaLockSessionNotifications:
    """Track session milestones and persist notification delivery state."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.store = Store(hass, 1, f"{DOMAIN}_session_notifications_{entry.entry_id}")
        self.state: dict[str, Any] = {}
        self.service = str(entry.options.get(CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE))

    async def async_start(self) -> None:
        saved = await self.store.async_load()
        if isinstance(saved, dict):
            self.state = saved
        self.entry.async_on_unload(
            async_track_time_interval(self.hass, self._tick, _CHECK_INTERVAL)
        )
        await self.async_check()

    async def _tick(self, _now: datetime) -> None:
        await self.async_check()

    async def _notify(self, title: str, message: str, event: str) -> bool:
        """Send to the selected mobile service and/or Home Assistant."""
        mobile_key = CONF_NOTIFY_DAILY if event == "daily" else CONF_NOTIFY_COMPLETION
        ha_key = CONF_NOTIFY_HA_DAILY if event == "daily" else CONF_NOTIFY_HA_COMPLETION
        delivered = False
        destination = self.entry.options.get(CONF_NOTIFICATION_DESTINATION)
        phone_enabled = destination in ("phone", "both") if destination else self.entry.options.get(CONF_ENABLE_PHONE_NOTIFICATIONS, False)
        ha_enabled = destination in ("home_assistant", "both") if destination else self.entry.options.get(CONF_ENABLE_HA_NOTIFICATIONS, False)
        if phone_enabled and self.entry.options.get(mobile_key, False):
            try:
                targets = self.entry.options.get(CONF_NOTIFICATION_TARGETS, [])
                if targets:
                    for target in targets:
                        service_name = str(target).removeprefix("notify.")
                        await self.hass.services.async_call(
                            "notify", service_name, {"title": title, "message": message}, blocking=True
                        )
                    delivered = True
                else:
                    service = self.service
                    if re.fullmatch(r"notify\.[a-z0-9_]+", service):
                        await self.hass.services.async_call(
                            "notify", service.split(".", 1)[1], {"title": title, "message": message}, blocking=True
                        )
                        delivered = True
            except Exception:
                _LOGGER.exception("Unable to send EmlaLock mobile notification through notify.%s", self.service)
        if ha_enabled and self.entry.options.get(ha_key, False):
            try:
                await self.hass.services.async_call(
                    "persistent_notification", "create",
                    {"title": title, "message": message, "notification_id": f"{DOMAIN}_{self.entry.entry_id}_{event}"},
                    blocking=True,
                )
                delivered = True
            except Exception:
                _LOGGER.exception("Unable to create EmlaLock Home Assistant notification")
        return delivered

    async def async_check(self) -> None:
        data = self.coordinator.data
        if not isinstance(data, dict):
            return
        session = data.get("chastitysession") or {}
        if not isinstance(session, dict):
            session = {}
        status = session.get("status")
        active = status is True or (isinstance(status, (int, float)) and status != 0) or (isinstance(status, str) and status.strip().lower() in {"active", "locked", "true", "1"})
        start = _timestamp(session.get("startdate"))
        now = datetime.now(timezone.utc).timestamp()
        name = str((data.get("user") or {}).get("username") or "emlalock session")
        changed = False

        if active and start is not None and start <= now:
            if not self.state.get("active_seen"):
                self.state["active_seen"] = True
                self.state["start"] = start
                changed = True
            # A changed start timestamp means a new session; reset milestone state.
            if self.state.get("start") != start:
                self.state.update({"start": start, "last_daily_day": 0, "completion_notified": False})
                changed = True
            elapsed_days = int(max(0, now - start) // 86400)
            if ((self.entry.options.get(CONF_ENABLE_PHONE_NOTIFICATIONS, False) and self.entry.options.get(CONF_NOTIFY_DAILY, False)) or (self.entry.options.get(CONF_ENABLE_HA_NOTIFICATIONS, False) and self.entry.options.get(CONF_NOTIFY_HA_DAILY, False))) and elapsed_days >= 1 and elapsed_days > int(self.state.get("last_daily_day", 0)):
                if await self._notify("emlalock 24-hour reminder", f"{name}: {elapsed_days} day(s) since the session started.", "daily"):
                    self.state["last_daily_day"] = elapsed_days
                    changed = True
        elif not active and self.state.get("active_seen") and not self.state.get("completion_notified"):
            if self.entry.options.get(CONF_NOTIFY_COMPLETION, False) or self.entry.options.get(CONF_NOTIFY_HA_COMPLETION, False):
                if await self._notify("emlalock session ended", f"{name} has ended.", "completion"):
                    self.state["completion_notified"] = True
                    changed = True
            else:
                # Do not send a delayed completion alert if the option is enabled later.
                self.state["completion_notified"] = True
                changed = True
            self.state["active_seen"] = False
            changed = True

        if changed:
            await self.store.async_save(self.state)


async def async_setup_notifications(hass: HomeAssistant, entry: ConfigEntry, coordinator) -> None:
    """Start notifications only after the master opt-in is enabled."""
    destination = entry.options.get(CONF_NOTIFICATION_DESTINATION)
    enabled = destination in ("phone", "both", "home_assistant") if destination else (
        entry.options.get(CONF_ENABLE_PHONE_NOTIFICATIONS, False) or entry.options.get(CONF_ENABLE_HA_NOTIFICATIONS, False)
    )
    if not enabled:
        return
    await EmlaLockSessionNotifications(hass, entry, coordinator).async_start()
