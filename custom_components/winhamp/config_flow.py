from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from .const import CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC, DEFAULT_NAME, DOMAIN


def _build_schema(name: str, base_topic: str) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=name): str,
            vol.Required(CONF_BASE_TOPIC, default=base_topic): str,
        }
    )


class WinampConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Winamp MQTT bridge."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            await self.async_set_unique_id(DOMAIN)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(DEFAULT_NAME, DEFAULT_BASE_TOPIC),
        )

    async def async_step_import(self, user_input: dict[str, Any]) -> FlowResult:
        """Handle YAML import (legacy)."""
        return await self.async_step_user(user_input)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> "WinampOptionsFlowHandler":
        return WinampOptionsFlowHandler(config_entry)


class WinampOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options or self.config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(
                current.get(CONF_NAME, DEFAULT_NAME),
                current.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC),
            ),
        )


def get_options_flow(config_entry: config_entries.ConfigEntry) -> WinampOptionsFlowHandler:
    return WinampOptionsFlowHandler(config_entry)
