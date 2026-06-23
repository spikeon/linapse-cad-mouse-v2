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

def mock_path_factory(temp_socket_path):
    def mock_path(*args, **kwargs):
        if args and "spnav.sock" in str(args[0]):
            return Path(temp_socket_path)
        return Path(*args, **kwargs)
    return mock_path

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


@pytest.fixture(scope="module")
def benchy_env(tmp_path_factory):
    global teardown_initiated, started_threads, ydotool_calls
    teardown_initiated = False
    started_threads.clear()
    ydotool_calls.clear()

    # Setup temporary configuration path
    tmp_path = tmp_path_factory.mktemp("playwright_benchy")
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
        "inversion": {},
        "custom_usb": {"enabled": True}
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
        patch("linapse_service.Path", mock_path_factory(tmp_path / "spnav.sock")),
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
        page.click("text=Motion")

        # Poll until benchyScene and its model are initialized
        start_time = time.time()
        initialized = False
        while time.time() - start_time < 5.0:
            is_ready = page.evaluate("() => typeof benchyScene !== 'undefined' && benchyScene !== null && benchyScene.benchy !== undefined && benchyScene.benchy.children.length > 0")
            if is_ready:
                initialized = True
                break
            time.sleep(0.1)

        assert initialized, "benchyScene model failed to initialize within 5 seconds"

        yield page, mock_serial, temp_actions_path, tmp_path

        browser.close()

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

    # Stop all patchers
    for p in reversed(patchers):
        p.stop()

    # Restore excepthook
    threading.Thread.__init__ = original_init
    threading.excepthook = original_excepthook


def get_current(page):
    return page.evaluate("() => { const b = benchyScene.benchy; return { x: b.position.x, y: b.position.y, rx: b.rotation.x, ry: b.rotation.y, rz: b.rotation.z }; }")


def reset_benchy(page):
    page.evaluate("() => { const b = benchyScene.benchy; b.position.set(0, 0, 0); b.rotation.set(0, 0, 0); }")
    time.sleep(0.05)


def wait_for_config_update(temp_actions_path, condition_func):
    start_wait = time.time()
    while time.time() - start_wait < 2.0:
        actions = linapse_service._actions_ref[0]
        if actions and condition_func(actions):
            return
        time.sleep(0.02)
    # Read action directly from disk if reference did not update yet
    for attempt in range(10):
        try:
            with open(temp_actions_path, "r") as f:
                actions = json.load(f)
                if actions and condition_func(actions):
                    return
        except (PermissionError, json.JSONDecodeError):
            pass
        time.sleep(0.05)
    raise TimeoutError("Configuration did not update to meet condition")


def reset_test_state(page, mock_serial, temp_actions_path, target_tab="Motion"):
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
        "inversion": {},
        "custom_usb": {"enabled": True}
    }
    with open(temp_actions_path, "w") as f:
        json.dump(initial_actions, f)

    mock_serial.writes.clear()
    while not mock_serial.input_queue.empty():
        try:
            mock_serial.input_queue.get_nowait()
        except queue.Empty:
            break

    linapse_service._held.clear()
    linapse_service._chord_fired = False
    linapse_service._timers.clear()
    linapse_service._scroll_threads.clear()
    linapse_service.reset_click_states()
    linapse_service._actions_ref[0] = initial_actions

    page.reload(timeout=60000)
    
    # Wait for websocket to connect
    page.locator("#connStatus.connected").wait_for(timeout=5000)
    
    page.click("text=Motion")

    # Wait for benchyScene model to load
    start_time = time.time()
    initialized = False
    while time.time() - start_time < 5.0:
        is_ready = page.evaluate("() => typeof benchyScene !== 'undefined' && benchyScene !== null && benchyScene.benchy !== undefined && benchyScene.benchy.children.length > 0")
        if is_ready:
            initialized = True
            break
        time.sleep(0.05)
    assert initialized, "benchyScene model failed to initialize after reload"

    if target_tab == "Axes":
        page.locator(".sens-tab", has_text="Axes").click()
    elif target_tab == "General":
        page.locator(".sens-tab", has_text="General").click()


