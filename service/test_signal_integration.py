#!/usr/bin/env python3
import asyncio
import os
import sys
import struct
import json
import time
import socket
import select
import builtins
import queue
import threading
import glob
import subprocess
import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
from importlib.machinery import SourceFileLoader
import importlib.util

try:
    import websockets
except ImportError:
    pytest.skip("websockets is not installed", allow_module_level=True)

# Load the service module
if "linapse_service" in sys.modules:
    linapse_service = sys.modules["linapse_service"]
else:
    service_path = Path(__file__).parent / "linapse-service"
    loader = SourceFileLoader("linapse_service", str(service_path))
    spec = importlib.util.spec_from_loader("linapse_service", loader)
    linapse_service = importlib.util.module_from_spec(spec)
    loader.exec_module(linapse_service)
    sys.modules["linapse_service"] = linapse_service

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
        if name in ("serial_thread", "hid_thread", "config_watcher", "volume_watcher", "_scroll_loop", "_on_single"):
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
    if "hidraw" in pattern:
        return ["/dev/input/by-id/usb-MockCAD_Mouse-if02-hidraw"]
    if "usb-Seeed_Studio_CAD_Mouse" in pattern or "ttyACM" in pattern:
        return ["/dev/ttyACM0"]
    return original_glob(pattern, *args, **kwargs)

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

class MockPathObj:
    def __init__(self, real_path):
        self._real_path = Path(real_path)
        
    def __getattr__(self, name):
        return getattr(self._real_path, name)
        
    def stat(self):
        if teardown_initiated and threading.current_thread() != threading.main_thread():
            raise KillThreadException("teardown active")
        return self._real_path.stat()
        
    def __fspath__(self):
        return os.fspath(self._real_path)

class MockSerial:
    def __init__(self):
        self.input_queue = queue.Queue()
        self.written_data = []
        self.is_open = True
        
    def readline(self):
        while not teardown_initiated:
            try:
                return self.input_queue.get(timeout=0.05)
            except queue.Empty:
                continue
        raise KillThreadException("teardown active")
        
    def write(self, data):
        self.written_data.append(data)
        
    def close(self):
        self.is_open = False

def get_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def mock_path_factory(temp_socket_path):
    def mock_path(*args, **kwargs):
        if args and "spnav.sock" in str(args[0]):
            return Path(temp_socket_path)
        return Path(*args, **kwargs)
    return mock_path

def mock_open_factory(read_fd):
    original_open = builtins.open
    def mock_open(file, mode="r", *args, **kwargs):
        if teardown_initiated and threading.current_thread() != threading.main_thread():
            raise KillThreadException("teardown active")
        if "MockCAD_Mouse" in str(file):
            return os.fdopen(read_fd, "rb", buffering=0)
        return original_open(file, mode, *args, **kwargs)
    return mock_open

