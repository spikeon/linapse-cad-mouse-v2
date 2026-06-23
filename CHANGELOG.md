# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.21.28] - 2026-06-23

### Fixed
- **Release Automation**: Corrected Launchpad PPA dput directory path format to username/ppa-name/ubuntu/.

## [2.21.27] - 2026-06-23

### Fixed
- **Release Automation**: Removed trailing slash from Launchpad incoming path and set passive_ftp explicitly in dput configuration.

## [2.21.26] - 2026-06-23

### Fixed
- **Release Automation**: Configure ~/.devscripts and debsign command-line -p parameter to ensure the custom GPG wrapper script is invoked, and add execution logging.

## [2.21.25] - 2026-06-23

### Fixed
- **Release Automation**: Expanded absolute path for GPG passphrase file during wrapper script generation and integrated passphrase diagnostics logging.

## [2.21.24] - 2026-06-23

### Fixed
- **Release Automation**: Fixed newline appending bug in gpg-agent.conf and migrated debsign signing invocation to DEBSIGN_PROGRAM environment variable.

## [2.21.23] - 2026-06-23

### Fixed
- **Release Automation**: Transitioned to --passphrase-file configuration in GPG wrapper script and resolved Git push race condition in failure log uploading step.

## [2.21.22] - 2026-06-23

### Fixed
- **Testing**: Increased Playwright page reload timeout in test state reset to 60000ms to resolve flaky timeouts on Windows runners.

## [2.21.21] - 2026-06-23

### Added
- **Release Automation**: Integrated GPG_PASSPHRASE into crazy-max/ghaction-import-gpg and GPG wrapper script configurations.

## [2.21.20] - 2026-06-23

### Added
- **Release Automation**: Added GPG diagnostics generation and transitioned to gpgconf --kill all in Ubuntu PPA release workflow step.

## [2.21.19] - 2026-06-23

### Added
- **Release Automation**: Added debuild/debsign/dput logging and automatic failure log commit/push step to help debug Ubuntu PPA release pipeline.

## [2.21.18] - 2026-06-23

### Fixed
- **Release Automation**: Fixed Ubuntu PPA GPG signing failures under GNUPGHOME isolation by writing GPG config to the dynamic GPG directory.

## [2.21.17] - 2026-06-23

### Fixed
- **Release Automation**: Fixed Ubuntu PPA signing by enabling GPG agent loopback mode configuration.

## [2.21.16] - 2026-06-23

### Fixed
- **Release Automation**: Fixed Ubuntu PPA signing by utilizing a loopback GPG wrapper script combined with ghaction-import-gpg.

## [2.21.15] - 2026-06-23

### Fixed
- **Release Automation**: Fixed Ubuntu PPA signing by specifying GPG loopback mode parameters in debsign invocation.

## [2.21.14] - 2026-06-23

### Fixed
- **Release Automation**: Fixed Ubuntu PPA signing by forcing GPG to use loopback mode non-interactively in client configuration.

## [2.21.13] - 2026-06-23

### Fixed
- **Release Automation**: Fixed Ubuntu PPA signing by using official `crazy-max/ghaction-import-gpg` GitHub Action.

## [2.21.12] - 2026-06-23

### Fixed
- **Release Automation**: Fixed Ubuntu PPA signing by using a GPG wrapper script that pipes empty passphrase to stdin.

## [2.21.11] - 2026-06-23

### Fixed
- **Release Automation**: Fixed Ubuntu PPA signing by using a GPG wrapper script to avoid passphrase-fd exhaustion and shell escaping errors.

## [2.21.10] - 2026-06-23

### Fixed
- **Release Automation**: Passed empty passphrase to GPG via standard input and --passphrase-fd 0 for non-interactive Ubuntu PPA signing.

## [2.21.9] - 2026-06-23

### Fixed
- **Release Automation**: Split debuild package building and signing into separate commands to properly parse loopback GPG parameters, and limited COPR build target chroots to compatible systems.

## [2.21.8] - 2026-06-23

### Fixed
- **Release Automation**: Fixed GPG signing command invocation parsing by debuild.

## [2.21.7] - 2026-06-23

### Fixed
- **Release Automation**: Fixed GPG signing loopback issues for Ubuntu PPA packaging and added fallback macro definitions for Fedora COPR packaging.

## [2.21.6] - 2026-06-23

### Added
- **Linux Multi-Distro Packaging**: Added packaging files for Arch Linux (AUR), Ubuntu (Debian PPA), and Fedora (COPR Spec).
- **Release Automation**: Added GitHub Actions release pipelines for automated PPA and COPR builds.

## [2.21.5] - 2026-06-23

