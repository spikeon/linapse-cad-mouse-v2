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
    def readline(self):
        while not teardown_initiated and self.is_open:
            try:
                return self.input_queue.get(timeout=0.05)
            except queue.Empty:
                continue
        raise KillThreadException("teardown active")
    def write(self, data):
        pass
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
    linux_dir = Path(__file__).parent
    configurator_dir = linux_dir.parent / "configurator"
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
    def run_service():
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(linapse_service.main())
        except Exception as e:
            print(f"Service main failed: {e}")

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
                with open(temp_actions_path, "r") as f:
                    saved_actions = json.load(f)
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
                with open(temp_actions_path, "r") as f:
                    saved_actions = json.load(f)
                assert not saved_actions.get("inversion", {}).get(name.lower()), f"{name} inversion failed to untoggle on disk"

            # --- 5. Test Y Axis inversion updates actions on disk ---
            page.click("#invY")
            time.sleep(0.3)
            with open(temp_actions_path, "r") as f:
                saved_actions = json.load(f)
            assert saved_actions.get("inversion", {}).get("y") is True, f"Y inversion failed to save on disk: {saved_actions}"

            # Untoggle Y Inversion
            page.click("#invY")
            time.sleep(0.3)
            with open(temp_actions_path, "r") as f:
                saved_actions = json.load(f)
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
        loop.call_soon_threadsafe(loop.stop)
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
