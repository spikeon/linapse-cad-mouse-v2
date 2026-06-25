import json
import os
import time
import asyncio
from pathlib import Path
from . import state

ACTIONS_PATH = Path.home() / ".config" / "cad-mouse" / "actions.json"

def get_active_mode_config(actions, category):
    if not isinstance(actions, dict):
        actions = {"button_override": False, "buttons": {}, "taps": {}}
    if "modes" in actions:
        current_mode = actions.get("current_mode")
        if current_mode and current_mode in actions["modes"]:
            mode_config = actions["modes"][current_mode]
            return mode_config.get(category, {})
        return {}
    else:
        return actions.get(category, {})

def switch_mode(target_mode):
    with state.config_lock:
        actions = state.actions_ref[0]
        if not actions or not isinstance(actions, dict) or "modes" not in actions:
            return
        if target_mode not in actions["modes"]:
            print(f"[mode] target mode '{target_mode}' does not exist")
            return

        actions["current_mode"] = target_mode

        try:
            ACTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = ACTIONS_PATH.with_suffix(".tmp")
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    with open(tmp_path, "w") as f:
                        json.dump(actions, f, indent=2)
                    os.replace(tmp_path, ACTIONS_PATH)
                    break
                except PermissionError as pe:
                    if attempt == max_retries - 1:
                        raise pe
                    time.sleep(0.05)
            print(f"[mode] switched to '{target_mode}' and saved configuration")
        except Exception as e:
            print(f"[mode] error saving configuration: {e}")

    led_config = actions["modes"][target_mode].get("led", {})
    effect = led_config.get("effect", "solid")
    color = led_config.get("color", "FFFFFF")
    brightness = led_config.get("brightness", 128)

    if state.loop and state.serial_queue:
        async def queue_cmds():
            await state.serial_queue.put(f"led effect {effect}")
            await state.serial_queue.put(f"led color {color}")
            await state.serial_queue.put(f"led brightness {brightness}")
        asyncio.run_coroutine_threadsafe(queue_cmds(), state.loop)

    state.broadcast_from_thread(f"MODE:{target_mode}")

