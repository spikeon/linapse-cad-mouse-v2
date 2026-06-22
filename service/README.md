# CAD Mouse MK2 — Linux Setup

This directory contains everything needed to get the CAD Mouse MK2 working on Linux, including full 6DoF motion in browser-based CAD and native applications.

## How it works

Linux has no official 3Dconnexion driver. The solution is a chain of open-source tools:

```
CAD Mouse MK2
    │  USB HID & Serial (Seeed XIAO RP2040)
    ▼
linapse-service    — bridges serial/HID inputs, translates buttons/taps via ydotool,
    │               and creates /run/user/<uid>/spnav.sock
    │
    ├─► Native Linux Apps (Blender, FreeCAD, etc.) — read spnav.sock via libspnav
    │
    └─► linapse-service — WebSocket bridge to browser apps (wss://127.51.68.120:8181)
            ▲
        Linapse Browser Connector (official extension)
            ▲
        Browser Apps (OnShape, SketchUp Web)
```

## Prerequisites

| Package | Notes |
|---------|-------|
| `ydotool` | Arch: `sudo pacman -S ydotool` |
| `python3` + pip | Browser bridge deps installed by `install.sh` (`fastapi`, `uvicorn`, `numpy`, `scipy`, `websockets`) |
| Browser | Install the [Linapse Browser Connector](../docs/BROWSER_EXTENSION.md) (Chrome, Edge, Firefox, Safari) |

## Firmware

Before running the installer, flash the firmware. You can do this easily from the **Firmware** tab in the **Linapse Configurator** UI (which compiles and flashes automatically), or manually:
1. Hold **B**, tap **R** on the XIAO RP2040 to enter BOOTSEL mode (or hold B while plugging in)
2. Build and copy the firmware: `pio run && sudo mount /dev/sdX1 /mnt && sudo cp .pio/build/seeed_xiao_rp2040/firmware.uf2 /mnt/ && sudo umount /mnt`

## Installation

```bash
cd service
chmod +x install.sh
./install.sh
```

The installer:
- Adds your user to the `input` group (needed for hidraw button access)
- Installs `linapse-service` to `~/.local/bin/`
- Installs and enables two systemd user services: `ydotoold`, `linapse-service` (includes the browser CAD bridge on port 8181)
- Configures `~/.config/environment.d/99-spnav.conf` so native apps find the user socket path automatically
- Installs udev rules so services restart automatically on plug/unplug
- Vendors the OnShape/SketchUp WebSocket protocol stack in `service/spacenav_ws/` (no external `spacenav-ws` PyPI package)

After the installer finishes, install the Linapse Browser Connector browser extension:

1. Install the Linapse Browser Connector from your browser's extension store (links printed at the end of install).
2. Open OnShape or SketchUp Web and open any document — motion should work immediately.

See **[docs/BROWSER_EXTENSION.md](../docs/BROWSER_EXTENSION.md)** for store links, enterprise policy install, and Safari build instructions.

For detailed setup, configuration, and verification guides for all 14 supported/experimental applications (including Blender, FreeCAD, Unreal Engine, Unity, etc.), see **[docs/INTEGRATIONS.md](../docs/INTEGRATIONS.md)**.

> **Note:** If you were just added to the `input` group, log out and back in (or reboot) before the buttons will work.

## Button mapping & Motion tuning

To change button maps, tap gestures, lighting, or motion tuning, use the **Linapse Configurator** (see `docs/USAGE.md` for details). 

Manual configuration is loaded from:
`~/.config/cad-mouse/actions.json`

If you modify configuration files manually, restart the service to apply changes:
```bash
systemctl --user restart linapse-service
```

## Troubleshooting

**Motion not working in Browser (OnShape / SketchUp)**
- Check the Linapse Browser Connector extension is enabled
- Check `linapse-service` is running: `systemctl --user status linapse-service`
- The browser bridge runs inside `linapse-service` at `wss://127.51.68.120:8181`

**Buttons not working**
- Ensure you're in the `input` group: `groups | grep input` (reboot if you just added yourself)
- Check the linapse-service logs: `journalctl --user -u linapse-service -f`
- Verify the hidraw device exists: `ls /dev/input/by-id/ | grep -i CAD_Mouse`

**Device not recognised after plugging in**
```bash
# Manually restart services
systemctl --user restart linapse-service
```

**Services hitting start-limit**
```bash
systemctl --user reset-failed linapse-service
systemctl --user restart linapse-service
```