@pytest.fixture
def running_service(tmp_path):
    global teardown_initiated, started_threads, ydotool_calls
    teardown_initiated = False
    started_threads.clear()
    ydotool_calls.clear()
    
    temp_socket_path = tmp_path / "spnav.sock"
    temp_actions_path = tmp_path / "actions.json"
    
    # Write initial configuration
    initial_actions = {
        "button_override": False,
        "buttons": {
            "0": {"action": "scroll_down"},
            "1": {"action": "scroll_up"},
            "chord": {"action": "key", "value": "shift+7"}
        },
        "taps": {
            "top:1": {"action": "key", "value": "ctrl+alt+t"}
        },
        "sensitivity": {},
        "inversion": {}
    }
    with open(temp_actions_path, "w") as f:
        json.dump(initial_actions, f)
        
    # Override service config paths and port
    linapse_service.ACTIONS_PATH = MockPathObj(temp_actions_path)
    free_port = get_free_port()
    linapse_service.WS_PORT = free_port
    
    # Setup pipe for HID mock
    read_fd, write_fd = os.pipe()
    mock_serial = MockSerial()
    
    # Setup loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    linapse_service._loop = loop
    
    # Reset internal variables
    linapse_service._socket_clients.clear()
    linapse_service._ws_clients.clear()
    linapse_service._held.clear()
    linapse_service._chord_fired = False
    linapse_service._timers.clear()
    linapse_service._scroll_threads.clear()
    linapse_service.reset_click_states()
    
    patchers = [
        patch("linapse_service.Path", mock_path_factory(temp_socket_path)),
        patch("linapse_service.serial.Serial", return_value=mock_serial),
        patch("linapse_service.glob.glob", custom_glob),
        patch("linapse_service.open", mock_open_factory(read_fd)),
        patch("linapse_service.subprocess.Popen", mock_popen),
        patch("time.sleep", custom_sleep),
    ]
    
    for p in patchers:
        p.start()
        
    threading.Thread.__init__ = custom_init
    threading.excepthook = custom_excepthook
    
    # Start service main
    service_task = loop.create_task(linapse_service.main())
    
    # Let event loop spin to startup servers
    loop.run_until_complete(asyncio.sleep(0.1))
    
    yield {
        "loop": loop,
        "ws_port": free_port,
        "socket_path": temp_socket_path,
        "actions_path": temp_actions_path,
        "mock_serial": mock_serial,
        "write_fd": write_fd,
        "read_fd": read_fd,
    }
    
    # Teardown sequence
    teardown_initiated = True
    
    # Cancel the main service task
    service_task.cancel()
    try:
        loop.run_until_complete(service_task)
    except asyncio.CancelledError:
        pass
        
    # Close pipes
    try:
        os.close(write_fd)
    except OSError:
        pass
    try:
        os.close(read_fd)
    except OSError:
        pass
        
    # Trigger thread exit across all threads by waking them up
    for t in started_threads:
        t.join(timeout=1.0)
        assert not t.is_alive(), f"Thread {t} (name={t.name}) failed to exit during teardown!"
        
    # Stop all patchers
    for p in reversed(patchers):
        p.stop()
        
    # Restore excepthook
    threading.Thread.__init__ = original_init
    threading.excepthook = original_excepthook
    
    # Clean up event loop and close lingering sockets
    linapse_service._loop = None
    
    # Close any lingering socket clients
    for writer in list(linapse_service._socket_clients):
        try:
            writer.close()
            loop.run_until_complete(writer.wait_closed())
        except Exception:
            pass
    linapse_service._socket_clients.clear()
    
    # Close any lingering ws clients
    for ws in list(linapse_service._ws_clients):
        try:
            loop.run_until_complete(ws.close())
        except Exception:
            pass
    linapse_service._ws_clients.clear()
    
    # Cancel all remaining tasks on loop
    pending = asyncio.all_tasks(loop)
    for task in pending:
        task.cancel()
    if pending:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        
    loop.close()

