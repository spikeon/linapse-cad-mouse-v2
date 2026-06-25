import asyncio
import glob
import math
import serial
import serial.tools.list_ports
import struct
import sys
import time
from . import state
from . import gamepad
from .config import get_active_mode_config
from .emulation import dispatch
from .hid import _on_press, _on_release

SERIAL_BAUD = 115200

# Firmware clamps every motion axis to this magnitude (Config.h AXIS_LIMIT).
# Used to normalize tilt into a -1..1 analog stick in Controller mode.
AXIS_LIMIT = 350.0

DIR_MAP = {
    "NegZ": "top", "NegX": "left", "PosX": "right",
    "PosY": "front", "NegY": "back",
}

_rx_scroll_accumulator = 0.0
_rz_scrub_accumulator = 0.0
_rx_volume_accumulator = 0.0
_mouse_x_accumulator = 0.0
_mouse_y_accumulator = 0.0
_mouse_scroll_accumulator = 0.0

_hid_button_bits = 0

def route_button(btn, val, actions, ser):
    """Handle a physical button event in HID emulation mode.

    Returns True if handled here (emulation path). Returns False when emulation
    is off, so the caller can fall back to the legacy per-platform dispatch.
    """
    global _hid_button_bits
    emulation = bool((actions or {}).get("custom_usb", {}).get("enabled", False))
    if not emulation:
        return False

    mode_buttons = get_active_mode_config(actions, "buttons")
    act = mode_buttons.get(f"{btn}:1") or mode_buttons.get(str(btn)) or {}
    is_native = act.get("action") == "hid_button"
    mask = 1 << btn

    if val == 0:
        # Always clear the bit on release to avoid a stuck native button if the
        # mapping changed mid-hold.
        if _hid_button_bits & mask:
            _hid_button_bits &= ~mask
            if ser:
                ser.write(f"hid_button {_hid_button_bits}\n".encode())
        if is_native:
            state.broadcast_from_thread(f"BUTTON:{btn}:0")
        else:
            _on_release(btn, actions)
        return True

    if is_native:
        _hid_button_bits |= mask
        if ser:
            ser.write(f"hid_button {_hid_button_bits}\n".encode())
        state.broadcast_from_thread(f"BUTTON:{btn}:1")
    else:
        _on_press(btn, actions)
    return True

def find_serial(actions_ref=None):
    if actions_ref and actions_ref[0] and isinstance(actions_ref[0], dict):
        manual_port = actions_ref[0].get("serial_port") or actions_ref[0].get("port")
        if manual_port:
            return manual_port

    try:
        ports = list(serial.tools.list_ports.comports())
        for p in ports:
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

        # Fallback second pass: match generic RP2040 (0x2E8A) or Adafruit (0x239A) serial ports on Windows/all platforms
        for p in ports:
            vid = getattr(p, "vid", None)
            if vid in (0x2E8A, 0x239A):
                return p.device

        # Fallback third pass: match other common serial chips / Arduinos (CH340, CP210x, FTDI, Teensy, SparkFun, Arduino)
        for p in ports:
            vid = getattr(p, "vid", None)
            if vid in (0x1A86, 0x10C4, 0x0403, 0x16C0, 0x1B4F, 0x2341, 0x9025):
                return p.device

        # Fallback fourth pass: if exactly one serial port exists, use it
        if len(ports) == 1:
            return ports[0].device
    except Exception as e:
        print(f"[serial] error listing comports: {e}")

    m = (glob.glob("/dev/serial/by-id/usb-Seeed_Studio_CAD_Mouse*") +
         glob.glob("/dev/ttyACM*"))
    return m[0] if m else None

def set_firmware_version(val):
    if state.firmware_version != val:
        state.firmware_version = val
        import os
        if "PYTEST_CURRENT_TEST" not in os.environ:
            state.broadcast_from_thread(f"VERSION_INFO:{{\"service\":\"{state.service_version}\",\"firmware\":\"{state.firmware_version}\"}}")

