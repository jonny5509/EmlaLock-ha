from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import voluptuous as vol
from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv

from .api import EmlaLockApi, EmlaLockApiError
from .const import (
    CONF_API_KEY,
    CONF_HOLDER_API_KEY,
    CONF_USER_ID,
    DOMAIN,
)
from .coordinator import EmlaLockCoordinator
from .runtime_data import EmlaLockConfigEntry, EmlaLockRuntimeData

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
]

_CARD_URL = "/emlalock/emlalock-card.js"
_CARD_FILE = Path(__file__).resolve().parent / "www" / "emlalock-card.js"

_SHORT_TIME_RE = re.compile(r"^(?:W\d+|D\d+|H\d+|M\d+|S\d+)+$", re.IGNORECASE)


def _time_value(value: Any) -> int | str:
    """Validate an EmlaLock time value: seconds or documented short terms."""
    if isinstance(value, bool):
        raise vol.Invalid("Time value must be a number or EmlaLock short-term string")
    if isinstance(value, int):
        if value < 0:
            raise vol.Invalid("Time value cannot be negative")
        return value
    if isinstance(value, str):
        value = value.strip()
        if value.isdigit():
            return int(value)
        if not _SHORT_TIME_RE.fullmatch(value):
            raise vol.Invalid("Invalid EmlaLock time value")
        return value.upper()
    raise vol.Invalid("Time value must be a number or EmlaLock short-term string")


TIME_VALUE = _time_value

CONFIG_SCHEMA = cv.empty_config_schema()

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): cv.string,
        vol.Required("value"): TIME_VALUE,
        vol.Optional("text", default=""): vol.All(cv.string, vol.Length(max=49)),
    }
)

REQUIREMENT_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): cv.string,
        vol.Required("value"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)

TIME_RANDOM_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): cv.string,
        vol.Required("from_value"): TIME_VALUE,
        vol.Required("to_value"): TIME_VALUE,
    }
)

REQUIREMENT_RANDOM_SCHEMA = vol.Schema(
    {
        vol.Required("entry_id"): cv.string,
        vol.Required("from_value"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Required("to_value"): vol.All(vol.Coerce(int), vol.Range(min=0)),
    }
)

TIME_ENDPOINTS_WITH_TEXT = {"add", "sub"}


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    """Set up the EmlaLock integration."""
    if _CARD_FILE.is_file():
        await hass.http.async_register_static_paths(
            [StaticPathConfig(_CARD_URL, str(_CARD_FILE), cache_headers=False)]
        )
        frontend.add_extra_js_url(hass, _CARD_URL)

    if hass.services.has_service(DOMAIN, "add_time"):
        return True

    async def run_action(
        call: ServiceCall, endpoint: str, random: bool = False
    ) -> None:
        entry = hass.config_entries.async_get_entry(call.data["entry_id"])
        if entry is None or entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError("The EmlaLock config entry is not loaded")

        runtime_data = entry.runtime_data
        if not isinstance(runtime_data, EmlaLockRuntimeData):
            raise HomeAssistantError("The EmlaLock integration is not loaded")

        try:
            if random:
                params = {
                    "from": call.data["from_value"],
                    "to": call.data["to_value"],
                }
            else:
                params = {"value": call.data["value"]}
                if endpoint in TIME_ENDPOINTS_WITH_TEXT and call.data.get("text"):
                    params["text"] = call.data["text"]

            await runtime_data.api.action(endpoint, **params)
            await runtime_data.coordinator.async_request_refresh()
        except EmlaLockApiError as err:
            raise HomeAssistantError(str(err)) from err

    service_schemas = {
        "add_time": ("add", False, SERVICE_SCHEMA),
        "subtract_time": ("sub", False, SERVICE_SCHEMA),
        "add_maximum": ("addmaximum", False, SERVICE_SCHEMA),
        "subtract_maximum": ("submaximum", False, SERVICE_SCHEMA),
        "add_minimum": ("addminimum", False, SERVICE_SCHEMA),
        "subtract_minimum": ("subminimum", False, SERVICE_SCHEMA),
        "add_requirements": ("addrequirement", False, REQUIREMENT_SCHEMA),
        "subtract_requirements": ("subrequirement", False, REQUIREMENT_SCHEMA),
    }

    for service_name, (endpoint, random, schema) in service_schemas.items():

        async def handler(call: ServiceCall, ep=endpoint, is_random=random) -> None:
            await run_action(call, ep, is_random)

        hass.services.async_register(DOMAIN, service_name, handler, schema=schema)

    random_schemas = {
        "add_time_random": ("addrandom", TIME_RANDOM_SCHEMA),
        "subtract_time_random": ("subrandom", TIME_RANDOM_SCHEMA),
        "add_maximum_random": ("addmaximumrandom", TIME_RANDOM_SCHEMA),
        "subtract_maximum_random": ("submaximumrandom", TIME_RANDOM_SCHEMA),
        "add_minimum_random": ("addminimumrandom", TIME_RANDOM_SCHEMA),
        "subtract_minimum_random": ("subminimumrandom", TIME_RANDOM_SCHEMA),
        "add_requirements_random": ("addrequirementrandom", REQUIREMENT_RANDOM_SCHEMA),
        "subtract_requirements_random": ("subrequirementrandom", REQUIREMENT_RANDOM_SCHEMA),
    }

    for service_name, (endpoint, schema) in random_schemas.items():

        async def random_handler(call: ServiceCall, ep=endpoint) -> None:
            await run_action(call, ep, True)

        hass.services.async_register(
            DOMAIN, service_name, random_handler, schema=schema
        )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: EmlaLockConfigEntry) -> bool:
    """Set up an EmlaLock config entry."""
    action_api = EmlaLockApi(
        hass,
        entry.data[CONF_USER_ID],
        entry.data[CONF_API_KEY],
        holder_api_key=entry.data.get(CONF_HOLDER_API_KEY),
    )
    coordinator = EmlaLockCoordinator(hass, action_api)
    entry.runtime_data = EmlaLockRuntimeData(action_api, coordinator)

    await coordinator.async_config_entry_first_refresh()
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: EmlaLockConfigEntry) -> bool:
    """Unload an EmlaLock config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Migrate older EmlaLock config entries."""
    if config_entry.version < 6:
        user_id = str(config_entry.data.get(CONF_USER_ID, "")).strip()
        if user_id:
            hass.config_entries.async_update_entry(
                config_entry, unique_id=user_id, version=6
            )
        else:
            hass.config_entries.async_update_entry(config_entry, version=6)
    return True
