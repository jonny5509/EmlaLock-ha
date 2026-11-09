"""Persistent calendar history for EmlaLock sessions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.components.calendar import CalendarEntity, CalendarEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util.dt import as_local

from .const import CONF_USER_ID, DOMAIN
from .coordinator import EmlaLockCoordinator

_STORAGE_VERSION = 1


def _session(coordinator: EmlaLockCoordinator) -> dict[str, Any]:
    """Return the current session payload, if available."""
    data = coordinator.data if isinstance(coordinator.data, dict) else {}
    session = data.get("chastitysession")
    return session if isinstance(session, dict) else {}


def _is_active(session: dict[str, Any]) -> bool:
    """Whether an EmlaLock session payload reports an active session."""
    status_value = session.get("status")
    return status_value is True or str(status_value).lower() in {
        "active",
        "true",
        "1",
        "running",
    }


def _format_duration(start: datetime, end: datetime) -> str | None:
    """Format the elapsed time of a completed session for its description."""
    total = int((end - start).total_seconds())
    if total <= 0 or end <= start:
        return None
    minutes = total // 60
    if minutes <= 0:
        return f"{total}s"
    days, remainder = divmod(minutes, 24 * 60)
    hours, mins = divmod(remainder, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if days or hours or mins:
        parts.append(f"{mins}m")
    return " ".join(parts)


def _with_duration(description: str, start: datetime, end: datetime) -> str:
    """Append the session duration to a completed event's description."""
    duration = _format_duration(start, end)
    if duration is None:
        return description
    if description:
        return f"{description}\nDuration: {duration}"
    return f"Duration: {duration}"


def _datetime_value(value: Any) -> datetime | None:
    """Parse Unix timestamps or ISO date strings into aware UTC datetimes."""
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        try:
            timestamp = float(value)
            if abs(timestamp) >= 10_000_000_000:
                timestamp /= 1000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
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


def _parse_saved(value: Any) -> datetime | None:
    return _datetime_value(value)


