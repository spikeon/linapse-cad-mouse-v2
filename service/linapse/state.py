import asyncio
import threading

# Version information
service_version = "2.9.8"
firmware_version = "unknown"

# Shared state variables
loop: asyncio.AbstractEventLoop = None
ws_clients: set = set()
socket_clients: set = set()
socket_clients_busy: set = set()
serial_queue: asyncio.Queue = None
ser_holder: list = [None]  # [serial.Serial | None]
actions_ref: list = [None]  # [dict | None]
config_lock = threading.Lock()
flashing_active = False
last_volume_change_time = 0.0

async def broadcast(msg: str):
    dead = set()
    for ws in list(ws_clients):
        try:
            await ws.send(msg)
        except Exception:
            dead.add(ws)
    ws_clients.difference_update(dead)

def broadcast_from_thread(msg: str):
    if loop:
        fut = asyncio.run_coroutine_threadsafe(broadcast(msg), loop)
        def cb(f):
            try:
                f.result()
            except Exception as e:
                print(f"[broadcast] exception: {e}", flush=True)
        fut.add_done_callback(cb)

async def broadcast_socket(packet: bytes):
    if not socket_clients:
        return
    for writer in list(socket_clients):
        try:
            if writer.is_closing():
                socket_clients.discard(writer)
                continue
            if writer.transport and writer.transport.get_write_buffer_size() > 65536:
                print(f"[sock] discarding slow client (buffer size={writer.transport.get_write_buffer_size()})")
                socket_clients.discard(writer)
                try:
                    writer.close()
                except Exception:
                    pass
                continue
            writer.write(packet)
        except Exception as e:
            print(f"[sock] write error: {e}")
            socket_clients.discard(writer)
            try:
                writer.close()
            except Exception:
                pass
    await asyncio.sleep(0)

def broadcast_socket_from_thread(packet: bytes):
    if loop:
        fut = asyncio.run_coroutine_threadsafe(broadcast_socket(packet), loop)
        def cb(f):
            try:
                f.result()
            except Exception as e:
                print(f"[broadcast_socket] exception: {e}", flush=True)
        fut.add_done_callback(cb)
