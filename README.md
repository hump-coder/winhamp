# winhamp

Winamp to Home Assistant bridge.

## Prerequisites

- Home Assistant with the built-in MQTT integration configured and connected to the same broker that Winamp will use.
- [HACS](https://hacs.xyz/) installed in Home Assistant so you can add a custom repository.
- A reachable MQTT broker (local IP or host on your network).

## MQTT bridge

The `winamp_mqtt_bridge.py` script runs on the Windows machine that hosts Winamp. It publishes Winamp state to MQTT and listens for control commands.

1. Open `winamp_mqtt_bridge.py` and adjust the config constants near the top:
   - `MQTT_HOST`, `MQTT_PORT`, `MQTT_USERNAME`, `MQTT_PASSWORD` to match your broker.
   - `BASE_TOPIC` if you want a topic other than `winamp`.
   - Be sure `MQTT_HOST` points to your broker's IP/hostname and set the username/password if your broker requires authentication.
2. Install dependencies on the Windows machine (Python, `paho-mqtt`, and `pywin32`). Run:

   ```bash
   pip install paho-mqtt pywin32
   ```
3. Start the script while Winamp is running. Leave it running so it can publish state and accept commands.

Topics used by the bridge:

- State: `<base>/state` (JSON payload with playback status, title, volume, and playlist details).
- Availability: `<base>/availability` (online/offline retained message).
- Commands: `<base>/cmnd/*` (play, pause, stop, next, prev, toggle, vol_up, vol_down, volume, play_index).

## Home Assistant integration (HACS)

The `custom_components/winhamp` directory contains a custom integration that creates a fully featured media player entity backed by the MQTT bridge.

### Install via HACS (recommended)

1. In Home Assistant, open **HACS → Integrations** and choose **⋮ → Custom repositories**.
2. Add this repository URL and choose **Integration** as the category. Save.
3. Back in **HACS → Integrations**, click **Explore & download repositories**, search for **Winamp MQTT Bridge**, and install it.
4. Restart Home Assistant to load the new integration.

### Configure the integration in Home Assistant

1. Go to **Settings → Devices & Services → Add Integration**.
2. Select **Winamp MQTT Bridge**.
3. Provide the required options:
   - **Name**: Friendly name for the entity (defaults to "Winamp").
   - **Base topic**: The same base topic you set in `winamp_mqtt_bridge.py` (defaults to `winamp`).
   - **State/command/availability segments**: Override the topic suffixes if your bridge uses something other than the defaults of `state`, `cmnd`, and `availability`.
   - **Volume step**: How many percent to step the volume when using volume up/down buttons (defaults to 5%).
4. Submit and wait for the integration to create the media player entity.

### End-to-end checklist (HACS to working media player)

1. **MQTT ready**: MQTT integration in Home Assistant is connected to your broker.
2. **Bridge configured**: `winamp_mqtt_bridge.py` has the correct broker credentials and base topic, and is running on the Windows/Winamp machine.
3. **HACS install done**: Repository added as a custom repository, integration installed, and Home Assistant restarted.
4. **Integration added**: Winamp MQTT Bridge added via **Devices & Services** with the same base topic as the bridge.
5. **Verify entity**: A media player entity (e.g., `media_player.winamp`) appears and shows the current track/volume. Try play/pause or volume commands from Home Assistant to confirm round-trip control.

### Features

- Real-time state updates via MQTT push.
- Media controls: play/pause/stop, previous/next track, toggle, volume up/down, set volume.
- Playlist browsing and selection exposed as sources in Home Assistant (reads Winamp.m3u8 from `%APPDATA%\Winamp`).
- Availability tracking using the bridge's availability topic.
- Device metadata for easy identification in Home Assistant.
- Fully configurable MQTT topic segments and volume step size through the integration's options flow.