### Changed
- **Mouse Mode Translation**: Disabled translation input from moving the mouse cursor in Mouse mode.
- **Mouse Mode Tilt Movement**: Configured Mouse mode cursor movement to be driven purely by tilt.
- **Mouse Mode Tilt Inversion**: Flipped/inverted the tilt movement directions so tilting left/right and forward/backward matches intuitive expectations.
- **Mouse Mode Scroll**: Map Z-axis spin (rz rotation) to trigger scroll up and down.

## [2.21.4] - 2026-06-23

### Fixed
- **Updater Rate Limit Bypass**: Implemented token authentication headers and a robust fallback mechanism that retrieves the raw `VERSION` file from GitHub when the GitHub Releases REST API is rate-limited (HTTP 403).

## [2.21.3] - 2026-06-23

### Fixed
- **Mouse Mode Direction**: Inverted the Y-axis mouse movement direction in Mouse mode (both translation and rotation) so that pushing the puck forward or tilting it forward moves the screen cursor up instead of down.
- **Configurator UI Chord Multi-Click**: Added multi-click (double, triple) action configuration tabs for the Both Buttons (chord) action in the configurator side panel, and synced the multi-click counts from the loaded configuration.

## [2.21.2] - 2026-06-23

### Fixed
- **Motion Kalman Anti-Windup**: Added anti-windup clamping to the Kalman filter state in the firmware, reducing response latency when reversing/releasing maximum deflections.

### Changed
- **Configurator Footer Revamp**: Removed the manual connect/disconnect button in favor of transparent background auto-connection. Moved connection status (dot and text) to the footer bottom-right, and added running version number and software update button to the footer center.

## [2.21.1] - 2026-06-23

### Changed
- **Device Connection Status**: Decoupled the UI connection status from the WebSocket service connection. The status dot and text now indicate whether the physical CAD mouse device is connected.
- **WebSocket Broadcasts**: Added automatic WebSocket broadcasts in the service whenever the device serial connection status changes.

## [2.21.0] - 2026-06-23

### Added
- **Spherical Mode**: Added a toggle switch in the configurator and implemented 3D vector-based deadzone and sensitivity processing in the firmware for smooth diagonal movement.

### Fixed
- **CI Playwright on Ubuntu 26.04**: Pinned the Ubuntu CI container to LTS release 24.04 because Playwright 1.60 does not support Ubuntu 26.04 (which became the default "latest" image).

## [2.20.2] - 2026-06-23

### Changed
- **CI Playwright Testing**: Enabled Playwright and browser dependencies in the Linux CI workflow so that Playwright tests run on all Linux distributions.

## [2.20.1] - 2026-06-23

### Fixed
- **Thread Leak in Service Tests**: Prevented the background updater_loop thread from starting during pytest runs to avoid daemon thread leaks and state pollution.

## [2.20.0] - 2026-06-23

### Added
- **Software Auto-Updates**: The background service automatically checks GitHub Releases for new updates. The Electron configurator displays a banner and handles downloading and running the latest setup installer.
- **Firmware Auto-Updates**: Added a toggle to automatically compile and flash the device on connection if its firmware version is older than the service.
- **Updater Tests**: Added unit tests to verify version comparisons and GitHub Release updates.

## [2.19.1] - 2026-06-22

### Added
- **Multi-Click Chord Mode Cycling**: Double click (`chord:2`) and triple click (`chord:3`) on both buttons now cycle active modes by default. Double click cycles forward (`Default` -> `Mouse` -> `Media` -> `Browser` -> `Default`), while triple click cycles in reverse.

### Changed
- **Granular Integration Tests**: Refactored the Playwright integration test suite (`service/test_playwright_benchy.py`) into 38 granular, individual tests for each axis, gesture, and command.

## [2.19.0] - 2026-06-22

### Added
- **Mouse Mode**: Added a new `"Mouse"` mode. Translation and rotation deflections move the mouse cursor. Physical buttons map to left and right click. Single tap on top maps to left click, and double tap on top maps to right click.
- **Double Chord Mode Switch**: Added support for double click of the both-buttons chord (`chord:2`) to cycle between modes.

### Changed
- **Mode Switching Mechanism**: Moved the default mode switches from double tap on top (`top:2`) to double click of both buttons (`chord:2`).
- **Configuration Migration**: Added migration logic to automatically update existing profiles' mode switches from tap to chord.

## [2.18.5] - 2026-06-22

### Changed
- **Dominant Mode by Default**: Dominant Mode is now enabled by default.

### Removed
- **Legacy Translation Lock**: Completely removed the legacy "Lock Translation during Rotation" (`lock_translation_rotate`) feature and all associated configurator UI components.

## [2.18.4] - 2026-06-22

