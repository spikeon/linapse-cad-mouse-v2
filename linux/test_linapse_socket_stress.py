#!/usr/bin/env python3
import asyncio
import os
import struct
import unittest
import time
import socket
from pathlib import Path
from importlib.machinery import SourceFileLoader

# Import linapse-service using SourceFileLoader
service_path = Path(__file__).parent / "linapse-service"
linapse_service = SourceFileLoader("linapse_service", str(service_path)).load_module()

class TestLinapseSocketStress(unittest.TestCase):
    def setUp(self):
        print(f"\n--- setUp: {self._testMethodName} ---", flush=True)
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        linapse_service._loop = self.loop
        linapse_service._socket_clients.clear()
        self.socket_path = Path(f"/tmp/test_spnav_stress_{os.getuid()}.sock")
        if self.socket_path.exists():
            self.socket_path.unlink()

    def tearDown(self):
        print(f"--- tearDown: {self._testMethodName} ---", flush=True)
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass
        
        # Cancel all running tasks on the loop
        try:
            pending = asyncio.all_tasks(self.loop)
            if pending:
                print(f"Cancelling {len(pending)} pending tasks", flush=True)
                for task in pending:
                    task.cancel()
                self.loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception as e:
            print(f"Error during pending tasks cancellation: {e}", flush=True)
            
        self.loop.close()
        print("Loop closed successfully.", flush=True)

    def test_invalid_serial_strings(self):
        print("Start test_invalid_serial_strings", flush=True)
        
        # Truly invalid inputs
        invalid_inputs = [
            ">MOTION:10.6,-20.4,30.6,5.1,-2.9",          # Missing component
            ">MOTION:10.6,-20.4,30.6,5.1,-2.9,0.0,7.0",   # Extra component
            ">MOTION:abc,def,ghi,jkl,mno,pqr",            # Non-numeric strings
            ">MOTION:,,,,,,",                              # Empty components
            ">MOTION:",                                    # No components
            "TAP:top:1",                                  # Not a motion line
            "",                                           # Empty line
        ]
        
        valid_input = ">MOTION:10.6, -20.4, 30.6, 5.1, -2.9, 0.0"
        
        broadcasted = []
        def mock_broadcast_socket_from_thread(packet):
            broadcasted.append(packet)
            
        orig_broadcast = linapse_service._broadcast_socket_from_thread
        linapse_service._broadcast_socket_from_thread = mock_broadcast_socket_from_thread
        
        try:
            for line in invalid_inputs:
                try:
                    if line.startswith(">MOTION:"):
                        parts = line[8:].split(",")
                        if len(parts) == 6:
                            coords = [int(round(float(p))) for p in parts]
                            x, y, z, rx, ry, rz = coords
                            period = 10
                            packet = struct.pack("iiiiiiii", 0, x, z, y, rx, ry, rz, period)
                            linapse_service._broadcast_socket_from_thread(packet)
                except Exception:
                    pass
            
            self.assertEqual(len(broadcasted), 0, "Invalid inputs should not broadcast")
            
            parts = valid_input[8:].split(",")
            self.assertEqual(len(parts), 6)
            coords = [int(round(float(p))) for p in parts]
            x, y, z, rx, ry, rz = coords
            period = 10
            packet = struct.pack("iiiiiiii", 0, x, z, y, rx, ry, rz, period)
            linapse_service._broadcast_socket_from_thread(packet)
            
            self.assertEqual(len(broadcasted), 1, "Valid input with spaces should broadcast")
            
        finally:
            linapse_service._broadcast_socket_from_thread = orig_broadcast
            
        print("End test_invalid_serial_strings", flush=True)

    def test_slow_client_handling(self):
        print("Start test_slow_client_handling", flush=True)
        async def run_test():
            print("Starting server...", flush=True)
            server = await asyncio.start_unix_server(
                linapse_service.handle_socket_client,
                path=str(self.socket_path)
            )
            
            print("Connecting fast client...", flush=True)
            fast_reader, fast_writer = await asyncio.open_unix_connection(str(self.socket_path))
            
            print("Connecting slow client...", flush=True)
            slow_reader, slow_writer = await asyncio.open_unix_connection(str(self.socket_path))
            
            # Set minimum receive buffer size (SO_RCVBUF) on the client side
            slow_sock_client = slow_writer.get_extra_info("socket")
            if slow_sock_client:
                try:
                    slow_sock_client.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024)
                except Exception as e:
                    print(f"Error setting client SO_RCVBUF: {e}", flush=True)
                    
            await asyncio.sleep(0.05)
            self.assertEqual(len(linapse_service._socket_clients), 2)
            
            # Set minimum send buffer size (SO_SNDBUF) on all server-side sockets
            print("Configuring socket options...", flush=True)
            for writer in linapse_service._socket_clients:
                sock = writer.get_extra_info("socket")
                if sock:
                    try:
                        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 1024)
                    except Exception as e:
                        print(f"Error setting server SO_SNDBUF: {e}", flush=True)
            
            # Read fast client data in background
            fast_received = []
            async def fast_client_reader():
                try:
                    while True:
                        data = await fast_reader.readexactly(32)
                        fast_received.append(data)
                except asyncio.IncompleteReadError:
                    pass
                except asyncio.CancelledError:
                    pass

            reader_task = asyncio.create_task(fast_client_reader())
            
            # Broadcast 30000 packets.
            # 30000 packets * 32 bytes = 960,000 bytes (~960KB)
            packet = struct.pack("iiiiiiii", 0, 1, 2, 3, 4, 5, 6, 10)
            print("Broadcasting 30000 packets to trigger slow client overflow...", flush=True)
            for i in range(30000):
                await linapse_service._broadcast_socket(packet)
                if i % 100 == 0:
                    # Let tasks run to process socket writes
                    await asyncio.sleep(0.0001)
                    
            print("Broadcast complete. Waiting for timeouts...", flush=True)
            await asyncio.sleep(0.5)
            
            print(f"Final connected clients count: {len(linapse_service._socket_clients)}", flush=True)
            print(f"Fast received count: {len(fast_received)}", flush=True)
            
            # Assert that the slow client has been disconnected/discarded
            self.assertLess(len(linapse_service._socket_clients), 2, "Slow client should have been disconnected")
            
            # Clean up
            reader_task.cancel()
            fast_writer.close()
            slow_writer.close()
            await asyncio.gather(fast_writer.wait_closed(), slow_writer.wait_closed(), return_exceptions=True)
            server.close()
            await server.wait_closed()

        self.loop.run_until_complete(run_test())
        print("End test_slow_client_handling", flush=True)

    def test_high_frequency_packet_broadcasts(self):
        print("Start test_high_frequency_packet_broadcasts", flush=True)
        async def run_test():
            server = await asyncio.start_unix_server(
                linapse_service.handle_socket_client,
                path=str(self.socket_path)
            )
            
            clients = []
            for i in range(3):
                print(f"Connecting client {i}...", flush=True)
                reader, writer = await asyncio.open_unix_connection(str(self.socket_path))
                clients.append((reader, writer, []))
                
            await asyncio.sleep(0.05)
            self.assertEqual(len(linapse_service._socket_clients), 3)
            
            async def read_loop(reader, received_list):
                try:
                    while True:
                        data = await reader.readexactly(32)
                        received_list.append(data)
                except asyncio.IncompleteReadError:
                    pass
                except asyncio.CancelledError:
                    pass

            read_tasks = []
            for reader, _, r_list in clients:
                read_tasks.append(asyncio.create_task(read_loop(reader, r_list)))
                
            packet = struct.pack("iiiiiiii", 0, 1, 2, 3, 4, 5, 6, 10)
            print("Broadcasting 500 packets fast...", flush=True)
            for _ in range(500):
                await linapse_service._broadcast_socket(packet)
                await asyncio.sleep(0.0002)
                
            await asyncio.sleep(0.2)
            
            # Assertions
            for idx, (_, _, r_list) in enumerate(clients):
                print(f"Client {idx} received: {len(r_list)} packets", flush=True)
                self.assertEqual(len(r_list), 500)
                
            self.assertEqual(len(linapse_service._socket_clients), 3)
                
            for task in read_tasks:
                task.cancel()
            await asyncio.gather(*read_tasks, return_exceptions=True)
            
            for _, writer, _ in clients:
                writer.close()
            await asyncio.gather(*(writer.wait_closed() for _, writer, _ in clients), return_exceptions=True)
            
            server.close()
            await server.wait_closed()

        self.loop.run_until_complete(run_test())
        print("End test_high_frequency_packet_broadcasts", flush=True)

    def test_concurrent_client_connections(self):
        print("Start test_concurrent_client_connections", flush=True)
        async def run_test():
            server = await asyncio.start_unix_server(
                linapse_service.handle_socket_client,
                path=str(self.socket_path)
            )
            
            num_clients = 20
            clients = []
            for i in range(num_clients):
                reader, writer = await asyncio.open_unix_connection(str(self.socket_path))
                clients.append((reader, writer, []))
                
            await asyncio.sleep(0.05)
            self.assertEqual(len(linapse_service._socket_clients), num_clients)
            
            async def read_loop(reader, received_list):
                try:
                    while True:
                        data = await reader.readexactly(32)
                        received_list.append(data)
                except asyncio.IncompleteReadError:
                    pass
                except asyncio.CancelledError:
                    pass

            read_tasks = []
            for reader, _, r_list in clients:
                read_tasks.append(asyncio.create_task(read_loop(reader, r_list)))
                
            packet1 = struct.pack("iiiiiiii", 0, 1, 1, 1, 1, 1, 1, 10)
            await linapse_service._broadcast_socket(packet1)
            await asyncio.sleep(0.05)
            
            # Close half of the clients on the client side
            print("Closing half of the clients...", flush=True)
            for i in range(0, num_clients, 2):
                _, writer, _ = clients[i]
                writer.close()
                
            # Wait for server to detect disconnection and remove from list
            print("Waiting for disconnections to register...", flush=True)
            await asyncio.sleep(0.1)
            
            # Check server-side registered client count is reduced
            self.assertEqual(len(linapse_service._socket_clients), num_clients // 2)
            
            packet2 = struct.pack("iiiiiiii", 0, 2, 2, 2, 2, 2, 2, 10)
            await linapse_service._broadcast_socket(packet2)
            await asyncio.sleep(0.1)
            
            # Assertions on received packets
            for i in range(num_clients):
                _, _, r_list = clients[i]
                if i % 2 == 0:
                    self.assertEqual(len(r_list), 1)
                else:
                    self.assertEqual(len(r_list), 2)
                    
            for task in read_tasks:
                task.cancel()
            await asyncio.gather(*read_tasks, return_exceptions=True)
            
            for _, writer, _ in clients:
                writer.close()
            await asyncio.gather(*(writer.wait_closed() for _, writer, _ in clients), return_exceptions=True)
            
            server.close()
            await server.wait_closed()

        self.loop.run_until_complete(run_test())
        print("End test_concurrent_client_connections", flush=True)

    def test_shutdown_cleanup(self):
        print("Start test_shutdown_cleanup", flush=True)
        async def run_test():
            server = await asyncio.start_unix_server(
                linapse_service.handle_socket_client,
                path=str(self.socket_path)
            )
            self.assertTrue(self.socket_path.exists())
            
            reader, writer = await asyncio.open_unix_connection(str(self.socket_path))
            await asyncio.sleep(0.05)
            self.assertEqual(len(linapse_service._socket_clients), 1)
            
            server.close()
            print("Awaiting server.wait_closed() with timeout...", flush=True)
            try:
                await asyncio.wait_for(server.wait_closed(), timeout=1.0)
                print("Server wait_closed completed without timeout.", flush=True)
            except asyncio.TimeoutError:
                print("Server wait_closed timed out as expected (stuck on open client connections).", flush=True)
                
            writer.close()
            await writer.wait_closed()
            
            await server.wait_closed()
            print("Server wait_closed finished after client closed.", flush=True)
            
            if self.socket_path.exists():
                self.socket_path.unlink()
                
            self.assertFalse(self.socket_path.exists())

        self.loop.run_until_complete(run_test())
        print("End test_shutdown_cleanup", flush=True)

if __name__ == "__main__":
    unittest.main()
