# Linapse — CAD Mouse MK2 (v2)

<!-- DISTRO_BADGES_START -->
[![Ubuntu](https://img.shields.io/badge/Ubuntu-failing-critical)](#) [![Debian](https://img.shields.io/badge/Debian-failing-critical)](#) [![Fedora](https://img.shields.io/badge/Fedora-failing-critical)](#)
<!-- DISTRO_BADGES_END -->

**Linapse** is a complete Linux software stack for the [CAD Mouse MK2](https://github.com/sb-ocr/cad-mouse-mk2) — a DIY 6-degrees-of-freedom "space mouse" that senses motion with three magnetic field sensors instead of optics. The hardware has no Linux driver from 3Dconnexion, so this project supplies everything needed to make it a first-class input device on Linux: device firmware, a host-side service, and a web configurator.

> This is an independent software fork focused on Linux support and the Linapse configurator. It is **not** intended to be merged back upstream. Hardware design, enclosure, PCB, and BOM live in the [original project](https://github.com/sb-ocr/cad-mouse-mk2).

---

## What it does

- **6DoF motion in OnShape, SketchUp Web, and Native Linux apps.** The firmware presents the device to the OS as a SpaceMouse, so `spacenavd` drives it. A WebSocket bridge plus a Tampermonkey userscript carry motion into browser apps (OnShape, SketchUp Web), while native apps (Blender, FreeCAD, OrcaSlicer, etc.) connect directly via UNIX socket.
- **Physical buttons, taps, and gestures.** The host service maps the two buttons (and tap-on-the-cap gestures detected in firmware) to keystrokes, clicks, scrolling, and macros via `ydotool` (Wayland-native input injection).
- **Addressable RGB lighting.** SK6812 LEDs with multiple effects (solid, breathing, motion-reactive, swirls) configured live.
- **Linapse web configurator.** A browser UI to remap buttons/taps, design lighting, and tune the motion filter — with a live 3D Benchy viewport you can push around with the puck to feel sensitivity changes in real time.

## The configurator

A single static web app with three tabs, talking to `linapse-service` over WebSocket and writing changes to the device live. Full walkthrough: **[docs/USAGE.md](docs/USAGE.md)**.

| Customize | Lighting | Sensitivity |
|-----------|----------|-------------|
| [![Customize tab](docs/images/configurator-customize.png)](docs/images/configurator-customize.png) | [![Lighting tab](docs/images/configurator-lighting.gif)](docs/images/configurator-lighting.gif) | [![Sensitivity tab](docs/images/configurator-sensitivity.gif)](docs/images/configurator-sensitivity.gif) |
| Remap the 2 buttons, the chord, and 5 cap-tap zones to keys, clicks, scrolls, commands, or macros. | Drive the SK6812 ring — solid, breathing, motion-reactive, swirl, gradient, rainbow — with live color and brightness. | Tune dead zones, the Kalman filter, and the response curve against a live 3D Benchy you push with the puck. |

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  CAD Mouse MK2  (Seeed XIAO RP2040 + 3× TLx493D magnetic sensors)  │
│  firmware/                                                         │
│   • 6DoF motion decode + Kalman filter + sensitivity curve         │
│   • tap detection, LED effect engine                               │
│   • USB HID (spoofed as a SpaceMouse)  +  serial telemetry/config  │
└───────────────┬───────────────────────────────┬──────────────────┘
                │ USB HID (6DoF)                 │ USB serial
                ▼                                ▼
        spacenavd                        linapse-service  (linux/)
        /var/run/spnav.sock              ws://localhost:13000
                │                          • owns the serial port
                ▼                          • dispatches buttons/taps → ydotool
        spacenav-ws  (ws :8181)           • broadcasts TAP / MOTION events
                │                          • reads/writes device config
                ▼                                ▲
        Web Apps (OnShape, SketchUp)             │ WebSocket
        (Tampermonkey userscript)                │
                                          Linapse configurator  (configurator/)
                                           • buttons / taps / lighting / sensitivity
                                           • live 3D Benchy motion test
```

Two independent paths share the device:
- **Motion** flows over USB HID → `spacenavd` → `spacenav-ws` → Web Apps (OnShape, SketchUp), or directly to native Linux apps (Blender, FreeCAD, Maya, etc.) via the UNIX socket.
- **Buttons, taps, lighting, and config** flow over USB serial ↔ `linapse-service` ↔ the configurator.

## Repository layout

| Path | What it is |
|------|------------|
| [`setup.sh`](setup.sh) | Top-level installer — packages, firmware (`--flash`), host integration, and configurator service. |
| [`firmware/`](firmware/) | RP2040 firmware (PlatformIO). Motion decode, filtering, tap detection, LED engine, USB HID + serial protocol. See [firmware/README.md](firmware/README.md) and [firmware/LED_COLOR_CONFIG.md](firmware/LED_COLOR_CONFIG.md). |
| [`linux/`](linux/) | Host-side integration: `install.sh`, `linapse-service` (serial ↔ WebSocket bridge), `spacenav-ws` patch, udev rules, systemd user units, OnShape userscript, tap calibration tools. See [linux/README.md](linux/README.md). |
| [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md) | Application integrations guide — how to setup, configure and verify all 14 supported and unsupported applications. |
| [`configurator/`](configurator/) | Linapse web configurator — a static web app (Three.js 3D viewport) that talks to `linapse-service` over WebSocket. |
| [`platformio.ini`](platformio.ini) | Firmware build configuration. |

## Quick start

### One-step setup

The top-level [`setup.sh`](setup.sh) orchestrates the whole stack: it installs the distro packages (`spacenavd`, `ydotool`, `uv`), runs the host integration, and installs a systemd user service that serves the configurator.

```bash
./setup.sh                 # packages + host integration + configurator service
./setup.sh --flash         # also build & flash the firmware first (needs PlatformIO)
./setup.sh --port 7890     # configurator port (default 7890)
./setup.sh --yes           # don't prompt before installing packages
```

It still leaves two inherently hands-on steps to you: flashing the firmware (the RP2040 must be physically put into BOOTSEL mode — `--flash` walks you through it) and installing the Tampermonkey userscript (browser extensions can't be scripted). The manual breakdown below documents each piece if you'd rather run them yourself.

### 1. Flash the firmware

The firmware spoofs its USB VID/PID to a 3Dconnexion SpaceMouse so `spacenavd` recognises it automatically. **You must supply the VID/PID yourself** — they are intentionally left blank in [`platformio.ini`](platformio.ini):

```ini
; board_build.arduino.earlephilhower.usb_vid = 0xXXXX
; board_build.arduino.earlephilhower.usb_pid = 0xYYYY
```

Uncomment and fill in the VID/PID of the SpaceMouse model you want to emulate, then build and flash:

```bash
pio run                       # build
# enter BOOTSEL: hold B, tap R on the XIAO RP2040 (or hold B while plugging in)
# copy .pio/build/seeed_xiao_rp2040/firmware.uf2 to the mounted RPI-RP2 drive
```

### 2. Install the Linux integration

```bash
cd linux
chmod +x install.sh
./install.sh
```

This installs `linapse-service`, enables the systemd user services (`ydotoold`, `spacenav-ws`, `linapse-service`), writes udev rules, and patches `spacenav-ws`. Full details, prerequisites, and troubleshooting are in **[linux/README.md](linux/README.md)**.

Then install the Tampermonkey userscript ([`linux/linapse-browser-connector.user.js`](linux/linapse-browser-connector.user.js)) and open OnShape or SketchUp Web. For setup instructions for native applications (Blender, FreeCAD, Maya, etc.) and game engines (Unreal, Unity), see **[docs/INTEGRATIONS.md](docs/INTEGRATIONS.md)**.

### 3. Open the configurator

The configurator is a static web app. Serve the `configurator/` directory with any static HTTP server and open it in a browser while `linapse-service` is running:

```bash
cd configurator
python3 -m http.server 7890
# then open http://localhost:7890
```

It connects to `linapse-service` at `ws://localhost:13000`. From there you can remap buttons and taps, design lighting, and tune the motion filter against the live 3D test viewport. See **[docs/USAGE.md](docs/USAGE.md)** for a tab-by-tab walkthrough.

## Tuning

- **Feel / gains / deadzones:** firmware defaults live in `firmware/include/Config.h` — see [firmware/README.md](firmware/README.md).
- **Live motion filter** (Kalman responsiveness/smoothness, dead zones, sensitivity curve): the configurator's Sensitivity tab, applied to the device over serial in real time.
- **spacenavd sensitivity:** `/etc/spnavrc` (installed by `install.sh`).

## Security note

The USB VID/PID used to emulate a SpaceMouse are **not** included in this repository — they are placeholders (`0xXXXX` / `0xYYYY`). Supply your own before flashing.

## Credits & license

Built on the open-source hardware and firmware of **[sb-ocr/cad-mouse-mk2](https://github.com/sb-ocr/cad-mouse-mk2)** by sb-ocr, incorporating the Kalman filter and sensitivity curves logic by **[lenkaiser](https://github.com/lenkaiser)** from pull request [sb-ocr/cad-mouse-mk2#3](https://github.com/sb-ocr/cad-mouse-mk2/pull/3). Hardware build guide: [Instructables](https://www.instructables.com/CAD-Mouse-MK2-a-6DoF-Space-Mouse-Using-Magnets).

Licensed under [CC BY-NC-SA 4.0][cc-by-nc-sa], matching the upstream project.

[![CC BY-NC-SA 4.0][cc-by-nc-sa-shield]][cc-by-nc-sa]

[cc-by-nc-sa]: http://creativecommons.org/licenses/by-nc-sa/4.0/
[cc-by-nc-sa-shield]: https://img.shields.io/badge/License-CC%20BY--NC--SA%204.0-lightgrey.svg