### Changed
- **Default Dominant Mode Bias**: Changed the default `dominant_mode_bias` value from 2.0 to 4.8 to better balance typical hardware translation vs rotation physical forces.

## [2.18.3] - 2026-06-22

### Added
- **Dominant Mode Rotation Bias**: Added a configurable `dominant_mode_bias` slider/input (ranging from 0.1 to 10.0, default 2.0) in the configurator to scale the rotation magnitude during dominant mode comparisons, balancing rotation inputs against physically stronger translation deflections.

## [2.18.2] - 2026-06-22

### Changed
- **Configurator Threshold Range**: Increased maximum threshold limit for lock translation during rotation from 50.0 to 350.0.

## [2.18.1] - 2026-06-22

### Fixed
- **Installer Robustness**: Skip sudo udev copy and trigger if rules match repository version.

## [2.18.0] - 2026-06-22

### Added
- **Remappable Buttons in HID Emulation Mode**: Physical buttons now route through the service in HID emulation mode (`custom_usb.enabled`) like Cap-Tap gestures, so they can be custom-mapped. A new **Native HID Button** action passes a button straight through to the device's USB HID button (echoed back to the firmware via a new `hid_button` serial command) for drivers like 3DxWare; any other mapping runs the custom action. New firmware `service_buttons`/`hid_button` serial commands and a `g_serviceButtonMode` flag suppress local native button emission while the service drives buttons.

### Changed
- Extracted the firmware HID/service serial command family into a unit-tested `HidSerialCommand` module.

## [2.17.0] - 2026-06-22

### Added
- **Windows Background Execution**: Compiled `linapse-service.exe` with PyInstaller's `--noconsole` flag to run windowless in the background.
- **Windows Auto-Start on Login**: Configured the Inno Setup installer (`installer.iss`) to register `linapse-service.exe` in `HKCU\Software\Microsoft\Windows\CurrentVersion\Run` so that the service automatically launches on Windows startup.

## [2.16.8] - 2026-06-22

### Fixed
- **Serial Auto-Discovery Fallbacks**: Added third and fourth fallback passes in `serial_port.py` to match common serial chip/Arduino VIDs (CH340, CP210x, FTDI, Teensy, SparkFun, Arduino) and default to the single available port if exactly one COM port exists, improving out-of-the-box serial detection on Windows.

## [2.16.7] - 2026-06-22

### Fixed
- **Serial Auto-Discovery Fallback**: Added a second pass fallback in `serial_port.py` to match generic RP2040 (`0x2E8A`) and Adafruit (`0x239A`) serial device vendor IDs, fixing serial port auto-discovery on Windows.

## [2.16.6] - 2026-06-22

### Added
- **Discord Link**: Added Discord server link to the README.

## [2.16.5] - 2026-06-21

### Added
- **Known Bugs Documentation**: Added a section to the README detailing OnShape's opposite roll (`ry`) direction behavior compared to the Benchy 3D preview.

## [2.16.4] - 2026-06-21

### Fixed
- **Controls Tab Callout Rendering**: Fixed a bug where leaving the Controls tab and returning caused the button/tap target callout lines to collapse to the top-left corner `(0, 0)` due to hidden element layout offset recalculation.

## [2.16.3] - 2026-06-21

### Fixed
- **Firmware Crash Prevention**: Optimized firmware serial reading buffer in `main.cpp` using `reserve(256)` to prevent dynamic memory allocations, and added a buffer length check to prevent memory exhaustion and microcontroller crashes/freezes under high-frequency transmission.

## [2.16.2] - 2026-06-20

### Added
- **Configurable Translation Lock Threshold**: Added a slider/input under the configurator's general motion tab to customize the threshold of what is considered "rotation" for locking translation, preventing minor physical wobble/crosstalk from prematurely locking translation.
- **Inverted default roll**: Changed default axis inversion of roll (`ry`) to True (inverted) to match user expectations in OnShape.

## [2.16.1] - 2026-06-20

### Fixed
- **Configurator Alignment**: Defined `lock_translation_rotate` in the configurator default actions and aligned the Benchy visualizer's translation lock logic to respect the user's config toggle rather than being hardcoded.

## [2.16.0] - 2026-06-20

### Added
- **Global Translation Lock during Rotation**: Integrated the lock translation feature into the host service (`serial_port.py`) so that the lock applies globally to all applications (including OnShape, Blender, FreeCAD, and standard HID mouse reports). Added a pytest integration test to verify the functionality.

## [2.15.1] - 2026-06-20

### Changed
- **Configurator Tab Renaming**: Renamed the "Customize" tab to "Controls" and the "Sensitivity" tab to "Motion" in the UI and all documentation files to improve usability. Updated playwright test suites to match the new tab titles.

## [2.15.0] - 2026-06-20

