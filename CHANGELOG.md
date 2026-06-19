# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.6.10] - 2026-06-19

### Changed
- **Metadata and Badges**: Corrected Debian build badge manually to passing and bumped version metadata across repository files.

## [2.6.9] - 2026-06-19

### Changed
- **CI/CD Debugging Enhancement**: Extended workflow to output pytest logs for Linux matrix runs (Ubuntu, Debian, Fedora) and download/commit all distro failure logs to `ci_logs/` for easy local retrieval.

## [2.6.8] - 2026-06-19

### Fixed
- **Windows Test Collection**: Fixed secondary `geteuid` AttributeError crash on Windows in `test_installer_adversarial.py` (line 125).

## [2.6.7] - 2026-06-19

### Fixed
- **Windows Test Collection**: Resolved AttributeError crashes during test collection on Windows by checking for the presence of `os.getuid` before defining `YDOTOOL_SOCKET` in `linapse-service` and using `getattr(os, "geteuid", ...)` in `test_installer_adversarial.py`.

## [2.6.6] - 2026-06-19

### Added
- **Square App Logo**: Integrated the new `linapse-square-logo.png` square logo for system shortcuts, application menu items, and installers.
- **Shortcut Icon Update**: Updated the Linux launcher `.desktop` template to use the square logo icon.
- **Electron Build Icon**: Configured `electron-builder` and window instantiation to bundle and display the new square logo icon instead of the wide header logo.

## [2.6.5] - 2026-06-19

### Changed
- **CI/CD Debugging**: Updated GitHub Actions `multi-distro-test.yml` workflow to write Windows pytest output to `pytest_output.txt` and upload it on failure as an artifact to assist in debugging test failures.

## [2.6.4] - 2026-06-19

