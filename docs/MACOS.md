# Linapse CAD Mouse — macOS Installation & Quick Start

> [!WARNING]
> macOS support is currently in active development and may not work as expected.

This guide helps you set up and configure the **CAD Mouse MK2** using **Linapse** on Apple macOS.

---

## How It Works on macOS

macOS does not use UNIX sockets or `udev` rules. Instead:
- **Motion Telemetry** is sent from the CAD Mouse MK2 over the USB Serial interface (COM port) to `linapse-service`.
- **Physical Buttons** are sent over USB Serial to `linapse-service`, just like Cap-Tap gestures, so they can be custom-mapped. When HID Emulation is enabled, a button left as **Native HID Button** is echoed back to the device's hardware to emit the real USB HID button press, so drivers like 3DxWare pick it up; any other mapping runs the custom action instead.
- **Cap-Tap Gestures** are detected by the firmware, sent over USB Serial, and simulated on the host OS by the service using the `pynput` library.
- **Browser CAD Applications** (such as OnShape or SketchUp Web) connect via the browser bridge built into `linapse-service` and the official Linapse Browser Connector extension.

---

## Installation Options

### Option 1: Automatic Setup (Recommended)

1. Download the latest `linapse-service.pkg` installer package directly from the [latest release download link](https://github.com/spikeon/linapse-cad-mouse-v2/releases/latest/download/linapse-service.pkg).
2. Open and run the package installer. This will:
   - Copy the service binary to `/usr/local/bin/linapse-service`.
   - Copy the **Linapse Configurator** GUI app to `/Applications/Linapse Configurator.app`.
   - Register a `launchd` launch agent plist at `/Library/LaunchAgents/com.linapse.service.plist`.
3. The launch agent ensures the background service starts automatically when you log into macOS. You will see **Linapse Configurator** in your Applications folder and App List.

### Option 2: Running from Source (Python)

If you prefer to run the daemon manually from source:

1. Ensure Python 3 is installed (usually preinstalled or via Homebrew `brew install python`).
2. Open Terminal and install the required dependencies:
   ```bash
   pip3 install websockets pyserial pynput
   ```
3. Run the service:
   ```bash
   python3 service/linapse-service
   ```
4. **Auto-Start on Boot (Optional)**:
   - Create a launch agent plist under `~/Library/LaunchAgents/com.linapse.service.plist` pointing to your Python path and the script path.
   - Load the agent:
     ```bash
     launchctl load ~/Library/LaunchAgents/com.linapse.service.plist
     ```

---

## Required macOS Permissions

> [!CAUTION]
> **Accessibility Permissions**: macOS security policies block standard scripts from simulating keyboard or mouse inputs.
> To allow tap gestures and other custom macro actions to work:
> 1. When the service first runs and attempts to simulate a keypress, macOS will display an "Accessibility Access" prompt.
> 2. Go to **System Settings > Privacy & Security > Accessibility**.
> 3. Add and toggle **ON** the program running the service:
>    - If running the pre-compiled installer: Enable `/usr/local/bin/linapse-service`.
>    - If running from source: Enable **Terminal** (or your terminal emulator of choice).

---

## Browser CAD Connector Setup (OnShape & SketchUp Web)

Browser-based CAD tools sandbox network connections. Install the official **Linapse Browser Connector** extension:

1. Install from the Chrome, Edge, or Firefox store — see **[docs/BROWSER_EXTENSION.md](BROWSER_EXTENSION.md)** for links. Safari users can build the Safari Web Extension locally from the same doc.
2. Click **Add** / **Install** in your browser.
3. Open or refresh OnShape (`https://cad.onshape.com`) or SketchUp Web. The device will be recognized immediately, allowing 6DoF camera motion.

---

## Tuning with the Electron Configurator

The configurator is an Electron app that interfaces with `linapse-service` over WebSocket (`ws://localhost:13000`):

1. Open the `configurator/` directory, install dependencies, and start the app:
   ```bash
   cd configurator
   npm install
   npm start
   ```
3. Ensure the indicator in the top-left reads **CONNECTED** (red dot).
4. Use the **Motion** tab to adjust dead zones, Kalman filters, and axes inversion in real time. Use the **Lighting** tab to configure the SK6812 LED ring.

---

## Customization Differences on macOS

> [!IMPORTANT]
> - **Physical Buttons**: With **HID Emulation** enabled, the **Controls** tab's remappings for **Left Button**, **Right Button**, and the **Chord** (both buttons) *are* applied by the host service. Set a button's action to **Native HID Button** to instead pass it straight through to the device's native USB HID button (e.g. for 3DxWare).
> - **Taps & Gestures**: Taps (Top Tap, Front Tap, Back Tap, Left Tap, Right Tap) *are* processed by the service and can be bound to key combinations, mouse clicks, scrolls, macros, and profile modes.