def load_actions():
    with state.config_lock:
        actions = None
        file_existed = False
        parsing_error = False
        migrated = False
        try:
            if ACTIONS_PATH.exists():
                file_existed = True
                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        with open(ACTIONS_PATH) as f:
                            actions = json.load(f)
                        break
                    except PermissionError as pe:
                        if attempt == max_retries - 1:
                            raise pe
                        time.sleep(0.05)
        except Exception as e:
            print(f"[actions] {e}")
            parsing_error = True
            if file_existed and state.actions_ref[0] is not None:
                return state.actions_ref[0]

        if actions is None or not isinstance(actions, dict):
            actions = {
                "button_override": False,
                "auto_update_firmware": False,
                "dominant_mode": True,
                "dominant_mode_bias": 4.8,
                "sleep_timeout_ms": 0,
                "sleep_wake_threshold": 15.0,
                "sensitivity": {
                    "x_pos": 1.0, "x_neg": 1.0, "y_pos": 1.0, "y_neg": 1.0, "z_pos": 1.0, "z_neg": 1.0,
                    "rx_pos": 1.0, "rx_neg": 1.0, "ry_pos": 1.0, "ry_neg": 1.0, "rz_pos": 1.0, "rz_neg": 1.0
                },
                "inversion": {
                    "x": False, "y": False, "z": False, "rx": True, "ry": True, "rz": True
                },
                "controller": {
                    "sensitivity": {"look": 1.0, "turn": 1.0, "move": 1.0, "strafe": 1.0},
                    "deadzone": 0.06,
                    "invert": {"rx": True, "ry": False, "rz": False, "x": False, "y": False}
                },
                "modes": {
                    "Default": {
                        "buttons": {
                            "0": {"action": "mouse_scroll", "direction": "down", "amount": 1},
                            "1": {"action": "mouse_scroll", "direction": "up", "amount": 1},
                            "chord": {"action": "key", "value": "shift+7"},
                            "chord:2": {"action": "mode", "value": "Mouse"},
                            "chord:3": {"action": "mode", "value": "Browser"}
                        },
                        "taps": {
                            "top:1": {"action": "mouse_click", "button": "left"},
                            "top:2": {"action": "none"},
                            "top:3": {"action": "none"},
                            "left:1": {"action": "none"}, "left:2": {"action": "none"},
                            "right:1": {"action": "none"}, "right:2": {"action": "none"},
                            "front:1": {"action": "none"}, "front:2": {"action": "none"},
                            "back:1": {"action": "none"}, "back:2": {"action": "none"}
                        },
                        "led": {
                            "effect": "reactive",
                            "color": "FF0000",
                            "brightness": 128
                        }
                    },
                    "TargetMode": {
                        "buttons": {
                            "0": {"action": "mouse_scroll", "direction": "down", "amount": 1},
                            "1": {"action": "mouse_scroll", "direction": "up", "amount": 1},
                            "chord": {"action": "key", "value": "shift+7"},
                            "chord:2": {"action": "mode", "value": "Mouse"},
                            "chord:3": {"action": "mode", "value": "Browser"}
                        },
                        "taps": {
                            "top:1": {"action": "mouse_click", "button": "left"},
                            "top:2": {"action": "none"},
                            "top:3": {"action": "none"},
                            "left:1": {"action": "none"}, "left:2": {"action": "none"},
                            "right:1": {"action": "none"}, "right:2": {"action": "none"},
                            "front:1": {"action": "none"}, "front:2": {"action": "none"},
                            "back:1": {"action": "none"}, "back:2": {"action": "none"}
                        },
                        "led": {
                            "effect": "solid",
                            "color": "FFFFFF",
                            "brightness": 128
                        }
                    },
                    "Browser": {
                        "buttons": {
                            "0": {"action": "key", "value": "ctrl+pageup"},
                            "1": {"action": "key", "value": "ctrl+pagedown"},
                            "chord:2": {"action": "mode", "value": "Default"},
                            "chord:3": {"action": "mode", "value": "Media"}
                        },
                        "taps": {
                            "top:2": {"action": "none"}
                        },
                        "led": {
                            "effect": "solid",
                            "color": "0000FF",
                            "brightness": 128
                        }
                    },
                    "Media": {
                        "buttons": {
                            "0": {"action": "key", "value": "prev"},
                            "1": {"action": "key", "value": "next"},
                            "chord:2": {"action": "mode", "value": "Browser"},
                            "chord:3": {"action": "mode", "value": "Controller"}
                        },
                        "taps": {
                            "top:2": {"action": "none"}
                        },
                        "led": {
                            "effect": "volume",
                            "color": "00FF00",
                            "brightness": 128
                        }
                    },
                    "Mouse": {
                        "buttons": {
                            "0": {"action": "mouse_click", "button": "left"},
                            "1": {"action": "mouse_click", "button": "right"},
                            "chord:2": {"action": "mode", "value": "Controller"},
                            "chord:3": {"action": "mode", "value": "Default"}
                        },
                        "taps": {
                            "top:1": {"action": "mouse_click", "button": "left"},
                            "top:2": {"action": "mouse_click", "button": "right"},
                            "top:3": {"action": "none"},
                            "left:1": {"action": "none"}, "left:2": {"action": "none"},
                            "right:1": {"action": "none"}, "right:2": {"action": "none"},
                            "front:1": {"action": "none"}, "front:2": {"action": "none"},
                            "back:1": {"action": "none"}, "back:2": {"action": "none"}
                        },
                        "led": {
                            "effect": "solid",
                            "color": "00FFFF",
                            "brightness": 128
                        }
                    },
                    "Controller": {
                        "buttons": {
                            "0": {"action": "gamepad_button", "button": 0},
                            "1": {"action": "gamepad_button", "button": 1},
                            "chord:2": {"action": "mode", "value": "Media"},
                            "chord:3": {"action": "mode", "value": "Mouse"}
                        },
                        "taps": {
                            "top:1": {"action": "gamepad_button", "button": 0},
                            "top:2": {"action": "gamepad_button", "button": 1}
                        },
                        "led": {
                            "effect": "rainbow_swirl",
                            "color": "FFFFFF",
                            "brightness": 128
                        }
                    }
                },
                "current_mode": "Browser"
            }
            migrated = True

        migrated_legacy = False
        if "buttons" in actions or "taps" in actions:
            legacy_buttons = actions.pop("buttons", {})
            legacy_taps = actions.pop("taps", {})
            actions["modes"] = {
                "Default": {
                    "buttons": legacy_buttons,
                    "taps": legacy_taps,
                    "led": {"effect": "solid", "color": "FFFFFF", "brightness": 128}
                }
            }
            actions["current_mode"] = "Default"
            migrated_legacy = True
            migrated = True

        if "modes" not in actions:
            actions["modes"] = {}

        if "Browser" not in actions["modes"]:
            actions["modes"]["Browser"] = {
                "buttons": {
                    "0": {"action": "key", "value": "ctrl+pageup"},
                    "1": {"action": "key", "value": "ctrl+pagedown"},
                    "chord:2": {"action": "mode", "value": "Default"},
                    "chord:3": {"action": "mode", "value": "Media"}
                },
                "taps": {
                    "top:2": {"action": "none"}
                },
                "led": {"effect": "solid", "color": "0000FF", "brightness": 128}
            }
            migrated = True

        if "Media" not in actions["modes"]:
            actions["modes"]["Media"] = {
                "buttons": {
                    "0": {"action": "key", "value": "prev"},
                    "1": {"action": "key", "value": "next"},
                    "chord:2": {"action": "mode", "value": "Browser"},
                    "chord:3": {"action": "mode", "value": "Controller"}
                },
                "taps": {
                    "top:2": {"action": "none"}
                },
                "led": {"effect": "volume", "color": "00FF00", "brightness": 128}
            }
            migrated = True
        elif "Media" in actions["modes"]:
            media_mode = actions["modes"]["Media"]
            if media_mode.get("led", {}).get("effect") == "dot_swirl":
                if "led" not in media_mode:
                    media_mode["led"] = {}
                media_mode["led"]["effect"] = "volume"
                migrated = True

        if "Mouse" not in actions["modes"]:
            actions["modes"]["Mouse"] = {
                "buttons": {
                    "0": {"action": "mouse_click", "button": "left"},
                    "1": {"action": "mouse_click", "button": "right"},
                    "chord:2": {"action": "mode", "value": "Controller"},
                    "chord:3": {"action": "mode", "value": "Default"}
                },
                "taps": {
                    "top:1": {"action": "mouse_click", "button": "left"},
                    "top:2": {"action": "mouse_click", "button": "right"}
                },
                "led": {"effect": "solid", "color": "00FFFF", "brightness": 128}
            }
            migrated = True

        if "Controller" not in actions["modes"]:
            actions["modes"]["Controller"] = {
                "buttons": {
                    "0": {"action": "gamepad_button", "button": 0},
                    "1": {"action": "gamepad_button", "button": 1},
                    "chord:2": {"action": "mode", "value": "Media"},
                    "chord:3": {"action": "mode", "value": "Mouse"}
                },
                "taps": {
                    "top:1": {"action": "gamepad_button", "button": 0},
                    "top:2": {"action": "gamepad_button", "button": 1}
                },
                "led": {"effect": "rainbow_swirl", "color": "FFFFFF", "brightness": 128}
            }
            migrated = True

        if "auto_update_firmware" not in actions:
            actions["auto_update_firmware"] = False
            migrated = True

        if "sleep_timeout_ms" not in actions:
            actions["sleep_timeout_ms"] = 0
            migrated = True

        if "sleep_wake_threshold" not in actions:
            actions["sleep_wake_threshold"] = 15.0
            migrated = True

        if "controller" not in actions:
            actions["controller"] = {
                "sensitivity": {"look": 1.0, "turn": 1.0, "move": 1.0, "strafe": 1.0},
                "deadzone": 0.06,
                "invert": {"rx": True, "ry": False, "rz": False, "x": False, "y": False}
            }
            migrated = True
        elif not isinstance(actions["controller"].get("sensitivity"), dict):
            # Upgrade the old single sensitivity scalar to per-axis controls.
            s = actions["controller"].get("sensitivity", 1.0)
            try:
                s = float(s)
            except (TypeError, ValueError):
                s = 1.0
            actions["controller"]["sensitivity"] = {"look": s, "turn": s, "move": s, "strafe": s}
            migrated = True

        # Default mode LED: ship red reactive. Only migrate the old stock rainbow
        # (rainbow_swirl + FFFFFF); never clobber a user-customized LED.
        if "Default" in actions["modes"]:
            default_led = actions["modes"]["Default"].get("led", {})
            if default_led.get("effect") == "rainbow_swirl" and default_led.get("color") == "FFFFFF":
                actions["modes"]["Default"]["led"] = {
                    "effect": "reactive", "color": "FF0000",
                    "brightness": default_led.get("brightness", 128)
                }
                migrated = True

        # Ensure all modes carry the current chord cycle:
        # double: Default -> Mouse -> Controller -> Media -> Browser -> (Default)
        # triple: the reverse
        mode_cycle_mapping_double = {
            "Default": "Mouse",
            "Mouse": "Controller",
            "Controller": "Media",
            "Media": "Browser",
            "Browser": "Default",
        }
        mode_cycle_mapping_triple = {
            "Default": "Browser",
            "Browser": "Media",
            "Media": "Controller",
            "Controller": "Mouse",
            "Mouse": "Default",
        }
        # chord values treated as "still a default" (legacy + pre-Controller), safe
        # to re-point. The != target guard below keeps re-runs idempotent.
        old_double_defaults = {
            "Default": {"Browser", "Mouse"},
            "Browser": {"Media", "Default"},
            "Media": {"Mouse", "Browser"},
            "Mouse": {"Default", "Media"},
            "Controller": {"Default", "Media"},
        }
        old_triple_defaults = {
            "Default": {"Browser"},
            "Browser": {"Media"},
            "Media": {"Mouse", "Controller"},
            "Mouse": {"Default"},
            "Controller": {"Mouse"},
        }
        for mname in ["Default", "Browser", "Media", "Mouse", "Controller"]:
            if mname in actions["modes"]:
                mode_cfg = actions["modes"][mname]
                if "buttons" not in mode_cfg:
                    mode_cfg["buttons"] = {}

                # 1. Migrate the legacy taps top:2 mode switch
                has_old_switch = False
                if "taps" in mode_cfg and "top:2" in mode_cfg["taps"]:
                    tap_act = mode_cfg["taps"]["top:2"]
                    if tap_act.get("action") == "mode":
                        has_old_switch = True
                if has_old_switch:
                    if mname == "Mouse":
                        mode_cfg["taps"]["top:2"] = {"action": "mouse_click", "button": "right"}
                    else:
                        mode_cfg["taps"]["top:2"] = {"action": "none"}
                    migrated = True

                # 2. Re-point chord:2 (double) if missing or still on a default
                target_double = mode_cycle_mapping_double[mname]
                current_c2 = mode_cfg["buttons"].get("chord:2", {}).get("value")
                if current_c2 != target_double and (current_c2 is None or current_c2 in old_double_defaults[mname]):
                    mode_cfg["buttons"]["chord:2"] = {"action": "mode", "value": target_double}
                    migrated = True

                # 3. Re-point chord:3 (triple) if missing or still on a default
                target_triple = mode_cycle_mapping_triple[mname]
                current_c3 = mode_cfg["buttons"].get("chord:3", {}).get("value")
                if current_c3 != target_triple and (current_c3 is None or current_c3 in old_triple_defaults[mname]):
                    mode_cfg["buttons"]["chord:3"] = {"action": "mode", "value": target_triple}
                    migrated = True

        if migrated and not parsing_error:
            try:
                ACTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
                tmp_path = ACTIONS_PATH.with_suffix(".tmp")
                max_retries = 5
                for attempt in range(max_retries):
                    try:
                        with open(tmp_path, "w") as f:
                            json.dump(actions, f, indent=2)
                        os.replace(tmp_path, ACTIONS_PATH)
                        break
                    except PermissionError as pe:
                        if attempt == max_retries - 1:
                            raise pe
                        time.sleep(0.05)
                print(f"[actions] migrated and saved to {ACTIONS_PATH}")
            except Exception as e:
                print(f"[actions] failed to save migrated actions: {e}")
        return actions

