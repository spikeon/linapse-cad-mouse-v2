import sys
import os
import subprocess
import time
from . import state
from .config import switch_mode

# Try loading pynput conditionally
pynput_keyboard = None
pynput_mouse = None
Button = None
Key = None
KeyCode = None
if sys.platform in ("win32", "darwin"):
    try:
        import pynput
        from pynput.keyboard import Controller as KeyboardController, Key, KeyCode
        from pynput.mouse import Controller as MouseController, Button
        pynput_keyboard = KeyboardController()
        pynput_mouse = MouseController()
    except Exception as e:
        print(f"[pynput] warning: failed to initialize pynput: {e}. Emulation will fail on Windows/macOS.")

YDOTOOL_SOCKET = f"/run/user/{os.getuid()}/.ydotool_socket" if hasattr(os, "getuid") else ""

_MOUSE_BTN = {"left": 0xC0, "right": 0xC1, "middle": 0xC2}

_KEY_CODES = {
    # Modifiers
    "shift": 42, "lshift": 42, "rshift": 54,
    "ctrl": 29, "control": 29, "lctrl": 29, "rctrl": 97,
    "alt": 56, "lalt": 56, "ralt": 100,
    "meta": 125, "super": 125, "win": 125, "cmd": 125,
    # Numbers
    "1": 2, "2": 3, "3": 4, "4": 5, "5": 6, "6": 7, "7": 8, "8": 9, "9": 10, "0": 11,
    # Letters
    "a": 30, "b": 48, "c": 46, "d": 32, "e": 18, "f": 33, "g": 34, "h": 35, "i": 23,
    "j": 36, "k": 37, "l": 38, "m": 50, "n": 49, "o": 24, "p": 25, "q": 16, "r": 19,
    "s": 31, "t": 20, "u": 22, "v": 47, "w": 17, "x": 45, "y": 21, "z": 44,
    # Function keys
    "f1": 59, "f2": 60, "f3": 61, "f4": 62, "f5": 63, "f6": 64,
    "f7": 65, "f8": 66, "f9": 67, "f10": 68, "f11": 87, "f12": 88,
    # Others
    "enter": 28, "return": 28, "space": 57, "spacebar": 57, "backspace": 14, "tab": 15,
    "escape": 1, "esc": 1,
    "up": 103, "down": 108, "left": 105, "right": 106,
    "pageup": 104, "pgup": 104, "pagedown": 109, "pgdn": 109,
    "home": 102, "end": 107, "insert": 110, "ins": 110, "delete": 111, "del": 111,
    # Symbols
    "-": 12, "minus": 12,
    "=": 13, "equal": 13,
    "[": 26, "]": 27,
    ";": 39, "semicolon": 39,
    "'": 40,
    "`": 41, "grave": 41,
    "\\": 43, "backslash": 43,
    ",": 51, "comma": 51,
    ".": 52, "period": 52,
    "/": 53, "slash": 53,
    # Media keys
    "volup": 115,
    "voldown": 114,
    "next": 163,
    "prev": 165,
    "playpause": 164,
    "play": 207,
    "pause": 201,
    "mute": 113
}

_REVERSE_KEY_CODES = {v: k for k, v in _KEY_CODES.items()}

def get_pynput_key(name: str):
    name = name.lower().strip()
    mapping = {
        "ctrl": Key.ctrl if Key else None,
        "control": Key.ctrl if Key else None,
        "lctrl": Key.ctrl_l if Key else None,
        "rctrl": Key.ctrl_r if Key else None,
        "shift": Key.shift if Key else None,
        "lshift": Key.shift_l if Key else None,
        "rshift": Key.shift_r if Key else None,
        "alt": Key.alt if Key else None,
        "lalt": Key.alt_l if Key else None,
        "ralt": Key.alt_gr if Key else None,
        "meta": Key.cmd if Key else None,
        "super": Key.cmd if Key else None,
        "win": Key.cmd if Key else None,
        "cmd": Key.cmd if Key else None,
        "enter": Key.enter if Key else None,
        "return": Key.enter if Key else None,
        "space": Key.space if Key else None,
        "spacebar": Key.space if Key else None,
        "backspace": Key.backspace if Key else None,
        "tab": Key.tab if Key else None,
        "escape": Key.esc if Key else None,
        "esc": Key.esc if Key else None,
        "up": Key.up if Key else None,
        "down": Key.down if Key else None,
        "left": Key.left if Key else None,
        "right": Key.right if Key else None,
        "pageup": Key.page_up if Key else None,
        "pgup": Key.page_up if Key else None,
        "pagedown": Key.page_down if Key else None,
        "pgdn": Key.page_down if Key else None,
        "home": Key.home if Key else None,
        "end": Key.end if Key else None,
        "insert": Key.insert if Key else None,
        "ins": Key.insert if Key else None,
        "delete": Key.delete if Key else None,
        "del": Key.delete if Key else None,
        "volup": getattr(Key, "media_volume_up", None) if Key else None,
        "voldown": getattr(Key, "media_volume_down", None) if Key else None,
        "next": getattr(Key, "media_next", None) if Key else None,
        "prev": getattr(Key, "media_previous", None) if Key else None,
        "playpause": getattr(Key, "media_play_pause", None) if Key else None,
        "mute": getattr(Key, "media_volume_mute", None) if Key else None,
    }
    # Add F1-F12
    for i in range(1, 13):
        mapping[f"f{i}"] = getattr(Key, f"f{i}", None) if Key else None
        
    if name in mapping:
        return mapping[name]
    if len(name) == 1:
        try:
            return KeyCode.from_char(name) if KeyCode else name
        except Exception:
            return name
    return None

