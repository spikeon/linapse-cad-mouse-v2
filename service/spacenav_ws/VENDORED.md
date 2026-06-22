Vendored from [RmStorm/spacenav-ws](https://github.com/RmStorm/spacenav-ws) v0.1.5 (GPL-3.0).

Linapse ships this code in-tree so browser CAD support does not depend on
`uv run --with spacenav-ws` or PyPI at install time. Local patches:

- `controller.py`: ignore button events (prevents view snap on button press)
- `browser_bridge.py` (in `linapse/`): dynamic spnav socket path and reconnect logic
