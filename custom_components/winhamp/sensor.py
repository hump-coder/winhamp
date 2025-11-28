from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable

from homeassistant.components import mqtt
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.util import dt as dt_util

from .const import (
    CONF_AVAILABILITY_TOPIC,
    CONF_BASE_TOPIC,
    CONF_COMMAND_TOPIC,
    CONF_STATE_TOPIC,
    DEFAULT_AVAILABILITY_TOPIC,
    DEFAULT_BASE_TOPIC,
    DEFAULT_COMMAND_TOPIC,
    DEFAULT_NAME,
    DEFAULT_STATE_TOPIC,
    DOMAIN,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = {**entry.data, **entry.options}
    name: str = data.get(CONF_NAME, DEFAULT_NAME)
    base_topic: str = data.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC).rstrip("/")
    state_topic: str = data.get(CONF_STATE_TOPIC, DEFAULT_STATE_TOPIC).strip("/")
    command_topic: str = data.get(CONF_COMMAND_TOPIC, DEFAULT_COMMAND_TOPIC).strip("/")
    availability_topic: str = data.get(
        CONF_AVAILABILITY_TOPIC, DEFAULT_AVAILABILITY_TOPIC
    ).strip("/")

    async_add_entities(
        [
            AvailabilityDebugSensor(
                hass,
                name,
                base_topic,
                availability_topic,
                command_topic,
                state_topic,
            ),
            StateDebugSensor(
                hass,
                name,
                base_topic,
                availability_topic,
                command_topic,
                state_topic,
            ),
        ]
    )


class BaseDebugSensor(SensorEntity):
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        base_topic: str,
        availability_topic: str,
        command_topic: str,
        state_topic: str,
    ) -> None:
        self.hass = hass
        self._attr_name = name
        self._base_topic = base_topic
        self._availability_topic = availability_topic
        self._command_topic = command_topic
        self._state_topic = state_topic
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, base_topic)},
            manufacturer="Winamp",
            model="MQTT Bridge",
            name=name,
        )
        self._last_message_time: datetime | None = None
        self._availability_unsub: Callable[[], None] | None = None
        self._state_unsub: Callable[[], None] | None = None

    async def async_will_remove_from_hass(self) -> None:
        if self._availability_unsub:
            self._availability_unsub()
        if self._state_unsub:
            self._state_unsub()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "base_topic": self._base_topic,
            "state_topic": f"{self._base_topic}/{self._state_topic}",
            "command_topic": f"{self._base_topic}/{self._command_topic}",
            "availability_topic": f"{self._base_topic}/{self._availability_topic}",
            "last_message": self._last_message_time,
        }


class AvailabilityDebugSensor(BaseDebugSensor):
    _attr_icon = "mdi:lan-connect"

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        base_topic: str,
        availability_topic: str,
        command_topic: str,
        state_topic: str,
    ) -> None:
        super().__init__(
            hass, name, base_topic, availability_topic, command_topic, state_topic
        )
        self._availability_online = False
        self._attr_name = f"{name} MQTT Availability"

    async def async_added_to_hass(self) -> None:
        self._availability_unsub = await mqtt.async_subscribe(
            self.hass,
            f"{self._base_topic}/{self._availability_topic}",
            self._handle_availability,
        )

    @property
    def native_value(self) -> str:
        return "online" if self._availability_online else "offline"

    @callback
    def _handle_availability(self, msg: ReceiveMessage) -> None:
        self._availability_online = msg.payload.decode().strip().lower() == "online"
        self._last_message_time = dt_util.utcnow()
        self.async_write_ha_state()


class StateDebugSensor(BaseDebugSensor):
    _attr_icon = "mdi:message-text"

    def __init__(
        self,
        hass: HomeAssistant,
        name: str,
        base_topic: str,
        availability_topic: str,
        command_topic: str,
        state_topic: str,
    ) -> None:
        super().__init__(
            hass, name, base_topic, availability_topic, command_topic, state_topic
        )
        self._attr_name = f"{name} MQTT State"
        self._status: str | None = None
        self._last_payload: str | None = None
        self._last_title: str | None = None
        self._last_volume: float | None = None
        self._last_available: bool | None = None

    async def async_added_to_hass(self) -> None:
        self._state_unsub = await mqtt.async_subscribe(
            self.hass,
            f"{self._base_topic}/{self._state_topic}",
            self._handle_state,
        )

    @property
    def native_value(self) -> str | None:
        return self._status or "unknown"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attrs = super().extra_state_attributes
        attrs.update(
            {
                "last_payload": self._last_payload,
                "last_title": self._last_title,
                "last_volume": self._last_volume,
                "reported_available": self._last_available,
            }
        )
        return attrs

    @callback
    def _handle_state(self, msg: ReceiveMessage) -> None:
        raw = msg.payload.decode()
        self._last_payload = raw
        self._last_message_time = dt_util.utcnow()

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            self._status = "invalid_payload"
            self._last_title = None
            self._last_volume = None
            self._last_available = None
            self.async_write_ha_state()
            return

        status = payload.get("status")
        if isinstance(status, str):
            self._status = status.lower()
        else:
            self._status = "unknown"

        title = payload.get("title")
        self._last_title = title if isinstance(title, str) else None

        volume = payload.get("volume")
        if isinstance(volume, (int, float)):
            self._last_volume = max(0.0, min(1.0, float(volume) / 100.0))
        else:
            self._last_volume = None

        available_value = payload.get("available")
        if isinstance(available_value, bool):
            self._last_available = available_value
        else:
            self._last_available = None

        self.async_write_ha_state()