# ==================== VIEWPORT MOTION TESTS ====================

def test_viewport_motion_x_normal(benchy_env):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path)

    # Positive Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:100.0,0,0,0,0,0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_pos = curr['x'] - initial['x']
    assert delta_pos > 0.01, f"X normal positive movement failed: got {delta_pos}"

    # Negative Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:-100.0,0,0,0,0,0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_neg = curr['x'] - initial['x']
    assert delta_neg < -0.01, f"X normal negative movement failed: got {delta_neg}"


def test_viewport_motion_x_inverted(benchy_env):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path, target_tab="General")

    # Toggle inversion
    page.click("#invX")
    wait_for_config_update(temp_actions_path, lambda actions: actions.get("inversion", {}).get("x") is True)

    # Positive Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:100.0,0,0,0,0,0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_pos = curr['x'] - initial['x']
    assert delta_pos < -0.01, f"X inverted positive movement failed: got {delta_pos}"

    # Negative Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:-100.0,0,0,0,0,0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_neg = curr['x'] - initial['x']
    assert delta_neg > 0.01, f"X inverted negative movement failed: got {delta_neg}"


def test_viewport_motion_z_normal(benchy_env):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path)

    # Positive Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:0,0,100.0,0,0,0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_pos = curr['y'] - initial['y']
    assert delta_pos < -0.01, f"Z normal positive movement failed: got {delta_pos}"

    # Negative Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:0,0,-100.0,0,0,0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_neg = curr['y'] - initial['y']
    assert delta_neg > 0.01, f"Z normal negative movement failed: got {delta_neg}"


def test_viewport_motion_z_inverted(benchy_env):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path, target_tab="General")

    # Toggle inversion
    page.click("#invZ")
    wait_for_config_update(temp_actions_path, lambda actions: actions.get("inversion", {}).get("z") is True)

    # Positive Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:0,0,100.0,0,0,0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_pos = curr['y'] - initial['y']
    assert delta_pos > 0.01, f"Z inverted positive movement failed: got {delta_pos}"

    # Negative Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:0,0,-100.0,0,0,0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_neg = curr['y'] - initial['y']
    assert delta_neg < -0.01, f"Z inverted negative movement failed: got {delta_neg}"


def test_viewport_motion_rx_normal(benchy_env):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path)

    # Positive Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:0,0,0,100.0,0,0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_pos = curr['rx'] - initial['rx']
    assert delta_pos > 0.01, f"RX normal positive movement failed: got {delta_pos}"

    # Negative Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:0,0,0,-100.0,0,0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_neg = curr['rx'] - initial['rx']
    assert delta_neg < -0.01, f"RX normal negative movement failed: got {delta_neg}"


def test_viewport_motion_rx_inverted(benchy_env):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path, target_tab="General")

    # Toggle inversion
    page.click("#invRx")
    wait_for_config_update(temp_actions_path, lambda actions: actions.get("inversion", {}).get("rx") is True)

    # Positive Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:0,0,0,100.0,0,0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_pos = curr['rx'] - initial['rx']
    assert delta_pos < -0.01, f"RX inverted positive movement failed: got {delta_pos}"

    # Negative Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:0,0,0,-100.0,0,0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_neg = curr['rx'] - initial['rx']
    assert delta_neg > 0.01, f"RX inverted negative movement failed: got {delta_neg}"


def test_viewport_motion_ry_normal(benchy_env):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path)

    # Positive Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:0,0,0,0,100.0,0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_pos = curr['rz'] - initial['rz']
    assert delta_pos > 0.01, f"RY normal positive movement failed: got {delta_pos}"

    # Negative Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:0,0,0,0,-100.0,0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_neg = curr['rz'] - initial['rz']
    assert delta_neg < -0.01, f"RY normal negative movement failed: got {delta_neg}"