class EmlaLockSessionCalendar(CoordinatorEntity[EmlaLockCoordinator], CalendarEntity):
    """Expose current sessions and persist them after completion."""

    _attr_has_entity_name = True
    _attr_name = "EmlaLock Session Calendar"
    _attr_icon = "mdi:calendar-lock"

    def __init__(self, coordinator: EmlaLockCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.data[CONF_USER_ID]}_session_calendar"
        self._store: Store[dict[str, Any]] = Store(
            coordinator.hass, _STORAGE_VERSION, f"{DOMAIN}_{entry.entry_id}_calendar_history"
        )
        self._history: list[dict[str, Any]] = []
        self._save_task: Any = None

    async def async_added_to_hass(self) -> None:
        saved = await self._store.async_load()
        if isinstance(saved, dict) and isinstance(saved.get("events"), list):
            self._history = [
                {
                    **item,
                    "summary": self._summary_for_start(_parse_saved(item.get("start"))),
                }
                for item in saved["events"]
                if isinstance(item, dict)
                and isinstance(item.get("uid"), str)
                and isinstance(item.get("start"), str)
                and isinstance(item.get("end"), str)
            ]
        await super().async_added_to_hass()
        self._record_current()

    async def async_will_remove_from_hass(self) -> None:
        if self._save_task is not None:
            await self._save_task
        await super().async_will_remove_from_hass()

    @staticmethod
    def _summary_for_start(start: datetime | None) -> str:
        """Format the title with the session start time in local time."""
        if start is None:
            return "EmlaLock — Active session"
        local_start = as_local(start)
        return f"EmlaLock — Active session — started {local_start.strftime('%H:%M')}"

    def _current_event(self) -> CalendarEvent | None:
        session = _session(self.coordinator)
        start = _datetime_value(session.get("startdate"))
        end = _datetime_value(session.get("enddate"))
        if start is None or end is None or end <= start:
            return None
        data = self.coordinator.data if isinstance(self.coordinator.data, dict) else {}
        user = data.get("user", {})
        username = user.get("username") if isinstance(user, dict) else None
        session_id = str(session.get("chastitysessionid") or f"{start.timestamp():.0f}")
        active = _is_active(session)
        title = self._summary_for_start(start)
        now = datetime.now(timezone.utc)
        # A scheduled end time is not proof that the session ended. Keep an
        # active overdue session visible and refresh its calendar end forward.
        if active and end <= now:
            interval = getattr(self.coordinator, "update_interval", None)
            seconds = interval.total_seconds() if isinstance(interval, timedelta) else 60
            end = now + timedelta(seconds=max(60, seconds))
        status = "active" if active else "inactive"
        return CalendarEvent(
            summary=title,
            start=start,
            end=end,
            description=f"Session status: {status}\nSession ID: {session_id}",
            uid=f"emlalock-session-{session_id}",
        )

    @property
    def event(self) -> CalendarEvent | None:
        """Expose the current session as an all-day event for the local day."""
        current = self._current_event()
        if current is None:
            return None
        if not _is_active(_session(self.coordinator)):
            # Ended sessions keep timed bounds capped at the observed end,
            # showing how long the session actually lasted instead of the
            # whole calendar day.
            end_dt = min(current.end, datetime.now(timezone.utc))
            if end_dt <= current.start:
                return current
            return CalendarEvent(
                summary=current.summary,
                start=current.start,
                end=end_dt,
                description=_with_duration(current.description or "", current.start, end_dt),
                uid=current.uid,
            )
        local_start = as_local(current.start)
        event_day = local_start.date()
        summary = (
            current.summary
            if event_day == local_start.date()
            else "EmlaLock — Active session"
        )
        return CalendarEvent(
            summary=summary,
            start=event_day,
            end=event_day + timedelta(days=1),
            description=current.description,
            uid=f"{current.uid}-{event_day.isoformat()}",
        )

    def _queue_save(self) -> None:
        snapshot = {"events": [dict(item) for item in self._history]}
        previous = self._save_task

        async def save() -> None:
            if previous is not None:
                try:
                    await previous
                except Exception:  # noqa: BLE001
                    pass
            await self._store.async_save(snapshot)

        self._save_task = self.hass.async_create_task(save())

    def _record_current(self) -> None:
        event = self._current_event()
        session_active = event is not None and _is_active(_session(self.coordinator))
        changed = False
        active_records = [item for item in self._history if item.get("active")]
        now = datetime.now(timezone.utc)
        if event is not None:
            start_dt = event.start.astimezone(timezone.utc)
            if session_active:
                end_dt = event.end.astimezone(timezone.utc)
            else:
                # The session is already ended. Supersede a still-future
                # scheduled end with the observed end so the calendar shows
                # how long the session actually lasted, not a full day.
                end_dt = min(event.end.astimezone(timezone.utc), now)
                if end_dt <= start_dt:
                    # Upcoming or zero-length entry: close replaced sessions
                    # but do not persist a new history record for it.
                    for item in active_records:
                        if item.get("uid") != event.uid:
                            item["end"] = now.isoformat()
                            item["active"] = False
                            changed = True
                    if changed:
                        self._queue_save()
                    return
            start = start_dt.isoformat()
            end = end_dt.isoformat()
            for item in active_records:
                if item.get("uid") != event.uid:
                    # A new session replaced the previous one without an
                    # empty snapshot between them. Close it at observation
                    # time so it becomes a timed history entry.
                    item["end"] = now.isoformat()
                    item["active"] = False
                    changed = True
            record = next((item for item in self._history if item.get("uid") == event.uid), None)
            description = event.description or ""
            if not session_active:
                description = _with_duration(description, start_dt, end_dt)
            serialized = {
                "uid": str(event.uid), "summary": event.summary,
                "description": description, "start": start, "end": end,
                "active": session_active,
            }
            if record is None:
                self._history.append(serialized)
                changed = True
            elif record != serialized:
                record.update(serialized)
                changed = True
        else:
            # No current session: close any previously active records at the
            # observed time so they reappear as timed entries spanning only
            # how long the session ran, not as all-day blocks. Skip this
            # before the coordinator's first fetch (data is None), so an
            # active session surviving a restart is not closed at startup.
            if not isinstance(self.coordinator.data, dict):
                return
            for item in active_records:
                item["end"] = now.isoformat()
                item["active"] = False
                changed = True
        if changed:
            self._queue_save()

    def _handle_coordinator_update(self) -> None:
        self._record_current()
        super()._handle_coordinator_update()

    async def async_get_events(
        self, hass: HomeAssistant, start_date: datetime, end_date: datetime
    ) -> list[CalendarEvent]:
        current = self._current_event()
        session_active = current is not None and _is_active(_session(self.coordinator))
        records = [dict(item) for item in self._history]
        if current is not None:
            records = [item for item in records if item.get("uid") != current.uid]
            start_dt = current.start.astimezone(timezone.utc)
            end_dt = current.end.astimezone(timezone.utc)
            description = current.description or ""
            if not session_active:
                # Ended but still present in the API payload: present it as a
                # timed entry spanning its actual duration, not as all-day.
                end_dt = min(end_dt, datetime.now(timezone.utc))
                description = _with_duration(description, start_dt, end_dt)
            records.append({
                "uid": str(current.uid), "summary": current.summary,
                "description": description,
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(), "active": session_active,
            })
        elif isinstance(self.coordinator.data, dict):
            # Coordinator data is known and reports no current session, so any
            # still-active history records belonged to sessions that already
            # ended. Present them as timed entries capped at observation time
            # instead of leaving them as lingering all-day blocks.
            now = datetime.now(timezone.utc)
            for item in records:
                if not item.get("active"):
                    continue
                parsed_start = _parse_saved(item.get("start"))
                parsed_end = _parse_saved(item.get("end"))
                if parsed_start is None or parsed_end is None:
                    continue
                capped_end = min(parsed_end, now)
                if capped_end > parsed_start:
                    item["end"] = capped_end.isoformat()
                item["active"] = False
        start_bound = start_date.astimezone(timezone.utc) if start_date.tzinfo else start_date.replace(tzinfo=timezone.utc)
        end_bound = end_date.astimezone(timezone.utc) if end_date.tzinfo else end_date.replace(tzinfo=timezone.utc)
        events: list[CalendarEvent] = []
        for item in records:
            start = _parse_saved(item.get("start"))
            end = _parse_saved(item.get("end"))
            if start is None or end is None or end <= start or end <= start_bound or start >= end_bound:
                continue
            description = str(item.get("description") or "")
            if item.get("active"):
                # Split active sessions at local midnight, respecting DST.
                segment_start = start
                first_segment = True
                while segment_start < end:
                    local_start = as_local(segment_start)
                    next_midnight = local_start.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ) + timedelta(days=1)
                    segment_end = min(end, next_midnight.astimezone(timezone.utc))
                    if segment_end <= segment_start:
                        break
                    summary = (
                        str(item.get("summary") or "EmlaLock — Active session")
                        if first_segment
                        else "EmlaLock — Active session"
                    )
                    event_day = local_start.date()
                    events.append(CalendarEvent(
                        summary=summary,
                        start=event_day,
                        end=event_day + timedelta(days=1),
                        description=description,
                        uid=f"{item['uid']}-{event_day.isoformat()}",
                    ))
                    segment_start = segment_end
                    first_segment = False
            else:
                if "Duration:" not in description:
                    description = _with_duration(description, start, end)
                events.append(CalendarEvent(
                    summary=str(item.get("summary") or "EmlaLock session"),
                    start=start, end=end, description=description,
                    uid=str(item["uid"]),
                ))
        return sorted(events, key=lambda event: event.start)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the EmlaLock session calendar."""
    coordinator: EmlaLockCoordinator = hass.data[DOMAIN]["entries"][entry.entry_id]["coordinator"]
    async_add_entities([EmlaLockSessionCalendar(coordinator, entry)])
