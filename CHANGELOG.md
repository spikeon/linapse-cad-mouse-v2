# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.1.7] - 2026-06-18

### Changed
- **Documentation**: Cited compatibility with OrcaSlicer instead of Bambu Studio/Bambu Slicer in README.md and docs/INTEGRATIONS.md, clarifying that official Linux builds of Bambu Studio do not compile with libspnav support.

## [2.1.6] - 2026-06-18

### Added
- **Dynamic Monkey-patching Proxy (`linapse-ws-proxy`)**: Introduced `linux/linapse-ws-proxy` to handle in-memory runtime patching of `spacenav-ws` (ignoring button events and auto-reconnecting) without modifying package cache folders.

### Removed
- **Fragile Patcher (`patch-spacenav-ws.py`)**: Deleted `linux/patch-spacenav-ws.py` which modified package files directly in the global `uv` cache.

### Changed
- **Systemd service configuration**: Updated `linux/systemd/spacenav-ws.service` to launch the local `linapse-ws-proxy` script via `uv run` instead of calling `uvx spacenav-ws` directly.
- **Installer and Tests updates**: Modified `linux/install.sh` to copy `linapse-ws-proxy` to user bin and remove the patching execution step. Cleaned up `linux/test_installer_mock.py` and `linux/test_installer_adversarial.py` to assert the presence of `linapse-ws-proxy` and remove obsolete patching checks.

## [2.1.5] - 2026-06-18

### Removed
- **Legacy button daemon**: Deleted the unused `linux/spnav-buttons` script and its systemd service file `linux/systemd/spnav-buttons.service`.
- **Legacy config file**: Deleted `linux/spnavrc` which was used by the uninstalled `spacenavd` daemon.

### Changed
- **Script refactoring**: Updated `linux/tap-calibrate.py` and `linux/tap-wobble.py` to tell users to stop `linapse-service` instead of the legacy `spnav-buttons` daemon to free up the serial port.
- **Documentation cleanup**: Rewrote `linux/README.md` to remove legacy mentions of `spnav-buttons` and `spnavrc` and reflect the modern `linapse-service` architecture.

## [2.1.4] - 2026-06-18

### Removed
- **Legacy status script**: Deleted the unused, outdated `linux/spacemouse-status` health check script.

## [2.1.3] - 2026-06-18

### Removed
- **VID/PID Comment lines**: Removed the commented-out `usb_vid` and `usb_pid` placeholder lines from `platformio.ini` entirely.
- **Outdated test assertions**: Deleted the corresponding mock test `test_platformio_ini_vid_pid_commented` checking for the commented-out lines from `linux/test_installer_mock.py`.

## [2.1.2] - 2026-06-18

### Security
- **USB VID/PID cleanup**: Replaced all hardcoded default 3Dconnexion SpaceMouse USB Vendor IDs and Product IDs (`256f` / `c635` / `256F` / `C635`) in code comments, test assertions, and status scripts with generic placeholders (`0xXXXX`, `0xYYYY`, `xxxx:yyyy`) to prevent publishing them.

## [2.1.1] - 2026-06-18

### Changed
- **Credits update**: Added credit to **lenkaiser** in README.md for their Kalman filter and sensitivity curves contribution in pull request #3 of the upstream repository.

## [2.1.0] - 2026-06-18

### Added
- **Systemd Environment variable setup (`SPNAV_SOCKET`)**: Automatically configures `~/.config/environment.d/99-spnav.conf` to expose the user-space socket path (`${XDG_RUNTIME_DIR}/spnav.sock`) to all native applications.
- **Support for SketchUp Web**: Expanded browser connector userscript matching patterns to support `https://*.sketchup.com/*` and `https://sketchup.com/*`.
- **Integrations Documentation**: Added a comprehensive setup and troubleshooting guide at `docs/INTEGRATIONS.md` covering 14 applications (Blender, FreeCAD, Maya, Unreal Engine, Unity, ZBrush, etc.).
- **Automatic installer updates**: Modified `linux/install.sh` and `setup.sh` to install environment files and check dependencies.

### Changed
- Renamed browser userscript from `linux/onshape-spacenav.user.js` to `linux/linapse-browser-connector.user.js`.

## [2.0.0] - 2026-06-18

- Initial baseline release of the fork for the Linapse CAD Mouse MK2 stack on Linux.