def translate_friendly_combo(combo_str: str) -> str:
    combo_str = combo_str.lower().strip()
    if not combo_str:
        return ""
    if ":" in combo_str:
        return combo_str
    parts = [p.strip() for p in combo_str.split("+") if p.strip()]
    keycodes = []
    for p in parts:
        code = _KEY_CODES.get(p)
        if code is not None:
            keycodes.append(code)
        else:
            print(f"[dispatch] warning: unknown key name '{p}' in combo '{combo_str}'")
    if not keycodes:
        return ""
    presses = " ".join(f"{code}:1" for code in keycodes)
    releases = " ".join(f"{code}:0" for code in reversed(keycodes))
    return f"{presses} {releases}"

def ydotool(*args):
    env = os.environ.copy()
    env["YDOTOOL_SOCKET"] = YDOTOOL_SOCKET
    flat_args = []
    for arg in args:
        if isinstance(arg, str):
            flat_args.extend(arg.split())
        else:
            flat_args.append(arg)
    try:
        subprocess.Popen(["ydotool"] + flat_args, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[ydotool] spawn error: {e}")

def dispatch(action_obj):
    if not action_obj:
        return
    act = action_obj.get("action", "none")
    print(f"[dispatch] action: {act} obj: {action_obj}")
    if act == "none":
        pass
    elif act == "hid_button":
        # Native HID passthrough is handled in serial_port.route_button; it must
        # never reach OS-level dispatch.
        pass
    elif act == "mode":
        val = action_obj.get("value", "")
        if val:
            switch_mode(val)
    elif act == "media":
        cmd = action_obj.get("command", "")
        media_map = {
            "play": "play",
            "pause": "pause",
            "forward": "next",
            "back": "prev",
            "fast_forward": "right",
            "rewind": "left",
            "mute": "mute",
            "volume_up": "volup",
            "volume_down": "voldown"
        }
        key = media_map.get(cmd)
        if key:
            dispatch({"action": "key", "value": key})
    elif act == "key":
        val = action_obj.get("value", "")
        if val:
            if sys.platform in ("win32", "darwin"):
                if pynput_keyboard:
                    try:
                        if ":" in val:
                            for token in val.split():
                                if ":" in token:
                                    code_str, state_str = token.split(":", 1)
                                    code = int(code_str)
                                    state = int(state_str)
                                    friendly = _REVERSE_KEY_CODES.get(code)
                                    if friendly:
                                        key = get_pynput_key(friendly)
                                        if key:
                                            if state == 1:
                                                pynput_keyboard.press(key)
                                            else:
                                                pynput_keyboard.release(key)
                        else:
                            parts = [p.strip() for p in val.split("+") if p.strip()]
                            keys = []
                            for p in parts:
                                key = get_pynput_key(p)
                                if key:
                                    keys.append(key)
                                else:
                                    print(f"[pynput] warning: unknown key name '{p}' in combo '{val}'")
                            for k in keys:
                                pynput_keyboard.press(k)
                            for k in reversed(keys):
                                pynput_keyboard.release(k)
                    except Exception as e:
                        print(f"[pynput] error emulating key combo '{val}': {e}")
                else:
                    print(f"[pynput] cannot emulate key '{val}', keyboard not initialized")
            else:
                if ":" not in val:
                    translated = translate_friendly_combo(val)
                    print(f"[dispatch] key '{val}' translated to raw codes '{translated}'")
                    val = translated
                if val:
                    ydotool("key", val)
    elif act == "mouse_click":
        if sys.platform in ("win32", "darwin"):
            if pynput_mouse:
                btn_name = action_obj.get("button", "left")
                btn = Button.left if btn_name == "left" else (Button.right if btn_name == "right" else Button.middle)
                pynput_mouse.click(btn)
        else:
            code = _MOUSE_BTN.get(action_obj.get("button", "left"), 0xC0)
            ydotool("click", hex(code))
    elif act == "mouse_scroll":
        if sys.platform in ("win32", "darwin"):
            if pynput_mouse:
                d = action_obj.get("direction", "down")
                a = int(action_obj.get("amount", 3))
                dx, dy = 0, 0
                if d == "up":
                    dy = a
                elif d == "down":
                    dy = -a
                elif d == "left":
                    dx = -a
                elif d == "right":
                    dx = a
                pynput_mouse.scroll(dx, dy)
        else:
            d = action_obj.get("direction", "down")
            a = int(action_obj.get("amount", 3))
            delta = (-a if d == "up" else a) if d in ("up", "down") else (-a if d == "left" else a)
            if d in ("up", "down"):
                ydotool("mousemove", "-w", "--", "0", str(delta))
            else:
                ydotool("mousemove", "-w", "--", str(delta), "0")
    elif act == "mouse_move":
        if sys.platform in ("win32", "darwin"):
            if pynput_mouse:
                pynput_mouse.move(action_obj.get("x", 0), action_obj.get("y", 0))
        else:
            ydotool("mousemove", "--", str(action_obj.get("x", 0)), str(action_obj.get("y", 0)))
    elif act in ("scroll_up", "scroll_down"):
        if sys.platform in ("win32", "darwin"):
            if pynput_mouse:
                dy = 3 if act == "scroll_up" else -3
                pynput_mouse.scroll(0, dy)
        else:
            ydotool("mousemove", "-w", "--", "0", str(-3 if act == "scroll_up" else 3))
    elif act == "exec":
        val = action_obj.get("value", "")
        if val:
            subprocess.Popen(val, shell=True)
    elif act == "macro":
        for step in action_obj.get("steps", []):
            step_action = step.get("action", "none")
            if step_action != "none":
                dispatch(step)
            if "delay" in step:
                time.sleep(step["delay"] / 1000.0)
