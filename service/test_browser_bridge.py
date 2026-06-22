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
