"""Calendar entity for EmlaLock sessions."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_USER_ID, DOMAIN
from .coordinator import EmlaLockCoordinator


def _session(coordinator: EmlaLockCoordinator) -> dict[str, Any]:
    """Return the current session payload, if available."""
    data = coordinator.data if isinstance(coordinator.data, dict) else {}
    session = data.get("chastitysession")
    return session if isinstance(session, dict) else {}


def _datetime_value(value: Any) -> datetime | None:
    """Parse EmlaLock Unix timestamps or ISO date strings into aware UTC datetimes."""
    if value is None or value == "" or isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        try:
            timestamp = float(value)
            # Accommodate millisecond Unix timestamps as well as seconds.
            if abs(timestamp) >= 10_000_000_000:
                timestamp /= 1000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None
    try:
        timestamp = float(text)
    except ValueError:
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except (TypeError, ValueError, OverflowError):
            return None
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed

    try:
        if abs(timestamp) >= 10_000_000_000:
            timestamp /= 1000
        return datetime.fromtimestamp(timestamp, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


class EmlaLockSessionCalendar(CoordinatorEntity[EmlaLockCoordinator], CalendarEntity):
    """Expose the EmlaLock session start and end as a calendar event."""

    _attr_has_entity_name = True
    _attr_name = "EmlaLock Session Calendar"
    _attr_icon = "mdi:calendar-lock"

    def __init__(self, coordinator: EmlaLockCoordinator, user_id: str) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{user_id}_session_calendar"

    @property
    def event(self) -> CalendarEvent | None:
        """Return the current session when its dates are available."""
        session = _session(self.coordinator)
        start = _datetime_value(session.get("startdate"))
        end = _datetime_value(session.get("enddate"))
        if start is None or end is None or end <= start:
            return None

        user = (self.coordinator.data or {}).get("user", {})
        username = user.get("username") if isinstance(user, dict) else None
        title = f"{username} - EmlaLock session" if username else "EmlaLock session"
        status = "active" if session.get("status") else "inactive"
        session_id = session.get("chastitysessionid", "unknown")
        return CalendarEvent(
            summary=title,
            start=start,
            end=end,
            description=f"Session status: {status}\nSession ID: {session_id}",
            uid=f"emlalock-session-{session_id}",
        )

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        """Return the session if it overlaps the requested calendar range."""
        event = self.event
        if event is None or event.start >= end_date or event.end <= start_date:
            return []
        return [event]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the EmlaLock session calendar."""
    coordinator: EmlaLockCoordinator = hass.data[DOMAIN]["entries"][entry.entry_id][
        "coordinator"
    ]
    async_add_entities([EmlaLockSessionCalendar(coordinator, entry.data[CONF_USER_ID])])
