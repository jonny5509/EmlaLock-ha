from __future__ import annotations

import logging
import re
from pathlib import Path

import voluptuous as vol
from homeassistant.components import frontend
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .api import EmlaLockApi, EmlaLockApiError
from .const import (CONF_API_KEY, CONF_HOLDER_API_KEY, CONF_USER_ID, DOMAIN, CONF_ENABLE_NOTIFICATIONS, CONF_NOTIFICATION_SERVICE, CONF_NOTIFY_DAILY, CONF_NOTIFY_COMPLETION, CONF_NOTIFY_HA_DAILY, CONF_NOTIFY_HA_COMPLETION, DEFAULT_NOTIFICATION_SERVICE)
from .notifications import async_setup_notifications
from .coordinator import EmlaLockCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR, Platform.BUTTON, Platform.CALENDAR]
CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

_CARD_URL = "/emlalock/emlalock-card.js"
_CARD_FILE = Path(__file__).resolve().parent / "www" / "emlalock-card.js"

_SHORT_TIME_RE = re.compile(r"^(?:W\d+|D\d+|H\d+|M\d+|S\d+)+$", re.IGNORECASE)
TIME_ENDPOINTS_WITH_TEXT = {"add", "sub"}


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


def _build_service_schemas():
    """Build service schemas only after Home Assistant has loaded the integration."""
    service_schema = vol.Schema(
        {
            vol.Required("entry_id"): cv.string,
            vol.Required("value"): TIME_VALUE,
            vol.Optional("text", default=""): vol.All(cv.string, vol.Length(max=49)),
        }
    )
    requirement_schema = vol.Schema(
        {
            vol.Required("entry_id"): cv.string,
            vol.Required("value"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        }
    )
    time_random_schema = vol.Schema(
        {
            vol.Required("entry_id"): cv.string,
            vol.Required("from_value"): TIME_VALUE,
            vol.Required("to_value"): TIME_VALUE,
        }
    )
    requirement_random_schema = vol.Schema(
        {
            vol.Required("entry_id"): cv.string,
            vol.Required("from_value"): vol.All(vol.Coerce(int), vol.Range(min=0)),
            vol.Required("to_value"): vol.All(vol.Coerce(int), vol.Range(min=0)),
        }
    )

    return (
        {
            "add_time": ("add", service_schema),
            "subtract_time": ("sub", service_schema),
            "add_maximum": ("addmaximum", service_schema),
            "subtract_maximum": ("submaximum", service_schema),
            "add_minimum": ("addminimum", service_schema),
            "subtract_minimum": ("subminimum", service_schema),
            "add_requirements": ("addrequirement", requirement_schema),
            "subtract_requirements": ("subrequirement", requirement_schema),
        },
        {
            "add_time_random": ("addrandom", time_random_schema),
            "subtract_time_random": ("subrandom", time_random_schema),
            "add_maximum_random": ("addmaximumrandom", time_random_schema),
            "subtract_maximum_random": ("submaximumrandom", time_random_schema),
            "add_minimum_random": ("addminimumrandom", time_random_schema),
            "subtract_minimum_random": ("subminimumrandom", time_random_schema),
            "add_requirements_random": ("addrequirementrandom", requirement_random_schema),
            "subtract_requirements_random": ("subrequirementrandom", requirement_random_schema),
        },
    )


async def async_setup(hass: HomeAssistant, config):
    """Set up EmlaLock."""
    hass.data.setdefault(DOMAIN, {"entries": {}, "services_registered": False})

    async def test_notification(call: ServiceCall) -> None:
        entries = hass.config_entries.async_entries(DOMAIN)
        entry = next((item for item in entries if item.options.get(CONF_ENABLE_NOTIFICATIONS, False)), None)
        if entry is None:
            raise HomeAssistantError("Enable notifications in EmlaLock integration options first")
        options = entry.options
        mobile = options.get(CONF_NOTIFY_DAILY, False) or options.get(CONF_NOTIFY_COMPLETION, False)
        persistent = options.get(CONF_NOTIFY_HA_DAILY, False) or options.get(CONF_NOTIFY_HA_COMPLETION, False)
        if not mobile and not persistent:
            raise HomeAssistantError("Enable at least one test destination in EmlaLock notification options")
        title = "EmlaLock test notification"
        message = "This is a test notification. Your EmlaLock notification delivery is configured."
        if mobile:
            service = str(options.get(CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE))
            if not re.fullmatch(r"notify\\.[a-z0-9_]+", service):
                raise HomeAssistantError("Select a valid mobile notification service in EmlaLock options")
            await hass.services.async_call("notify", service.split(".", 1)[1], {"title": title, "message": message}, blocking=True)
        if persistent:
            await hass.services.async_call("persistent_notification", "create", {"title": title, "message": message, "notification_id": f"emlalock_test_{entry.entry_id}"}, blocking=True)

    if not hass.services.has_service(DOMAIN, "test_notification"):
        hass.services.async_register(DOMAIN, "test_notification", test_notification, schema=vol.Schema({}))
    if _CARD_FILE.is_file():
        try:
            from homeassistant.components.http import StaticPathConfig

            await hass.http.async_register_static_paths(
                [StaticPathConfig(_CARD_URL, str(_CARD_FILE), cache_headers=False)]
            )
            frontend.add_extra_js_url(hass, _CARD_URL)
        except (ImportError, AttributeError, KeyError) as err:
            _LOGGER.warning("Unable to register the EmlaLock Lovelace card: %s", err)

    if not hass.data[DOMAIN]["services_registered"]:
        service_schemas, random_schemas = _build_service_schemas()

        async def run_action(call: ServiceCall, endpoint: str, random: bool = False):
            entry = hass.data[DOMAIN]["entries"].get(call.data["entry_id"])
            if not entry:
                raise HomeAssistantError("Unknown EmlaLock entry")

            try:
                if random:
                    params = {"from": call.data["from_value"], "to": call.data["to_value"]}
                else:
                    params = {"value": call.data["value"]}
                    if endpoint in TIME_ENDPOINTS_WITH_TEXT and call.data.get("text"):
                        params["text"] = call.data["text"]

                await entry["action_api"].action(endpoint, **params)
                await entry["coordinator"].async_request_refresh()
            except EmlaLockApiError as err:
                raise HomeAssistantError(str(err)) from err

        for service_name, (endpoint, schema) in service_schemas.items():

            async def handler(call, ep=endpoint):
                await run_action(call, ep)

            hass.services.async_register(DOMAIN, service_name, handler, schema=schema)

        for service_name, (endpoint, schema) in random_schemas.items():

            async def random_handler(call, ep=endpoint):
                await run_action(call, ep, True)

            hass.services.async_register(DOMAIN, service_name, random_handler, schema=schema)

        hass.data[DOMAIN]["services_registered"] = True
    return True


async def async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry."""
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
    entry.async_on_unload(entry.add_update_listener(async_options_updated))
    await async_setup_notifications(hass, entry, coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    hass.data[DOMAIN]["entries"].pop(entry.entry_id, None)
    if unload_ok and not hass.data[DOMAIN]["entries"]:
        for service_name in (
            "add_time", "subtract_time",
            "add_maximum", "subtract_maximum",
            "add_minimum", "subtract_minimum",
            "add_requirements", "subtract_requirements",
            "add_time_random", "subtract_time_random",
            "add_maximum_random", "subtract_maximum_random",
            "add_minimum_random", "subtract_minimum_random",
            "add_requirements_random", "subtract_requirements_random",
        ):
            if hass.services.has_service(DOMAIN, service_name):
                hass.services.async_remove(DOMAIN, service_name)
        hass.data[DOMAIN]["services_registered"] = False
    return unload_ok