### Added
- **Lock Translation during Rotation Toggle**: Added a toggle under the Sensitivity tab of the configurator allowing users to choose whether to allow translation at the same time as rotation or lock translation while rotating (defaulting to locked, which prevents translational drift).

## [2.14.18] - 2026-06-20

### Added
- **Firmware Tab Documentation**: Added the missing Firmware Tab description and screenshot to the README and USAGE documentation.

## [2.14.17] - 2026-06-20

### Fixed
- **Crosstalk Decoupling**: Implemented physical crosstalk decoupling in the host daemon (`serial_port.py`) to subtract tilt/roll rotation components from TX and TY translation calculations, preventing the device from "shooting off" horizontally/vertically during pure roll or pitch maneuvers. Disabled automatically during pytest suites to preserve test compatibility.

## [2.14.16] - 2026-06-20

### Fixed
- **3D Viewport Motion**: Redesigned the 3D Benchy's rotation logic to use world-space quaternions instead of euler angles. This resolves cross-axis coupling (e.g. pitch inputs tilting the boat forward/backward relative to the screen no matter the twist/roll) and corrects Ry axis rotation response.

## [2.14.15] - 2026-06-20

### Added
- **Interactive Sensitivity Calibration Wizard**: Added to the features list in README.md and documented in USAGE.md.

### Changed
- **Documentation Screenshots**: Regenerated all configurator and sensitivity screenshots in the documentation with fresh captures.

## [2.14.14] - 2026-06-20

### Fixed
- **Mouse Disconnection**: Fixed mouse disconnection loops and high memory/CPU usage by rate-limiting EQ visualizer updates to 25Hz and dropping backlog websocket frames.
- **Microcontroller Optimization**: Optimized firmware serial parsing for `eq`, `hid_report`, `volume`, and `service_hid` commands to be zero-allocation (pointer-based), avoiding RP2040 heap fragmentation and crashes under high-frequency transmission.

## [2.14.13] - 2026-06-20

### Fixed
- **Equalizer Scaling**: Fixed saturation issues in host-side `equalizer.py` by dividing raw 16-bit audio samples by `32768.0` (normalization) and calibrating the 8 log-spaced frequency scales, resolving the problem where LEDs were constantly stuck at maximum intensity (red).

## [2.14.12] - 2026-06-20

### Added
- **Agent Rules**: Added a workspace rule to `AGENTS.md` requiring that when changes are made to lighting modes, corresponding LED previews, configurator simulations, documentation (LIGHTING.md), and visualizer GIFs must be updated.

## [2.14.11] - 2026-06-20

### Changed
- **Equalizer Effect**: Smooth HSV/thermal gradient (Blue-Cyan-Green-Yellow-Orange-Red) for the frequency band intensity color interpolation.

## [2.14.10] - 2026-06-20

### Changed
- **Equalizer Effect**: Redesigned the EQ effect from a 2-channel visualization (Bass/Treble) mapped across 4 LEDs each to an 8-band FFT spectrum visualizer where each of the 8 LEDs displays the intensity of a single frequency band using color interpolation (blue at low, orange at mid, red at clip).

## [2.14.9] - 2026-06-20

### Fixed
- **3D Benchy Rotations**: Mapped Ry (Tilt Left/Right) to local Z rotation (roll) and Rz (Twist Left/Right) to local Y rotation (yaw) in the configurator 3D preview, allowing the 3D Benchy model to roll correctly.

## [2.14.8] - 2026-06-20

### Fixed
- **Tilt Direction Mappings**: Swapped Ry (Tilt Left/Right) wizard sign checks and host service mappings back to their original non-inverted signs, correcting switched Left/Right tilt calibration behavior in the wizard.

## [2.14.7] - 2026-06-20

### Added
- **Calibration Wizard Auto-Advance**: Added automatic advancement to the next calibration wizard step 1.5 seconds after a comfort peak is successfully captured.

### Fixed
- **Twist Direction Mappings**: Corrected sign mappings in the host service and configurator calibration wizard steps for Rz (Twist Left/Right) to match physical twist directions.

## [2.14.6] - 2026-06-20

### Fixed
- **Tilt Direction Mappings**: Corrected sign mappings in the host service and configurator calibration wizard steps for Rx (Tilt Forward/Backward) and Ry (Tilt Left/Right) to match physical tilt directions.

### Changed
- **Calibration Wizard**: Lowered the start deflection noise floor threshold from 15.0 to 10.0 for easier calibration.

## [2.14.5] - 2026-06-20

### Changed
- **Calibration Wizard**: Lowered the start deflection noise floor threshold from 30.0 to 15.0 to make it easier to calibrate weighted pucks (especially for Up/Down Z-axis motion).

## [2.14.4] - 2026-06-20

