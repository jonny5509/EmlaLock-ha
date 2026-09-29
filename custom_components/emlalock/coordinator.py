from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import EmlaLockApi, EmlaLockApiError
from .const import DEFAULT_SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class EmlaLockCoordinator(DataUpdateCoordinator[dict]):
    def __init__(self, hass: HomeAssistant, api: EmlaLockApi):
        self.api = api
        super().__init__(
            hass,
            logger=_LOGGER,
            name="EmlaLock",
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )

    async def _async_update_data(self):
        try:
            data = await self.api.info()
        except EmlaLockApiError as err:
            raise UpdateFailed(str(err)) from err

        if "user" not in data:
            raise UpdateFailed("EmlaLock response is missing the user object")
        return data
