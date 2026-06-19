#!/usr/bin/env python3
import asyncio
import os
import json
import time
import threading
import unittest
from pathlib import Path
from importlib.machinery import SourceFileLoader
import importlib.util

service_path = Path(__file__).parent / "linapse-service"
loader = SourceFileLoader("linapse_service", str(service_path))
spec = importlib.util.spec_from_loader("linapse_service", loader)
linapse_service = importlib.util.module_from_spec(spec)
loader.exec_module(linapse_service)

class TestModesAdversarial(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = Path("/tmp/linapse_test_modes")
        self.tmp_dir.mkdir(parents=True, exist_ok=True)
        self.actions_path = self.tmp_dir / "actions.json"
        
        # Save original path
        self.orig_actions_path = linapse_service.ACTIONS_PATH
        linapse_service.ACTIONS_PATH = self.actions_path
        
        self.orig_loop = linapse_service._loop
        linapse_service._loop = None
        
        self.orig_serial_queue = linapse_service._serial_queue
        linapse_service._serial_queue = None
        
        self.orig_socket_clients = list(linapse_service._socket_clients)
        linapse_service._socket_clients.clear()
        
        self.orig_ws_clients = list(linapse_service._ws_clients)
        linapse_service._ws_clients.clear()
        
        self.orig_actions_ref_val = linapse_service._actions_ref[0]
        
        self.initial_actions = {
            "current_mode": "Default",
            "modes": {
                "Default": {
                    "buttons": {"0": {"action": "scroll_down"}},
                    "taps": {"top:1": {"action": "none"}},
                    "led": {"effect": "solid", "color": "FFFFFF", "brightness": 128}
                },
                "CAD": {
                    "buttons": {"0": {"action": "none"}},
                    "taps": {},
                    "led": {"effect": "pulse", "color": "FF0000", "brightness": 255}
                }
            }
        }
        with open(self.actions_path, "w") as f:
            json.dump(self.initial_actions, f)
        linapse_service._actions_ref[0] = linapse_service.load_actions()

    def tearDown(self):
        linapse_service.ACTIONS_PATH = self.orig_actions_path
        linapse_service._loop = self.orig_loop
        linapse_service._serial_queue = self.orig_serial_queue
        linapse_service._socket_clients.clear()
        for c in self.orig_socket_clients:
            linapse_service._socket_clients.add(c)
        linapse_service._ws_clients.clear()
        for c in self.orig_ws_clients:
            linapse_service._ws_clients.add(c)
        linapse_service._actions_ref[0] = self.orig_actions_ref_val
        
        if self.actions_path.exists():
            self.actions_path.unlink()
        try:
            self.tmp_dir.rmdir()
        except OSError:
            pass

    def test_rapid_mode_switching_corruption_risk(self):
        corruption_detected = False
        orig_broadcast = linapse_service._broadcast_from_thread
        linapse_service._broadcast_from_thread = lambda msg: None
        num_iterations = 200
        
        def run_switch():
            for i in range(num_iterations):
                linapse_service.switch_mode("Default" if i % 2 == 0 else "CAD")
                time.sleep(0.001)
                
        def run_load():
            nonlocal corruption_detected
            for i in range(num_iterations):
                try:
                    act = linapse_service.load_actions()
                    if act and "modes" in act:
                        if "CAD" not in act["modes"]:
                            corruption_detected = True
                    else:
                        corruption_detected = True
                except Exception:
                    corruption_detected = True
                time.sleep(0.001)
                
        try:
            t1 = threading.Thread(target=run_switch)
            t2 = threading.Thread(target=run_load)
            t1.start()
            t2.start()
            t1.join()
            t2.join()
        finally:
            linapse_service._broadcast_from_thread = orig_broadcast
            
        with open(self.actions_path) as f:
            final_data = json.load(f)
        self.assertFalse(corruption_detected, "Corruption/wipeout detected!")
        self.assertIn("CAD", final_data.get("modes", {}))

    def test_corrupt_json_file_handling(self):
        with open(self.actions_path, "w") as f:
            f.write("[]")
        loaded_list = linapse_service.load_actions()
        try:
            res = linapse_service.get_active_mode_config(loaded_list, "buttons")
        except AttributeError:
            res = None
        self.assertIsNotNone(res, "Crashed on list input!")

if __name__ == "__main__":
    unittest.main()