def save_actions(json_str):
    try:
        data = json.loads(json_str)
        if not isinstance(data, dict):
            data = {"button_override": False, "buttons": {}, "taps": {}}
        if "buttons" in data or "taps" in data:
            legacy_buttons = data.pop("buttons", {})
            legacy_taps = data.pop("taps", {})
            data["modes"] = {
                "Default": {
                    "buttons": legacy_buttons,
                    "taps": legacy_taps,
                    "led": {"effect": "solid", "color": "FFFFFF", "brightness": 128}
                }
            }
            data["current_mode"] = "Default"
            
        with state.config_lock:
            ACTIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = ACTIONS_PATH.with_suffix(".tmp")
            max_retries = 5
            for attempt in range(max_retries):
                try:
                    with open(tmp_path, "w") as f:
                        json.dump(data, f, indent=2)
                    os.replace(tmp_path, ACTIONS_PATH)
                    break
                except PermissionError as pe:
                    if attempt == max_retries - 1:
                        raise pe
                    time.sleep(0.05)
            state.actions_ref[0] = data
        print(f"[config] saved {ACTIONS_PATH}")
        return True
    except Exception as e:
        print(f"[config] save error: {e}")
        return False

def config_watcher(actions_ref):
    last_mtime = 0
    while True:
        try:
            mtime = ACTIONS_PATH.stat().st_mtime
            if mtime != last_mtime:
                last_mtime = mtime
                state.actions_ref[0] = load_actions()
                print(f"[config] reloaded {ACTIONS_PATH}")
        except FileNotFoundError:
            pass
        time.sleep(2)
