#!/usr/bin/env python3
"""
Unit tests for cross-platform support in linapse-service (Milestone 2).
Verifies:
1. find_serial manual overrides and comports list scanning.
2. pynput keyboard/mouse input simulation.
3. Unix socket and signal handlers bypass on Windows/macOS.
"""

import sys
import unittest
from unittest.mock import MagicMock, patch
from pathlib import Path
from importlib.machinery import SourceFileLoader
import importlib.util

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

class TestCrossPlatform(unittest.TestCase):
    def setUp(self):
        # Backup original state
        self.orig_platform = sys.platform
        self.orig_pynput_kbd = linapse_service.pynput_keyboard
        self.orig_pynput_mse = linapse_service.pynput_mouse

    def tearDown(self):
        # Restore original state
        sys.platform = self.orig_platform
        linapse_service.pynput_keyboard = self.orig_pynput_kbd
        linapse_service.pynput_mouse = self.orig_pynput_mse

    def test_find_serial_manual_override(self):
        # 1. Test manual override using serial_port key
        actions_ref = [{"serial_port": "COM9"}]
        port = linapse_service.find_serial(actions_ref)
        self.assertEqual(port, "COM9")

        # 2. Test manual override using port key
        actions_ref = [{"port": "COM3"}]
        port = linapse_service.find_serial(actions_ref)
        self.assertEqual(port, "COM3")

    @patch("linapse_service.serial.tools.list_ports.comports")
    def test_find_serial_comport_scan(self, mock_comports):
        # Mock comports list returning multiple devices
        device_unrelated = MagicMock()
        device_unrelated.vid = 0x1234
        device_unrelated.description = "Unrelated USB Device"
        device_unrelated.product = "None"
        device_unrelated.device = "COM1"

        device_seeed_vid = MagicMock()
        device_seeed_vid.vid = 0x2886
        device_seeed_vid.description = "Some Seeed Device"
        device_seeed_vid.product = "None"
        device_seeed_vid.device = "COM5"

        mock_comports.return_value = [device_unrelated, device_seeed_vid]

        port = linapse_service.find_serial(None)
        self.assertEqual(port, "COM5")

        # Mock comport matching product string
        device_cad_mouse = MagicMock()
        device_cad_mouse.vid = 0x9999
        device_cad_mouse.description = "None"
        device_cad_mouse.product = "CAD_Mouse v2"
        device_cad_mouse.device = "COM6"

        mock_comports.return_value = [device_unrelated, device_cad_mouse]
        port = linapse_service.find_serial(None)
        self.assertEqual(port, "COM6")

    def test_pynput_keyboard_emulation(self):
        # Mock pynput controllers
        mock_kbd = MagicMock()
        linapse_service.pynput_keyboard = mock_kbd
        sys.platform = "win32"

        # Mock Key and KeyCode objects
        mock_key = MagicMock()
        linapse_service.Key = mock_key
        mock_key.ctrl = "ctrl_key"
        mock_key.page_up = "page_up_key"

        # Dispatch a key combo
        action = {"action": "key", "value": "ctrl+pageup"}
        linapse_service.dispatch(action)

        # Assert correct keys were pressed and released
        mock_kbd.press.assert_any_call("ctrl_key")
        mock_kbd.press.assert_any_call("page_up_key")
        mock_kbd.release.assert_any_call("ctrl_key")
        mock_kbd.release.assert_any_call("page_up_key")

    def test_pynput_mouse_emulation(self):
        # Mock pynput controller
        mock_mouse = MagicMock()
        linapse_service.pynput_mouse = mock_mouse
        sys.platform = "darwin"

        mock_button = MagicMock()
        linapse_service.Button = mock_button
        mock_button.left = "left_btn"

        # 1. Click
        action_click = {"action": "mouse_click", "button": "left"}
        linapse_service.dispatch(action_click)
        mock_mouse.click.assert_called_with("left_btn")

        # 2. Scroll up
        action_scroll = {"action": "mouse_scroll", "direction": "up", "amount": 5}
        linapse_service.dispatch(action_scroll)
        mock_mouse.scroll.assert_called_with(0, 5)

        # 3. Scroll down
        action_scroll_dn = {"action": "mouse_scroll", "direction": "down", "amount": 2}
        linapse_service.dispatch(action_scroll_dn)
        mock_mouse.scroll.assert_called_with(0, -2)

        # 4. Mouse Move
        action_move = {"action": "mouse_move", "x": 10, "y": -15}
        linapse_service.dispatch(action_move)
        mock_mouse.move.assert_called_with(10, -15)

    @patch("linapse.flashing.state")
    @patch("linapse.flashing.asyncio.create_subprocess_exec")
    @patch("linapse.flashing.find_repo_root")
    @patch("linapse.flashing.locate_or_mount_rpi_rp2")
    @patch("linapse.flashing.shutil.copy")
    def test_flash_device_custom_usb(self, mock_copy, mock_mount, mock_repo_root, mock_exec, mock_state):
        mock_repo_root.return_value = Path("/mock/repo")
        mock_mount.return_value = Path("/mock/mount")
        
        mock_process = MagicMock()
        mock_process.communicate = MagicMock()
        async def mock_communicate():
            return (b"stdout", b"stderr")
        mock_process.communicate.side_effect = mock_communicate
        mock_process.returncode = 0
        
        self.captured_env = {}
        async def mock_exec_coro(*args, **kwargs):
            self.captured_env = kwargs.get("env", {})
            return mock_process
        mock_exec.side_effect = mock_exec_coro
        
        mock_state.actions_ref = [{"custom_usb": {"enabled": True, "vid": "0x1234", "pid": "0x5678"}}]
        mock_state.flashing_active = False
        
        async def mock_broadcast(msg):
            pass
        mock_state.broadcast = mock_broadcast
        
        with patch("pathlib.Path.exists", return_value=True):
            import asyncio
            from linapse.flashing import flash_device
            asyncio.run(flash_device())
            
        self.assertEqual(self.captured_env.get("LINAPSE_USB_VID"), "0x1234")
        self.assertEqual(self.captured_env.get("LINAPSE_USB_PID"), "0x5678")

if __name__ == "__main__":
    unittest.main()
