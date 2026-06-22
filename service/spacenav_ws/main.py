import asyncio
import logging
import struct
from pathlib import Path

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse

from spacenav_ws.controller import create_mouse_controller
from spacenav_ws.spacenav import from_message, get_async_spacenav_socket_reader
from spacenav_ws.wamp import WampSession

logging.basicConfig(level="INFO", format="%(message)s")

ORIGINS = [
    "https://127.51.68.120",
    "https://127.51.68.120:8181",
    "https://3dconnexion.com",
    "https://cad.onshape.com",
]

CERT_FILE = Path(__file__).parent / "certs" / "ip.crt"
KEY_FILE = Path(__file__).parent / "certs" / "ip.key"

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS, allow_methods=["GET", "OPTIONS"], allow_headers=["*"])


@app.get("/3dconnexion/nlproxy")
async def get_info():
    """HTTP info endpoint for the 3Dconnexion client. Returns which port the WAMP bridge will use and its version."""
    return {"port": 8181, "version": "1.4.8.21486"}


@app.get("/")
def homepage():
    """Tiny bit of HTML that displays mouse movement data"""
    html = """
    <html>
        <body>
            <h1>Mouse Stream</h1>
            <p>Move your spacemouse and motion data should appear here!</p>
            <pre id="output"></pre>
            <script>
                const evtSource = new EventSource("/events");
                const maxLines = 30;
                const lines = [];

                evtSource.onmessage = function(event) {
                    lines.push(event.data);
                    if (lines.length > maxLines) {lines.shift()}
                    document.getElementById("output").textContent = lines.join("\\n");
                };
            </script>
        </body>
    </html>
    """
    return HTMLResponse(content=html, status_code=200)


async def get_mouse_event_generator():
    reader, _ = await get_async_spacenav_socket_reader()
    while True:
        mouse_event = await reader.readexactly(32)
        nums = struct.unpack("iiiiiiii", mouse_event)
        event_data = from_message(list(nums))
        yield f"data: {event_data}\n\n"  # <- SSE format


@app.get("/events")
async def event_stream():
    """Stream mouse motion data"""
    return StreamingResponse(get_mouse_event_generator(), media_type="text/event-stream")


@app.websocket("/")
async def nlproxy(ws: WebSocket):
    """Default endpoint; Linapse browser_bridge replaces this at runtime."""
    wamp_session = WampSession(ws)
    spacenav_reader, _ = await get_async_spacenav_socket_reader()
    ctrl = await create_mouse_controller(wamp_session, spacenav_reader)
    async with asyncio.TaskGroup() as tg:
        tg.create_task(ctrl.start_mouse_event_stream(), name="mouse")
        tg.create_task(ctrl.wamp_state_handler.start_wamp_message_stream(), name="wamp")