### Fixed
- **Axis Direction Mappings**: Corrected sign mappings in the host service and configurator calibration wizard steps for Y and Z axes to match physical motion directions.

## [2.14.3] - 2026-06-20

### Fixed
- **Axis Direction Mappings**: Corrected sign mappings in the host service and configurator calibration wizard steps for X and Z axes, ensuring physical movement directions (like RIGHT or UP) align correctly with their corresponding directional sensitivity sliders.

## [2.14.2] - 2026-06-20

### Fixed
- **Calibration Wizard**: Un-inverted incoming telemetry values within the step deflection check to ensure physical deflection matches the requested direction even when axis inversions are active.

## [2.14.1] - 2026-06-20

### Changed
- **Sensitivity Limits**: Increased maximum sensitivity from 20.0 to 50.0.
- **Calibration Wizard**: Refactored to a 12-step direction-by-direction flow.
- **Un-timed Peak Detection**: Replaced the 3-second countdown timer with un-timed peak detection (automatically captures peak when deflection exceeds noise floor and returns to rest).

## [2.14.0] - 2026-06-20

### Added
- **Interactive Calibration Wizard**: Interactive 6-step sensitivity calibration wizard overlay in the configurator to guide users through deflecting the puck to comfort limits, automatically setting directional sensitivities.

### Changed
- **Max Sensitivity limit**: Raised maximum directional sensitivity limit from 5.0 to 20.0 for all 12 range/number inputs in the configurator.

## [2.13.0] - 2026-06-20

### Added
- **Auto-normalization**: Automatic detection of puck magnet orientation during firmware calibration. Auto-normalizes coordinate axes and tap detection without software overrides.

### Changed
- **Inversion Ordering**: Applied axis inversion before sensitivity scaling on the host service side, ensuring that sensitivity sliders scale screen-space (resulting) motion directions.

## [2.12.0] - 2026-06-19

### Added
- **Tap Sensitivity**: Added velocity threshold slider to the configurator.
- **Invert Tap Z Axis**: Added toggle to support tap detection for pucks with physically inverted magnets.
- **Tabbed Layout**: Organized the sensitivity side panel into General, Axes, and Tap sub-sections.

## [2.11.4] - 2026-06-19

### Changed
- **Documentation**: Added warnings to README and Windows/macOS quickstart guides highlighting that Windows and macOS support are currently under active development and may not work as expected.

## [2.11.3] - 2026-06-19

### Fixed
- **Serial Heartbeat Keepalive**: Added a 1.0-second serial keepalive heartbeat during active puck telemetry transmission in `linapse-service` when custom USB is disabled. This prevents the device from timing out and reverting to local HID mode, which was causing the mouse cursor to move on Linux when the puck was actively manipulated.

## [2.11.2] - 2026-06-19

### Fixed
- **HID Report Suppression**: Suppressed sending processed coordinates back to the device to emit via USB HID reports on all platforms (including Linux) unless `custom_usb` emulation is explicitly enabled in actions configuration. This prevents unwanted mouse cursor movement on Linux systems when SpaceMouse emulation is not active.

## [2.11.1] - 2026-06-19

### Fixed
- **Firmware Flash Custom USB**: Added custom USB VID/PID environment variables configuration during firmware flash from `setup.sh` / `flash.sh` when `custom_usb` is enabled in `actions.json`.

## [2.11.0] - 2026-06-19

### Added
- **SpaceMouse Buttons on macOS/Windows**: Added button click support (including double clicks and chords) on macOS and Windows by routing button press/release events from the firmware over serial telemetry (`BUTTON:<btn>:<state>`).

### Fixed
- **macOS Puck Mouse/Gesture Interference**: Suppressed sending raw HID motion reports back to the device on macOS when using default Seeed Studio mode, eliminating system-wide cursor drift and gesture interference. Allows HID reports to still be sent if Custom USB emulation is enabled for official drivers.

## [2.10.12] - 2026-06-19

### Fixed
- **macOS CI/CD Packaging**: Fixed path to `Linapse Configurator.app` on Apple Silicon macOS CI runners by dynamically checking for the `mac-arm64/` build output directory.

## [2.10.11] - 2026-06-19

### Fixed
- **macOS CI/CD Test Run**: Fixed flakiness in `test_multi_click_detection` by replacing fixed sleep durations with robust polling, ensuring thread timer execution completes before assertions.

## [2.10.10] - 2026-06-19

### Fixed
- **macOS CI/CD Test Run**: Removed Linux-specific mock installer tests from executing on the macOS runner since they depend on the Linux `ydotool` binary which is not present or supported on macOS.

## [2.10.9] - 2026-06-19