def test_motion_bounds_scaling_inversion_and_invalid(running_service):
    """Verify bounds, sensitivity scaling, axis inversions, Y/Z swaps, and invalid coordinate handling."""
    loop = running_service["loop"]
    mock_serial = running_service["mock_serial"]
    socket_path = running_service["socket_path"]
    
    async def run():
        # Connect to UNIX domain socket server
        reader, writer = await asyncio.open_unix_connection(str(socket_path))
        
        # Configure sensitivity and inversions
        config = {
            "sensitivity": {
                "x_pos": 2.0, "x_neg": 0.5,
                "y_pos": 1.5, "y_neg": 0.8,
                "z_pos": 3.0, "z_neg": 0.2,
                "rx_pos": 1.0, "rx_neg": 1.0,
                "ry_pos": 1.0, "ry_neg": 1.0,
                "rz_pos": 1.0, "rz_neg": 1.0
            },
            "inversion": {
                "x": True,
                "y": False,
                "z": True,
                "rx": False,
                "ry": True,
                "rz": False
            }
        }
        # Write config to actions_path and advance mtime to force config reload
        with open(running_service["actions_path"], "w") as f:
            json.dump(config, f)
        
        future_time = time.time() + 10.0
        os.utime(running_service["actions_path"], (future_time, future_time))
        await asyncio.sleep(0.1)
        
        # Test normal motion with sensitivity and inversion
        # Input: x=10.0, y=-20.0, z=5.0, rx=2.0, ry=-3.0, rz=4.0
        # Calculation:
        # X: 10.0, invert -> -10.0, scales by x_neg (0.5) -> -5.0. ix = -5
        # Y: -20.0, scales by y_pos (1.5) -> -30.0. Spacenav mapping: y = -y = 30.0. iy = 30
        # Z: 5.0, invert -> -5.0, scales by z_pos (3.0) -> -15.0. Spacenav mapping: z = -z = 15.0. iz = 15
        # RX: 2.0. irx = 2
        # RY: -3.0, invert -> 3.0, scales by ry_pos (1.0) -> 3.0. iry = 3
        # RZ: 4.0. irz = 4
        # Swapped layout: [0, ix, iz, iy, irx, irz, iry, period] -> [0, -5, 15, 30, 2, 4, 3, 10]
        
        mock_serial.input_queue.put(b">MOTION:10.0,-20.0,5.0,2.0,-3.0,4.0\n")
        data = await asyncio.wait_for(reader.readexactly(32), timeout=1.0)
        unpacked = struct.unpack("iiiiiiii", data)
        assert unpacked == (0, -5, 15, 30, 2, 4, 3, 10)
        
        # Test invalid coordinates (NaN, Inf, overflow, non-numeric, incomplete, empty)
        invalid_lines = [
            b">MOTION:nan,0,0,0,0,0\n",
            b">MOTION:inf,0,0,0,0,0\n",
            b">MOTION:-inf,0,0,0,0,0\n",
            b">MOTION:1e20,0,0,0,0,0\n",
            b">MOTION:abc,0,0,0,0,0\n",
            b">MOTION:1,2,3\n",
            b">MOTION:,,,,,\n"
        ]
        
        for line in invalid_lines:
            mock_serial.input_queue.put(line)
            
        # Since nan, inf, and -inf are sanitized to 0.0 and processed successfully,
        # they will write three packets of all zeroes to the UNIX socket.
        # Let's read and verify them.
        for _ in range(3):
            data = await asyncio.wait_for(reader.readexactly(32), timeout=1.0)
            unpacked = struct.unpack("iiiiiiii", data)
            assert unpacked == (0, 0, 0, 0, 0, 0, 0, 10)
            
        # Send a final valid motion to ensure the loop is still alive and processing correctly
        mock_serial.input_queue.put(b">MOTION:1.0,1.0,1.0,1.0,1.0,1.0\n")
        
        # x = 1.0, invert -> -1.0, scales by x_neg (0.5) -> -0.5 -> round -> 0. ix = 0
        # y = 1.0, scales by y_neg (0.8) -> 0.8, mapping: y = -y = -0.8 -> round -> -1. iy = -1
        # z = 1.0, invert -> -1.0, scales by z_pos (3.0) -> -3.0, mapping: z = -z = 3.0 -> round -> 3. iz = 3
        # rx = 1.0. irx = 1
        # ry = 1.0, invert -> -1.0, scales by ry_neg (1.0) -> -1.0. iry = -1
        # rz = 1.0. irz = 1
        # Swapped layout: [0, ix, iz, iy, irx, irz, iry, period] -> [0, 0, 3, -1, 1, 1, -1, 10]
        
        data = await asyncio.wait_for(reader.readexactly(32), timeout=1.0)
        unpacked = struct.unpack("iiiiiiii", data)
        assert unpacked == (0, 0, 3, -1, 1, 1, -1, 10)

        
        writer.close()
        await writer.wait_closed()
        
    loop.run_until_complete(run())

