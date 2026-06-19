import glob
import math
import serial
import serial.tools.list_ports
import struct
import time
from . import state
from .config import get_active_mode_config
from .emulation import dispatch

SERIAL_BAUD = 115200

DIR_MAP = {
    "NegZ": "top", "NegX": "left", "PosX": "right",
    "PosY": "front", "NegY": "back",
}

_rx_scroll_accumulator = 0.0
_rz_scrub_accumulator = 0.0
_rx_volume_accumulator = 0.0

def find_serial(actions_ref=None):
    if actions_ref and actions_ref[0] and isinstance(actions_ref[0], dict):
        manual_port = actions_ref[0].get("serial_port") or actions_ref[0].get("port")
        if manual_port:
            return manual_port

    try:
        for p in serial.tools.list_ports.comports():
            vid = getattr(p, "vid", None)
            desc = getattr(p, "description", "") or ""
            prod = getattr(p, "product", "") or ""
            if vid == 0x2886:
                return p.device
            if actions_ref and actions_ref[0] and isinstance(actions_ref[0], dict):
                custom_usb = actions_ref[0].get("custom_usb", {})
                if custom_usb.get("enabled", False) and custom_usb.get("vid"):
                    try:
                        custom_vid = int(custom_usb.get("vid"), 16)
                        if vid == custom_vid:
                            return p.device
                    except Exception:
                        pass
            for term in ("Seeed", "CAD Mouse", "CAD_Mouse"):
                if term in desc or term in prod:
                    return p.device
    except Exception as e:
        print(f"[serial] error listing comports: {e}")

    m = (glob.glob("/dev/serial/by-id/usb-Seeed_Studio_CAD_Mouse*") +
         glob.glob("/dev/ttyACM*"))
    return m[0] if m else None

