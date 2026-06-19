import os
import sys
import time
import socket
import queue
import json
import asyncio
import threading
import http.server
import socketserver
import importlib.util
import glob
import subprocess
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

try:
    from playwright.sync_api import sync_playwright
    HAS_PLAYWRIGHT = True
except ImportError:
    HAS_PLAYWRIGHT = False

# Skip if playwright is not installed
pytestmark = pytest.mark.skipif(not HAS_PLAYWRIGHT, reason="Playwright not installed")

# Global variables for tracking and controlling background threads
started_threads = []
original_init = threading.Thread.__init__
original_sleep = time.sleep
original_glob = glob.glob
original_popen = subprocess.Popen
original_excepthook = threading.excepthook

teardown_initiated = False
ydotool_calls = []

class KillThreadException(BaseException):
    """Custom exception to cleanly terminate background daemon threads."""
    pass

def custom_init(self, *args, **kwargs):
    is_ours = False
    target = kwargs.get("target")
    if target:
        name = getattr(target, "__name__", "")
        if name in ("serial_thread", "hid_thread", "config_watcher", "_scroll_loop", "_on_single"):
            is_ours = True
    elif isinstance(self, threading.Timer) or self.__class__.__name__ == "Timer":
        is_ours = True
    if is_ours:
        started_threads.append(self)
    original_init(self, *args, **kwargs)

def custom_sleep(seconds):
    if teardown_initiated and threading.current_thread() != threading.main_thread():
        raise KillThreadException("teardown active")
    # Speed up service loops by mapping long sleeps to a minimal duration
    if seconds in (2, 3, 5):
        original_sleep(0.01)
    else:
        original_sleep(seconds)

def custom_glob(pattern, *args, **kwargs):
    if teardown_initiated and threading.current_thread() != threading.main_thread():
        raise KillThreadException("teardown active")
    return []

def mock_popen(args, *args_etc, **kwargs):
    if teardown_initiated and threading.current_thread() != threading.main_thread():
        raise KillThreadException("teardown active")
    if isinstance(args, list) and args[0] == "ydotool":
        ydotool_calls.append(args)
        proc = MagicMock()
        proc.poll.return_value = 0
        proc.wait.return_value = 0
        return proc
    if kwargs.get("shell") and isinstance(args, str):
        ydotool_calls.append(["shell_exec", args])
        proc = MagicMock()
        proc.poll.return_value = 0
        proc.wait.return_value = 0
        return proc
    return original_popen(args, *args_etc, **kwargs)

def custom_excepthook(args):
    if args.exc_type == KillThreadException:
        # Suppress traceback output for clean daemon shutdowns
        return
    original_excepthook(args)

# Helper to find free ports
def get_free_port():
    s = socket.socket()
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port

