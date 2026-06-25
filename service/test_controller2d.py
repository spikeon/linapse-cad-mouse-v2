"""Regression: loading a config without the 2D controller block migrates in
controller2d (per-axis horizontal/vertical sens + invert) and controller_view."""
import json

import linapse.config as config
import linapse.state as state


def test_migration_adds_controller2d_and_view(tmp_path, monkeypatch):
    p = tmp_path / "actions.json"
    p.write_text(json.dumps({"current_mode": "Default", "modes": {"Default": {}}}))
    monkeypatch.setattr(config, "ACTIONS_PATH", p)
    monkeypatch.setattr(state, "broadcast_from_thread", lambda *a, **k: None)

    actions = config.load_actions()

    assert actions["controller2d"]["sensitivity"] == {"horizontal": 1.0, "vertical": 1.0}
    assert actions["controller2d"]["invert"] == {"horizontal": False, "vertical": True}
    assert actions["controller_view"] == "3d"
