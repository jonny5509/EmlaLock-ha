from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_USER_ID, DOMAIN
from .coordinator import EmlaLockCoordinator
from .runtime_data import EmlaLockConfigEntry


class EmlaLockSessionActive(
    CoordinatorEntity[EmlaLockCoordinator], BinarySensorEntity
):
    """Represent whether an EmlaLock session is active."""

    _attr_has_entity_name = True
    _attr_name = "Session active"
    _attr_translation_key = "session_active"

    def __init__(self, coordinator: EmlaLockCoordinator, user_id: str) -> None:
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
    hass: HomeAssistant,
    entry: EmlaLockConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up EmlaLock binary sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([EmlaLockSessionActive(coordinator, entry.data[CONF_USER_ID])])
