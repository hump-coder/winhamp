from __future__ import annotations

import json
from typing import Callable

from homeassistant.components import mqtt
from homeassistant.components.mqtt.models import Message
from homeassistant.components.media_player import MediaPlayerEntity, MediaPlayerEntityFeature, MediaPlayerState
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import DeviceInfo

from .const import CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC, DEFAULT_NAME, DOMAIN


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = {**entry.data, **entry.options}
    name: str = data.get(CONF_NAME, DEFAULT_NAME)
    base_topic: str = data.get(CONF_BASE_TOPIC, DEFAULT_BASE_TOPIC).rstrip("/")

    async_add_entities([WinampMqttMediaPlayer(hass, name, base_topic)])


class WinampMqttMediaPlayer(MediaPlayerEntity):
    _attr_should_poll = False

    def __init__(self, hass: HomeAssistant, name: str, base_topic: str) -> None:
        self.hass = hass
        self._attr_name = name
        self._base_topic = base_topic
        self._status: MediaPlayerState | None = None
        self._title: str | None = None
        self._volume: float | None = None
        self._available_flag: bool | None = None
        self._availability_online = False
        self._state_unsub: Callable[[], None] | None = None
        self._availability_unsub: Callable[[], None] | None = None
        self._attr_supported_features = (
            MediaPlayerEntityFeature.PLAY
            | MediaPlayerEntityFeature.PAUSE
            | MediaPlayerEntityFeature.STOP
            | MediaPlayerEntityFeature.NEXT_TRACK
            | MediaPlayerEntityFeature.PREVIOUS_TRACK
            | MediaPlayerEntityFeature.VOLUME_SET
            | MediaPlayerEntityFeature.VOLUME_STEP
            | MediaPlayerEntityFeature.TURN_ON
            | MediaPlayerEntityFeature.TURN_OFF
        )

    async def async_added_to_hass(self) -> None:
        self._state_unsub = await mqtt.async_subscribe(
            self.hass,
            f"{self._base_topic}/state",
            self._handle_state_message,
        )
        self._availability_unsub = await mqtt.async_subscribe(
            self.hass,
            f"{self._base_topic}/availability",
            self._handle_availability,
        )

    async def async_will_remove_from_hass(self) -> None:
        if self._state_unsub:
            self._state_unsub()
        if self._availability_unsub:
            self._availability_unsub()

    @property
    def available(self) -> bool:
        if self._available_flag is None:
            return self._availability_online
        return self._availability_online and self._available_flag

    @property
    def state(self) -> MediaPlayerState | None:
        return self._status

    @property
    def media_title(self) -> str | None:
        return self._title

    @property
    def volume_level(self) -> float | None:
        return self._volume

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._base_topic)},
            manufacturer="Winamp",
            model="MQTT Bridge",
            name=self._attr_name,
        )

    @callback
    def _handle_state_message(self, msg: Message) -> None:
        try:
            payload = json.loads(msg.payload)
        except json.JSONDecodeError:
            return

        status = payload.get("status")
        if status == "playing":
            self._status = MediaPlayerState.PLAYING
        elif status == "paused":
            self._status = MediaPlayerState.PAUSED
        elif status in ("idle", "off"):
            self._status = MediaPlayerState.IDLE
        else:
            self._status = None

        self._title = payload.get("title") or None

        volume = payload.get("volume")
        if isinstance(volume, (int, float)):
            self._volume = max(0.0, min(1.0, float(volume) / 100.0))
        else:
            self._volume = None

        available_value = payload.get("available")
        if isinstance(available_value, bool):
            self._available_flag = available_value

        self.async_write_ha_state()

    @callback
    def _handle_availability(self, msg: Message) -> None:
        self._availability_online = msg.payload.decode().strip().lower() == "online"
        self.async_write_ha_state()

    async def async_media_play(self) -> None:
        await self._publish_command("play")

    async def async_media_pause(self) -> None:
        await self._publish_command("pause")

    async def async_media_stop(self) -> None:
        await self._publish_command("stop")

    async def async_media_next_track(self) -> None:
        await self._publish_command("next")

    async def async_media_previous_track(self) -> None:
        await self._publish_command("prev")

    async def async_toggle(self) -> None:
        await self._publish_command("toggle")

    async def async_turn_on(self) -> None:
        await self._publish_command("play")

    async def async_turn_off(self) -> None:
        await self._publish_command("stop")

    async def async_volume_up(self) -> None:
        await self._publish_command("vol_up")

    async def async_volume_down(self) -> None:
        await self._publish_command("vol_down")

    async def async_set_volume_level(self, volume: float) -> None:
        percent = max(0, min(100, int(volume * 100)))
        await self._publish_command("volume", str(percent))

    async def _publish_command(self, command: str, payload: str | None = None) -> None:
        topic = f"{self._base_topic}/cmnd/{command}"
        await mqtt.async_publish(self.hass, topic, payload or "")
