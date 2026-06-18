# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.8] - 2026-06-18

### Fixed
- **Integration Tests**: Prevented unwritable directory and read-only file test execution errors when running as the `root` user in containerized CI environments. Also modified `tempfile.mkdtemp` to use local subdirectories under the repository in `test_installer_mock.py` and `test_installer_adversarial.py` to bypass `noexec` restriction on `/tmp`.
- **Systemd User Manager Environment**: Imported script `PATH` into the user-level systemd session manager inside `install.sh` to ensure `uv` is successfully located by the `spacenav-ws` service daemon.

## [2.2.7] - 2026-06-18

### Fixed
- **CI/CD Multi-Distro Workflow**: Switched Debian container image to use stable version tag `12` where `ydotool` is packaged, and configured `pytest` step inside Docker containers to pass `XDG_RUNTIME_DIR` and `DBUS_SESSION_BUS_ADDRESS` so that systemd user bus connections succeed.

## [2.2.6] - 2026-06-18

### Added
- **Features List**: Added a bullet-point features list to README.md highlighting key accomplishments of the Linapse stack.

## [2.2.5] - 2026-06-18

### Changed
- **Configurator Layout**: Replaced custom `carousel` blocks in README.md and docs/USAGE.md with standard Markdown headers and lists to prevent raw code blocks from displaying on GitHub.

## [2.2.4] - 2026-06-18

### Changed
- **Configurator Layout**: Swapped the main Customize Tab preview screenshot in README.md and docs/USAGE.md to a thinner aspect ratio screenshot (`configurator-customize-tap.png`) to prevent layout stretching.

## [2.2.3] - 2026-06-18

### Changed
- **Configurator Layout**: Replaced the squeezed Markdown table of configurator tabs in README.md with a full-width carousel to prevent image squishing and display larger previews.

## [2.2.2] - 2026-06-18

### Changed
- **Documentation Media**: Updated README.md and docs/USAGE.md to feature animated GIFs demonstrating the configurator's Lighting and Sensitivity features. Copied specific screen captures for Key Combo, Mouse Scroll, Tap & Mouse, and Macro configurations from Downloads and integrated them as an interactive carousel in docs/USAGE.md.

## [2.2.1] - 2026-06-18

### Added
- **Dynamic Tap Counts**: Added a Plus (`+`) button to the tap configuration panels in the web configurator, allowing users to add an arbitrary number of taps for any gesture direction. The configurator automatically scans loaded profiles to display expanded tap counts.

## [2.2.0] - 2026-06-18

### Added
- **Macro Step Card Configuration**: Redesigned the Macro configuration editor in the web configurator to display each step as a card containing the full action sub-form (e.g. key combo, mouse click chips, mouse scroll chips/amount, mouse move X/Y, exec command) and an embedded post-step delay field that defaults to 500ms.
- **Embedded Step Delay Support**: Updated the host service (`linapse-service`) macro dispatcher to support dispatching action steps and executing their embedded delay sequentially.

## [2.1.9] - 2026-06-18

### Fixed
- **CI/CD**: Fixed multiple distro container test jobs by switching debian image tag from `stable` to `latest`, starting `dbus` before running `loginctl`, and resolving the empty `$USER` variable issue when running `setup.sh`/`install.sh` non-interactively in docker.

## [2.1.8] - 2026-06-18

### Removed
- **Documentation**: Removed unsupported applications (TinkerCAD, ZBrush, 3ds Max, Twinmotion) from the integrations guide support matrix and detailed section lists.

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