def test_websocket_server_integration(running_service):
    """Verify loading, saving, querying config, and broadcasting of button, tap, and motion events to WebSocket clients."""
    loop = running_service["loop"]
    ws_port = running_service["ws_port"]
    mock_serial = running_service["mock_serial"]
    write_fd = running_service["write_fd"]
    
    async def run():
        uri = f"ws://localhost:{ws_port}"
        async with websockets.connect(uri) as ws:
            # 1. Query Config
            await ws.send("actions_get")
            response = await asyncio.wait_for(ws.recv(), timeout=1.0)
            assert response.startswith("ACTIONS:")
            config_data = json.loads(response[8:])
            assert "buttons" in config_data or "modes" in config_data
            
            # 2. Save Config
            new_config = {
                "button_override": True,
                "buttons": {
                    "0": {"action": "key", "value": "x"}
                },
                "taps": {}
            }
            await ws.send("actions " + json.dumps(new_config))
            response = await asyncio.wait_for(ws.recv(), timeout=1.0)
            assert response == "OK actions saved"
            
            # Check file is updated
            with open(running_service["actions_path"]) as f:
                saved = json.load(f)
                assert saved["button_override"] is True
                
            # 3. Broadcast Motion
            mock_serial.input_queue.put(b">MOTION:1.0,2.0,3.0,4.0,5.0,6.0\n")
            response = await asyncio.wait_for(ws.recv(), timeout=1.0)
            assert response == "MOTION:1.0,2.0,3.0,4.0,5.0,6.0"
            
            # 4. Broadcast Tap
            mock_serial.input_queue.put(b"TAP:NegZ:1\n")
            response = await asyncio.wait_for(ws.recv(), timeout=1.0)
            assert response == "TAP:top:1"
            
            # 5. Broadcast Button Event (via HID raw mock pipe)
            # Press button 0 (bits = 0x01)
            report_press = bytes([3, 1]) + b"\x00" * 62
            os.write(write_fd, report_press)
            response = await asyncio.wait_for(ws.recv(), timeout=1.0)
            assert response == "BUTTON:0:1"
            
            # Release button 0 (bits = 0x00)
            report_release = bytes([3, 0]) + b"\x00" * 62
            os.write(write_fd, report_release)
            response = await asyncio.wait_for(ws.recv(), timeout=1.0)
            assert response == "BUTTON:0:0"
            
    loop.run_until_complete(run())

def test_websocket_volume_eq_integration(running_service):
    """Verify that volume_get, eq_get, and real-time volume/EQ broadcasts work over WebSockets."""
    loop = running_service["loop"]
    ws_port = running_service["ws_port"]
    
    async def run():
        uri = f"ws://localhost:{ws_port}"
        async with websockets.connect(uri) as ws:
            # 1. Query Volume
            await ws.send("volume_get")
            response = await asyncio.wait_for(ws.recv(), timeout=1.0)
            assert response.startswith("VOLUME:")
            
            # 2. Query EQ
            await ws.send("eq_get")
            response = await asyncio.wait_for(ws.recv(), timeout=1.0)
            assert response.startswith("EQ:")
            
            # 3. Test manual broadcast of volume
            from linapse import state
            state.broadcast_from_thread("VOLUME:88")
            response = await asyncio.wait_for(ws.recv(), timeout=1.0)
            assert response == "VOLUME:88"
            
            # 4. Test manual broadcast of EQ
            state.broadcast_from_thread("EQ:42:73")
            response = await asyncio.wait_for(ws.recv(), timeout=1.0)
            assert response == "EQ:42:73"
            
    loop.run_until_complete(run())