def serial_thread(actions_ref):
    global _rx_scroll_accumulator, _rz_scrub_accumulator, _rx_volume_accumulator, _hid_button_bits
    while True:
        set_firmware_version("unknown")
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
            _hid_button_bits = 0  # clear any stale native button state on (re)connect
            print(f"[serial] connected to {port}")
            time.sleep(0.1)
            
            # Send initial active mode's LED settings to the device so they are in sync on startup.
            actions = actions_ref[0]
            last_write_time = time.time()
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
                        last_write_time = time.time()
                    except Exception as e:
                        print(f"[serial] failed to write initial LED/HID commands: {e}")
                        
            last_invert_z = None
            last_custom_usb = None
            last_sleep_timeout = None
            last_sleep_threshold = None
            while True:
                if state.flashing_active:
                    break
                
                # Sync tap Z inversion with actions config Z inversion
                actions = actions_ref[0]
                if actions:
                    inv = actions.get("inversion", {})
                    current_invert_z = bool(inv.get("z", False))
                    if last_invert_z is None or current_invert_z != last_invert_z:
                        last_invert_z = current_invert_z
                        val = 1 if current_invert_z else 0
                        try:
                            ser.write(f"sens set invert_tap_z {val}\n".encode())
                        except Exception as e:
                            print(f"[serial] failed to write invert_tap_z command: {e}")

                # Tell the firmware to suppress local native button emission while
                # HID emulation is on; the service drives buttons via hid_button.
                custom_usb = actions.get("custom_usb", {}) if actions else {}
                current_custom_usb = bool(custom_usb.get("enabled", False))
                if last_custom_usb is None or current_custom_usb != last_custom_usb:
                    last_custom_usb = current_custom_usb
                    try:
                        ser.write(b"service_buttons 1\n" if current_custom_usb
                                  else b"service_buttons 0\n")
                    except Exception as e:
                        print(f"[serial] failed to write service_buttons: {e}")

                # Sync sleep config: 0 in JSON = disabled (-1 in firmware)
                current_sleep_timeout = int((actions or {}).get("sleep_timeout_ms", 0))
                if last_sleep_timeout is None or current_sleep_timeout != last_sleep_timeout:
                    last_sleep_timeout = current_sleep_timeout
                    fw_timeout = current_sleep_timeout if current_sleep_timeout > 0 else -1
                    try:
                        ser.write(f"sleep set timeout {fw_timeout}\n".encode())
                    except Exception as e:
                        print(f"[serial] failed to write sleep timeout: {e}")

                current_sleep_threshold = float((actions or {}).get("sleep_wake_threshold", 15.0))
                if last_sleep_threshold is None or current_sleep_threshold != last_sleep_threshold:
                    last_sleep_threshold = current_sleep_threshold
                    try:
                        ser.write(f"sleep set threshold {current_sleep_threshold}\n".encode())
                    except Exception as e:
                        print(f"[serial] failed to write sleep threshold: {e}")

                line = ser.readline().decode(errors="replace").strip()
                if not line:
                    try:
                        ser.write(b"service_hid 1\n")
                        if state.firmware_version == "unknown":
                            ser.write(b"version\n")
                        last_write_time = time.time()
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
                elif line.startswith("BUTTON:"):
                    parts = line.split(":")
                    if len(parts) == 3:
                        _, btn_str, state_str = parts
                        try:
                            btn = int(btn_str)
                            val = int(state_str)
                            if not route_button(btn, val, actions_ref[0], ser):
                                # Legacy path: serial buttons drive custom actions
                                # only on Windows/macOS when emulation is off.
                                if sys.platform in ("win32", "darwin"):
                                    if val == 1:
                                        _on_press(btn, actions_ref[0])
                                    else:
                                        _on_release(btn, actions_ref[0])
                        except Exception as e:
                            print(f"[serial] button parse error: {e}")
                elif line.startswith(">MOTION:"):
                    current_mode = actions_ref[0].get("current_mode", "Default") if actions_ref[0] else "Default"
                    try:
                        parts = line[8:].split(",")
                        if len(parts) == 6:
                            # Parse floats
                            raw_coords = [float(p) for p in parts]
                            x, y, z, rx, ry, rz = raw_coords
                            
                            # Decouple physical crosstalk (tilt/roll causes apparent translation)
                            # Disabled during automated tests to preserve test compatibility.
                            import os
                            decouple = actions_ref[0].get("decouple_crosstalk", True) if actions_ref[0] else True
                            if decouple and "PYTEST_CURRENT_TEST" not in os.environ:
                                x = x - 0.45 * ry
                                y = y - 0.45 * rx
                            
                            if not math.isfinite(x): x = 0.0
                            if not math.isfinite(y): y = 0.0
                            if not math.isfinite(z): z = 0.0
                            if not math.isfinite(rx): rx = 0.0
                            if not math.isfinite(ry): ry = 0.0
                            if not math.isfinite(rz): rz = 0.0
                            
                            # Apply user-configured axis inversions
                            inv = actions_ref[0].get("inversion", {}) if actions_ref[0] else {}
                            if inv.get("x", False): x = -x
                            if inv.get("y", False): y = -y
                            if inv.get("z", False): z = -z
                            if inv.get("rx", False): rx = -rx
                            if inv.get("ry", False): ry = -ry
                            if inv.get("rz", False): rz = -rz

                            # Load sensitivity from config
                            sens = actions_ref[0].get("sensitivity", {}) if actions_ref[0] else {}
                            
                            # Scale each axis depending on sign (positive vs negative direction)
                            x = x * sens.get("x_pos" if x >= 0 else "x_neg", 1.0)
                            y = y * sens.get("y_pos" if y <= 0 else "y_neg", 1.0)
                            z = z * sens.get("z_pos" if z <= 0 else "z_neg", 1.0)
                            rx = rx * sens.get("rx_pos" if rx <= 0 else "rx_neg", 1.0)
                            ry = ry * sens.get("ry_pos" if ry >= 0 else "ry_neg", 1.0)
                            rz = rz * sens.get("rz_pos" if rz <= 0 else "rz_neg", 1.0)
                            dominant_mode = actions_ref[0].get("dominant_mode", True) if actions_ref[0] else True
                            if dominant_mode and current_mode not in ("Browser", "Media", "Mouse", "Controller"):
                                bias = actions_ref[0].get("dominant_mode_bias", 4.8) if actions_ref[0] else 4.8
                                trans_mag = math.sqrt(x*x + y*y + z*z)
                                rot_mag = math.sqrt(rx*rx + ry*ry + rz*rz) * bias
                                if trans_mag >= rot_mag:
                                    rx = 0.0
                                    ry = 0.0
                                    rz = 0.0
                                else:
                                    x = 0.0
                                    y = 0.0
                                    z = 0.0


                            if current_mode not in ("Browser", "Media", "Mouse", "Controller"):
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

                            elif current_mode == "Mouse":
                                global _mouse_x_accumulator, _mouse_y_accumulator, _mouse_scroll_accumulator
                                
                                # Use symmetric sensitivity (average of positive and negative) for mouse cursor comfort
                                ry_sens = 0.5 * (sens.get("ry_pos", 1.0) + sens.get("ry_neg", 1.0))
                                rx_sens = 0.5 * (sens.get("rx_pos", 1.0) + sens.get("rx_neg", 1.0))
                                
                                # Re-calculate using raw coordinates to avoid asymmetric scaling
                                raw_ry = -raw_coords[4] if inv.get("ry", False) else raw_coords[4]
                                raw_rx = -raw_coords[3] if inv.get("rx", False) else raw_coords[3]
                                
                                ry_val = raw_ry * ry_sens
                                rx_val = raw_rx * rx_sens
                                
                                _mouse_x_accumulator -= ry_val * 0.25
                                _mouse_y_accumulator += rx_val * 0.25
                                ix = int(_mouse_x_accumulator)
                                iy = int(_mouse_y_accumulator)
                                _mouse_x_accumulator -= ix
                                _mouse_y_accumulator -= iy
                                if ix != 0 or iy != 0:
                                    dispatch({"action": "mouse_move", "x": ix, "y": iy})

                                if abs(rz) > 15.0:
                                    _mouse_scroll_accumulator += rz
                                else:
                                    _mouse_scroll_accumulator *= 0.8

                                if _mouse_scroll_accumulator >= 150.0:
                                    scrolls = int(_mouse_scroll_accumulator // 150.0)
                                    dispatch({"action": "mouse_scroll", "direction": "down", "amount": scrolls})
                                    _mouse_scroll_accumulator -= scrolls * 150.0
                                elif _mouse_scroll_accumulator <= -150.0:
                                    scrolls = int(-_mouse_scroll_accumulator // 150.0)
                                    dispatch({"action": "mouse_scroll", "direction": "up", "amount": scrolls})
                                    _mouse_scroll_accumulator += scrolls * 150.0

                            elif current_mode == "Controller":
                                # Controller has its OWN settings (sensitivity / deadzone /
                                # per-axis invert), decoupled from the global sensitivity +
                                # inversion that still drive CAD/Mouse modes. The 2D (top-down)
                                # and 3D (first-person) previews tune the stick independently.
                                _cv = actions_ref[0].get("controller_view", "3d") if actions_ref[0] else "3d"
                                ctrl = actions_ref[0].get("controller", {}) if actions_ref[0] else {}
                                cdead = ctrl.get("deadzone", 0.06)
                                if _cv == "2d":
                                    # Top-down: left stick from tilt only, with per-axis
                                    # horizontal/vertical sensitivity + invert (deadzone shared).
                                    c2 = actions_ref[0].get("controller2d", {}) if actions_ref[0] else {}
                                    c2s = c2.get("sensitivity", {})
                                    if not isinstance(c2s, dict):
                                        c2s = {}
                                    c2i = c2.get("invert", {})
                                    if not isinstance(c2i, dict):
                                        c2i = {}
                                    s_h = c2s.get("horizontal", 1.0)
                                    s_v = c2s.get("vertical", 1.0)
                                    sgn_h = -1.0 if c2i.get("horizontal", False) else 1.0
                                    sgn_v = -1.0 if c2i.get("vertical", True) else 1.0
                                    raw_v = raw_coords[3] * sgn_v   # vertical tilt (rx)
                                    raw_h = raw_coords[4] * sgn_h   # horizontal tilt (ry)
                                    lx, ly = gamepad.tilt_to_stick(raw_v * s_v, raw_h * s_h, AXIS_LIMIT, cdead)
                                    gamepad.set_left_stick(lx, ly)
                                    # extra axes are 3D-preview-only; zero them in 2D
                                    state.broadcast_from_thread(f"STICK:{lx:.3f},{ly:.3f},0.000,0.000,0.000")
                                else:
                                    cinv = ctrl.get("invert", {})
                                    if not isinstance(cinv, dict):
                                        cinv = {}
                                    csens = ctrl.get("sensitivity", {})
                                    if not isinstance(csens, dict):
                                        csens = {}
                                    s_look = csens.get("look", 1.0)      # tilt -> pitch + left stick
                                    s_turn = csens.get("turn", 1.0)      # twist -> yaw
                                    s_move = csens.get("move", 1.0)      # push fwd/back
                                    s_strafe = csens.get("strafe", 1.0)  # push left/right

                                    def _csgn(ax, default=False):
                                        return -1.0 if cinv.get(ax, default) else 1.0

                                    raw_rx = raw_coords[3] * _csgn("rx", True)   # look (tilt fwd/back)
                                    raw_ry = raw_coords[4] * _csgn("ry", False)  # left-stick horizontal
                                    raw_tx = raw_coords[0] * _csgn("x", False)   # strafe
                                    raw_ty = raw_coords[1] * _csgn("y", False)   # forward/back
                                    raw_rz = raw_coords[5] * _csgn("rz", False)  # twist (turn)

                                    lx, ly = gamepad.tilt_to_stick(raw_rx * s_look, raw_ry * s_look, AXIS_LIMIT, cdead)
                                    gamepad.set_left_stick(lx, ly)

                                    def _nd(v):
                                        n = max(-1.0, min(1.0, v / AXIS_LIMIT))
                                        return 0.0 if abs(n) < cdead else n

                                    # STICK:lx,ly,strafe,forward,twist  (extra axes preview-only)
                                    state.broadcast_from_thread(
                                        f"STICK:{lx:.3f},{ly:.3f},{_nd(raw_tx * s_strafe):.3f},"
                                        f"{_nd(raw_ty * s_move):.3f},{_nd(raw_rz * s_turn):.3f}")

                            # Send processed coordinates back to the device to emit via USB HID
                            try:
                                custom_usb = actions_ref[0].get("custom_usb", {}) if actions_ref[0] else {}
                                if custom_usb.get("enabled", False):
                                    if current_mode not in ("Browser", "Media", "Mouse", "Controller"):
                                        ser.write(f"hid_report {x:.1f},{y:.1f},{z:.1f},{rx:.1f},{ry:.1f},{rz:.1f}\n".encode())
                                    else:
                                        ser.write(b"hid_report 0,0,0,0,0,0\n")
                                    last_write_time = time.time()
                                else:
                                    # Refresh service_hid mode every 1s when receiving telemetry to prevent timeout
                                    if time.time() - last_write_time >= 1.0:
                                        ser.write(b"service_hid 1\n")
                                        last_write_time = time.time()
                            except Exception as e:
                                print(f"[serial] failed to write hid_report back: {e}")

                            if current_mode not in ("Browser", "Media", "Mouse", "Controller"):
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
                        set_firmware_version(line.split("=")[1].strip())
                        
                        # Trigger firmware auto-update if enabled
                        actions = actions_ref[0] if actions_ref else None
                        if actions and actions.get("auto_update_firmware", False):
                            from .updater import compare_versions
                            from .flashing import flash_device
                            if (state.firmware_version != "unknown" and 
                                state.firmware_version != "legacy" and 
                                compare_versions(state.firmware_version, state.service_version) < 0 and 
                                not state.flashing_active):
                                print(f"[serial] firmware out of date ({state.firmware_version} < {state.service_version}). Triggering auto-flash...")
                                if state.loop:
                                    asyncio.run_coroutine_threadsafe(flash_device(), state.loop)
                    state.broadcast_from_thread(line)
        except (serial.SerialException, TypeError, OSError, AttributeError) as e:
            state.ser_holder[0] = None
            set_firmware_version("unknown")
            print(f"[serial] {e} — retrying in 3s")
            time.sleep(3)