def test_viewport_motion_ry_inverted(benchy_env):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path, target_tab="General")

    # Toggle inversion
    page.click("#invRy")
    wait_for_config_update(temp_actions_path, lambda actions: actions.get("inversion", {}).get("ry") is True)

    # Positive Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:0,0,0,0,100.0,0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_pos = curr['rz'] - initial['rz']
    assert delta_pos < -0.01, f"RY inverted positive movement failed: got {delta_pos}"

    # Negative Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:0,0,0,0,-100.0,0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_neg = curr['rz'] - initial['rz']
    assert delta_neg > 0.01, f"RY inverted negative movement failed: got {delta_neg}"


def test_viewport_motion_rz_normal(benchy_env):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path)

    # Positive Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:0,0,0,0,0,100.0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_pos = curr['ry'] - initial['ry']
    assert delta_pos > 0.01, f"RZ normal positive movement failed: got {delta_pos}"

    # Negative Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:0,0,0,0,0,-100.0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_neg = curr['ry'] - initial['ry']
    assert delta_neg < -0.01, f"RZ normal negative movement failed: got {delta_neg}"


def test_viewport_motion_rz_inverted(benchy_env):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path, target_tab="General")

    # Toggle inversion
    page.click("#invRz")
    wait_for_config_update(temp_actions_path, lambda actions: actions.get("inversion", {}).get("rz") is True)

    # Positive Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:0,0,0,0,0,100.0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_pos = curr['ry'] - initial['ry']
    assert delta_pos < -0.01, f"RZ inverted positive movement failed: got {delta_pos}"

    # Negative Input
    reset_benchy(page)
    initial = get_current(page)
    mock_serial.input_queue.put(b">MOTION:0,0,0,0,0,-100.0\n")
    time.sleep(0.3)
    curr = get_current(page)
    delta_neg = curr['ry'] - initial['ry']
    assert delta_neg > 0.01, f"RZ inverted negative movement failed: got {delta_neg}"


def test_viewport_motion_y_inversion(benchy_env):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path, target_tab="General")

    # Toggle Y Inversion
    page.click("#invY")
    wait_for_config_update(temp_actions_path, lambda actions: actions.get("inversion", {}).get("y") is True)

    # Untoggle Y Inversion
    page.click("#invY")
    wait_for_config_update(temp_actions_path, lambda actions: not actions.get("inversion", {}).get("y"))


# ==================== GESTURE TOAST TESTS ====================

def test_toast_tap_gesture(benchy_env):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path)

    mock_serial.input_queue.put(b"TAP:NegZ:1\n")
    time.sleep(0.3)
    tap_toast_header = page.locator(".toast-header").last.text_content()
    tap_toast_body = page.locator(".toast-body").last.text_content()
    assert "Tap Registered" in tap_toast_header
    assert "TOP TAP (1X)" in tap_toast_body.upper()


def test_toast_button_press(benchy_env):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path)

    linapse_service._broadcast_from_thread("BUTTON:0:1")
    time.sleep(0.3)
    toast_header = page.locator(".toast-header").last.text_content()
    toast_body = page.locator(".toast-body").last.text_content()
    assert "Button Pressed" in toast_header
    assert "LEFT BUTTON" in toast_body


# ==================== SENSITIVITY VISUAL DISPLACEMENT TESTS ====================

