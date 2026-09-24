from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_USER_ID, DOMAIN
from .coordinator import EmlaLockCoordinator


class EmlaLockSessionActive(
    CoordinatorEntity[EmlaLockCoordinator], BinarySensorEntity
):
    _attr_has_entity_name = True
    _attr_name = "Session active"
    _attr_translation_key = "session_active"

    def __init__(self, coordinator, user_id: str):
        super().__init__(coordinator)
        self._attr_unique_id = f"{user_id}_session_active"

    @property
    def device_info(self):
        username = (self.coordinator.data or {}).get("user", {}).get("username")
        return {
            "identifiers": {(DOMAIN, self.coordinator.api.user_id)},
            "name": f"EmlaLock - {username}" if username else "EmlaLock",
            "manufacturer": "EmlaLock",
        }

    @property
    def is_on(self) -> bool:
        session = (self.coordinator.data or {}).get("chastitysession") or {}
        return bool(session.get("status"))


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: EmlaLockCoordinator = hass.data[DOMAIN]["entries"][entry.entry_id][
        "coordinator"
    ]
    async_add_entities([EmlaLockSessionActive(coordinator, entry.data[CONF_USER_ID])])
