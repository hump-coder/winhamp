import time
import json
import logging
import threading
import os

import win32gui
import win32api
import win32con
import win32process
import paho.mqtt.client as mqtt

# --- CONFIG -----------------------------------------------------------------

MQTT_HOST = "192.168.1.11"   # <-- change to your MQTT broker IP
MQTT_PORT = 1883
MQTT_USERNAME = "user"         # or "user"
MQTT_PASSWORD = "pass"         # or "pass"

BASE_TOPIC = "winamp"        # will use winamp/state and winamp/cmnd/...

# Where to read the current playlist from. Winamp keeps an updated copy of the
# active playlist at %APPDATA%\Winamp\Winamp.m3u8 by default, but some
# installations (portable installs, legacy versions, custom settings) write the
# playlist next to winamp.exe or only emit the ANSI Winamp.m3u variant. We try
# all known locations and pick the most recently modified file.
PLAYLIST_PATH = os.path.join(os.environ.get("APPDATA", ""), "Winamp", "Winamp.m3u8")
MAX_PLAYLIST_ITEMS = 500

POLL_INTERVAL_SEC = 2        # how often to publish state

# --- WINAMP CONSTANTS -------------------------------------------------------

WINAMP_CLASS = "Winamp v1.x"

WM_COMMAND = win32con.WM_COMMAND
WM_WA_IPC = win32con.WM_USER  # Winamp’s IPC base :contentReference[oaicite:1]{index=1}

# WM_COMMAND playback IDs (documented Winamp API)
WA_PREV  = 40044
WA_PLAY  = 40045
WA_PAUSE = 40046
WA_STOP  = 40047
WA_NEXT  = 40048          # :contentReference[oaicite:2]{index=2}

# IPC codes
IPC_ISPLAYING = 104       # 1=playing, 3=paused, 0=stopped :contentReference[oaicite:3]{index=3}
IPC_SETVOLUME = 122       # 0–255; -666 returns current volume :contentReference[oaicite:4]{index=4}
IPC_SETPLAYLISTPOS = 121
IPC_GETLISTLENGTH = 124
IPC_GETLISTPOS = 125

# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def find_winamp_hwnd():
    """Find Winamp main window handle."""
    hwnd = win32gui.FindWindow(WINAMP_CLASS, None)
    return hwnd or None


def send_winamp_command(cmd_id):
    hwnd = find_winamp_hwnd()
    if not hwnd:
        logging.warning("Winamp window not found for command %s", cmd_id)
        return False
    win32api.SendMessage(hwnd, WM_COMMAND, cmd_id, 0)
    return True


def set_volume_percent(percent):
    hwnd = find_winamp_hwnd()
    if not hwnd:
        logging.warning("Winamp window not found for volume set")
        return False

    percent = max(0, min(100, int(percent)))
    vol_0_255 = int(percent * 255 / 100)
    win32api.SendMessage(hwnd, WM_WA_IPC, vol_0_255, IPC_SETVOLUME)
    return True


def get_volume_percent(hwnd):
    """Return volume 0–100 or None."""
    res = win32api.SendMessage(hwnd, WM_WA_IPC, -666, IPC_SETVOLUME)
    if res < 0:
        return None
    return int(res * 100 / 255)


def get_playback_status(hwnd):
    """
    Return 'playing', 'paused', 'idle' based on IPC_ISPLAYING.
    """
    res = win32api.SendMessage(hwnd, WM_WA_IPC, 0, IPC_ISPLAYING)
    if res == 1:
        return "playing"
    elif res == 3:
        return "paused"
    else:
        return "idle"


def get_title_from_window(hwnd):
    """
    Grab Winamp window title and strip trailing ' - Winamp'.
    Typically looks like: '01. Artist - Track - Winamp'. :contentReference[oaicite:5]{index=5}
    """
    raw = win32gui.GetWindowText(hwnd)
    if raw.lower().endswith(" - winamp"):
        raw = raw[:-len(" - Winamp")]
    return raw


def get_playlist_position(hwnd):
    """Return the current playlist index or None if unavailable."""
    res = win32api.SendMessage(hwnd, WM_WA_IPC, 0, IPC_GETLISTPOS)
    if res < 0:
        return None
    return int(res)


def set_playlist_position(hwnd, position):
    """Jump to a playlist index and start playback."""
    if position is None or position < 0:
        return False
    win32api.SendMessage(hwnd, WM_WA_IPC, int(position), IPC_SETPLAYLISTPOS)
    send_winamp_command(WA_PLAY)
    return True


def read_playlist_from_disk():
    """Return a list of playlist entries from the newest available playlist file."""

    def candidate_paths():
        # Caller may override via env var (useful for debugging/testing)
        override = os.environ.get("WINAMP_PLAYLIST_PATH")
        if override:
            yield override

        # Default AppData location (UTF-8)
        if PLAYLIST_PATH:
            yield PLAYLIST_PATH
            yield os.path.splitext(PLAYLIST_PATH)[0] + ".m3u"

        # Portable installs often keep the playlist next to winamp.exe
        hwnd = find_winamp_hwnd()
        if hwnd:
            process = None
            try:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                process = win32api.OpenProcess(
                    win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ,
                    False,
                    pid,
                )
                exe_path = win32process.GetModuleFileNameEx(process, 0)
                winamp_dir = os.path.dirname(exe_path)
                yield os.path.join(winamp_dir, "Winamp.m3u8")
                yield os.path.join(winamp_dir, "Winamp.m3u")
            except Exception:
                logging.debug("Unable to resolve Winamp executable path", exc_info=True)
            finally:
                if process:
                    win32api.CloseHandle(process)

    def newest_existing_path():
        newest = None
        newest_mtime = None
        for path in candidate_paths():
            if not path:
                continue
            try:
                mtime = os.path.getmtime(path)
            except FileNotFoundError:
                continue
            if newest is None or mtime > newest_mtime:
                newest = path
                newest_mtime = mtime
        return newest

    playlist_file = newest_existing_path()
    if not playlist_file:
        logging.debug("No playlist file found in expected locations")
        return []

    try:
        with open(playlist_file, "r", encoding="utf-8", errors="ignore") as fh:
            items = []
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                items.append(line)
                if len(items) >= MAX_PLAYLIST_ITEMS:
                    break
            return items
    except Exception:
        logging.exception("Could not read playlist from %s", playlist_file)
        return []