def test_button_chord_timing_debouncing(running_service):
    """Verify button chord combination logic, timing delays, debouncing, and race condition / boundary overlaps."""
    actions = {
        "button_override": False,
        "buttons": {
            "0": {"action": "key", "value": "a"},
            "1": {"action": "key", "value": "b"},
            "chord": {"action": "key", "value": "shift+7"}
        }
    }
    
    global ydotool_calls
    
    # 1. Chord Success (pressed within chord window)
    ydotool_calls.clear()
    linapse_service._on_press(0, actions)
    assert len(linapse_service._timers) == 1
    
    linapse_service._on_press(1, actions)
    assert linapse_service._chord_fired is True
    assert len(linapse_service._timers) == 0
    assert len(ydotool_calls) == 1
    assert ydotool_calls[0] == ["ydotool", "key", "42:1", "8:1", "8:0", "42:0"]
    
    linapse_service._on_release(0)
    linapse_service._on_release(1)
    assert linapse_service._chord_fired is False
    
    # 2. Debouncing / Swallowed Click (released before chord window fires)
    ydotool_calls.clear()
    linapse_service._on_press(0, actions)
    assert len(linapse_service._timers) == 1
    
    linapse_service._on_release(0)
    assert len(linapse_service._timers) == 0
    assert len(ydotool_calls) == 0
    
    # 3. Chord Boundary Overlap (button 1 pressed after button 0 timer expired)
    ydotool_calls.clear()
    linapse_service._on_press(0, actions)
    
    # Manually execute the timer's callback (representing chord window expiration)
    timer = linapse_service._timers[0]
    timer.cancel()
    linapse_service._on_single(0, actions)
    
    assert len(ydotool_calls) == 1
    assert ydotool_calls[0] == ["ydotool", "key", "30:1", "30:0"]
    
    # Press button 1 after boundary
    linapse_service._on_press(1, actions)
    assert linapse_service._chord_fired is True
    assert len(ydotool_calls) == 2
    assert ydotool_calls[1] == ["ydotool", "key", "42:1", "8:1", "8:0", "42:0"]
    
    linapse_service._on_release(0)
    linapse_service._on_release(1)
    
    # 4. Debouncing/Race Condition: release processed exactly when timer fires
    ydotool_calls.clear()
    actions_scroll = {
        "button_override": False,
        "buttons": {
            "0": {"action": "scroll_down"}
        }
    }
    linapse_service._on_press(0, actions_scroll)
    linapse_service._on_release(0)
    # Simulate the timer execution starting after the release finished
    linapse_service._on_single(0, actions_scroll)
    
    assert 0 in linapse_service._scroll_threads
    
    # Terminate the leaked thread cleanly
    thread, stop_event = linapse_service._scroll_threads.pop(0)
    stop_event.set()
    thread.join(timeout=1.0)

def test_tap_configuration_actions(running_service):
    """Verify tap overrides trigger correct commands: key combos, clicks, scrolls, macros, programs."""
    mock_serial = running_service["mock_serial"]
    global ydotool_calls
    ydotool_calls.clear()
    
    actions = {
        "taps": {
            "top:1": {"action": "key", "value": "ctrl+alt+t"},
            "left:2": {"action": "mouse_click", "button": "middle"},
            "right:1": {"action": "mouse_scroll", "direction": "up", "amount": 5},
            "front:1": {"action": "exec", "value": "/bin/true"},
            "back:1": {
                "action": "macro",
                "steps": [
                    {"action": "key", "value": "a", "delay": 50},
                    {"action": "mouse_click", "button": "left"}
                ]
            }
        }
    }
    linapse_service._save_actions(json.dumps(actions), [linapse_service.load_actions()])
    
    # Send all tap events
    mock_serial.input_queue.put(b"TAP:NegZ:1\n")
    time.sleep(0.05)
    
    mock_serial.input_queue.put(b"TAP:NegX:2\n")
    time.sleep(0.05)
    
    mock_serial.input_queue.put(b"TAP:PosX:1\n")
    time.sleep(0.05)
    
    mock_serial.input_queue.put(b"TAP:PosY:1\n")
    time.sleep(0.05)
    
    mock_serial.input_queue.put(b"TAP:NegY:1\n")
    time.sleep(0.15)  # Let macro steps run
    
    assert len(ydotool_calls) == 6
    assert ydotool_calls[0] == ["ydotool", "key", "29:1", "56:1", "20:1", "20:0", "56:0", "29:0"]
    assert ydotool_calls[1] == ["ydotool", "click", "0xc2"]
    assert ydotool_calls[2] == ["ydotool", "mousemove", "-w", "--", "0", "-5"]
    assert ydotool_calls[3] == ["shell_exec", "/bin/true"]
    assert ydotool_calls[4] == ["ydotool", "key", "30:1", "30:0"]
    assert ydotool_calls[5] == ["ydotool", "click", "0xc0"]

