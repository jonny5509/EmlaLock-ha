from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_API_KEY
from homeassistant.core import callback

from .api import EmlaLockApi, EmlaLockApiError
from .const import (
    CONF_HOLDER_API_KEY, CONF_USER_ID, DOMAIN, CONF_ENABLE_NOTIFICATIONS, CONF_ENABLE_PHONE_NOTIFICATIONS, CONF_ENABLE_HA_NOTIFICATIONS,
    CONF_NOTIFICATION_SERVICE, CONF_NOTIFY_DAILY, CONF_NOTIFY_COMPLETION,
    CONF_NOTIFY_HA_DAILY, CONF_NOTIFY_HA_COMPLETION,
    DEFAULT_NOTIFICATION_SERVICE,
)


class EmlaLockConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 5

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return EmlaLockOptionsFlow()

    async def async_step_user(self, user_input=None):
        if self._async_current_entries():
            return self.async_abort(reason="already_configured")

        errors = {}

        if user_input is not None:
            user_input[CONF_USER_ID] = user_input[CONF_USER_ID].strip()
            user_input[CONF_API_KEY] = user_input[CONF_API_KEY].strip()
            if user_input.get(CONF_HOLDER_API_KEY):
                user_input[CONF_HOLDER_API_KEY] = user_input[CONF_HOLDER_API_KEY].strip()

            try:
                info = await EmlaLockApi(
                    self.hass,
                    user_input[CONF_USER_ID],
                    user_input[CONF_API_KEY],
                ).info()
            except EmlaLockApiError as err:
                if err.code in {"WrongAPIKey", "UserNotFound"}:
                    errors["base"] = "invalid_auth"
                elif err.code is None:
                    errors["base"] = "cannot_connect"
                else:
                    errors["base"] = "unknown"
            else:
                user = info.get("user", {})
                username = user.get("username", user_input[CONF_USER_ID])
                userid = str(user.get("userid", user_input[CONF_USER_ID]))

                existing = next(
                    (
                        entry
                        for entry in self.hass.config_entries.async_entries(DOMAIN)
                        if str(entry.data.get(CONF_USER_ID, "")) == userid
                    ),
                    None,
                )
                if existing:
                    data = dict(existing.data)
                    data[CONF_USER_ID] = user_input[CONF_USER_ID]
                    data[CONF_API_KEY] = user_input[CONF_API_KEY]
                    if user_input.get(CONF_HOLDER_API_KEY):
                        data[CONF_HOLDER_API_KEY] = user_input[CONF_HOLDER_API_KEY]
                    else:
                        data.pop(CONF_HOLDER_API_KEY, None)

                    self.hass.config_entries.async_update_entry(
                        existing,
                        title=f"EmlaLock - {username}",
                        data=data,
                    )
                    await self.hass.config_entries.async_reload(existing.entry_id)
                    return self.async_abort(reason="already_configured")

                await self.async_set_unique_id("emlalock")
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=f"EmlaLock - {username}",
                    data=user_input,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USER_ID): str,
                    vol.Required(CONF_API_KEY): str,
                    vol.Optional(CONF_HOLDER_API_KEY): str,
                }
            ),
            errors=errors,
        )


class EmlaLockOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)
        options = self.config_entry.options
        notify_services = sorted(self.hass.services.async_services().get("notify", {}))
        if "notify" not in notify_services:
            notify_services.insert(0, "notify")
        service_options = [f"notify.{name}" for name in notify_services]
        if options.get(CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE) not in service_options:
            service_options.append(options.get(CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE))
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(CONF_ENABLE_PHONE_NOTIFICATIONS, default=options.get(CONF_ENABLE_PHONE_NOTIFICATIONS, False)): bool,
                vol.Optional(CONF_ENABLE_HA_NOTIFICATIONS, default=options.get(CONF_ENABLE_HA_NOTIFICATIONS, False)): bool,
                vol.Optional(CONF_NOTIFICATION_SERVICE, default=options.get(CONF_NOTIFICATION_SERVICE, DEFAULT_NOTIFICATION_SERVICE)): vol.In(service_options),
                vol.Optional(CONF_NOTIFY_HA_DAILY, default=options.get(CONF_NOTIFY_HA_DAILY, False)): bool,
                vol.Optional(CONF_NOTIFY_HA_COMPLETION, default=options.get(CONF_NOTIFY_HA_COMPLETION, False)): bool,
                vol.Optional(CONF_NOTIFY_DAILY, default=options.get(CONF_NOTIFY_DAILY, False)): bool,
                vol.Optional(CONF_NOTIFY_COMPLETION, default=options.get(CONF_NOTIFY_COMPLETION, False)): bool,
            }),
        )