def test_sensitivity_z_pos_visual_scale(benchy_env):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path, target_tab="Axes")

    # 1. Take initial screenshot and send moderate input for 0.5s at default sensitivity (1.0)
    reset_benchy(page)
    initial_pos = get_current(page)
    page.screenshot(path=str(tmp_path / "screenshot_1_initial.png"))

    for _ in range(10):
        mock_serial.input_queue.put(b">MOTION:0,0,-30.0,0,0,0\n")
        time.sleep(0.05)

    page.screenshot(path=str(tmp_path / "screenshot_2_after_move.png"))
    final_pos = get_current(page)
    dy_default = final_pos['y'] - initial_pos['y']

    # 2. Change sensitivity to max (5.0) in UI, reload page to test persistence
    page.fill("#sensZPosVal", "5.0")
    page.locator("#sensZPosVal").evaluate("el => el.dispatchEvent(new Event('change'))")

    wait_for_config_update(temp_actions_path, lambda actions: actions.get("sensitivity", {}).get("z_pos") == 5.0)

    # 3. Take screenshot and send same input for 0.5s at max sensitivity (5.0)
    reset_benchy(page)
    initial_pos_max = get_current(page)
    page.screenshot(path=str(tmp_path / "screenshot_3_max_initial.png"))

    for _ in range(10):
        mock_serial.input_queue.put(b">MOTION:0,0,-30.0,0,0,0\n")
        time.sleep(0.05)

    page.screenshot(path=str(tmp_path / "screenshot_4_max_after_move.png"))
    final_pos_max = get_current(page)
    dy_max = final_pos_max['y'] - initial_pos_max['y']

    assert abs(dy_max) > abs(dy_default) * 2.0, f"Expected max sensitivity displacement to be larger, got max={dy_max}, default={dy_default}"

    # 4. Change sensitivity to min (0.1) in UI
    page.fill("#sensZPosVal", "0.1")
    page.locator("#sensZPosVal").evaluate("el => el.dispatchEvent(new Event('change'))")
    wait_for_config_update(temp_actions_path, lambda actions: actions.get("sensitivity", {}).get("z_pos") == 0.1)

    # 5. Take screenshot and send same input for 0.5s at min sensitivity (0.1)
    reset_benchy(page)
    initial_pos_min = get_current(page)
    page.screenshot(path=str(tmp_path / "screenshot_5_min_initial.png"))

    for _ in range(10):
        mock_serial.input_queue.put(b">MOTION:0,0,-30.0,0,0,0\n")
        time.sleep(0.05)

    page.screenshot(path=str(tmp_path / "screenshot_6_min_after_move.png"))
    final_pos_min = get_current(page)
    dy_min = final_pos_min['y'] - initial_pos_min['y']

    assert abs(dy_min) < abs(dy_default) * 0.5, f"Expected min sensitivity displacement to be smaller, got min={dy_min}, default={dy_default}"


def test_sensitivity_z_pos_persists(benchy_env):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path, target_tab="Axes")

    page.fill("#sensZPosVal", "5.0")
    page.locator("#sensZPosVal").evaluate("el => el.dispatchEvent(new Event('change'))")

    wait_for_config_update(temp_actions_path, lambda actions: actions.get("sensitivity", {}).get("z_pos") == 5.0)

    # Refresh page
    page.reload()
    page.click("text=Motion")
    page.click("text=Axes")
    time.sleep(0.5)

    sens_val = page.locator("#sensZPosVal").input_value()
    assert float(sens_val) == 5.0, f"Expected persisted Z+ sensitivity to be 5.0, got {sens_val}"


# ==================== MATHEMATICAL SENSITIVITY SCALING TESTS ====================

def verify_sensitivity_scaling(benchy_env, param, selector, raw_packet, axis_idx, sign):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path, target_tab="Axes")

    # Set sensitivity to 5.0
    page.fill(selector, "5.0")
    page.locator(selector).evaluate("el => el.dispatchEvent(new Event('change'))")

    wait_for_config_update(temp_actions_path, lambda actions: actions.get("sensitivity", {}).get(param) == 5.0)

    # Clear serial writes and feed raw telemetry
    mock_serial.writes.clear()
    mock_serial.input_queue.put(raw_packet.encode())
    time.sleep(0.1)

    # Verify daemon output was scaled correctly
    hid_reports = [w for w in mock_serial.writes if w.decode().strip().startswith("hid_report")]
    assert len(hid_reports) > 0, f"No hid_report written to serial port for {param}"
    last_report = hid_reports[-1].decode().strip()

    # Parse the float values
    vals = [float(v) for v in last_report[11:].split(",")]
    expected_val = 20.0 * 5.0 * sign
    assert abs(vals[axis_idx] - expected_val) < 0.1, f"Expected scaled value for {param} to be {expected_val}, got {vals[axis_idx]} in report {vals}"


