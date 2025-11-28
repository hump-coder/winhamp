from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
from homeassistant.const import CONF_NAME
from homeassistant.core import callback

from .const import (
    CONF_AVAILABILITY_TOPIC,
    CONF_BASE_TOPIC,
    CONF_COMMAND_TOPIC,
    CONF_STATE_TOPIC,
    CONF_VOLUME_STEP,
    DEFAULT_AVAILABILITY_TOPIC,
    DEFAULT_BASE_TOPIC,
    DEFAULT_COMMAND_TOPIC,
    DEFAULT_NAME,
    DEFAULT_STATE_TOPIC,
    DEFAULT_VOLUME_STEP,
    DOMAIN,
)


def _build_schema(
    name: str,
    base_topic: str,
    state_topic: str,
    command_topic: str,
    availability_topic: str,
    volume_step: int,
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME, default=name): str,
            vol.Required(CONF_BASE_TOPIC, default=base_topic): str,
            vol.Required(CONF_STATE_TOPIC, default=state_topic): str,
            vol.Required(CONF_COMMAND_TOPIC, default=command_topic): str,
            vol.Required(CONF_AVAILABILITY_TOPIC, default=availability_topic): str,
            vol.Optional(
                CONF_VOLUME_STEP, default=volume_step
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=50)),
        }
    )


def _normalize_base_topic(raw: str) -> str:
    return raw.rstrip("/") or DEFAULT_BASE_TOPIC


class WinampConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the config flow for Winamp MQTT bridge."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            base_topic = _normalize_base_topic(user_input[CONF_BASE_TOPIC])
            user_input[CONF_BASE_TOPIC] = base_topic
            await self.async_set_unique_id(base_topic)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=user_input[CONF_NAME], data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=_build_schema(
                DEFAULT_NAME,
                DEFAULT_BASE_TOPIC,
                DEFAULT_STATE_TOPIC,
                DEFAULT_COMMAND_TOPIC,
                DEFAULT_AVAILABILITY_TOPIC,
                DEFAULT_VOLUME_STEP,
            ),
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
            base_topic = _normalize_base_topic(user_input[CONF_BASE_TOPIC])
            user_input[CONF_BASE_TOPIC] = base_topic
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options or self.config_entry.data
        return self.async_show_form(
            step_id="init",
            data_schema=_build_schema(
                current.get(CONF_NAME, DEFAULT_NAME),
                current.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC),
                current.get(CONF_STATE_TOPIC, DEFAULT_STATE_TOPIC),
                current.get(CONF_COMMAND_TOPIC, DEFAULT_COMMAND_TOPIC),
                current.get(CONF_AVAILABILITY_TOPIC, DEFAULT_AVAILABILITY_TOPIC),
                current.get(CONF_VOLUME_STEP, DEFAULT_VOLUME_STEP),
            ),
        )


def get_options_flow(config_entry: config_entries.ConfigEntry) -> WinampOptionsFlowHandler:
    return WinampOptionsFlowHandler(config_entry)
