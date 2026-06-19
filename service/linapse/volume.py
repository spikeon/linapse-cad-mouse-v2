import sys
import time
import re
import subprocess
from . import state

def volume_watcher():
    last_val = -1
    state.last_volume_change_time = 0.0
    while True:
        try:
            vol = -1
            if sys.platform == "win32":
                try:
                    from pycaw.pycaw import AudioUtilities
                    from ctypes import cast, POINTER
                    from comtypes import CLSCTX_ALL
                    from pycaw.pycaw import IAudioEndpointVolume
                    devices = AudioUtilities.GetSpeakers()
                    if devices:
                        interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
                        volume = cast(interface, POINTER(IAudioEndpointVolume))
                        vol = int(round(volume.GetMasterVolumeLevelScalar() * 100))
                except Exception:
                    pass
            elif sys.platform == "darwin":
                try:
                    out = subprocess.check_output(["osascript", "-e", "output volume of (get volume settings)"], stderr=subprocess.DEVNULL).decode().strip()
                    vol = int(out)
                except Exception:
                    pass
            else: # Linux/other
                try:
                    out = subprocess.check_output(["amixer", "sget", "Master"], stderr=subprocess.DEVNULL).decode()
                    m = re.search(r"\[(\d+)%\]", out)
                    if m:
                        vol = int(m.group(1))
                except Exception:
                    pass
                if vol == -1:
                    try:
                        out = subprocess.check_output(["pactl", "get-sink-volume", "@DEFAULT_SINK@"], stderr=subprocess.DEVNULL).decode()
                        m = re.search(r"(\d+)%", out)
                        if m:
                            vol = int(m.group(1))
                    except Exception:
                        pass

            if vol != -1 and vol != last_val:
                if last_val != -1:
                    state.last_volume_change_time = time.time()
                last_val = vol
                state.last_system_volume = vol
                state.broadcast_from_thread(f"VOLUME:{vol}")
                if state.loop and state.serial_queue:
                    state.loop.call_soon_threadsafe(state.serial_queue.put_nowait, f"volume {vol}")
        except Exception:
            pass
        sleep_time = 0.25 if (time.time() - state.last_volume_change_time < 10.0) else 1.0
        time.sleep(sleep_time)