def test_sensitivity_x_pos(benchy_env):
    verify_sensitivity_scaling(benchy_env, "x_pos", "#sensXPosVal", ">MOTION:20.0,0,0,0,0,0\n", 0, 1)


def test_sensitivity_x_neg(benchy_env):
    verify_sensitivity_scaling(benchy_env, "x_neg", "#sensXNegVal", ">MOTION:-20.0,0,0,0,0,0\n", 0, -1)


def test_sensitivity_y_pos(benchy_env):
    verify_sensitivity_scaling(benchy_env, "y_pos", "#sensYPosVal", ">MOTION:0,-20.0,0,0,0,0\n", 1, -1)


def test_sensitivity_y_neg(benchy_env):
    verify_sensitivity_scaling(benchy_env, "y_neg", "#sensYNegVal", ">MOTION:0,20.0,0,0,0,0\n", 1, 1)


def test_sensitivity_z_pos(benchy_env):
    verify_sensitivity_scaling(benchy_env, "z_pos", "#sensZPosVal", ">MOTION:0,0,-20.0,0,0,0\n", 2, -1)


def test_sensitivity_z_neg(benchy_env):
    verify_sensitivity_scaling(benchy_env, "z_neg", "#sensZNegVal", ">MOTION:0,0,20.0,0,0,0\n", 2, 1)


def test_sensitivity_rx_pos(benchy_env):
    verify_sensitivity_scaling(benchy_env, "rx_pos", "#sensRxPosVal", ">MOTION:0,0,0,-20.0,0,0\n", 3, -1)


def test_sensitivity_rx_neg(benchy_env):
    verify_sensitivity_scaling(benchy_env, "rx_neg", "#sensRxNegVal", ">MOTION:0,0,0,20.0,0,0\n", 3, 1)


def test_sensitivity_ry_pos(benchy_env):
    verify_sensitivity_scaling(benchy_env, "ry_pos", "#sensRyPosVal", ">MOTION:0,0,0,0,20.0,0\n", 4, 1)


def test_sensitivity_ry_neg(benchy_env):
    verify_sensitivity_scaling(benchy_env, "ry_neg", "#sensRyNegVal", ">MOTION:0,0,0,0,-20.0,0\n", 4, -1)


def test_sensitivity_rz_pos(benchy_env):
    verify_sensitivity_scaling(benchy_env, "rz_pos", "#sensRzPosVal", ">MOTION:0,0,0,0,0,-20.0\n", 5, -1)


def test_sensitivity_rz_neg(benchy_env):
    verify_sensitivity_scaling(benchy_env, "rz_neg", "#sensRzNegVal", ">MOTION:0,0,0,0,0,20.0\n", 5, 1)


# ==================== MATHEMATICAL INVERSION SCALING TESTS ====================

def verify_inversion_scaling(benchy_env, name, selector, raw_packet, axis_idx, normal_val):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path, target_tab="General")

    # Enable inversion in UI
    page.click(selector)
    wait_for_config_update(temp_actions_path, lambda actions: actions.get("inversion", {}).get(name) is True)

    # Clear and send motion
    mock_serial.writes.clear()
    mock_serial.input_queue.put(raw_packet.encode())
    time.sleep(0.1)

    # Verify report has inverted sign
    hid_reports = [w for w in mock_serial.writes if w.decode().strip().startswith("hid_report")]
    assert len(hid_reports) > 0, f"No hid_report written to serial port for inversion of {name}"
    last_report = hid_reports[-1].decode().strip()
    vals = [float(v) for v in last_report[11:].split(",")]
    expected_val = -normal_val # Sign flipped
    assert abs(vals[axis_idx] - expected_val) < 0.1, f"Inversion of {name} failed: expected {expected_val}, got {vals[axis_idx]}"