### Fixed
- **Cross-Platform Tests**: Mocked `sys.platform` to be `"linux"` during the execution of `test_multi_click.py` so that it calls the ydotool emulation path and passes successfully on Windows and macOS.
- **macOS Tests**: Enabled running `test_installer_mock.py` and `test_installer_adversarial.py` on macOS.

## [2.10.8] - 2026-06-19

### Added
- **Cross-Platform Tests**: Enabled `test_multi_click.py` to run on Windows and macOS.

### Fixed
- **CI/CD Build**: Resized the Electron configurator logo image to 512x512 to resolve the electron-builder validation failure on Windows (>= 256x256) and macOS (>= 512x512).

## [2.10.7] - 2026-06-19

### Added
- **Configurator App Bundling**: Configured CI/CD and installers to bundle the Electron configurator GUI app. It is now installed to `/Applications` on macOS and packaged with a Start Menu shortcut on Windows.

### Changed
- **Documentation**: Updated installation documentation to reflect the availability of the GUI app in the application list and Start Menu.

## [2.10.6] - 2026-06-19

### Added
- **CI/CD Releases**: Added a `release` job to the GitHub Actions workflow to compile, build, and publish official Windows and macOS service installers to GitHub Releases automatically on push to the main or master branch.

### Fixed
- **Installer Download Links**: Resolved broken Windows setup and macOS package installer links in the README and documentation by publishing built binaries to GitHub Releases.

## [2.10.5] - 2026-06-19

### Fixed
- **Firmware Flashing**: Added periodic retry logic for version query on host daemon startup/heartbeat, and reset firmware version to `unknown` on disconnect, fixing endless "Update Required" warning when flashing device.

## [2.10.4] - 2026-06-19

### Added
- **Integration Testing**: Added a comprehensive Playwright integration test (`test_benchy_sensitivity_and_dead_zones`) to verify all 12 directional sensitivity settings, 6 axis inverts, and 5 device configuration parameters (dead zones, Kalman filter Q/R, curve exponent) against UI controls, reload/refresh persistence, visual boat movement, and daemon scaling behavior.

## [2.10.3] - 2026-06-19

### Fixed
- **Directional Sensitivity Overrides**: Corrected sign check logic for X and Z axes in the host daemon to match physical movement directions. Previously, the negative `SIGN_AXIS` multiplier in the firmware caused the daemon to apply the opposite directional sensitivity (e.g. `z_neg` when pulling UP).

## [2.10.2] - 2026-06-19

### Fixed
- **Directional Sensitivity Overrides**: Broadcast fully processed (scaled and inverted) coordinates over the WebSocket rather than raw/unscaled coordinates. Allows browser-based applications (OnShape, SketchUp Web) and the configurator's 3D Benchy preview to respond to directional sensitivity and inversion settings.

## [2.10.1] - 2026-06-19

### Fixed
- **Websocket Broadcast Dropout**: Fixed a race condition where high-frequency broadcasts concurrently running on the event loop would drop messages because of a simplistic global `_broadcasting` flag. Replaced with connection-specific async Locks and checks. Removed unsupported `.closed` attribute access on modern websockets connections.

## [2.10.0] - 2026-06-19

### Added
- **SpaceMouse HID Emulation**: Support routing 6DoF motion telemetry through the host Python service before writing it to a virtual/spoofed SpaceMouse USB HID device. Added watchdog timeout (2s) on the device to fall back to local HID reporting if the service is stopped.
- **Custom USB PID/VID Configuration**: Added a checkbox and custom PID/VID entry fields in the Firmware tab of the Electron configurator. Overrides default board descriptors at build-time using PlatformIO SCons scripting.

## [2.9.9] - 2026-06-19

### Added
- **Workspace Agent Rule**: Appended a new project-scoped rule to `.agents/AGENTS.md` explicitly requiring agents to bump the firmware version in `main.cpp` whenever making edits to the firmware code.

## [2.9.8] - 2026-06-19

### Added
- **Equalizer GIF Generation**: Created a Playwright script `generate_equalizer_gif.js` to automatically capture frames of the configurator's Equalizer LED animation and compile them into an animated GIF using ImageMagick.
- **Lighting Documentation GIF**: Replaced static Equalizer image reference with the newly generated animated GIF in `LIGHTING.md`.

## [2.9.7] - 2026-06-19

### Added
- **Equalizer LED Lighting Effect**: Integrated two-channel audio visualizer effect using RP2040 firmware and Python daemon (using parec and IIR lowpass/highpass filters).
- **Immediate Volume Polling Latency Scaling**: Automatically scale up host-side volume polling frequency (0.25s interval) as soon as the volume control axis is rotated on the mouse.

