import sys
import time
import glob
import os
import select
import threading
from . import state
from .config import get_active_mode_config
from .emulation import dispatch

BUTTON_REPORT_ID = 3
CHORD_WINDOW = 0.05
SCROLL_INTERVAL = 0.05

class ButtonClickState:
    def __init__(self, btn):
        self.btn = btn
        self.click_count = 0
        self.timer = None
        self.released = False

_click_states = {0: ButtonClickState(0), 1: ButtonClickState(1)}
_held = set()
_chord_fired = False
_timers = {}
_scroll_threads = {}

class ChordClickState:
    def __init__(self):
        self.click_count = 0
        self.timer = None
        self.released = False

_chord_state = ChordClickState()
_chord_held = False

def reset_click_states():
    global _chord_held
    for state_obj in _click_states.values():
        if state_obj.timer:
            state_obj.timer.cancel()
            state_obj.timer = None
        state_obj.click_count = 0
        state_obj.released = False
    if _chord_state.timer:
        _chord_state.timer.cancel()
        _chord_state.timer = None
    _chord_state.click_count = 0
    _chord_state.released = False
    _chord_held = False

def _scroll_loop(btn, stop_event, actions):
    while not stop_event.is_set():
        mode_buttons = get_active_mode_config(actions, "buttons")
        act = mode_buttons.get(f"{btn}:1")
        if not act:
            act = mode_buttons.get(str(btn), {"action": "scroll_down" if btn == 0 else "scroll_up"})
        dispatch(act)
        time.sleep(SCROLL_INTERVAL)

def _on_single(btn, actions):
    global _chord_fired
    if _chord_fired:
        return
    state.broadcast_from_thread(f"BUTTON:{btn}:1")
    if actions.get("button_override", False):
        return
    mode_buttons = get_active_mode_config(actions, "buttons")
    act = mode_buttons.get(f"{btn}:1")
    if not act:
        act = mode_buttons.get(str(btn), {"action": "scroll_down" if btn == 0 else "scroll_up"})
    if act.get("action") in ("scroll_up", "scroll_down"):
        stop_event = threading.Event()
        t = threading.Thread(target=_scroll_loop, args=(btn, stop_event, actions), daemon=True)
        _scroll_threads[btn] = (t, stop_event)
        t.start()
    else:
        dispatch(act)

def _fire_multi_chord(count, actions):
    state.broadcast_from_thread(f"BUTTON:chord:{count}")
    if actions.get("button_override", False):
        return
    mode_buttons = get_active_mode_config(actions, "buttons")
    act = None
    if count == 2:
        act = mode_buttons.get("chord:2")
        if not act:
            # Fallback mode cycle: Default -> Browser -> Media -> Mouse -> Default
            current_mode = actions.get("current_mode", "Default")
            mode_cycle = ["Default", "Browser", "Media", "Mouse"]
            if current_mode in mode_cycle:
                idx = mode_cycle.index(current_mode)
                next_mode = mode_cycle[(idx + 1) % len(mode_cycle)]
                act = {"action": "mode", "value": next_mode}
    else:
        act = mode_buttons.get("chord:1") or mode_buttons.get("chord")
    if act:
        dispatch(act)

def _fire_multi_click(btn, count, actions):
    global _chord_fired
    if _chord_fired:
        return
    state.broadcast_from_thread(f"BUTTON:{btn}:{count}")
    if actions.get("button_override", False):
        return
    mode_buttons = get_active_mode_config(actions, "buttons")
    act = mode_buttons.get(f"{btn}:{count}")
    if not act and count == 1:
        act = mode_buttons.get(str(btn), {"action": "scroll_down" if btn == 0 else "scroll_up"})
    if act:
        dispatch(act)