def test_config_reloading_on_file_change(running_service):
    """Verify that writing changes to actions.json triggers automatic config reload in the service."""
    actions_path = running_service["actions_path"]
    mock_serial = running_service["mock_serial"]
    global ydotool_calls
    ydotool_calls.clear()
    
    # Initial tap action verification (key combo)
    mock_serial.input_queue.put(b"TAP:NegZ:1\n")
    time.sleep(0.05)
    assert len(ydotool_calls) == 1
    assert ydotool_calls[0] == ["ydotool", "key", "29:1", "56:1", "20:1", "20:0", "56:0", "29:0"]
    
    ydotool_calls.clear()
    
    # Update config file to trigger reloading
    new_actions = {
        "button_override": False,
        "buttons": {},
        "taps": {
            "top:1": {"action": "mouse_click", "button": "right"}
        }
    }
    with open(actions_path, "w") as f:
        json.dump(new_actions, f)
        
    # Artificially advance mtime to force reload detection
    future_time = time.time() + 10.0
    os.utime(actions_path, (future_time, future_time))
    
    # Give config_watcher thread a brief moment to run (it polls using custom_sleep which is fast)
    time.sleep(0.1)
    
    mock_serial.input_queue.put(b"TAP:NegZ:1\n")
    time.sleep(0.05)
    
    # It should have reloaded and now dispatches right mouse click (0xc1)
    assert len(ydotool_calls) == 1
    assert ydotool_calls[0] == ["ydotool", "click", "0xc1"]

def test_modes_feature_integration(running_service):
    """Verify configuration migration, mode switching, button mapping updates, and robustness."""
    loop = running_service["loop"]
    ws_port = running_service["ws_port"]
    mock_serial = running_service["mock_serial"]
    actions_path = running_service["actions_path"]
    
    # 1. Configuration Migration: Write a legacy config directly
    legacy_actions = {
        "button_override": False,
        "buttons": {
            "0": {"action": "key", "value": "a"}
        },
        "taps": {
            "top:1": {"action": "mode", "value": "Game"}
        }
    }
    with open(actions_path, "w") as f:
        json.dump(legacy_actions, f)
        
    # Force reload
    future_time = time.time() + 10.0
    os.utime(actions_path, (future_time, future_time))
    time.sleep(0.1)
    
    # Verify that the loaded config in memory (and on disk) has been migrated
    with open(actions_path) as f:
        migrated_config = json.load(f)
    assert "modes" in migrated_config
    assert "current_mode" in migrated_config
    assert migrated_config["current_mode"] == "Default"
    assert "buttons" not in migrated_config
    assert "taps" not in migrated_config
    
    default_mode = migrated_config["modes"]["Default"]
    assert default_mode["buttons"] == {"0": {"action": "key", "value": "a"}}
    assert default_mode["taps"] == {"top:1": {"action": "mode", "value": "Game"}}
    assert default_mode["led"] == {"effect": "solid", "color": "FFFFFF", "brightness": 128}

    # Add Game mode
    migrated_config["modes"]["Game"] = {
        "buttons": {
            "0": {"action": "key", "value": "g"}
        },
        "taps": {
            "top:1": {"action": "mode", "value": "Default"}
        },
        "led": {"effect": "breathe", "color": "FF0000", "brightness": 200}
    }
    with open(actions_path, "w") as f:
        json.dump(migrated_config, f)
        
    # Force reload
    future_time = time.time() + 20.0
    os.utime(actions_path, (future_time, future_time))
    time.sleep(0.1)
    
    global ydotool_calls
    ydotool_calls.clear()
    
    # Trigger button 0 press in Default mode
    linapse_service._on_press(0, linapse_service._actions_ref[0])
    timer = linapse_service._timers[0]
    timer.cancel()
    linapse_service._on_single(0, linapse_service._actions_ref[0])
    
    assert len(ydotool_calls) == 1
    assert ydotool_calls[0] == ["ydotool", "key", "30:1", "30:0"]
    ydotool_calls.clear()
    
    # 2. Mode Switching via tap event
    mock_serial.written_data.clear()
    
    async def run_ws_check():
        uri = f"ws://localhost:{ws_port}"
        async with websockets.connect(uri) as ws:
            # Send the tap event
            mock_serial.input_queue.put(b"TAP:NegZ:1\n")
            
            # Wait for WS notification of mode change
            first_msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
            second_msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
            assert {first_msg, second_msg} == {"TAP:top:1", "MODE:Game"}
            
    loop.run_until_complete(run_ws_check())
    
    # Check that current_mode on disk is updated to "Game"
    with open(actions_path) as f:
        saved_config = json.load(f)
    assert saved_config["current_mode"] == "Game"
    
    # Check that LED commands were written to mock serial
    assert b"led effect breathe\n" in mock_serial.written_data
    assert b"led color FF0000\n" in mock_serial.written_data
    assert b"led brightness 200\n" in mock_serial.written_data
    
    # 3. Verification of button mappings in the new active mode
    ydotool_calls.clear()
    linapse_service._on_press(0, linapse_service._actions_ref[0])
    timer = linapse_service._timers[0]
    timer.cancel()
    linapse_service._on_single(0, linapse_service._actions_ref[0])
    
    assert len(ydotool_calls) == 1
    assert ydotool_calls[0] == ["ydotool", "key", "34:1", "34:0"]
    ydotool_calls.clear()
    
    # 4. Robustness: switching to a non-existent mode does nothing
    linapse_service.switch_mode("NonExistent")
    assert linapse_service._actions_ref[0]["current_mode"] == "Game"

