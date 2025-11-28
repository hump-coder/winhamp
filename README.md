# winhamp

Winamp to Home Assistant bridge.

## MQTT bridge

The `winamp_mqtt_bridge.py` script connects to Winamp on Windows and publishes state/commands to MQTT.

- Configure broker credentials at the top of the script.
- State is published to `<base>/state` as JSON with playback status, title, and volume.
- Availability is published to `<base>/availability`.
- Commands are consumed from `<base>/cmnd/*` (play, pause, stop, next, prev, toggle, vol_up, vol_down, volume).

## Home Assistant integration (HACS)

A custom integration is included under `custom_components/winhamp` for use with HACS. It creates a full media player entity powered by the MQTT bridge.

### Installation

1. Copy this repository into your Home Assistant `custom_components` directory or add it as a custom repository in HACS.
2. Restart Home Assistant to load the integration.
3. In Home Assistant, add **Winamp MQTT Bridge** via **Settings → Devices & Services → Add Integration** and supply:
   - **Name**: Friendly name for the entity (default: Winamp).
   - **Base topic**: The MQTT root topic used by the bridge (default: `winamp`).

### Features

- Real-time state updates via MQTT push.
- Media controls: play/pause/stop, previous/next track, toggle, volume up/down, set volume.
- Availability tracking using the bridge's availability topic.
- Device metadata for easy identification in Home Assistant.

Ensure that Home Assistant's MQTT integration is configured and connected to the same broker as the Winamp bridge.