def _on_press(btn, actions):
    global _chord_fired, _chord_held
    _held.add(btn)
    if len(_held) == 2:
        _chord_fired = True
        _chord_held = True
        for t in _timers.values():
            t.cancel()
        _timers.clear()
        for state_obj in _click_states.values():
            if state_obj.timer:
                state_obj.timer.cancel()
                state_obj.timer = None
            state_obj.click_count = 0
        
        # Chord pressed: manage chord multi-click detection if double chord is configured
        mode_buttons = get_active_mode_config(actions, "buttons")
        has_double_chord = "chord:2" in mode_buttons
        
        if has_double_chord:
            if _chord_state.timer:
                _chord_state.timer.cancel()
                _chord_state.timer = None
                _chord_state.click_count += 1
            else:
                _chord_state.click_count = 1
            _chord_state.released = False
        else:
            # No double chord, fire single chord immediately
            _fire_multi_chord(1, actions)
        return

    if _chord_held:
        return

    mode_buttons = get_active_mode_config(actions, "buttons")
    has_double = f"{btn}:2" in mode_buttons

    if has_double:
        state_obj = _click_states[btn]
        if state_obj.timer:
            state_obj.timer.cancel()
            state_obj.timer = None
            state_obj.click_count += 1
        else:
            state_obj.click_count = 1
        state_obj.released = False
    else:
        t = threading.Timer(CHORD_WINDOW, _on_single, args=[btn, actions])
        _timers[btn] = t
        t.start()

def _on_release(btn, actions=None):
    global _chord_fired, _chord_held
    _held.discard(btn)
    if btn in _timers:
        _timers.pop(btn).cancel()
    if btn in _scroll_threads:
        _, stop_event = _scroll_threads.pop(btn)
        stop_event.set()

    if actions is None:
        actions = state.actions_ref[0] or {}

    # If chord was active and now released (len(_held) < 2)
    if _chord_held and len(_held) < 2:
        _chord_held = False
        if _chord_state.click_count > 0:
            if not _chord_state.released:
                _chord_state.released = True
                def fire_chord():
                    _fire_multi_chord(_chord_state.click_count, actions)
                    _chord_state.click_count = 0
                    _chord_state.timer = None
                _chord_state.timer = threading.Timer(0.25, fire_chord)
                _chord_state.timer.start()

    if not _held:
        _chord_fired = False

    # Handle single button click count release only if chord is not active
    if not _chord_fired:
        state_obj = _click_states.get(btn)
        if state_obj and state_obj.click_count > 0 and not state_obj.released:
            state_obj.released = True
            def fire():
                _fire_multi_click(btn, state_obj.click_count, actions)
                state_obj.click_count = 0
                state_obj.timer = None
            state_obj.timer = threading.Timer(0.25, fire)
            state_obj.timer.start()

    state.broadcast_from_thread(f"BUTTON:{btn}:0")

def hid_thread(actions_ref):
    if sys.platform in ("win32", "darwin"):
        print("[hid] disabled on Windows/macOS")
        return
    while True:
        candidates = (
            glob.glob("/dev/input/by-id/usb-*CAD_Mouse*-if02-hidraw") +
            glob.glob("/dev/input/by-id/usb-Seeed_Studio*-if02-hidraw")
        )
        if not candidates:
            time.sleep(3)
            continue
        try:
            with open(candidates[0], "rb") as fd:
                os.set_blocking(fd.fileno(), False)
                prev_bits = 0
                print(f"[hid] watching {fd.name}")
                while True:
                    r, _, _ = select.select([fd], [], [], 1)
                    if not r:
                        continue
                    data = fd.read(64)
                    if not data:
                        raise OSError("no data (disconnected)")
                    if data[0] != BUTTON_REPORT_ID:
                        continue
                    bits = data[1] & 0x03
                    if bits == prev_bits:
                        continue
                    # In HID emulation mode the serial BUTTON path is the sole
                    # button source; ignore reports here (they are service-driven
                    # native echoes and would double-dispatch).
                    if bool((actions_ref[0] or {}).get("custom_usb", {}).get("enabled", False)):
                        prev_bits = bits
                        continue
                    for btn in range(2):
                        mask = 1 << btn
                        was = bool(prev_bits & mask)
                        now = bool(bits & mask)
                        if now and not was:
                            _on_press(btn, actions_ref[0])
                        elif was and not now:
                            _on_release(btn)
                    prev_bits = bits
        except (OSError, IOError) as e:
            print(f"[hid] error/disconnect: {e} — retrying in 3s")
            for btn in list(_held):
                _on_release(btn)
            time.sleep(3)
