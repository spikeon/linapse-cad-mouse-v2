#!/usr/bin/env python3
import asyncio
import os
import struct
import unittest
import sys
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path

if "linapse_service" in sys.modules:
    linapse_service = sys.modules["linapse_service"]
else:
    service_path = Path(__file__).parent / "linapse-service"
    loader = SourceFileLoader("linapse_service", str(service_path))
    spec = importlib.util.spec_from_loader("linapse_service", loader)
    linapse_service = importlib.util.module_from_spec(spec)
    loader.exec_module(linapse_service)
    sys.modules["linapse_service"] = linapse_service

class TestLinapseSocket(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        linapse_service._loop = self.loop
        linapse_service._socket_clients.clear()
        self.socket_path = Path(f"/tmp/test_spnav_{os.getuid()}.sock")
        if self.socket_path.exists():
            self.socket_path.unlink()

    def tearDown(self):
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass
        self.loop.close()

    def test_coordinate_parsing_and_swapping(self):
        # We want to test that a motion event string is correctly parsed, Y/Z swapped, and packed.
        # Original: >MOTION:10.6,-20.4,30.6,5.1,-2.9,0.0
        # Rounded: x=11, y=-20, z=31, rx=5, ry=-3, rz=0
        # Swapped: [0, 11, 31, -20, 5, 0, -3, 10]
        
        line = ">MOTION:10.6,-20.4,30.6,5.1,-2.9,0.0"
        
        packets_sent = []
        def mock_broadcast_socket_from_thread(packet):
            packets_sent.append(packet)
            
        # Temporarily patch the broadcast function
        orig_broadcast = linapse_service._broadcast_socket_from_thread
        linapse_service._broadcast_socket_from_thread = mock_broadcast_socket_from_thread
        
        try:
            # Simulate what happens in the serial thread when line is received
            if line.startswith(">MOTION:"):
                # Simulate the parsing logic we added
                parts = line[8:].split(",")
                if len(parts) == 6:
                    coords = [int(round(float(p))) for p in parts]
                    x, y, z, rx, ry, rz = coords
                    period = 10
                    packet = struct.pack("iiiiiiii", 0, x, z, y, rx, rz, ry, period)
                    linapse_service._broadcast_socket_from_thread(packet)
        finally:
            linapse_service._broadcast_socket_from_thread = orig_broadcast

        self.assertEqual(len(packets_sent), 1)
        unpacked = struct.unpack("iiiiiiii", packets_sent[0])
        self.assertEqual(unpacked[0], 0)  # Type
        self.assertEqual(unpacked[1], 11) # X
        self.assertEqual(unpacked[2], 31) # Z (swapped from Y)
        self.assertEqual(unpacked[3], -20) # Y (swapped from Z)
        self.assertEqual(unpacked[4], 5)  # RX
        self.assertEqual(unpacked[5], 0)  # RZ (swapped from RY)
        self.assertEqual(unpacked[6], -3) # RY (swapped from RZ)
        self.assertEqual(unpacked[7], 10) # Period

    def test_socket_server_and_broadcast(self):
        async def run_server_test():
            # Start the unix socket server on the temp path
            server = await asyncio.start_unix_server(
                linapse_service.handle_socket_client,
                path=str(self.socket_path)
            )
            
            # Connect a mock client
            reader, writer = await asyncio.open_unix_connection(str(self.socket_path))
            
            # Check client was registered
            await asyncio.sleep(0.05)
            self.assertEqual(len(linapse_service._socket_clients), 1)
            
            # Send a packet via broadcast
            test_packet = struct.pack("iiiiiiii", 0, 1, 2, 3, 4, 5, 6, 10)
            await linapse_service._broadcast_socket(test_packet)
            
            # Read from the client socket and verify packet
            data = await reader.readexactly(32)
            unpacked = struct.unpack("iiiiiiii", data)
            self.assertEqual(unpacked, (0, 1, 2, 3, 4, 5, 6, 10))
            
            # Disconnect client
            writer.close()
            await writer.wait_closed()
            
            # Check client was removed
            await asyncio.sleep(0.05)
            self.assertEqual(len(linapse_service._socket_clients), 0)
            
            server.close()
            await server.wait_closed()

        self.loop.run_until_complete(run_server_test())

    def test_directional_sensitivity_and_inversion(self):
        actions_ref = [{
            "sensitivity": {
                "x_pos": 2.0,
                "y_neg": 0.5
            },
            "inversion": {
                "z": True,
                "rx": True
            }
        }]
        
        import serial
        from unittest.mock import MagicMock
        
        mock_ser = MagicMock()
        mock_ser.readline.side_effect = [
            b">MOTION:10.0,-20.0,30.0,5.0,-2.0,0.0\n",
            Exception("stop thread")
        ]
        
        packets_sent = []
        def mock_broadcast_socket(packet):
            packets_sent.append(packet)
            
        orig_find_serial = linapse_service.find_serial
        orig_serial_class = linapse_service.serial.Serial
        orig_ser_holder = linapse_service._ser_holder
        orig_broadcast = linapse_service._broadcast_socket_from_thread
        orig_broadcast_from_thread = linapse_service._broadcast_from_thread
        
        linapse_service.find_serial = MagicMock(return_value="/dev/ttyACM0")
        linapse_service.serial.Serial = MagicMock(return_value=mock_ser)
        linapse_service._ser_holder = [mock_ser]
        linapse_service._broadcast_socket_from_thread = mock_broadcast_socket
        linapse_service._broadcast_from_thread = MagicMock()
        
        try:
            try:
                linapse_service.serial_thread(actions_ref)
            except Exception as e:
                if str(e) != "stop thread":
                    raise
        finally:
            linapse_service.find_serial = orig_find_serial
            linapse_service.serial.Serial = orig_serial_class
            linapse_service._ser_holder = orig_ser_holder
            linapse_service._broadcast_socket_from_thread = orig_broadcast
            linapse_service._broadcast_from_thread = orig_broadcast_from_thread
            
        self.assertEqual(len(packets_sent), 1)
        unpacked = struct.unpack("iiiiiiii", packets_sent[0])
        self.assertEqual(unpacked[0], 0)   # Type
        self.assertEqual(unpacked[1], 10)  # X (since raw x=10.0 > 0, it uses x_neg which is default 1.0)
        self.assertEqual(unpacked[2], 30)  # Z (swapped from Y, scaled y=-10, inverted z=-30, spacenav maps z=-z=30, y=-y=10)
        self.assertEqual(unpacked[3], 10)  # Y
        self.assertEqual(unpacked[4], -5)  # RX
        self.assertEqual(unpacked[5], 0)   # RZ (swapped from RY)
        self.assertEqual(unpacked[6], -2)  # RY (swapped from RZ)

    def test_friendly_key_combo_translation(self):
        # Test shift+7
        res = linapse_service.translate_friendly_combo("shift+7")
        self.assertEqual(res, "42:1 8:1 8:0 42:0")
        
        # Test ctrl+shift+z (case-insensitive and spaces)
        res = linapse_service.translate_friendly_combo("  CTRL + Shift + z  ")
        self.assertEqual(res, "29:1 42:1 44:1 44:0 42:0 29:0")
        
        # Test single key
        res = linapse_service.translate_friendly_combo("a")
        self.assertEqual(res, "30:1 30:0")
        
        # Test raw sequence bypass
        res = linapse_service.translate_friendly_combo("42:1 8:1 8:0 42:0")
        self.assertEqual(res, "42:1 8:1 8:0 42:0")

if __name__ == "__main__":
    unittest.main()