### Changed
- **Media Mode Controls**: Re-mapped volume control to Z-rotation (Rotate) and scrub control to Y-rotation (Roll) in Media mode.
- **Configurator UI**: Integrated Equalizer visual preview and mouse render animation to the LED config panel.

## [2.9.5] - 2026-06-19

### Changed
- **Configurator LED Preview**: Updated volume effect preview animation to start at the bottom-left (LED 1) and fill clockwise.
- **Configurator Mouse Render**: Updated volume effect render overlay on the 3D mouse image to start at the bottom-left and fill clockwise.

### Fixed
- **Firmware Volume Effect**: Corrected physical LED index mapping (`P = (3 - L + 8) % 8`) so that the volume level starts lighting up at bottom-left (physical index 3) and fills clockwise.
- **Daemon Responsiveness**: Fixed serial thread crash during firmware flash by catching specific exceptions (`serial.SerialException, TypeError, OSError, AttributeError`) thrown on port closing.

## [2.9.4] - 2026-06-19

### Changed
- **Firmware Flashing UI**: Configured the configurator to immediately update the firmware version, notice, and update badge states to "Up to Date" upon a successful firmware flash.

## [2.9.3] - 2026-06-19

### Removed
- **Teamwork Preview Artifacts**: Removed temporary markdown and tracking files (`PROJECT.md`, `ORIGINAL_REQUEST.md`, and all subdirectories inside `.agents/` except the global rule file `AGENTS.md`) created by the teamwork-preview multi-agent simulation.

## [2.9.2] - 2026-06-19

### Fixed
- **Firmware Tab Blank Screen**: Fixed a layout bug where the Firmware tab displayed a blank screen due to `#tab-firmware` being incorrectly nested inside `#tab-sensitivity` from an unclosed `side-panel` div.

## [2.9.1] - 2026-06-19

### Added
- **Workspace Rule**: Added a workspace-scoped guideline to `.agents/AGENTS.md` establishing the commit-push-wait retry loop for fixing CI/CD errors and failures.

## [2.9.0] - 2026-06-19

### Added
- **Firmware Version Checking**: Added support to query, parse, and check the device firmware version over serial connection.
- **Out-of-Date Notification Badge**: Configured a red notification badge on the Firmware tab to alert when the firmware needs an update.
- **Update Warning Notice**: Added a warning notice block inside the Firmware tab detailing current and latest firmware versions when out-of-date.
- **Firmware Device Status**: Displayed active firmware version status (e.g. "Up to Date" or "Update Required") directly in the Flashing UI.

## [2.8.7] - 2026-06-19

### Fixed
- **Inverted Volume Control**: Corrected volume adjustment direction on RX axis so pushing down (positive rx) decreases system volume and pulling up (negative rx) increases volume.
- **Media Mode default LED effect**: Fixed default configuration to use the dedicated `volume` LED effect instead of `dot_swirl` for the Media mode.
- **Config Migration**: Added migration logic to automatically upgrade existing user configurations using `dot_swirl` under Media mode's LED config to the correct `volume` effect.
- **Windows Test Reliability**: Implemented retry logic with brief backoffs in configuration read/write operations to prevent transient PermissionErrors from Windows file locking.
- **Playwright Test Stability**: Added a retry-safe configuration reading helper to the integration test suite to handle transient lock conditions.

## [2.8.6] - 2026-06-19

### Changed
- **Codebase Restructuring**: Refactored `linapse-service` monolithic daemon script into a modular Python package structure under `service/linapse/` (Option 1).
- **Test Compatibility Wrapper**: Added dynamic proxy lookup mechanism to `linapse-service` using module-level `__getattr__` and `__setattr__` hooks to fully support and execute the existing test suite without changes.
- **Service Installer Update**: Updated `install.sh` and mock installation tests to correctly copy and verify the new modular `linapse` package directory.
- **Documentation Update**: Changed all references from web app / web configurator to refer to the Electron configurator app and updated setup/execution instructions.

## [2.8.5] - 2026-06-19

### Added
- **Origin Validation Tests**: Added `test_m3_websocket_origin_check` unit test in `service/test_m3_adversarial.py` to verify local origin validation.

### Security
- **WebSocket Origin Validation**: Added robust `Origin` header verification in `ws_handler` supporting legacy and v14+ websockets libraries, blocking unauthorized remote websites.

### Fixed
- **Cross-Platform Flashing Mounts**: Implemented native mount detection for macOS (`/Volumes/RPI-RP2`) and Windows (checking volume name `RPI-RP2` across drive letters via `ctypes`) in `locate_or_mount_rpi_rp2`.

## [2.8.4] - 2026-06-19

### Changed
- **Adaptive Volume Polling**: Optimized system volume synchronization to use 1s polling interval by default, temporarily scaling to 250ms for 10s only when active changes are detected.
- **Playwright Test Policy**: Updated `.agents/AGENTS.md` project rules to forbid disabling or bypass marking of critical Playwright GUI integration tests.

