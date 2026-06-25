"""Tests for the in-tree browser CAD bridge."""

from pathlib import Path

SERVICE = Path(__file__).parent


def test_spacenav_ws_vendored():
    pkg = SERVICE / "spacenav_ws"
    assert (pkg / "main.py").exists()
    assert (pkg / "controller.py").exists()
    assert (pkg / "certs" / "ip.crt").exists()
    assert (pkg / "LICENSE").exists()


def test_browser_bridge_imports():
    from linapse import browser_bridge

    assert browser_bridge.BROWSER_PORT == 8181
    cert, key = browser_bridge.cert_paths()
    assert Path(cert).exists()
    assert Path(key).exists()


def test_controller_ignores_button_events():
    source = (SERVICE / "spacenav_ws" / "controller.py").read_text(encoding="utf-8")
    assert "isinstance(event, ButtonEvent)" in source
    assert "continue" in source


def test_patch_app_installs_linapse_ws_handler():
    """patch_app must put the Linapse nlproxy (with reconnect) on the WS '/'
    route, and leave the HTTP info/homepage routes intact."""
    from starlette.routing import WebSocketRoute
    from linapse import browser_bridge

    app = browser_bridge.patch_app()

    ws_root = [r for r in app.router.routes
               if getattr(r, "path", None) == "/" and isinstance(r, WebSocketRoute)]
    assert len(ws_root) == 1, "exactly one WebSocket '/' route expected"
    assert ws_root[0].endpoint is browser_bridge.nlproxy, "vanilla handler still bound"

    http_paths = {getattr(r, "path", None) for r in app.router.routes
                  if not isinstance(r, WebSocketRoute)}
    assert "/3dconnexion/nlproxy" in http_paths
    assert "/" in http_paths  # homepage GET survived


def test_wamp_stream_swallows_disconnect():
    source = (SERVICE / "spacenav_ws" / "wamp.py").read_text(encoding="utf-8")
    assert "except WebSocketDisconnect" in source
