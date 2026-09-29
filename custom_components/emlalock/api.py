from __future__ import annotations

import asyncio
from typing import Any
from urllib.parse import urlencode

from aiohttp import ClientError, ContentTypeError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_BASE


# The documented API accepts holderapikey on holder-authorized subtract
# operations. Add/info endpoints do not need it.
HOLDER_API_KEY_ENDPOINTS = frozenset(
    {
        "sub",
        "subrandom",
        "submaximum",
        "submaximumrandom",
        "subminimum",
        "subminimumrandom",
        "subrequirement",
        "subrequirementrandom",
    }
)


# EmlaLock's documented error codes. Keep the API code available to callers
# while exposing a useful Home Assistant-facing message.
ERROR_MESSAGES = {
    "MissingRequiredData": "EmlaLock rejected the request because required data is missing.",
    "UserNotFound": "The EmlaLock user was not found.",
    "WrongAPIKey": "The EmlaLock API key is invalid.",
    "NoActiveSession": "There is no active EmlaLock session.",
    "SessionHasNoHolder": "The EmlaLock session does not have a holder.",
    "HolderNotFound": "The EmlaLock holder could not be found or the holder API key is invalid.",
    "InvalidTimeValue": "The EmlaLock time value is invalid.",
}


class EmlaLockApiError(Exception):
    """EmlaLock API error."""

    def __init__(self, message: str, code: str | None = None):
        super().__init__(message)
        self.code = code


class EmlaLockApi:
    def __init__(
        self,
        hass,
        user_id: str,
        api_key: str,
        holder_api_key: str | None = None,
    ):
        self.hass = hass
        self.user_id = user_id
        self.api_key = api_key
        self.holder_api_key = holder_api_key.strip() if holder_api_key else None
        self.session = async_get_clientsession(hass)

    async def request(self, endpoint: str, **params: Any) -> dict[str, Any]:
        endpoint = endpoint.lstrip("/")
        query = {"userid": self.user_id, "apikey": self.api_key, **params}

        if self.holder_api_key and endpoint in HOLDER_API_KEY_ENDPOINTS:
            query["holderapikey"] = self.holder_api_key

        url = f"{API_BASE}/{endpoint}?{urlencode(query)}"
        try:
            async with self.session.get(url, timeout=20) as response:
                try:
                    data = await response.json(content_type=None)
                except (ContentTypeError, ValueError) as err:
                    raise EmlaLockApiError(
                        f"Invalid response from EmlaLock (HTTP {response.status})"
                    ) from err

                if not isinstance(data, dict):
                    raise EmlaLockApiError("Invalid response from EmlaLock")

                error_code = data.get("error")
                if response.status >= 400 or error_code:
                    if isinstance(error_code, str):
                        message = ERROR_MESSAGES.get(error_code, f"EmlaLock API error: {error_code}")
                    else:
                        message = f"EmlaLock API request failed (HTTP {response.status})"
                    raise EmlaLockApiError(message, error_code)

                return data
        except asyncio.TimeoutError as err:
            raise EmlaLockApiError("EmlaLock API request timed out") from err
        except ClientError as err:
            raise EmlaLockApiError("EmlaLock API request failed") from err

    async def info(self) -> dict[str, Any]:
        return await self.request("info")

    async def action(self, endpoint: str, **params: Any) -> dict[str, Any]:
        return await self.request(endpoint, **params)
