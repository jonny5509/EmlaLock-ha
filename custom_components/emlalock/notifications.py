"""Consistent, restart-safe session milestone and completion notifications."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store

from .const import (
    CONF_ENABLE_PHONE_NOTIFICATIONS,
    CONF_ENABLE_HA_NOTIFICATIONS,
    CONF_NOTIFICATION_DESTINATION,
    CONF_NOTIFICATION_SERVICE,
    CONF_NOTIFICATION_TARGETS,
    DEFAULT_NOTIFICATION_SERVICE,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)
_CHECK_INTERVAL = timedelta(minutes=1)
_PHONE_SERVICE = re.compile(r"notify\\.mobile_app_[a-z0-9_]+")
_DAY_SECONDS = 86400


def _timestamp(value: Any) -> float | None:
    """Parse API timestamps, accepting seconds, milliseconds, and ISO dates."""
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


def _destination(options: dict[str, Any]) -> str:
    """Normalize current and legacy destination option values."""
    value = options.get(CONF_NOTIFICATION_DESTINATION)
    if value == "ha":
        value = "home_assistant"
    if value in {"none", "home_assistant", "phone", "both"}:
        return value
    phone = options.get(CONF_ENABLE_PHONE_NOTIFICATIONS, False)
    ha = options.get(CONF_ENABLE_HA_NOTIFICATIONS, False)
    return "both" if phone and ha else "phone" if phone else "home_assistant" if ha else "none"


def _phone_targets(options: dict[str, Any]) -> list[str]:
    """Return unique mobile-app notify services, including legacy settings."""
    targets = options.get(CONF_NOTIFICATION_TARGETS)
    if isinstance(targets, str):
        targets = [targets]
    if targets is None:
        targets = [options.get(CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE)]
    services: list[str] = []
    for target in targets if isinstance(targets, list) else []:
        if not isinstance(target, str):
            continue
        service = target if target.startswith("notify.") else f"notify.{target}"
        if _PHONE_SERVICE.fullmatch(service) and service not in services:
            services.append(service)
    return services


def _duration(days: int) -> str:
    """Format elapsed days consistently across integrations."""
    return f"{days} day" if days == 1 else f"{days} days"


class EmlaLockSessionNotifications:
    """Track session milestones and persist successful notification delivery."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, coordinator) -> None:
        self.hass = hass
        self.entry = entry
        self.coordinator = coordinator
        self.store = Store(hass, 1, f"{DOMAIN}_session_notifications_{entry.entry_id}")
        self.state: dict[str, Any] = {}

    async def async_start(self) -> None:
        saved = await self.store.async_load()
        self.state = saved if isinstance(saved, dict) else {}
        self.entry.async_on_unload(
            async_track_time_interval(self.hass, self._tick, _CHECK_INTERVAL)
        )
        await self.async_check()

    async def _tick(self, _now: datetime) -> None:
        await self.async_check()

    async def _notify(self, title: str, message: str, event: str) -> bool:
        """Send the same notification payload to selected phone and HA destinations."""
        options = self.entry.options
        destination = _destination(options)
        delivered = False
        if destination in {"phone", "both"}:
            for service in _phone_targets(options):
                try:
                    domain, name = service.split(".", 1)
                    await self.hass.services.async_call(
                        domain, name, {"title": title, "message": message}, blocking=True
                    )
                    delivered = True
                except Exception:
                    _LOGGER.exception("Unable to send %s phone notification via %s", DOMAIN, service)
        if destination in {"home_assistant", "both"}:
            try:
                await self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {
                        "title": title,
                        "message": message,
                        "notification_id": f"{DOMAIN}_{self.entry.entry_id}_{event}",
                    },
                    blocking=True,
                )
                delivered = True
            except Exception:
                _LOGGER.exception("Unable to create %s Home Assistant notification", DOMAIN)
        return delivered

    async def async_check(self) -> None:
        data = self.coordinator.data
        if not isinstance(data, dict):
            return
        session = data.get("chastitysession")
        if not isinstance(session, dict):
            session = {}

        status = session.get("status")
        active = (
            status is True
            or (isinstance(status, (int, float)) and not isinstance(status, bool) and status != 0)
            or (isinstance(status, str) and status.strip().lower() in {"active", "locked", "true", "1"})
        )
        start = _timestamp(session.get("startdate"))
        now = datetime.now(timezone.utc).timestamp()
        user = data.get("user")
        name = str(user.get("username") if isinstance(user, dict) else "" or "EmlaLock session")
        changed = False

        if active and start is not None and start <= now:
            saved_start = _timestamp(self.state.get("start"))
            if not self.state.get("active_seen") or saved_start is None or abs(saved_start - start) > 60:
                self.state.update({
                    "active_seen": True,
                    "start": start,
                    "last_daily_day": 0,
                    "completion_notified": False,
                })
                changed = True

            elapsed_days = max(0, int((now - start) // _DAY_SECONDS))
            if (
                _destination(self.entry.options) != "none"
                and elapsed_days >= 1
                and elapsed_days > int(self.state.get("last_daily_day", 0))
            ):
                title = "Session milestone reached"
                message = f"🎉 Day {elapsed_days} complete for {name}. Keep it going!"
                if await self._notify(title, message, f"daily_{elapsed_days}"):
                    self.state["last_daily_day"] = elapsed_days
                    changed = True
        elif not active and self.state.get("active_seen") and not self.state.get("completion_notified"):
            saved_start = _timestamp(self.state.get("start"))
            elapsed_days = max(0, int((now - saved_start) // _DAY_SECONDS)) if saved_start is not None else 0
            if _destination(self.entry.options) != "none":
                title = "Session completed"
                message = f"🏆 {name} is complete after {_duration(elapsed_days)}. Well done!"
                if await self._notify(title, message, "completion"):
                    self.state["completion_notified"] = True
                    changed = True
            else:
                self.state["completion_notified"] = True
                changed = True
            self.state["active_seen"] = False
            changed = True

        if changed:
            await self.store.async_save(self.state)


async def async_setup_notifications(hass: HomeAssistant, entry: ConfigEntry, coordinator) -> None:
    """Start notification tracking only when at least one destination is enabled."""
    if _destination(entry.options) == "none":
        return
    await EmlaLockSessionNotifications(hass, entry, coordinator).async_start()
