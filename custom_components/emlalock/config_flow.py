from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_API_KEY
from homeassistant.helpers.selector import TextSelector, TextSelectorConfig, TextSelectorType

from .api import EmlaLockApi, EmlaLockApiError
from .const import CONF_HOLDER_API_KEY, CONF_USER_ID, DOMAIN


class EmlaLockConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle EmlaLock config flows."""

    VERSION = 6

    async def _validate_input(
        self, user_input: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, str | None]:
        user_id = user_input[CONF_USER_ID].strip()
        api_key = user_input[CONF_API_KEY].strip()
        holder_api_key = user_input.get(CONF_HOLDER_API_KEY, "").strip()

        try:
            info = await EmlaLockApi(self.hass, user_id, api_key).info()
        except EmlaLockApiError as err:
            if err.code in {"WrongAPIKey", "UserNotFound"}:
                return None, "invalid_auth"
            if err.code is None:
                return None, "cannot_connect"
            return None, "unknown"

        user = info.get("user", {})
        username = user.get("username", user_id)
        verified_user_id = str(user.get("userid", user_id))

        return {
            CONF_USER_ID: user_id,
            CONF_API_KEY: api_key,
            **({CONF_HOLDER_API_KEY: holder_api_key} if holder_api_key else {}),
            "_username": username,
            "_verified_user_id": verified_user_id,
        }, None

    def _schema(self, *, include_user_id: bool = True) -> vol.Schema:
        fields: dict[Any, Any] = {}
        if include_user_id:
            fields[vol.Required(CONF_USER_ID)] = TextSelector(
                TextSelectorConfig(type=TextSelectorType.TEXT)
            )
        fields[vol.Required(CONF_API_KEY)] = TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
        fields[vol.Optional(CONF_HOLDER_API_KEY)] = TextSelector(
            TextSelectorConfig(type=TextSelectorType.PASSWORD)
        )
        return vol.Schema(fields)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial setup flow."""
        if user_input is not None:
            validated, error = await self._validate_input(user_input)
            if error:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._schema(),
                    errors={"base": error},
                )

            assert validated is not None
            verified_user_id = validated.pop("_verified_user_id")
            username = validated.pop("_username")

            await self.async_set_unique_id(verified_user_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=f"EmlaLock - {username}", data=validated
            )

        return self.async_show_form(
            step_id="user",
            data_schema=self._schema(),
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        """Handle reauthentication after an API authentication failure."""
        self._reauth_entry = self.hass.config_entries.async_get_entry(
            self.context["entry_id"]
        )
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm new credentials during reauthentication."""
        errors: dict[str, str] = {}
        entry = self._reauth_entry

        if user_input is not None and entry is not None:
            merged = {
                CONF_USER_ID: entry.data[CONF_USER_ID],
                CONF_API_KEY: user_input[CONF_API_KEY],
                CONF_HOLDER_API_KEY: user_input.get(
                    CONF_HOLDER_API_KEY, entry.data.get(CONF_HOLDER_API_KEY, "")
                ),
            }
            validated, error = await self._validate_input(merged)
            if error:
                errors["base"] = error
            else:
                assert validated is not None
                verified_user_id = validated.pop("_verified_user_id")
                username = validated.pop("_username")
                if verified_user_id != str(entry.data[CONF_USER_ID]):
                    errors["base"] = "wrong_account"
                else:
                    await self.async_set_unique_id(str(entry.unique_id or verified_user_id))
                    return self.async_update_reload_and_abort(
                        entry,
                        title=f"EmlaLock - {username}",
                        data_updates=validated,
                    )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=self._schema(include_user_id=False),
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of EmlaLock credentials."""
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        errors: dict[str, str] = {}

        if user_input is not None and entry is not None:
            merged = {
                CONF_USER_ID: user_input.get(CONF_USER_ID, entry.data[CONF_USER_ID]),
                CONF_API_KEY: user_input[CONF_API_KEY],
                CONF_HOLDER_API_KEY: user_input.get(CONF_HOLDER_API_KEY, ""),
            }
            validated, error = await self._validate_input(merged)
            if error:
                errors["base"] = error
            else:
                assert validated is not None
                verified_user_id = validated.pop("_verified_user_id")
                username = validated.pop("_username")
                if verified_user_id != str(entry.data[CONF_USER_ID]):
                    errors["base"] = "wrong_account"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        title=f"EmlaLock - {username}",
                        data_updates=validated,
                    )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self._schema(),
            errors=errors,
        )
