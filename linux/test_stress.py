#!/usr/bin/env python3
import asyncio
import os
import struct
import unittest
import sys
import time
import signal
import subprocess
from pathlib import Path
from importlib.machinery import SourceFileLoader

# Load the service module
service_path = Path(__file__).parent / "linapse-service"
linapse_service = SourceFileLoader("linapse_service", str(service_path)).load_module()

class TestAdversarialStress(unittest.TestCase):
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        linapse_service._loop = self.loop
        linapse_service._socket_clients.clear()
        self.socket_path = Path(f"/tmp/test_stress_spnav_{os.getuid()}.sock")
        if self.socket_path.exists():
            self.socket_path.unlink()

    def tearDown(self):
        if self.socket_path.exists():
            try:
                self.socket_path.unlink()
            except OSError:
                pass
        self.loop.close()

    def test_slow_client_concurrency_issue(self):
        """
        Test that sending many packets to a slow client does not cause RuntimeError.
        A slow client does not read from the stream, filling the buffer.
        """
        async def run_test():
            server = await asyncio.start_unix_server(
                linapse_service.handle_socket_client,
                path=str(self.socket_path)
            )
            
            # Connect client that reads nothing (slow client)
            reader, writer = await asyncio.open_unix_connection(str(self.socket_path))
            
            await asyncio.sleep(0.05)
            self.assertEqual(len(linapse_service._socket_clients), 1)
            
            # Send high-frequency packets to the slow client
            packet = struct.pack("iiiiiiii", 0, 1, 2, 3, 4, 5, 6, 10)
            
            # We want to check if multiple concurrent drain tasks throw exceptions.
            # We will catch any exceptions raised in the loop.
            exceptions = []
            
            def handle_exception(loop, context):
                exceptions.append(context.get("exception", context.get("message")))
            
            self.loop.set_exception_handler(handle_exception)
            
            # Broadcast multiple packets quickly
            for _ in range(5000):
                await linapse_service._broadcast_socket(packet)
                
            # Allow time for tasks to execute and potentially hit write timeouts or RuntimeError
            await asyncio.sleep(0.5)
            
            # Close connection
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
                
            server.close()
            await server.wait_closed()
            
            # Print any caught exceptions
            if exceptions:
                print(f"[DEBUG] Caught exceptions: {exceptions}")
                
            # We assert if there were any RuntimeErrors or other crashes
            # in the asyncio loop due to concurrent drain/writes.
            for exc in exceptions:
                if isinstance(exc, RuntimeError) and "concurrent" in str(exc).lower():
                    self.fail(f"Concurrent drain error detected: {exc}")

        self.loop.run_until_complete(run_test())

    def test_slow_client_dos_fast_client(self):
        """
        Verify that a slow socket client doesn't degrade performance for a fast client.
        We broadcast 5000 packets.
        """
        async def run_test():
            server = await asyncio.start_unix_server(
                linapse_service.handle_socket_client,
                path=str(self.socket_path)
            )
            
            # Connect slow client
            slow_reader, slow_writer = await asyncio.open_unix_connection(str(self.socket_path))
            
            # Connect fast client
            fast_reader, fast_writer = await asyncio.open_unix_connection(str(self.socket_path))
            
            await asyncio.sleep(0.05)
            self.assertEqual(len(linapse_service._socket_clients), 2)
            
            packet = struct.pack("iiiiiiii", 0, 1, 2, 3, 4, 5, 6, 10)
            
            # Start a task to read from fast client
            received = []
            async def read_fast():
                try:
                    while len(received) < 5000:
                        data = await fast_reader.readexactly(32)
                        received.append(data)
                except Exception as e:
                    print(f"Fast reader exception: {e}")
                    
            read_task = asyncio.create_task(read_fast())
            
            # Start broadcasting
            start_time = time.time()
            for _ in range(5000):
                await linapse_service._broadcast_socket(packet)
                
            # Wait for fast reader to finish or timeout
            try:
                await asyncio.wait_for(read_task, timeout=5.0)
            except asyncio.TimeoutError:
                pass
                
            duration = time.time() - start_time
            print(f"[DEBUG] Fast client received {len(received)}/5000 packets in {duration:.3f}s")
            
            # Close connections
            slow_writer.close()
            fast_writer.close()
            try:
                await slow_writer.wait_closed()
                await fast_writer.wait_closed()
            except Exception:
                pass
                
            server.close()
            await server.wait_closed()
            
            self.assertEqual(len(received), 5000, "Fast client did not receive all packets due to event loop block/drop!")
            self.assertLess(duration, 1.5, f"Fast client took too long: {duration:.3f}s")

        self.loop.run_until_complete(run_test())

    def test_invalid_serial_strings(self):
        """
        Test that malformed/invalid serial inputs do not crash the parsing pipeline
        or result in malformed packets.
        """
        # We will mock _broadcast_socket_from_thread and _broadcast_from_thread
        socket_packets = []
        ws_messages = []
        
        def mock_broadcast_socket_from_thread(packet):
            socket_packets.append(packet)
            
        def mock_broadcast_from_thread(msg):
            ws_messages.append(msg)
            
        orig_ws = linapse_service._broadcast_from_thread
        orig_sock = linapse_service._broadcast_socket_from_thread
        
        linapse_service._broadcast_from_thread = mock_broadcast_from_thread
        linapse_service._broadcast_socket_from_thread = mock_broadcast_socket_from_thread
        
        actions_ref = [{"taps": {"front:1": {"action": "none"}}, "buttons": {}, "button_override": False}]
        
        # Test inputs
        malformed_inputs = [
            ">MOTION:invalid,data,here",  # too few values
            ">MOTION:1.0,abc,3.0,4.0,5.0,6.0",  # invalid float
            ">MOTION:1.0,2.0,3.0,4.0,5.0,6.0,7.0",  # too many values
            "TAP:invalid_dir:1",  # unknown direction
            "TAP:front:abc",  # non-integer count
            "TAP:front",  # too few parts
            "",  # empty line
            ">",  # only command char
        ]
        
        try:
            for line in malformed_inputs:
                # Replicate the logic inside serial_thread for line processing
                line_stripped = line.strip()
                if not line_stripped:
                    continue
                if line_stripped.startswith("TAP:"):
                    parts = line_stripped.split(":")
                    if len(parts) == 3:
                        _, fw_dir, count_str = parts
                        human = linapse_service.DIR_MAP.get(fw_dir)
                        if human:
                            key = f"{human}:{count_str}"
                            act = actions_ref[0].get("taps", {}).get(key)
                            if act:
                                linapse_service.dispatch(act)
                            linapse_service._broadcast_from_thread(f"TAP:{human}:{count_str}")
                elif line_stripped.startswith(">MOTION:"):
                    linapse_service._broadcast_from_thread(line_stripped[1:])
                    try:
                        parts = line_stripped[8:].split(",")
                        if len(parts) == 6:
                            coords = [int(round(float(p))) for p in parts]
                            x, y, z, rx, ry, rz = coords
                            period = 10
                            packet = struct.pack("iiiiiiii", 0, x, z, y, rx, ry, rz, period)
                            linapse_service._broadcast_socket_from_thread(packet)
                    except Exception as e:
                        # Print error to show it was caught
                        pass
        finally:
            linapse_service._broadcast_from_thread = orig_ws
            linapse_service._broadcast_socket_from_thread = orig_sock
            
        # We expect no socket packets and no crashes.
        self.assertEqual(len(socket_packets), 0)

    def test_concurrent_connections(self):
        """
        Test that connecting 50 concurrent socket clients works and broadcasts packets to all.
        """
        async def run_test():
            server = await asyncio.start_unix_server(
                linapse_service.handle_socket_client,
                path=str(self.socket_path)
            )
            
            clients = []
            for _ in range(50):
                reader, writer = await asyncio.open_unix_connection(str(self.socket_path))
                clients.append((reader, writer))
                
            await asyncio.sleep(0.1)
            self.assertEqual(len(linapse_service._socket_clients), 50)
            
            # Broadcast packet
            packet = struct.pack("iiiiiiii", 0, 10, 20, 30, 40, 50, 60, 10)
            await linapse_service._broadcast_socket(packet)
            
            # Let readers read and verify
            for reader, writer in clients:
                data = await reader.readexactly(32)
                unpacked = struct.unpack("iiiiiiii", data)
                self.assertEqual(unpacked, (0, 10, 20, 30, 40, 50, 60, 10))
                
            # Close all clients
            for reader, writer in clients:
                writer.close()
                try:
                    await writer.wait_closed()
                except Exception:
                    pass
                    
            await asyncio.sleep(0.1)
            self.assertEqual(len(linapse_service._socket_clients), 0)
            
            server.close()
            await server.wait_closed()

        self.loop.run_until_complete(run_test())

    def test_sigint_cleanup(self):
        """
        Verify if the socket file is cleaned up when the process receives SIGINT.
        """
        test_sock = f"/tmp/test_sigint_{os.getuid()}.sock"
        if os.path.exists(test_sock):
            os.unlink(test_sock)

        # Code to execute the service in a subprocess
        code = f"""
import asyncio
import os
import sys
import time
from pathlib import Path
from importlib.machinery import SourceFileLoader

service_path = Path("linux/linapse-service")

# Subclass PosixPath to intercept spnav.sock
PosixPath = type(Path())
class PatchedPath(PosixPath):
    def __new__(cls, *args, **kwds):
        path_str = "/".join(str(a) for a in args)
        if "spnav.sock" in path_str:
            return PosixPath("/tmp/test_sigint_{os.getuid()}.sock")
        return PosixPath(*args, **kwds)

import importlib
import pathlib
pathlib.Path = PatchedPath

# Now load the module
linapse_service = SourceFileLoader("linapse_service", str(service_path)).load_module()
linapse_service.Path = PatchedPath
linapse_service.WS_PORT = 13006

# Run main
try:
    asyncio.run(linapse_service.main())
except KeyboardInterrupt:
    pass
"""
        # Start subprocess
        proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait a bit for the socket file to be created
        time.sleep(1.5)
        
        # Check if the socket file was created
        if not os.path.exists(test_sock):
            stdout_data, stderr_data = proc.communicate(timeout=1.0)
            self.fail(f"Socket file was not created by the service.\nSTDOUT:\n{stdout_data.decode()}\nSTDERR:\n{stderr_data.decode()}")
        
        # Send SIGINT to the subprocess
        proc.send_signal(signal.SIGINT)
        
        # Wait for the process to exit
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            
        # Check if the socket file was cleaned up (unlinked)
        socket_exists = os.path.exists(test_sock)
        if socket_exists:
            # Clean it up ourselves
            os.unlink(test_sock)
            
        self.assertFalse(socket_exists, "Socket file was NOT cleaned up on SIGINT!")

    def test_sigterm_cleanup(self):
        """
        Verify if the socket file is cleaned up when the process receives SIGTERM.
        This is an expected failure because the service doesn't handle SIGTERM signals.
        """
        test_sock = f"/tmp/test_sigterm_{os.getuid()}.sock"
        if os.path.exists(test_sock):
            os.unlink(test_sock)

        # Code to execute the service in a subprocess
        code = f"""
import asyncio
import os
import sys
import time
from pathlib import Path
from importlib.machinery import SourceFileLoader

service_path = Path("linux/linapse-service")

# Subclass PosixPath to intercept spnav.sock
PosixPath = type(Path())
class PatchedPath(PosixPath):
    def __new__(cls, *args, **kwds):
        path_str = "/".join(str(a) for a in args)
        if "spnav.sock" in path_str:
            return PosixPath("/tmp/test_sigterm_{os.getuid()}.sock")
        return PosixPath(*args, **kwds)

import importlib
import pathlib
pathlib.Path = PatchedPath

# Now load the module
linapse_service = SourceFileLoader("linapse_service", str(service_path)).load_module()
linapse_service.Path = PatchedPath
linapse_service.WS_PORT = 13007

# Run main
try:
    asyncio.run(linapse_service.main())
except KeyboardInterrupt:
    pass
"""
        # Start subprocess
        proc = subprocess.Popen([sys.executable, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Wait a bit for the socket file to be created
        time.sleep(1.5)
        
        # Check if the socket file was created
        if not os.path.exists(test_sock):
            stdout_data, stderr_data = proc.communicate(timeout=1.0)
            self.fail(f"Socket file was not created by the service.\nSTDOUT:\n{stdout_data.decode()}\nSTDERR:\n{stderr_data.decode()}")
        
        # Send SIGTERM to the subprocess
        proc.send_signal(signal.SIGTERM)
        
        # Wait for the process to exit
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            
        # Check if the socket file was cleaned up (unlinked)
        socket_exists = os.path.exists(test_sock)
        if socket_exists:
            # Clean it up ourselves
            os.unlink(test_sock)
            
        self.assertFalse(socket_exists, "Socket file was NOT cleaned up on SIGTERM!")

if __name__ == "__main__":
    unittest.main()
