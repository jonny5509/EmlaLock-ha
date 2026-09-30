from __future__ import annotations

from datetime import datetime, timedelta, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_USER_ID, DOMAIN
from .coordinator import EmlaLockCoordinator


def _session(coordinator):
    return (coordinator.data or {}).get("chastitysession") or {}


def _user(coordinator):
    return (coordinator.data or {}).get("user") or {}


def _timestamp(value):
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        pass

    text = str(value).strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.timestamp()


def _datetime_value(value):
    timestamp = _timestamp(value)
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def _duration_seconds(value):
    if value is None or value == "":
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


class EmlaLockBase(CoordinatorEntity[EmlaLockCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator, user_id, unique_suffix):
        super().__init__(coordinator)
        self._attr_unique_id = f"{user_id}_{unique_suffix}"

    @property
    def device_info(self):
        username = _user(self.coordinator).get("username")
        return {
            "identifiers": {(DOMAIN, self.coordinator.api.user_id)},
            "name": f"EmlaLock - {username}" if username else "EmlaLock",
            "manufacturer": "EmlaLock",
        }


class EmlaLockSession(EmlaLockBase, SensorEntity):
    _attr_name = "Session"
    _attr_translation_key = "session"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ["active", "inactive"]

    @property
    def native_value(self):
        return "active" if _session(self.coordinator).get("status") else "inactive"


class EmlaLockUsername(EmlaLockBase, SensorEntity):
    _attr_name = "Username"
    _attr_translation_key = "username"

    @property
    def native_value(self):
        return _user(self.coordinator).get("username")


class EmlaLockSessionId(EmlaLockBase, SensorEntity):
    _attr_name = "Session ID"
    _attr_translation_key = "session_id"

    @property
    def native_value(self):
        return _session(self.coordinator).get("chastitysessionid")


class EmlaLockHolderId(EmlaLockBase, SensorEntity):
    _attr_name = "Holder ID"
    _attr_translation_key = "holder_id"

    @property
    def native_value(self):
        return _session(self.coordinator).get("holderid")


class EmlaLockSessionType(EmlaLockBase, SensorEntity):
    _attr_name = "Session type"
    _attr_translation_key = "session_type"

    @property
    def native_value(self):
        return _session(self.coordinator).get("sessiontype")


class EmlaLockStartDate(EmlaLockBase, SensorEntity):
    _attr_name = "Start date"
    _attr_translation_key = "start_date"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        return _datetime_value(_session(self.coordinator).get("startdate"))


class EmlaLockTimeInLock(EmlaLockBase, SensorEntity):
    _attr_name = "Time passed"
    _attr_translation_key = "time_passed"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        start = _timestamp(_session(self.coordinator).get("startdate"))
        if start is None:
            return 0.0
        return max(0.0, datetime.now(timezone.utc).timestamp() - start)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._unsub_timer = async_track_time_interval(
            self.hass, self._async_update_time, timedelta(seconds=1)
        )

    async def async_will_remove_from_hass(self) -> None:
        if hasattr(self, "_unsub_timer"):
            self._unsub_timer()
        await super().async_will_remove_from_hass()

    async def _async_update_time(self, _now) -> None:
        self.async_write_ha_state()


class EmlaLockEndDate(EmlaLockBase, SensorEntity):
    _attr_name = "End date"
    _attr_translation_key = "end_date"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        return _datetime_value(_session(self.coordinator).get("enddate"))


class EmlaLockTimeRemaining(EmlaLockBase, SensorEntity):
    _attr_name = "Time remaining"
    _attr_translation_key = "time_remaining"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        end = _timestamp(_session(self.coordinator).get("enddate"))
        if end is None:
            return 0.0
        return max(0.0, end - datetime.now(timezone.utc).timestamp())

    @property
    def extra_state_attributes(self):
        session = _session(self.coordinator)
        return {
            key: session.get(key)
            for key in (
                "chastitysessionid",
                "creatorid",
                "wearerid",
                "holderid",
                "status",
                "sessiontype",
                "duration",
                "startduration",
                "minduration",
                "maxduration",
                "requirements",
                "startdate",
                "enddate",
                "timeinlock",
                "lastverification",
                "incleaning",
                "cleaningstarted",
                "closedate",
                "endtype",
                "canbeclosed",
            )
        }

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._unsub_timer = async_track_time_interval(
            self.hass, self._async_update_time, timedelta(seconds=1)
        )

    async def async_will_remove_from_hass(self) -> None:
        if hasattr(self, "_unsub_timer"):
            self._unsub_timer()
        await super().async_will_remove_from_hass()

    async def _async_update_time(self, _now) -> None:
        self.async_write_ha_state()


class EmlaLockDuration(EmlaLockBase, SensorEntity):
    _attr_name = "Duration"
    _attr_translation_key = "duration"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        return _duration_seconds(_session(self.coordinator).get("duration"))


class EmlaLockStartingDuration(EmlaLockBase, SensorEntity):
    _attr_name = "Starting duration"
    _attr_translation_key = "starting_duration"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        return _duration_seconds(_session(self.coordinator).get("startduration"))


class EmlaLockMaximum(EmlaLockBase, SensorEntity):
    _attr_name = "Maximum duration"
    _attr_translation_key = "maximum_duration"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        return _duration_seconds(_session(self.coordinator).get("maxduration"))


class EmlaLockMinimum(EmlaLockBase, SensorEntity):
    _attr_name = "Minimum duration"
    _attr_translation_key = "minimum_duration"
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        return _duration_seconds(_session(self.coordinator).get("minduration"))


class EmlaLockRequirementLinks(EmlaLockBase, SensorEntity):
    _attr_name = "Requirement links"
    _attr_translation_key = "requirement_links"
    _attr_native_unit_of_measurement = "links"
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        value = _session(self.coordinator).get("requirements")
        try:
            return max(0, int(float(value))) if value is not None else 0
        except (TypeError, ValueError):
            return 0


class EmlaLockLastVerification(EmlaLockBase, SensorEntity):
    _attr_name = "Last verification"
    _attr_translation_key = "last_verification"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        return _datetime_value(_session(self.coordinator).get("lastverification"))


class EmlaLockCleaningStarted(EmlaLockBase, SensorEntity):
    _attr_name = "Cleaning started"
    _attr_translation_key = "cleaning_started"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        return _datetime_value(_session(self.coordinator).get("cleaningstarted"))


class EmlaLockCloseDate(EmlaLockBase, SensorEntity):
    _attr_name = "Close date"
    _attr_translation_key = "close_date"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        return _datetime_value(_session(self.coordinator).get("closedate"))


class EmlaLockEndType(EmlaLockBase, SensorEntity):
    _attr_name = "End type"
    _attr_translation_key = "end_type"

    @property
    def native_value(self):
        return _session(self.coordinator).get("endtype")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
):
    coordinator: EmlaLockCoordinator = hass.data[DOMAIN]["entries"][entry.entry_id][
        "coordinator"
    ]
    user_id = entry.data[CONF_USER_ID]
    async_add_entities(
        [
            EmlaLockSession(coordinator, user_id, "session"),
            EmlaLockUsername(coordinator, user_id, "username"),
            EmlaLockSessionId(coordinator, user_id, "session_id"),
            EmlaLockHolderId(coordinator, user_id, "holder_id"),
            EmlaLockSessionType(coordinator, user_id, "session_type"),
            EmlaLockStartDate(coordinator, user_id, "start_date"),
            EmlaLockTimeInLock(coordinator, user_id, "time_passed"),
            EmlaLockEndDate(coordinator, user_id, "end_date"),
            EmlaLockTimeRemaining(coordinator, user_id, "remaining"),
            EmlaLockDuration(coordinator, user_id, "duration"),
            EmlaLockStartingDuration(coordinator, user_id, "starting_duration"),
            EmlaLockMaximum(coordinator, user_id, "maximum"),
            EmlaLockMinimum(coordinator, user_id, "minimum"),
            EmlaLockRequirementLinks(coordinator, user_id, "requirements"),
            EmlaLockLastVerification(coordinator, user_id, "last_verification"),
            EmlaLockCleaningStarted(coordinator, user_id, "cleaning_started"),
            EmlaLockCloseDate(coordinator, user_id, "close_date"),
            EmlaLockEndType(coordinator, user_id, "end_type"),
        ]
    )
