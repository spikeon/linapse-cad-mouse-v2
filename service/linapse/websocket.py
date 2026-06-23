import asyncio
import json
import websockets
import websockets.exceptions
from . import state
from .config import save_actions
from .flashing import flash_device

async def ws_handler(websocket, actions_ref=None):
    request = getattr(websocket, "request", None)
    if request is not None:
        origin = request.headers.get("Origin")
    else:
        origin = getattr(websocket, "request_headers", {}).get("Origin")

    if origin:
        origin_lower = origin.lower()
        is_local = (
            "localhost" in origin_lower or
            "127.0.0.1" in origin_lower or
            origin_lower.startswith("file://") or
            origin_lower.startswith("chrome-extension://") or
            origin_lower == "null"
        )
        if not is_local:
            print(f"[ws] rejected connection from unauthorized origin: {origin}")
            await websocket.close(1008, "Unauthorized Origin")
            return

    state.ws_clients.add(websocket)
    print(f"[ws] client connected ({len(state.ws_clients)} total)")
    try:
        async for message in websocket:
            if message.startswith("actions "):
                ok = await asyncio.to_thread(save_actions, message[8:])
                await websocket.send("OK actions saved" if ok else "ERR actions save failed")
            elif message == "actions_get":
                await websocket.send("ACTIONS:" + json.dumps(state.actions_ref[0]))
            elif message == "volume_get":
                await websocket.send(f"VOLUME:{state.last_system_volume}")
            elif message == "eq_get":
                eq_str = ":".join(map(str, state.last_eq_levels))
                await websocket.send(f"EQ:{eq_str}")
            elif message == "version_get":
                await websocket.send(f"VERSION_INFO:{{\"service\":\"{state.service_version}\",\"firmware\":\"{state.firmware_version}\"}}")
                # Also send software update info if known
                if state.latest_software_version:
                    await websocket.send(f"SOFTWARE_UPDATE:available:{state.latest_software_version}:{state.software_update_url}")
                else:
                    await websocket.send(f"SOFTWARE_UPDATE:{state.software_update_status}")
            elif message == "software_update_check":
                from . import updater
                asyncio.create_task(asyncio.to_thread(updater.check_for_updates))
            elif message == "software_update_start":
                from . import updater
                asyncio.create_task(asyncio.to_thread(updater.download_and_install_update))
            elif message == "flash":
                if state.flashing_active:
                    await websocket.send("FLASH:error:Flash already in progress.")
                else:
                    asyncio.create_task(flash_device())
            else:
                await state.serial_queue.put(message)
    except websockets.exceptions.ConnectionClosed:
        pass
    finally:
        state.ws_clients.discard(websocket)
        print(f"[ws] client disconnected ({len(state.ws_clients)} total)")