### Added
- **Axis Inversion E2E Tests**: Added comprehensive Playwright tests in [test_playwright_benchy.py](file:///home/spikeon/Dev/linapse-cad-mouse-v2/linux/test_playwright_benchy.py) to test axis inversions (X, Z, RX, RY, RZ, Y) under both positive and negative movement signals.
- **Direction and Magnitude Verification**: Enabled verification that visual movements in the 3D Benchy viewport are in the correct and opposite directions when inversions are active, confirming movement with a strict sign multiplication check and magnitude threshold.
- **Disk Sync Validation**: Added automated assertions verifying that toggling axis inversions in the configurator UI correctly updates and persists settings to `actions.json` on the disk.

## [2.6.3] - 2026-06-19

### Fixed
- **3D Benchy Initial Profile Setup**: Excluded live device inversions from the initial layout pass rotation in the web configurator. This prevents the 3D Benchy model from loading upside down when rotation inversions (such as `rx` or `rz`) are enabled by default.

## [2.6.2] - 2026-06-19

### Fixed
- **3D Benchy Axis Inversion**: Updated the 3D Benchy rendering logic in the web configurator to correctly apply axis inversion settings (`actions.inversion`) to translations and rotations.
- **CI Dependency Fix**: Added `pyyaml` to the list of Python dependencies installed in container, Windows, and macOS GHA runners. This fixes the `ModuleNotFoundError` crash during the CI run.

## [2.6.1] - 2026-06-19

### Added
- **Start Menu / App Launcher Shortcuts**:
  - Integrated `linapse-configurator.desktop` generator for Linux to add the Electron configurator to the applications/start menu.
  - Added Start Menu shortcut configuration to `installer.iss` for the Windows service executable.
  - Configured explicit NSIS Start Menu and Desktop shortcut options in `configurator/package.json` for the Electron Windows builder.

## [2.6.0] - 2026-06-19

### Added
- **Electron Webapp Wrapper**: Added a cross-platform Electron shell container for the web configurator located in `configurator/`.
- **Auto-Updater Integration**: Configured `electron-updater` targeting GitHub releases (`spikeon/linapse-cad-mouse-v2`) for seamless, serverless background updates.

## [2.5.10] - 2026-06-19

### Fixed
- **Pynput Headless Environment Robustness**: Caught all generic exceptions when importing/initializing `pynput` inside `linux/linapse-service` on Windows and macOS. This prevents startup and test compilation crashes in headless/CI runner environments where Accessibility permissions or display hooks are unavailable.

## [2.5.9] - 2026-06-19

### Added
- **README Banner Logo**: Added transparent brand banner `linapse-banner-transparent.png` to the top of `README.md`.

## [2.5.8] - 2026-06-19

### Added
- **UI Header Logo**: Integrated the official `linapse-header-logo.png` logo image into the web configurator titlebar, replacing the text brand.

## [2.5.7] - 2026-06-19

### Added
- **Installer Badges**: Added installer badges/shields to `README.md` for Windows (`LinapseServiceSetup.exe`) and macOS (`linapse-service.pkg`) that dynamically link to the latest release downloads.

## [2.5.6] - 2026-06-19

### Changed
- **Documentation**: Updated `README.md` to document cross-platform compatibility for Windows, macOS, and Linux, and updated structural descriptions to reflect the multi-OS features.

## [2.5.5] - 2026-06-19

### Fixed
- **Playwright Test Host Isolation**: Mocked `subprocess.Popen` in `linux/test_playwright_benchy.py` to prevent real commands (like `ydotool`) from executing on the host machine. This fixes the issue where running tests spawned an empty terminal window (via `ctrl+alt+t` keyboard emulation).
- **Daemon Thread Teardown**: Implemented custom thread tracking and clean shutdown mechanism in the Playwright test suite to prevent background daemon threads (`serial_thread`, `config_watcher`, etc.) from leaking and polluting other tests in the suite.

## [2.5.4] - 2026-06-19

### Added
- **UI Toast Notification E2E Tests**: Extended Playwright test suite in `linux/test_playwright_benchy.py` to simulate tap gestures and physical button clicks, verifying that click and tap toast messages show up in the browser with correct title and content tags.

## [2.5.3] - 2026-06-19

### Added
- **Benchy 3D Viewport Playwright Tests**: Added browser-based automated testing using Playwright (`linux/test_playwright_benchy.py`) to verify that motion signals received by the configurator move the 3D Benchy model in the correct directions for all 6 DoF axes.
- **Workflow Playwright Configuration**: Updated `.github/workflows/multi-distro-test.yml` to install `playwright` and Chromium binaries inside GHA runners on Windows and macOS.

## [2.5.2] - 2026-06-19

### Added
- **Multi-OS CI/CD Test Environments**: Configured native Windows (`windows-latest`) and macOS (`macos-latest`) CI runners to execute the Pytest test suite prior to compilation.
- **Cross-Platform Test Filtering**: Created `linux/conftest.py` to dynamically discover and skip Linux-only systemd, udev, and unix socket tests when running on Windows and macOS, enabling cross-platform automated test suites.

## [2.5.1] - 2026-06-19

### Added
- **Packaging and CI/CD**: Added Inno Setup script `installer.iss` for Windows packaging and installer.
- **Workflow Automation**: Updated `.github/workflows/multi-distro-test.yml` with automated Windows and macOS compilation and packaging jobs, compiling executables via PyInstaller, updating version dynamically, and uploading setup/package artifacts.

## [2.5.0] - 2026-06-19


### Added
- **Cross-Platform Support**: Added compatibility for Windows and macOS to `linapse-service`.
- **Modular Input Backend**: Integrated conditional `pynput` input simulation for key combos, mouse clicks, mouse scrolls, and mouse moves on Windows and macOS.
- **Enhanced Serial Auto-Discovery**: Added `serial.tools.list_ports` scanning to match Seeed Studio serial ports by USB Vendor ID `0x2886` or product/description descriptions ("Seeed", "CAD Mouse", or "CAD_Mouse") on all platforms, fallback to glob-based scanning on Linux.
- **Manual Port Override**: Added support for `serial_port` or `port` configuration keys in `actions.json` for manual serial port specification.

### Changed
- **OS Guards**: Wrapped Linux-only Unix socket servers, udev/hidraw candidacy checks, and signal handlers in platform guards to prevent crashes on Windows and macOS.

## [2.4.2] - 2026-06-19

### Changed
- **New Project Defaults**: Pulled user's local `actions.json` settings (modes, buttons, taps, sensitivities, inversions, and active mode 'Browser') into the project as the new default configuration in `configurator/index.html` and `linapse-service`.
- **Documentation**: Added documentation and screenshots for profiles/modes, active mode selector dropdown, multi-click physical buttons, and media action settings in `README.md` and `docs/USAGE.md`.

## [2.4.1] - 2026-06-19

### Fixed
- **NameError in Tests**: Fixed missing `sys` module imports in `test_linapse_socket.py`, `test_linapse_socket_stress.py`, `test_m1_adversarial_bugfix.py`, and `test_m5_adversarial.py`.
- **Socket Buffer DOS Protection**: Replaced task-spawning drain loop with synchronous writes and a 64KB buffer-size limit check in `_broadcast_socket`, preventing event loop starvation.
- **Asyncio Sleep Yield**: Added `await asyncio.sleep(0)` yield point to socket broadcasting to ensure other asyncio tasks run under high frequency.
- **Teardown Thread Leaks**: Updated `started_threads` matching in `custom_init` to filter out internal `asyncio` loop threads, ensuring teardown only waits on daemon threads from `linapse-service`.
- **Mock Pollution**: Fixed global mock contamination by using `monkeypatch.setattr` in `test_multi_click.py`.

## [2.4.0] - 2026-06-19

### Added
- **Multi-Click Buttons**: Added support for double/multi-click configuration (e.g. `1×`, `2×`, `3×`+) for physical buttons. High-precision click counting with a 250ms press window, falling back to legacy single key mapping seamlessly and preserving zero-latency for standard scrolls.
- **Media Action Type**: Added a new action type `"media"` supporting *Play, Pause, Forward, Back, Fast Forward, Rewind, Mute, Volume Up, Volume Down* commands mapped to system keys via `ydotool`.
- **Discrete Media Keycodes**: Integrated keycodes for play (207), pause (201), and mute (113) into ydotool mappings.

### Changed
- **Inverted Volume Controls**: Inverted the volume controls for Media Mode so pushing the puck forward increases the volume and pulling it back decreases the volume.

## [2.3.7] - 2026-06-18

### Fixed
- **Accumulator Poisoning**: Sanitized 6DoF motion coordinates by replacing non-finite values (NaN and Inf) with `0.0` in the serial thread parser.
- **Robustness**: Updated test cases to verify that non-finite values do not poison the accumulators and that subsequent finite values are processed normally.

## [2.3.6] - 2026-06-18

### Added
- **Adversarial M3 Tests**: Added a dedicated test suite (`linux/test_m3_adversarial.py`) to stress-test specialized Browser and Media modes suppression, button mapping combos, and boundary coordinate accumulator stability.

## [2.3.5] - 2026-06-18

### Added
- **Browser and Media Modes**: Implemented Browser and Media modes in host service with custom accumulators for scrolls, scrub, and volume, bypassing raw motion/socket broadcasts.
- **Media Keys Support**: Added media/volume key codes ("volup", "voldown", "next", "prev", "playpause") to _KEY_CODES.

## [2.3.4] - 2026-06-18

### Added
- **Configurator UI Integration Tests**: Added a headless VM-based mock DOM test suite (`linux/test_configurator_gui.js`) to verify script parser initialization, nested mode structure migration, dynamic mode creation/renaming/deletion prompts, action selector collection, and profile save/load routines in `configurator/index.html`.

## [2.3.3] - 2026-06-18

### Added
- **Modes Configurator UI**: Implemented nested mode structure support with `getActiveMode` utility and dynamic configuration migration.
- **Mode Management UI**: Added Mode Selector Bar dropdown and New Mode, Rename, Delete control actions saving to backend.
- **Mode Action Type**: Added `mode` type to action list, render sub-fields with mode dropdown, and collect selected mode.
- **Lighting UI Integration**: Sync active lighting settings to/from the active mode configuration in real-time.

## [2.3.2] - 2026-06-18

### Fixed
- **Adversarial Tests warnings**: Fixed `ResourceWarning` leaks (unclosed subprocess pipes and un-awaited subprocesses) in `test_sigint_cleanup` and `test_sigterm_cleanup` inside `linux/test_stress.py`.

## [2.3.1] - 2026-06-18

### Fixed
- **Configuration Erasure & Truncation**: Implemented atomic configuration file saving using a temporary file and `os.replace` to prevent truncation race conditions.
- **Save Fail-safe**: Added thread-safety with `_config_lock` and implemented fallback to in-memory configuration when file is corrupted, preventing loading defaults.
- **JSON Validation**: Added dictionary type validation to prevent AttributeError crashes on invalid JSON layouts.
- **Asyncio Event Loop Responsiveness**: Moved synchronous file writing operations to a separate thread in the WebSocket handler using `asyncio.to_thread`.
- **Pytest Coroutine Warning**: Fixed coroutine warning in `test_directional_sensitivity_and_inversion` by mocking the broadcast helper correctly.

## [2.3.0] - 2026-06-18

### Added
- **Backend Modes Feature**: Added support for backend configuration modes. Legacy root-level `buttons` and `taps` configurations are automatically migrated to a modes structure under a `"Default"` mode.
- **Mode Switching Action**: Added `"mode"` action inside `dispatch` to transition between profiles thread-safely.
- **Serial Connection Sync**: Sends the active mode's LED settings (effect, color, brightness) to the device on serial thread startup.
- **Integration Tests**: Added tests in `linux/test_signal_integration.py` covering migration, mode switching, LED serial command transmission, WS broadcasting, and robustness.

## [2.2.9] - 2026-06-18

### Changed
- **Documentation**: Updated the top-level README.md architecture diagram and description to reflect that the system-wide `spacenavd` daemon is not used, and that `linapse-service` manages inputs directly (reading 6DoF motion coordinates over USB serial telemetry and button status over USB HID).
- **Documentation**: Removed obsolete SpaceMouse USB VID/PID hardware spoofing instructions and "Security note" from README.md.
- **Documentation**: Updated `setup.sh` comments and `firmware/README.md` to remove outdated references to `spacenavd` package installation and hardware spoofing configurations.
- **Configuration**: Updated `platformio.ini` USB comments to reflect the correct usage of the USB product name `CAD Mouse MK2` for local identification.

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
