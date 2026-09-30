from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_USER_ID, DOMAIN
from .coordinator import EmlaLockCoordinator


def _session(coordinator):
    return (coordinator.data or {}).get("chastitysession") or {}


class EmlaLockBinaryBase(CoordinatorEntity[EmlaLockCoordinator], BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, user_id, unique_suffix):
        super().__init__(coordinator)
        self._attr_unique_id = f"{user_id}_{unique_suffix}"

    @property
    def device_info(self):
        username = (coordinator_data := (self.coordinator.data or {}).get("user") or {}).get(
            "username"
        )
        return {
            "identifiers": {(DOMAIN, self.coordinator.api.user_id)},
            "name": f"EmlaLock - {username}" if username else "EmlaLock",
            "manufacturer": "EmlaLock",
        }


class EmlaLockSessionActive(EmlaLockBinaryBase):
    _attr_name = "Session active"
    _attr_translation_key = "session_active"

    def __init__(self, coordinator, user_id):
        super().__init__(coordinator, user_id, "session_active")

    @property
    def is_on(self) -> bool:
        return bool(_session(self.coordinator).get("status"))


class EmlaLockInCleaning(EmlaLockBinaryBase):
    _attr_name = "In cleaning"
    _attr_translation_key = "in_cleaning"

    def __init__(self, coordinator, user_id):
        super().__init__(coordinator, user_id, "in_cleaning")

    @property
    def is_on(self) -> bool:
        return bool(_session(self.coordinator).get("incleaning"))


class EmlaLockCanBeClosed(EmlaLockBinaryBase):
    _attr_name = "Can be closed"
    _attr_translation_key = "can_be_closed"

    def __init__(self, coordinator, user_id):
        super().__init__(coordinator, user_id, "can_be_closed")

    @property
    def is_on(self) -> bool:
        return bool(_session(self.coordinator).get("canbeclosed"))


class EmlaLockHasHolder(EmlaLockBinaryBase):
    _attr_name = "Has holder"
    _attr_translation_key = "has_holder"

    def __init__(self, coordinator, user_id):
        super().__init__(coordinator, user_id, "has_holder")

    @property
    def is_on(self) -> bool:
        return bool(_session(self.coordinator).get("holderid"))


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN]["entries"][entry.entry_id]["coordinator"]
    user_id = entry.data[CONF_USER_ID]
    async_add_entities(
        [
            EmlaLockSessionActive(coordinator, user_id),
            EmlaLockInCleaning(coordinator, user_id),
            EmlaLockCanBeClosed(coordinator, user_id),
            EmlaLockHasHolder(coordinator, user_id),
        ]
    )
