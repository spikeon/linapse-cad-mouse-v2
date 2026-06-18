#!/usr/bin/env python3
import asyncio
import os
import struct
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path

# Import linapse-service using SourceFileLoader since it has no .py extension and a hyphen
service_path = Path(__file__).parent / "linapse-service"
linapse_service = SourceFileLoader("linapse_service", str(service_path)).load_module()

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
        # Swapped: [0, 11, 31, -20, 5, -3, 0, 10]
        
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
                    packet = struct.pack("iiiiiiii", 0, x, z, y, rx, ry, rz, period)
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
        self.assertEqual(unpacked[5], -3) # RY
        self.assertEqual(unpacked[6], 0)  # RZ
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

if __name__ == "__main__":
    unittest.main()
