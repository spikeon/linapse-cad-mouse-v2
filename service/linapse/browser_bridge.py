"""OnShape / SketchUp Web browser bridge (vendored spacenav-ws + Linapse patches)."""

import asyncio
import logging
import os
from pathlib import Path

import uvicorn
from fastapi import WebSocket

import spacenav_ws.main
import spacenav_ws.spacenav
from spacenav_ws.controller import create_mouse_controller
from spacenav_ws.spacenav import get_async_spacenav_socket_reader
from spacenav_ws.wamp import WampSession

BROWSER_HOST = "127.51.68.120"
BROWSER_PORT = 8181


def spnav_socket_path() -> str:
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")
    return os.path.join(runtime_dir, "spnav.sock")


def configure_spnav_socket() -> str:
    path = spnav_socket_path()
    spacenav_ws.spacenav.SPACENAV_SOCKET_PATH = path
    logging.info("Browser bridge using spnav socket: %s", path)
    return path


def cert_paths() -> tuple[str, str]:
    pkg_dir = Path(__file__).resolve().parent.parent / "spacenav_ws" / "certs"
    return str(pkg_dir / "ip.crt"), str(pkg_dir / "ip.key")


async def nlproxy(ws: WebSocket):
    """WebSocket endpoint for browser CAD clients (OnShape / SketchUp Web)."""
    logging.info("Browser CAD client connected to nlproxy")
    wamp_session = WampSession(ws)
    socket_path = configure_spnav_socket()

    spacenav_reader = None
    for _ in range(5):
        try:
            spacenav_reader, _ = await get_async_spacenav_socket_reader()
            break
        except OSError:
            await asyncio.sleep(0.5)

    if spacenav_reader is None:
        spacenav_reader = asyncio.StreamReader()

    ctrl = await create_mouse_controller(wamp_session, spacenav_reader)

    async def mouse_with_reconnect():
        while True:
            try:
                if ctrl.reader.at_eof():
                    logging.info("Reconnecting browser bridge to spnav socket...")
                    reader, _ = await asyncio.open_unix_connection(socket_path)
                    ctrl.reader = reader
                    logging.info("Browser bridge reconnected to spnav socket")
                await ctrl.start_mouse_event_stream()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logging.warning("Browser bridge spnav error (%s), retrying in 1s...", exc)
                await asyncio.sleep(1)

    async with asyncio.TaskGroup() as tg:
        tg.create_task(mouse_with_reconnect(), name="mouse")
        tg.create_task(ctrl.wamp_state_handler.start_wamp_message_stream(), name="wamp")


def patch_app():
    configure_spnav_socket()
    app = spacenav_ws.main.app
    for route in app.routes:
        if getattr(route, "path", None) == "/" and hasattr(route, "endpoint"):
            route.endpoint = nlproxy
            logging.info("Patched spacenav-ws nlproxy endpoint for Linapse")
            break
    return app


async def serve(host: str = BROWSER_HOST, port: int = BROWSER_PORT):
    app = patch_app()
    cert_file, key_file = cert_paths()
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        ws="auto",
        ssl_certfile=cert_file,
        ssl_keyfile=key_file,
        log_level="info",
    )
    server = uvicorn.Server(config)
    logging.warning("Browser bridge listening on wss://%s:%s", host, port)
    await server.serve()


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(serve())