# Threaded HTTP Server to serve configurator/
class ThreadedHTTPServer:
    def __init__(self, port, directory):
        class Handler(http.server.SimpleHTTPRequestHandler):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, directory=directory, **kwargs)
            def log_message(self, format, *args):
                pass
        socketserver.TCPServer.allow_reuse_address = True
        self.server = socketserver.TCPServer(("localhost", port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()

# Mock serial class
class MockSerialPort:
    def __init__(self, *args, **kwargs):
        self.input_queue = queue.Queue()
        self.is_open = True
        self.writes = []
    def readline(self):
        while not teardown_initiated and self.is_open:
            try:
                return self.input_queue.get(timeout=0.05)
            except queue.Empty:
                continue
        raise KillThreadException("teardown active")
    def write(self, data):
        self.writes.append(data)
    def close(self):
        self.is_open = False

# Load linapse-service
if "linapse_service" in sys.modules:
    linapse_service = sys.modules["linapse_service"]
else:
    service_path = Path(__file__).parent / "linapse-service"
    loader = importlib.machinery.SourceFileLoader("linapse_service", str(service_path))
    spec = importlib.util.spec_from_loader("linapse_service", loader)
    linapse_service = importlib.util.module_from_spec(spec)
    loader.exec_module(linapse_service)
    sys.modules["linapse_service"] = linapse_service

def test_benchy_viewport_motion_and_toasts(tmp_path):
    global teardown_initiated, started_threads, ydotool_calls
    teardown_initiated = False
    started_threads.clear()
    ydotool_calls.clear()

    # Setup temporary configuration path
    temp_actions_path = tmp_path / "actions.json"
    initial_actions = {
        "current_mode": "Default",
        "modes": {
            "Default": {
                "buttons": {
                    "0": {"action": "mouse_click", "button": "left"}
                },
                "taps": {
                    "top:1": {"action": "key", "value": "ctrl+alt+t"}
                },
                "led": {
                    "effect": "solid",
                    "color": "FFFFFF",
                    "brightness": 128
                }
            }
        },
        "sensitivity": {},
        "inversion": {}
    }
    with open(temp_actions_path, "w") as f:
        json.dump(initial_actions, f)

    # Setup directories
    service_dir = Path(__file__).parent
    configurator_dir = service_dir.parent / "configurator"
    assert configurator_dir.exists(), f"Configurator directory not found at {configurator_dir}"

    # Allocate ports
    http_port = get_free_port()
    ws_port = get_free_port()

    # Configure linapse_service port & actions path
    linapse_service.ACTIONS_PATH = temp_actions_path
    linapse_service.WS_PORT = ws_port
    linapse_service.WS_HOST = "localhost"

    # Reset internal service lists
    linapse_service._socket_clients.clear()
    linapse_service._ws_clients.clear()
    linapse_service._loop = None
    linapse_service._held.clear()
    linapse_service._chord_fired = False
    linapse_service._timers.clear()
    linapse_service._scroll_threads.clear()
    linapse_service.reset_click_states()

    # Instantiate mock serial
    mock_serial = MockSerialPort()

    # Setup patchers
    patchers = [
        patch("linapse_service.serial.Serial", return_value=mock_serial),
        patch("linapse_service.find_serial", return_value="MOCK_COM"),
        patch("linapse_service.glob.glob", custom_glob),
        patch("linapse_service.subprocess.Popen", mock_popen),
        patch("time.sleep", custom_sleep),
    ]

    for p in patchers:
        p.start()

    threading.Thread.__init__ = custom_init
    threading.excepthook = custom_excepthook

    # Start HTTP server
    http_server = ThreadedHTTPServer(http_port, str(configurator_dir))
    http_server.start()

    # Run linapse-service inside a background thread
    loop = asyncio.new_event_loop()
    loop.add_signal_handler = lambda *args, **kwargs: None
    main_task = None
    def run_service():
        nonlocal main_task
        asyncio.set_event_loop(loop)
        try:
            main_task = loop.create_task(linapse_service.main())
            loop.run_until_complete(main_task)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Service main failed: {e}")
        finally:
            pending = asyncio.all_tasks(loop)
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    service_thread = threading.Thread(target=run_service, daemon=True)
    service_thread.start()

    # Wait for service loop to start
    start_time = time.time()
    while linapse_service._loop is None and time.time() - start_time < 3.0:
        time.sleep(0.1)
    
    assert linapse_service._loop is not None, "linapse-service failed to start"

    time.sleep(0.5)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Redirect WebSocket connection to our custom port
            redirect_js = f"""
            const OriginalWebSocket = window.WebSocket;
            window.WebSocket = class extends OriginalWebSocket {{
                constructor(url, protocols) {{
                    const newUrl = url.replace(':13000', ':{ws_port}');
                    super(newUrl, protocols);
                }}
            }};
            """
            page.add_init_script(redirect_js)

            # Load configurator index
            page.goto(f"http://localhost:{http_port}/index.html")

            # Click the "Sensitivity" tab to load the Benchy viewport
            page.click("text=Sensitivity")

            # Poll until benchyScene is initialized
            start_time = time.time()
            initialized = False
            while time.time() - start_time < 5.0:
                is_ready = page.evaluate("() => typeof benchyScene !== 'undefined' && benchyScene !== null && benchyScene.benchy !== undefined")
                if is_ready:
                    initialized = True
                    break
                time.sleep(0.1)

            assert initialized, "benchyScene failed to initialize within 5 seconds"

            # Get initial position and rotation
            initial = page.evaluate("() => { const b = benchyScene.benchy; return { x: b.position.x, y: b.position.y, rx: b.rotation.x, ry: b.rotation.y, rz: b.rotation.z }; }")
            # Helper to get current coordinates
            def get_current():
                return page.evaluate("() => { const b = benchyScene.benchy; return { x: b.position.x, y: b.position.y, rx: b.rotation.x, ry: b.rotation.y, rz: b.rotation.z }; }")

            # Helper to reset benchy position and rotation
            def reset_benchy():
                page.evaluate("() => { const b = benchyScene.benchy; b.position.set(0, 0, 0); b.rotation.set(0, 0, 0); }")
                time.sleep(0.05)

            # Helper to read actions config safely with retries
            def read_saved_actions():
                for attempt in range(10):
                    try:
                        with open(temp_actions_path, "r") as f:
                            return json.load(f)
                    except (PermissionError, json.JSONDecodeError):
                        time.sleep(0.05)
                with open(temp_actions_path, "r") as f:
                    return json.load(f)

            # We test all 5 visible axes: X, Z (which maps to Y on screen), RX, RY, RZ
            # For each axis, we verify movement direction under normal configuration,
            # then verify that enabling inversion results in movement in the opposite direction.
            # We also ensure the absolute movement magnitude is significant (> 0.01) to verify
            # it is actually moving and not just showing noise/float drift.
            axes_to_test = [
                # (axis_name, pos_input, neg_input, coord_getter, normal_pos_increases, selector)
                ("X", "100.0,0,0,0,0,0", "-100.0,0,0,0,0,0", lambda c: c['x'], True, "#invX"),
                ("Z", "0,0,100.0,0,0,0", "0,0,-100.0,0,0,0", lambda c: c['y'], False, "#invZ"),
                ("RX", "0,0,0,100.0,0,0", "0,0,0,-100.0,0,0", lambda c: c['rx'], True, "#invRx"),
                ("RY", "0,0,0,0,100.0,0", "0,0,0,0,-100.0,0", lambda c: c['ry'], True, "#invRy"),
                ("RZ", "0,0,0,0,0,100.0", "0,0,0,0,0,-100.0", lambda c: c['rz'], False, "#invRz"),
            ]

            for name, pos_input, neg_input, get_val, normal_pos_increases, selector in axes_to_test:
                # --- 1. Test normal (uninverted) movement ---
                # Positive Input
                reset_benchy()
                initial = get_current()
                mock_serial.input_queue.put(f">MOTION:{pos_input}\n".encode())
                time.sleep(0.3)
                curr = get_current()
                delta_pos_normal = get_val(curr) - get_val(initial)
                if normal_pos_increases:
                    assert delta_pos_normal > 0.01, f"{name} normal positive movement failed: expected positive delta, got {delta_pos_normal}"
                else:
                    assert delta_pos_normal < -0.01, f"{name} normal positive movement failed: expected negative delta, got {delta_pos_normal}"

                # Negative Input
                reset_benchy()
                initial = get_current()
                mock_serial.input_queue.put(f">MOTION:{neg_input}\n".encode())
                time.sleep(0.3)
                curr = get_current()
                delta_neg_normal = get_val(curr) - get_val(initial)
                if normal_pos_increases:
                    assert delta_neg_normal < -0.01, f"{name} normal negative movement failed: expected negative delta, got {delta_neg_normal}"
                else:
                    assert delta_neg_normal > 0.01, f"{name} normal negative movement failed: expected positive delta, got {delta_neg_normal}"

                # --- 2. Enable inversion and verify configuration saves to disk ---
                page.click(selector)
                time.sleep(0.3)
                saved_actions = read_saved_actions()
                assert saved_actions.get("inversion", {}).get(name.lower()) is True, f"{name} inversion failed to save on disk"

                # --- 3. Test inverted movement ---
                # Positive Input (should move opposite of normal positive)
                reset_benchy()
                initial = get_current()
                mock_serial.input_queue.put(f">MOTION:{pos_input}\n".encode())
                time.sleep(0.3)
                curr = get_current()
                delta_pos_inv = get_val(curr) - get_val(initial)
                # Confirm sign of movement is opposite
                assert delta_pos_inv * delta_pos_normal < 0, f"{name} inverted positive movement failed: expected opposite direction, normal={delta_pos_normal}, inverted={delta_pos_inv}"
                if normal_pos_increases:
                    assert delta_pos_inv < -0.01, f"{name} inverted positive movement failed: expected negative delta, got {delta_pos_inv}"
                else:
                    assert delta_pos_inv > 0.01, f"{name} inverted positive movement failed: expected positive delta, got {delta_pos_inv}"

                # Negative Input (should move opposite of normal negative)
                reset_benchy()
                initial = get_current()
                mock_serial.input_queue.put(f">MOTION:{neg_input}\n".encode())
                time.sleep(0.3)
                curr = get_current()
                delta_neg_inv = get_val(curr) - get_val(initial)
                # Confirm sign of movement is opposite
                assert delta_neg_inv * delta_neg_normal < 0, f"{name} inverted negative movement failed: expected opposite direction, normal={delta_neg_normal}, inverted={delta_neg_inv}"
                if normal_pos_increases:
                    assert delta_neg_inv > 0.01, f"{name} inverted negative movement failed: expected positive delta, got {delta_neg_inv}"
                else:
                    assert delta_neg_inv < -0.01, f"{name} inverted negative movement failed: expected negative delta, got {delta_neg_inv}"

                # --- 4. Turn inversion back off ---
                page.click(selector)
                time.sleep(0.3)
                saved_actions = read_saved_actions()
                assert not saved_actions.get("inversion", {}).get(name.lower()), f"{name} inversion failed to untoggle on disk"

            # --- 5. Test Y Axis inversion updates actions on disk ---
            page.click("#invY")
            time.sleep(0.3)
            saved_actions = read_saved_actions()
            assert saved_actions.get("inversion", {}).get("y") is True, f"Y inversion failed to save on disk: {saved_actions}"

            # Untoggle Y Inversion
            page.click("#invY")
            time.sleep(0.3)
            saved_actions = read_saved_actions()
            assert not saved_actions.get("inversion", {}).get("y"), f"Y inversion failed to untoggle on disk: {saved_actions}"
            

            # Test Tap Gesture Toast via mock serial
            # TAP:NegZ:1 maps to top tap, which is configured to key shortcut in initial_actions
            mock_serial.input_queue.put(b"TAP:NegZ:1\n")
            time.sleep(0.3)
            tap_toast_header = page.locator(".toast-header").last.text_content()
            tap_toast_body = page.locator(".toast-body").last.text_content()
            assert "Tap Registered" in tap_toast_header, f"Expected 'Tap Registered' in toast header, got '{tap_toast_header}'"
            assert "TOP TAP (1X)" in tap_toast_body.upper(), f"Expected 'TOP TAP (1X)' in toast body, got '{tap_toast_body}'"

            # Test Button Press Toast via daemon thread-safe broadcast
            linapse_service._broadcast_from_thread("BUTTON:0:1")
            time.sleep(0.3)
            toast_header = page.locator(".toast-header").last.text_content()
            toast_body = page.locator(".toast-body").last.text_content()
            assert "Button Pressed" in toast_header, f"Expected 'Button Pressed' in toast header, got '{toast_header}'"
            assert "LEFT BUTTON" in toast_body, f"Expected 'LEFT BUTTON' in toast body, got '{toast_body}'"

            browser.close()
    finally:
        # Teardown sequence
        teardown_initiated = True

        # Stop service
        mock_serial.close()
        if main_task:
            loop.call_soon_threadsafe(main_task.cancel)
        service_thread.join(timeout=3.0)
        http_server.stop()

        # Join started daemon threads to ensure clean exit
        for t in started_threads:
            t.join(timeout=1.0)
            assert not t.is_alive(), f"Thread {t} (name={t.name}) failed to exit during teardown!"

        # Stop all patchers
        for p in reversed(patchers):
            p.stop()

        # Restore excepthook
        threading.Thread.__init__ = original_init
        threading.excepthook = original_excepthook


def test_benchy_sensitivity_and_dead_zones(tmp_path):
    global teardown_initiated, started_threads, ydotool_calls
    teardown_initiated = False
    started_threads.clear()
    ydotool_calls.clear()

    # Setup temporary configuration path
    temp_actions_path = tmp_path / "actions.json"
    initial_actions = {
        "current_mode": "Default",
        "modes": {
            "Default": {
                "buttons": {
                    "0": {"action": "mouse_click", "button": "left"}
                },
                "taps": {
                    "top:1": {"action": "key", "value": "ctrl+alt+t"}
                },
                "led": {
                    "effect": "solid",
                    "color": "FFFFFF",
                    "brightness": 128
                }
            }
        },
        "sensitivity": {},
        "inversion": {}
    }
    with open(temp_actions_path, "w") as f:
        json.dump(initial_actions, f)

    # Setup directories
    service_dir = Path(__file__).parent
    configurator_dir = service_dir.parent / "configurator"
    assert configurator_dir.exists(), f"Configurator directory not found at {configurator_dir}"

    # Allocate ports
    http_port = get_free_port()
    ws_port = get_free_port()

    # Configure linapse_service port & actions path
    linapse_service.ACTIONS_PATH = temp_actions_path
    linapse_service.WS_PORT = ws_port
    linapse_service.WS_HOST = "localhost"

    # Reset internal service lists
    linapse_service._socket_clients.clear()
    linapse_service._ws_clients.clear()
    linapse_service._loop = None
    linapse_service._held.clear()
    linapse_service._chord_fired = False
    linapse_service._timers.clear()
    linapse_service._scroll_threads.clear()
    linapse_service.reset_click_states()

    # Instantiate mock serial
    mock_serial = MockSerialPort()

    # Setup patchers
    patchers = [
        patch("linapse_service.serial.Serial", return_value=mock_serial),
        patch("linapse_service.find_serial", return_value="MOCK_COM"),
        patch("linapse_service.glob.glob", custom_glob),
        patch("linapse_service.subprocess.Popen", mock_popen),
        patch("time.sleep", custom_sleep),
    ]

    for p in patchers:
        p.start()

    threading.Thread.__init__ = custom_init
    threading.excepthook = custom_excepthook

    # Start HTTP server
    http_server = ThreadedHTTPServer(http_port, str(configurator_dir))
    http_server.start()

    # Run linapse-service inside a background thread
    loop = asyncio.new_event_loop()
    loop.add_signal_handler = lambda *args, **kwargs: None
    main_task = None
    def run_service():
        nonlocal main_task
        asyncio.set_event_loop(loop)
        try:
            main_task = loop.create_task(linapse_service.main())
            loop.run_until_complete(main_task)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Service main failed: {e}")
        finally:
            pending = asyncio.all_tasks(loop)
            if pending:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            loop.close()

    service_thread = threading.Thread(target=run_service, daemon=True)
    service_thread.start()

    # Wait for service loop to start
    start_time = time.time()
    while linapse_service._loop is None and time.time() - start_time < 3.0:
        time.sleep(0.1)
    
    assert linapse_service._loop is not None, "linapse-service failed to start"
    time.sleep(0.5)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # Redirect WebSocket connection to our custom port
            redirect_js = f"""
            const OriginalWebSocket = window.WebSocket;
            window.WebSocket = class extends OriginalWebSocket {{
                constructor(url, protocols) {{
                    const newUrl = url.replace(':13000', ':{ws_port}');
                    super(newUrl, protocols);
                }}
            }};
            """
            page.add_init_script(redirect_js)

            # Load configurator index
            page.goto(f"http://localhost:{http_port}/index.html")

            # Click the "Sensitivity" tab to load the Benchy viewport
            page.click("text=Sensitivity")

            # Poll until benchyScene is initialized
            start_time = time.time()
            initialized = False
            while time.time() - start_time < 5.0:
                is_ready = page.evaluate("() => typeof benchyScene !== 'undefined' && benchyScene !== null && benchyScene.benchy !== undefined")
                if is_ready:
                    initialized = True
                    break
                time.sleep(0.1)

            assert initialized, "benchyScene failed to initialize within 5 seconds"

            # Helper to get current coordinates
            def get_current():
                return page.evaluate("() => { const b = benchyScene.benchy; return { x: b.position.x, y: b.position.y, rx: b.rotation.x, ry: b.rotation.y, rz: b.rotation.z }; }")

            # Helper to reset benchy position and rotation
            def reset_benchy():
                page.evaluate("() => { const b = benchyScene.benchy; b.position.set(0, 0, 0); b.rotation.set(0, 0, 0); }")
                time.sleep(0.05)

            # Helper to read actions config safely with retries
            def read_saved_actions():
                for attempt in range(10):
                    try:
                        with open(temp_actions_path, "r") as f:
                            return json.load(f)
                    except (PermissionError, json.JSONDecodeError):
                        time.sleep(0.05)
                with open(temp_actions_path, "r") as f:
                    return json.load(f)

            # --- Part 1: Boat Visual Movement with Screenshots, Max/Min, and Refresh Persistence ---
            
            # 1. Take initial screenshot and send moderate input for 0.5s at default sensitivity (1.0)
            reset_benchy()
            initial_pos = get_current()
            page.screenshot(path=str(tmp_path / "screenshot_1_initial.png"))
            
            # Send input at ~20Hz (every 50ms) for 0.5s
            for _ in range(10):
                mock_serial.input_queue.put(b">MOTION:0,0,-30.0,0,0,0\n")
                time.sleep(0.05)
                
            page.screenshot(path=str(tmp_path / "screenshot_2_after_move.png"))
            final_pos = get_current()
            dy_default = final_pos['y'] - initial_pos['y']
            
            # 2. Change sensitivity to max (5.0) in UI, reload page to test persistence
            page.fill("#sensZPosVal", "5.0")
            page.locator("#sensZPosVal").evaluate("el => el.dispatchEvent(new Event('change'))")
            time.sleep(0.3)
            
            # Verify actions saved on disk
            saved_actions = read_saved_actions()
            assert saved_actions.get("sensitivity", {}).get("z_pos") == 5.0
            
            # Refresh page
            page.reload()
            page.click("text=Sensitivity")
            time.sleep(0.5) # Wait for page and scene to load
            
            # Verify persisted value in UI
            sens_val = page.locator("#sensZPosVal").input_value()
            assert float(sens_val) == 5.0, f"Expected persisted Z+ sensitivity to be 5.0, got {sens_val}"
            
            # 3. Take screenshot and send same input for 0.5s at max sensitivity (5.0)
            reset_benchy()
            initial_pos_max = get_current()
            page.screenshot(path=str(tmp_path / "screenshot_3_max_initial.png"))
            
            for _ in range(10):
                mock_serial.input_queue.put(b">MOTION:0,0,-30.0,0,0,0\n")
                time.sleep(0.05)
                
            page.screenshot(path=str(tmp_path / "screenshot_4_max_after_move.png"))
            final_pos_max = get_current()
            dy_max = final_pos_max['y'] - initial_pos_max['y']
            
            # Boat should have moved significantly more
            assert abs(dy_max) > abs(dy_default) * 2.0, f"Expected max sensitivity displacement to be larger than default, got max={dy_max}, default={dy_default}"
            
            # 4. Change sensitivity to min (0.1) in UI, reload page to test persistence
            page.fill("#sensZPosVal", "0.1")
            page.locator("#sensZPosVal").evaluate("el => el.dispatchEvent(new Event('change'))")
            time.sleep(0.3)
            
            # Refresh page
            page.reload()
            page.click("text=Sensitivity")
            time.sleep(0.5)
            
            # Verify persisted value in UI
            sens_val = page.locator("#sensZPosVal").input_value()
            assert float(sens_val) == 0.1, f"Expected persisted Z+ sensitivity to be 0.1, got {sens_val}"
            
            # 5. Take screenshot and send same input for 0.5s at min sensitivity (0.1)
            reset_benchy()
            initial_pos_min = get_current()
            page.screenshot(path=str(tmp_path / "screenshot_5_min_initial.png"))
            
            for _ in range(10):
                mock_serial.input_queue.put(b">MOTION:0,0,-30.0,0,0,0\n")
                time.sleep(0.05)
                
            page.screenshot(path=str(tmp_path / "screenshot_6_min_after_move.png"))
            final_pos_min = get_current()
            dy_min = final_pos_min['y'] - initial_pos_min['y']
            
            # Boat should have moved significantly less
            assert abs(dy_min) < abs(dy_default) * 0.5, f"Expected min sensitivity displacement to be smaller than default, got min={dy_min}, default={dy_default}"

            # Restore Z+ sensitivity
            page.fill("#sensZPosVal", "1.0")
            page.locator("#sensZPosVal").evaluate("el => el.dispatchEvent(new Event('change'))")
            time.sleep(0.3)

            # --- Part 2: Mathematical Scaling Verification for ALL 12 Sensitivity Parameters ---
            
            # Define all 12 sensitivity parameters, UI elements, raw input packets, and index of expected non-zero axis in hid_report
            all_sens_tests = [
                # (param_name, val_input_id, raw_telemetry_packet, axis_index_in_report, expected_sign)
                ("x_pos", "#sensXPosVal", ">MOTION:-20.0,0,0,0,0,0\n", 0, -1),
                ("x_neg", "#sensXNegVal", ">MOTION:20.0,0,0,0,0,0\n", 0, 1),
                ("y_pos", "#sensYPosVal", ">MOTION:0,20.0,0,0,0,0\n", 1, 1),
                ("y_neg", "#sensYNegVal", ">MOTION:0,-20.0,0,0,0,0\n", 1, -1),
                ("z_pos", "#sensZPosVal", ">MOTION:0,0,-20.0,0,0,0\n", 2, -1),
                ("z_neg", "#sensZNegVal", ">MOTION:0,0,20.0,0,0,0\n", 2, 1),
                ("rx_pos", "#sensRxPosVal", ">MOTION:0,0,0,20.0,0,0\n", 3, 1),
                ("rx_neg", "#sensRxNegVal", ">MOTION:0,0,0,-20.0,0,0\n", 3, -1),
                ("ry_pos", "#sensRyPosVal", ">MOTION:0,0,0,0,20.0,0\n", 4, 1),
                ("ry_neg", "#sensRyNegVal", ">MOTION:0,0,0,0,-20.0,0\n", 4, -1),
                ("rz_pos", "#sensRzPosVal", ">MOTION:0,0,0,0,0,20.0\n", 5, 1),
                ("rz_neg", "#sensRzNegVal", ">MOTION:0,0,0,0,0,-20.0\n", 5, -1),
            ]

            for param, val_id, raw_packet, axis_idx, sign in all_sens_tests:
                # Set sensitivity to 5.0
                page.fill(val_id, "5.0")
                page.locator(val_id).evaluate("el => el.dispatchEvent(new Event('change'))")
                time.sleep(0.2)
                
                # Clear serial writes and feed raw telemetry
                mock_serial.writes.clear()
                mock_serial.input_queue.put(raw_packet.encode())
                time.sleep(0.1)
                
                # Verify daemon output was scaled correctly
                assert len(mock_serial.writes) > 0, f"No hid_report written to serial port for {param}"
                last_report = mock_serial.writes[-1].decode().strip()
                assert last_report.startswith("hid_report"), f"Expected hid_report command, got {last_report}"
                
                # Parse the float values
                vals = [float(v) for v in last_report[11:].split(",")]
                expected_val = 20.0 * 5.0 * sign
                assert abs(vals[axis_idx] - expected_val) < 0.1, f"Expected scaled value for {param} to be {expected_val}, got {vals[axis_idx]} in report {vals}"
                
                # Restore sensitivity back to 1.0
                page.fill(val_id, "1.0")
                page.locator(val_id).evaluate("el => el.dispatchEvent(new Event('change'))")
                time.sleep(0.1)

            # --- Part 3: Invert settings verification ---
            
            axes_inverts = [
                ("x", "#invX", ">MOTION:-20.0,0,0,0,0,0\n", 0, -20.0),
                ("y", "#invY", ">MOTION:0,20.0,0,0,0,0\n", 1, 20.0),
                ("z", "#invZ", ">MOTION:0,0,-20.0,0,0,0\n", 2, -20.0),
                ("rx", "#invRx", ">MOTION:0,0,0,20.0,0,0\n", 3, 20.0),
                ("ry", "#invRy", ">MOTION:0,0,0,0,20.0,0\n", 4, 20.0),
                ("rz", "#invRz", ">MOTION:0,0,0,0,0,20.0\n", 5, 20.0),
            ]
            
            for name, selector, raw_packet, axis_idx, normal_val in axes_inverts:
                # 1. Enable inversion in UI
                page.click(selector)
                time.sleep(0.2)
                
                # Clear and send motion
                mock_serial.writes.clear()
                mock_serial.input_queue.put(raw_packet.encode())
                time.sleep(0.1)
                
                # Verify report has inverted sign
                assert len(mock_serial.writes) > 0
                last_report = mock_serial.writes[-1].decode().strip()
                vals = [float(v) for v in last_report[11:].split(",")]
                expected_val = -normal_val # Sign flipped
                assert abs(vals[axis_idx] - expected_val) < 0.1, f"Inversion of {name} failed: expected {expected_val}, got {vals[axis_idx]}"
                
                # 2. Disable inversion in UI
                page.click(selector)
                time.sleep(0.2)

            # --- Part 4: Dead Zones, Curves, and Filter UI commands to device verification ---
            
            device_cmd_tests = [
                # (val_input_id, val_str, expected_serial_cmd)
                ("#sensDeadTVal", "30.0", b"sens set dead_t 30.00\n"),
                ("#sensDeadRVal", "25.0", b"sens set dead_r 25.00\n"),
                ("#sensKalQVal", "0.75", b"sens set kalman_q 0.75\n"),
                ("#sensKalRVal", "8.0", b"sens set kalman_r 8.00\n"),
                ("#sensExpVal", "4.5", b"sens set exp 4.50\n"),
            ]
            
            for val_id, value, expected_cmd in device_cmd_tests:
                mock_serial.writes.clear()
                page.fill(val_id, value)
                page.locator(val_id).evaluate("el => el.dispatchEvent(new Event('change'))")
                time.sleep(0.2)
                
                # Verify command was sent to device
                # Note: float format in index.html sends up to 3 decimals, let's check prefix
                # e.g., "sens set dead_t 30" or "sens set dead_t 30.0"
                found = False
                expected_prefix = expected_cmd.split()[0:3] # [b"sens", b"set", b"<param>"]
                for w in mock_serial.writes:
                    parts = w.split()
                    if len(parts) >= 3 and parts[0] == expected_prefix[0] and parts[1] == expected_prefix[1] and parts[2] == expected_prefix[2]:
                        # Verify the parsed value is correct
                        val = float(parts[3])
                        expected_val = float(expected_cmd.split()[3])
                        assert abs(val - expected_val) < 0.01
                        found = True
                        break
                assert found, f"Command {expected_cmd} was not written to device. Writes: {mock_serial.writes}"

            browser.close()
    finally:
        # Teardown sequence
        teardown_initiated = True

        # Stop service
        mock_serial.close()
        if main_task:
            loop.call_soon_threadsafe(main_task.cancel)
        service_thread.join(timeout=3.0)
        http_server.stop()

        # Join started daemon threads to ensure clean exit
        for t in started_threads:
            t.join(timeout=1.0)
            assert not t.is_alive(), f"Thread {t} (name={t.name}) failed to exit during teardown!"

        # Stop all patchers
        for p in reversed(patchers):
            p.stop()

        # Restore excepthook
        threading.Thread.__init__ = original_init
        threading.excepthook = original_excepthook