def test_browser_and_media_modes(running_service):
    """Verify Browser and Media modes configuration, suppression, and accumulation."""
    loop = running_service["loop"]
    ws_port = running_service["ws_port"]
    mock_serial = running_service["mock_serial"]
    socket_path = running_service["socket_path"]
    actions_path = running_service["actions_path"]
    
    # 1. Verify "Browser" and "Media" are automatically added
    with open(actions_path) as f:
        config = json.load(f)
    assert "Browser" in config["modes"]
    assert "Media" in config["modes"]
    
    # 2. Test WS and UNIX Socket suppression when in Browser mode
    linapse_service.switch_mode("Browser")
    assert linapse_service._actions_ref[0]["current_mode"] == "Browser"
    
    # Reset accumulators
    linapse_service._rx_scroll_accumulator = 0.0
    linapse_service._rz_scrub_accumulator = 0.0
    linapse_service._rx_volume_accumulator = 0.0
    
    global ydotool_calls
    ydotool_calls.clear()
    
    async def run_suppression_test():
        # Setup WS connection
        uri = f"ws://localhost:{ws_port}"
        async with websockets.connect(uri) as ws:
            # Setup UNIX connection
            reader, writer = await asyncio.open_unix_connection(str(socket_path))
            try:
                # Send motion event
                mock_serial.input_queue.put(b">MOTION:0,0,0,10.0,0,0\n")
                
                # WS should NOT receive any MOTION broadcast. Since we don't expect it, we can send a TAP to verify no motion was broadcast before it.
                mock_serial.input_queue.put(b"TAP:NegZ:1\n")
                first_msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                # Should be TAP, not MOTION
                assert first_msg == "TAP:top:1"
                
                # UNIX socket should NOT receive any packet.
                # Let's read with a small timeout to make sure nothing came
                with pytest.raises(asyncio.TimeoutError):
                    await asyncio.wait_for(reader.readexactly(32), timeout=0.1)
            finally:
                writer.close()
                await writer.wait_closed()
                
    loop.run_until_complete(run_suppression_test())
    
    # 3. Test Browser mode accumulators
    ydotool_calls.clear()
    linapse_service._rx_scroll_accumulator = 0.0
    
    # Accumulate rx scroll: abs(rx) <= 15.0 decays
    mock_serial.input_queue.put(b">MOTION:0,0,0,10.0,0,0\n")
    time.sleep(0.05)
    assert linapse_service._rx_scroll_accumulator == 0.0
    
    # Now send values > 15.0 to accumulate
    mock_serial.input_queue.put(b">MOTION:0,0,0,160.0,0,0\n")
    time.sleep(0.05)
    
    assert len(ydotool_calls) == 1
    assert ydotool_calls[0] == ["ydotool", "mousemove", "-w", "--", "0", "1"]
    assert abs(linapse_service._rx_scroll_accumulator - 10.0) < 0.01
    
    # Now send negative value to scroll up (exceed -150.0)
    ydotool_calls.clear()
    mock_serial.input_queue.put(b">MOTION:0,0,0,-170.0,0,0\n")
    time.sleep(0.05)
    assert len(ydotool_calls) == 1
    assert ydotool_calls[0] == ["ydotool", "mousemove", "-w", "--", "0", "-1"]
    assert abs(linapse_service._rx_scroll_accumulator - (-10.0)) < 0.01

    # 4. Switch to Media mode and verify accumulators
    linapse_service.switch_mode("Media")
    assert linapse_service._actions_ref[0]["current_mode"] == "Media"
    
    linapse_service._rz_scrub_accumulator = 0.0
    linapse_service._rx_volume_accumulator = 0.0
    ydotool_calls.clear()
    
    # Scrub RY accumulation
    mock_serial.input_queue.put(b">MOTION:0,0,0,0,210.0,0\n")
    time.sleep(0.05)
    assert ydotool_calls[0] == ["ydotool", "key", "106:1", "106:0"]
    assert abs(linapse_service._rz_scrub_accumulator - 10.0) < 0.01
    
    ydotool_calls.clear()
    mock_serial.input_queue.put(b">MOTION:0,0,0,0,-220.0,0\n")
    time.sleep(0.05)
    assert ydotool_calls[0] == ["ydotool", "key", "105:1", "105:0"]
    assert abs(linapse_service._rz_scrub_accumulator - (-10.0)) < 0.01

    # Volume RZ accumulation
    linapse_service._rx_volume_accumulator = 0.0
    ydotool_calls.clear()
    
    mock_serial.input_queue.put(b">MOTION:0,0,0,0,0,260.0\n")
    time.sleep(0.05)
    assert ydotool_calls[0] == ["ydotool", "key", "115:1", "115:0"]
    assert abs(linapse_service._rx_volume_accumulator - 10.0) < 0.01
    
    ydotool_calls.clear()
    mock_serial.input_queue.put(b">MOTION:0,0,0,0,0,-270.0\n")
    time.sleep(0.05)
    assert ydotool_calls[0] == ["ydotool", "key", "114:1", "114:0"]
    assert abs(linapse_service._rx_volume_accumulator - (-10.0)) < 0.01

    # Switch back to Default mode
    linapse_service.switch_mode("Default")