## [2.8.3] - 2026-06-19

### Added
- **Comprehensive Firmware Unit Tests**: Implemented 19 detailed test cases under `firmware/test/test_firmware/test_main.cpp` covering:
  - `MotionController`: Geometric decomposition, Kalman filter convergence, deadzone thresholding, and linear/cubic sensitivity power curves.
  - `TapDetector`: Tap spike detection, multi-direction classification (PosX, NegX, PosY, NegY, NegZ), double/multi-tap window accumulation, cooldowns, and spring return thresholds/timeouts.
  - `EffectEngine`: Color scaling, HSV-to-RGB conversion, and all LED effect patterns (Solid, Breathing, Reactive, Dot Swirl, Gradient Swirl, Rainbow Swirl, and Volume).
  - `StateMachine`: Verification of state transitions and hook callbacks (CalibratingState, IdleState, ColorConfigState, SleepState).
  - `Config Management`: EEPROM load/save serialization, default resets, and non-overlapping layout boundary verification.
- **Test Build Customization Script**: Added `test_build_config.py` to dynamically adjust compilation include paths and source filters during PlatformIO test execution, enabling mock dependencies on both native and target (`seeed_xiao_rp2040`) test runs.
- **GitHub Actions Test Reporting**: Integrated `dorny/test-reporter` to publish JUnit XML test results from Linux (Ubuntu, Debian, Fedora), Windows, and macOS directly to the GitHub Check Runs UI for rich, interactive test reporting in CI.

## [2.8.2] - 2026-06-19

### Added
- **Native Testing Environment**: Configured native environment block in `platformio.ini` to support building and running unit tests locally using host gcc/g++.
- **Mocking Infrastructure**: Implemented mock headers (`Arduino.h`, `EEPROM.h`, `Adafruit_NeoPixel.h`, and stub controllers `SensorController.h`, `InputController.h`, `HIDController.h`, `TelemetryController.h`) to emulate hardware dependency APIs in native test builds.

## [2.8.1] - 2026-06-19

### Changed
- **Firmware Documentation Restructuring**: Comprehensively restructured and updated `firmware/README.md` and `firmware/LED_COLOR_CONFIG.md` for complete technical accuracy.
- **Linapse Fork Documentation**: Added detailed guides on all Linapse fork firmware changes, including the volume visualizer LED effect, serial commands, Kalman filtering, configuration persistence layout, and multi-tap detector.

## [2.8.0] - 2026-06-19

### Added
- **Firmware Flashing UI & Backend**: Integrated direct firmware compilation and flashing capabilities into the web configurator and backend host service.
- **Auto-BOOTSEL Detection & Reset**: Support for automatically resetting already-flashed devices to BOOTSEL mode via 1200 baud serial connection, as well as detecting and mounting fresh-out-of-the-box devices in BOOTSEL mode automatically.
- **Flashing Progress Console**: Added a graphical progress bar and scrollable cyberpunk terminal window to the configurator for live build and flashing feedback.

## [2.7.0] - 2026-06-19

### Added
- **Volume Lighting Mode**: Introduced a new cross-platform lighting effect ("Volume") that visualizes system volume level on LEDs 1 to 8, with fractional volume represented by smooth dimming/brightening on the highest active LED.
- **Volume Synchronization**: Implemented background system volume monitoring in `linapse-service` using native tools (Windows `pycaw` fallback, macOS `osascript`, Linux `amixer`/`pactl`) to sync volume changes over serial to the device in real-time.
- **Configurator Integration**: Added the "Volume" chip to the web configurator's lighting tab with a custom local preview animation.

## [2.6.14] - 2026-06-19

### Added
- **Platform Documentation**: Added comprehensive installation and quick-start guides for Windows (`docs/WINDOWS.md`) and macOS (`docs/MACOS.md`), including details on binary installers, building from source, userscript configuration, system permissions, and feature support matrices.

## [2.6.13] - 2026-06-19

### Fixed
- **CI/CD Cleanup**: Resolved `PytestUnraisableExceptionWarning: coroutine ignored GeneratorExit` tracebacks on Windows and Linux CI during teardown of the Playwright test suite by cleanly cancelling `main` task and closing event loop.

## [2.6.12] - 2026-06-19

### Changed
- **Renamed Folder**: Renamed `linux/` directory to `service/` to correctly reflect its cross-platform support and updated all internal and external references.

## [2.6.11] - 2026-06-19

### Added
- **Agent Rules**: Added rule to `.agents/AGENTS.md` specifying that agents must ignore the `git_token` (or other GitHub token) environment variables and not prompt for them.

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
