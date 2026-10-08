from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EmlaLockApi, EmlaLockApiError
from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class EmlaLockCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate EmlaLock API updates."""

    def __init__(self, hass: HomeAssistant, api: EmlaLockApi) -> None:
        self.api = api
        super().__init__(
            hass,
            logger=_LOGGER,
            name="EmlaLock",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.api.info()
        except EmlaLockApiError as err:
            if err.code in {"WrongAPIKey", "UserNotFound"}:
                raise ConfigEntryAuthFailed(str(err)) from err
            raise UpdateFailed(str(err)) from err

        if "user" not in data:
            raise UpdateFailed("EmlaLock response is missing the user object")
        return data