def test_translation_lock_during_rotation(running_service):
    # Enable translation lock explicitly
    running_service_actions = linapse_service.state.actions_ref[0]
    running_service_actions["lock_translation_rotate"] = True
    
    loop = running_service["loop"]
    ws_port = running_service["ws_port"]
    mock_serial = running_service["mock_serial"]
    
    import websockets
    
    async def run_lock_test():
        uri = f"ws://localhost:{ws_port}"
        async with websockets.connect(uri) as ws:
            # 1. Pure translation should work normally
            mock_serial.input_queue.put(b">MOTION:10.0,0,0,0,0,0\n")
            # Wait for WS message
            msg1 = await asyncio.wait_for(ws.recv(), timeout=1.0)
            assert msg1 == "MOTION:10.0,0.0,0.0,0.0,0.0,0.0"
            
            # 2. Combined translation and rotation should suppress translation
            mock_serial.input_queue.put(b">MOTION:10.0,0,0,5.0,0,0\n")
            msg2 = await asyncio.wait_for(ws.recv(), timeout=1.0)
            assert msg2 == "MOTION:0.0,0.0,0.0,5.0,0.0,0.0"
            
            # 3. Disable translation lock and verify both are allowed
            running_service_actions["lock_translation_rotate"] = False
            mock_serial.input_queue.put(b">MOTION:10.0,0,0,5.0,0,0\n")
            msg3 = await asyncio.wait_for(ws.recv(), timeout=1.0)
            assert msg3 == "MOTION:10.0,0.0,0.0,5.0,0.0,0.0"

    loop.run_until_complete(run_lock_test())