def serial_thread(actions_ref):
    global _rx_scroll_accumulator, _rz_scrub_accumulator, _rx_volume_accumulator
    while True:
        if state.flashing_active:
            time.sleep(1)
            continue
        port = find_serial(actions_ref)
        if not port:
            print("[serial] no serial port found — retrying in 5s")
            for _ in range(5):
                if state.flashing_active:
                    break
                time.sleep(1)
            continue
        try:
            ser = serial.Serial(port, SERIAL_BAUD, timeout=1.0)
            state.ser_holder[0] = ser
            print(f"[serial] connected to {port}")
            
            # Send initial active mode's LED settings to the device so they are in sync on startup.
            actions = actions_ref[0]
            if actions and "modes" in actions:
                current_mode = actions.get("current_mode", "Default")
                if current_mode in actions["modes"]:
                    led_config = actions["modes"][current_mode].get("led", {})
                    effect = led_config.get("effect", "solid")
                    color = led_config.get("color", "FFFFFF")
                    brightness = led_config.get("brightness", 128)
                    try:
                        ser.write(f"led effect {effect}\n".encode())
                        ser.write(f"led color {color}\n".encode())
                        ser.write(f"led brightness {brightness}\n".encode())
                        ser.write(b"service_hid 1\n")
                        ser.write(b"version\n")
                    except Exception as e:
                        print(f"[serial] failed to write initial LED/HID commands: {e}")
                        
            while True:
                if state.flashing_active:
                    break
                line = ser.readline().decode(errors="replace").strip()
                if not line:
                    try:
                        ser.write(b"service_hid 1\n")
                    except Exception as e:
                        print(f"[serial] failed to write heartbeat: {e}")
                    continue
                if line.startswith("TAP:"):
                    parts = line.split(":")
                    if len(parts) == 3:
                        _, fw_dir, count_str = parts
                        human = DIR_MAP.get(fw_dir)
                        if human:
                            key = f"{human}:{count_str}"
                            mode_taps = get_active_mode_config(actions_ref[0], "taps")
                            act = mode_taps.get(key)
                            if act:
                                print(f"[tap] {key} → {act}")
                                dispatch(act)
                            state.broadcast_from_thread(f"TAP:{human}:{count_str}")
                elif line.startswith(">MOTION:"):
                    current_mode = actions_ref[0].get("current_mode", "Default") if actions_ref[0] else "Default"
                    try:
                        parts = line[8:].split(",")
                        if len(parts) == 6:
                            # Parse floats
                            raw_coords = [float(p) for p in parts]
                            x, y, z, rx, ry, rz = raw_coords
                            
                            if not math.isfinite(x): x = 0.0
                            if not math.isfinite(y): y = 0.0
                            if not math.isfinite(z): z = 0.0
                            if not math.isfinite(rx): rx = 0.0
                            if not math.isfinite(ry): ry = 0.0
                            if not math.isfinite(rz): rz = 0.0
                            
                            # Load sensitivity from config
                            sens = actions_ref[0].get("sensitivity", {}) if actions_ref[0] else {}
                            
                            # Scale each axis depending on sign (positive vs negative direction)
                            # Note: X and Z axes have negative SIGN_AXIS in firmware (-1), so their raw telemetry signs are inverted
                            # relative to physical movement directions. We correct for this to match UI labels.
                            x = x * sens.get("x_pos" if x <= 0 else "x_neg", 1.0)
                            y = y * sens.get("y_pos" if y >= 0 else "y_neg", 1.0)
                            z = z * sens.get("z_pos" if z <= 0 else "z_neg", 1.0)
                            rx = rx * sens.get("rx_pos" if rx >= 0 else "rx_neg", 1.0)
                            ry = ry * sens.get("ry_pos" if ry >= 0 else "ry_neg", 1.0)
                            rz = rz * sens.get("rz_pos" if rz >= 0 else "rz_neg", 1.0)
                            
                            # Apply user-configured axis inversions
                            inv = actions_ref[0].get("inversion", {}) if actions_ref[0] else {}
                            if inv.get("x", False): x = -x
                            if inv.get("y", False): y = -y
                            if inv.get("z", False): z = -z
                            if inv.get("rx", False): rx = -rx
                            if inv.get("ry", False): ry = -ry
                            if inv.get("rz", False): rz = -rz

                            if current_mode not in ("Browser", "Media"):
                                state.broadcast_from_thread(f"MOTION:{x:.1f},{y:.1f},{z:.1f},{rx:.1f},{ry:.1f},{rz:.1f}")

                            if current_mode == "Browser":
                                if abs(rx) > 15.0:
                                    _rx_scroll_accumulator += rx
                                else:
                                    _rx_scroll_accumulator *= 0.8

                                if _rx_scroll_accumulator >= 150.0:
                                    scrolls = int(_rx_scroll_accumulator // 150.0)
                                    dispatch({"action": "mouse_scroll", "direction": "down", "amount": scrolls})
                                    _rx_scroll_accumulator -= scrolls * 150.0
                                elif _rx_scroll_accumulator <= -150.0:
                                    scrolls = int(-_rx_scroll_accumulator // 150.0)
                                    dispatch({"action": "mouse_scroll", "direction": "up", "amount": scrolls})
                                    _rx_scroll_accumulator += scrolls * 150.0

                            elif current_mode == "Media":
                                if abs(ry) > 15.0:
                                    _rz_scrub_accumulator += ry
                                else:
                                    _rz_scrub_accumulator *= 0.8

                                if _rz_scrub_accumulator >= 200.0:
                                    presses = int(_rz_scrub_accumulator // 200.0)
                                    for _ in range(presses):
                                        dispatch({"action": "key", "value": "right"})
                                    _rz_scrub_accumulator -= presses * 200.0
                                elif _rz_scrub_accumulator <= -200.0:
                                    presses = int(-_rz_scrub_accumulator // 200.0)
                                    for _ in range(presses):
                                        dispatch({"action": "key", "value": "left"})
                                    _rz_scrub_accumulator += presses * 200.0

                                if abs(rz) > 15.0:
                                    _rx_volume_accumulator += rz
                                    state.last_volume_change_time = time.time()
                                else:
                                    _rx_volume_accumulator *= 0.8

                                if _rx_volume_accumulator >= 250.0:
                                    presses = int(_rx_volume_accumulator // 250.0)
                                    state.last_volume_change_time = time.time()
                                    for _ in range(presses):
                                        dispatch({"action": "key", "value": "volup"})
                                    _rx_volume_accumulator -= presses * 250.0
                                elif _rx_volume_accumulator <= -250.0:
                                    presses = int(-_rx_volume_accumulator // 250.0)
                                    state.last_volume_change_time = time.time()
                                    for _ in range(presses):
                                        dispatch({"action": "key", "value": "voldown"})
                                    _rx_volume_accumulator += presses * 250.0

                            # Send processed coordinates back to the device to emit via USB HID
                            try:
                                if current_mode not in ("Browser", "Media"):
                                    ser.write(f"hid_report {x:.1f},{y:.1f},{z:.1f},{rx:.1f},{ry:.1f},{rz:.1f}\n".encode())
                                else:
                                    ser.write(b"hid_report 0,0,0,0,0,0\n")
                            except Exception as e:
                                print(f"[serial] failed to write hid_report back: {e}")

                            if current_mode not in ("Browser", "Media"):
                                # Apply direction inversions for spacenav mapping
                                z = -z
                                y = -y
                                
                                # Round to integers
                                ix = int(round(x))
                                iy = int(round(y))
                                iz = int(round(z))
                                irx = int(round(rx))
                                iry = int(round(ry))
                                irz = int(round(rz))
                                
                                period = 10
                                # Swap Y and Z for both translation and rotation: [0, x, z, y, rx, rz, ry, period]
                                packet = struct.pack("iiiiiiii", 0, ix, iz, iy, irx, irz, iry, period)
                                state.broadcast_socket_from_thread(packet)
                    except Exception as e:
                        print(f"[serial] motion parse/pack error: {e}")
                elif not line.startswith(">"):
                    # Command response (OK, ERR ..., JSON from config get, etc.)
                    if line.startswith("version="):
                        state.firmware_version = line.split("=")[1].strip()
                        state.broadcast_from_thread(f"VERSION_INFO:{{\"service\":\"{state.service_version}\",\"firmware\":\"{state.firmware_version}\"}}")
                    state.broadcast_from_thread(line)
        except (serial.SerialException, TypeError, OSError, AttributeError) as e:
            state.ser_holder[0] = None
            print(f"[serial] {e} — retrying in 3s")
            time.sleep(3)
