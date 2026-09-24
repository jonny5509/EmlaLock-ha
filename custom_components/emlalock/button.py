from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import EmlaLockApiError
from .const import DOMAIN
from .coordinator import EmlaLockCoordinator


class EmlaLockRefreshButton(CoordinatorEntity[EmlaLockCoordinator], ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Refresh"

    def __init__(self, coordinator, user_id):
        super().__init__(coordinator)
        self._attr_unique_id = f"{user_id}_refresh"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.api.user_id)},
            "name": "EmlaLock",
            "manufacturer": "EmlaLock",
        }

    async def async_press(self) -> None:
        await self.coordinator.async_request_refresh()


class EmlaLockActionButton(CoordinatorEntity[EmlaLockCoordinator], ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, user_id, name, value, subtract=False):
        super().__init__(coordinator)
        self._value = value
        self._subtract = subtract
        self._attr_name = name
        self._attr_unique_id = f"{user_id}_{name.lower().replace(' ', '_')}"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.coordinator.api.user_id)},
            "name": "EmlaLock",
            "manufacturer": "EmlaLock",
        }

    @property
    def available(self) -> bool:
        if not super().available:
            return False

        session = (self.coordinator.data or {}).get("chastitysession") or {}
        if not session.get("status"):
            return False

        if not self.coordinator.api.holder_api_key:
            return False

        return True

    async def async_press(self) -> None:
        endpoint = "sub" if self._subtract else "add"
        try:
            await self.coordinator.api.action(
                endpoint,
                value=self._value,
                text="Home Assistant",
            )
        except EmlaLockApiError as err:
            raise HomeAssistantError(str(err)) from err

        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator: EmlaLockCoordinator = hass.data[DOMAIN]["entries"][entry.entry_id][
        "coordinator"
    ]
    user_id = entry.data["user_id"]

    entities = [EmlaLockRefreshButton(coordinator, user_id)]
    for value, label in (
        (3600, "1 hour"),
        (86400, "1 day"),
    ):
        entities.append(
            EmlaLockActionButton(coordinator, user_id, f"Add {label}", value)
        )
        entities.append(
            EmlaLockActionButton(
                coordinator,
                user_id,
                f"Subtract {label}",
                value,
                subtract=True,
            )
        )

    async_add_entities(entities)