def test_inversion_x(benchy_env):
    verify_inversion_scaling(benchy_env, "x", "#invX", ">MOTION:-20.0,0,0,0,0,0\n", 0, -20.0)


def test_inversion_y(benchy_env):
    verify_inversion_scaling(benchy_env, "y", "#invY", ">MOTION:0,20.0,0,0,0,0\n", 1, 20.0)


def test_inversion_z(benchy_env):
    verify_inversion_scaling(benchy_env, "z", "#invZ", ">MOTION:0,0,-20.0,0,0,0\n", 2, -20.0)


def test_inversion_rx(benchy_env):
    verify_inversion_scaling(benchy_env, "rx", "#invRx", ">MOTION:0,0,0,20.0,0,0\n", 3, 20.0)


def test_inversion_ry(benchy_env):
    verify_inversion_scaling(benchy_env, "ry", "#invRy", ">MOTION:0,0,0,0,20.0,0\n", 4, 20.0)


def test_inversion_rz(benchy_env):
    verify_inversion_scaling(benchy_env, "rz", "#invRz", ">MOTION:0,0,0,0,0,20.0\n", 5, 20.0)


# ==================== DEVICE PARAMETERS CONFIG TESTS ====================

def verify_device_cmd(benchy_env, selector, value, expected_cmd):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path, target_tab="General")

    mock_serial.writes.clear()
    page.fill(selector, value)
    page.locator(selector).evaluate("el => el.dispatchEvent(new Event('change'))")
    time.sleep(0.2)

    found = False
    expected_prefix = expected_cmd.split()[0:3] # [sens, set, param]
    for w in mock_serial.writes:
        parts = w.split()
        if len(parts) >= 3 and parts[0] == expected_prefix[0] and parts[1] == expected_prefix[1] and parts[2] == expected_prefix[2]:
            val = float(parts[3])
            expected_val = float(expected_cmd.split()[3])
            assert abs(val - expected_val) < 0.01
            found = True
            break
    assert found, f"Command {expected_cmd} was not written to device. Writes: {mock_serial.writes}"


def test_device_cmd_dead_t(benchy_env):
    verify_device_cmd(benchy_env, "#sensDeadTVal", "30.0", b"sens set dead_t 30.00\n")


def test_device_cmd_dead_r(benchy_env):
    verify_device_cmd(benchy_env, "#sensDeadRVal", "25.0", b"sens set dead_r 25.00\n")


def test_device_cmd_kalman_q(benchy_env):
    verify_device_cmd(benchy_env, "#sensKalQVal", "0.75", b"sens set kalman_q 0.75\n")


def test_device_cmd_kalman_r(benchy_env):
    verify_device_cmd(benchy_env, "#sensKalRVal", "8.0", b"sens set kalman_r 8.00\n")


def test_device_cmd_exp_curve(benchy_env):
    verify_device_cmd(benchy_env, "#sensExpVal", "4.5", b"sens set exp 4.50\n")


def test_device_cmd_spherical(benchy_env):
    page, mock_serial, temp_actions_path, tmp_path = benchy_env
    reset_test_state(page, mock_serial, temp_actions_path, target_tab="General")

    mock_serial.writes.clear()
    page.click("#sensSpherical")
    time.sleep(0.2)

    found = False
    for w in mock_serial.writes:
        if b"sens set spherical 1" in w:
            found = True
            break
    assert found, f"Command to enable spherical mode not written. Writes: {mock_serial.writes}"

    # Click again to turn off
    mock_serial.writes.clear()
    page.click("#sensSpherical")
    time.sleep(0.2)

    found = False
    for w in mock_serial.writes:
        if b"sens set spherical 0" in w:
            found = True
            break
    assert found, f"Command to disable spherical mode not written. Writes: {mock_serial.writes}"

