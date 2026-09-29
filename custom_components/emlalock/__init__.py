from __future__ import annotations

import re
from pathlib import Path

import voluptuous as vol
from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .api import EmlaLockApi, EmlaLockApiError
from .const import CONF_API_KEY, CONF_HOLDER_API_KEY, CONF_USER_ID, DOMAIN
from .coordinator import EmlaLockCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON]

_CARD_URL = "/emlalock/emlalock-card.js"
_CARD_FILE = Path(__file__).resolve().parent / "www" / "emlalock-card.js"

_SHORT_TIME_RE = re.compile(r"^(?:W\d+|D\d+|H\d+|M\d+|S\d+)+$", re.IGNORECASE)


def _time_value(value):
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


async def async_setup(hass: HomeAssistant, config):
    hass.data.setdefault(DOMAIN, {"entries": {}, "services_registered": False})

    # Make the bundled Lovelace card available automatically. The card lives
    # inside the installed integration package, so HACS installs it together
    # with EmlaLock and users do not need a separate dashboard resource.
    if _CARD_FILE.is_file():
        await hass.http.async_register_static_paths(
            [StaticPathConfig(_CARD_URL, str(_CARD_FILE), cache_headers=False)]
        )
        frontend.add_extra_js_url(hass, _CARD_URL)

    if not hass.data[DOMAIN]["services_registered"]:

        async def run_action(call: ServiceCall, endpoint: str, random: bool = False):
            entry = hass.data[DOMAIN]["entries"].get(call.data["entry_id"])
            if not entry:
                raise vol.Invalid("Unknown EmlaLock entry")

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

                await entry["action_api"].action(endpoint, **params)
                await entry["coordinator"].async_request_refresh()
            except EmlaLockApiError as err:
                raise vol.Invalid(str(err)) from err

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

            async def handler(call, ep=endpoint, is_random=random):
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

            async def random_handler(call, ep=endpoint):
                await run_action(call, ep, True)

            hass.services.async_register(DOMAIN, service_name, random_handler, schema=schema)

        hass.data[DOMAIN]["services_registered"] = True
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    data = entry.data
    action_api = EmlaLockApi(
        hass,
        data[CONF_USER_ID],
        data[CONF_API_KEY],
        holder_api_key=data.get(CONF_HOLDER_API_KEY),
    )

    coordinator = EmlaLockCoordinator(hass, action_api)
    await coordinator.async_config_entry_first_refresh()
    hass.data[DOMAIN]["entries"][entry.entry_id] = {
        "coordinator": coordinator,
        "action_api": action_api,
    }
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data[DOMAIN]["entries"].pop(entry.entry_id, None)
    return unload_ok