class WinampMqttBridge:
    def __init__(self):
        self.client = mqtt.Client()
        if MQTT_USERNAME:
            self.client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)

        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        self.last_state = {}

    # --- MQTT callbacks -----------------------------------------------------

    def on_connect(self, client, userdata, flags, reason_code, properties=None):
        logging.info("Connected to MQTT with result code %s", reason_code)
        # Command topics:
        #   winamp/cmnd/play, pause, stop, next, prev
        #   winamp/cmnd/toggle
        #   winamp/cmnd/volume (payload: 0–100)
        #   winamp/cmnd/vol_up, vol_down
        client.subscribe(BASE_TOPIC + "/cmnd/#")

        # Announce availability
        client.publish(
            BASE_TOPIC + "/availability",
            "online",
            retain=True
        )

    def on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode(errors="ignore").strip()
        logging.info("MQTT cmd %s => %s", topic, payload)

        cmd = topic[len(BASE_TOPIC + "/cmnd/"):] if topic.startswith(BASE_TOPIC + "/cmnd/") else ""

        if cmd == "play":
            send_winamp_command(WA_PLAY)
        elif cmd == "pause":
            send_winamp_command(WA_PAUSE)
        elif cmd == "stop":
            send_winamp_command(WA_STOP)
        elif cmd == "next":
            send_winamp_command(WA_NEXT)
        elif cmd == "prev":
            send_winamp_command(WA_PREV)
        elif cmd == "toggle":
            # Simple toggle: if playing -> pause, else play
            hwnd = find_winamp_hwnd()
            if hwnd:
                state = get_playback_status(hwnd)
                if state == "playing":
                    send_winamp_command(WA_PAUSE)
                else:
                    send_winamp_command(WA_PLAY)
        elif cmd == "vol_up":
            self.adjust_volume(+5)
        elif cmd == "vol_down":
            self.adjust_volume(-5)
        elif cmd == "volume":
            try:
                value = float(payload)
                set_volume_percent(value)
            except ValueError:
                logging.warning("Invalid volume payload: %r", payload)
        elif cmd == "play_index":
            try:
                target = int(payload)
            except ValueError:
                logging.warning("Invalid play_index payload: %r", payload)
                return

            hwnd = find_winamp_hwnd()
            if not hwnd:
                logging.warning("Cannot jump to playlist entry; Winamp window missing")
                return

            length = win32api.SendMessage(hwnd, WM_WA_IPC, 0, IPC_GETLISTLENGTH)
            if length < 0:
                logging.warning("Winamp playlist length unavailable")
                return

            if target < 0 or target >= length:
                logging.warning("Requested playlist index %s out of range (0-%s)", target, length - 1)
                return

            set_playlist_position(hwnd, target)

    def adjust_volume(self, delta):
        hwnd = find_winamp_hwnd()
        if not hwnd:
            return
        current = get_volume_percent(hwnd)
        if current is None:
            return
        set_volume_percent(current + delta)

    # --- State publishing loop ---------------------------------------------

    def publish_state_loop(self):
        while True:
            try:
                hwnd = find_winamp_hwnd()
                if not hwnd:
                    state = {
                        "available": False,
                        "status": "off",
                        "title": "",
                        "volume": None,
                        "playlist": [],
                        "position": None,
                    }
                else:
                    status = get_playback_status(hwnd)
                    title = get_title_from_window(hwnd)
                    volume = get_volume_percent(hwnd)
                    playlist_position = get_playlist_position(hwnd)
                    playlist_items = read_playlist_from_disk()
                    state = {
                        "available": True,
                        "status": status,   # playing|paused|idle
                        "title": title,
                        "volume": volume,
                        "playlist": playlist_items,
                        "position": playlist_position,
                    }

                if state != self.last_state:
                    self.client.publish(
                        BASE_TOPIC + "/state",
                        json.dumps(state),
                        retain=True
                    )
                    self.last_state = state
            except Exception as e:
                logging.exception("Error in publish_state_loop: %s", e)

            time.sleep(POLL_INTERVAL_SEC)

    def run(self):
        # Start MQTT loop in background thread
        self.client.will_set(
            BASE_TOPIC + "/availability",
            "offline",
            retain=True
        )

        self.client.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
        self.client.loop_start()

        # Mark the bridge online as soon as MQTT is connected so Home Assistant
        # can treat the media player as available. The LWT above will flip it
        # back to "offline" if the connection drops unexpectedly.
        self.client.publish(
            BASE_TOPIC + "/availability",
            "online",
            retain=True
        )

        # Blocking state loop
        self.publish_state_loop()


if __name__ == "__main__":
    bridge = WinampMqttBridge()
    bridge.run()
