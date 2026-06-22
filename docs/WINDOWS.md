# Linapse CAD Mouse — Windows Installation & Quick Start

> [!WARNING]
> Windows support is currently in active development and may not work as expected.

This guide helps you set up and configure the **CAD Mouse MK2** using **Linapse** on Microsoft Windows.

---

## How It Works on Windows

Windows does not use UNIX sockets or `udev` rules. Instead:
- **Motion Telemetry** is sent from the CAD Mouse MK2 over the USB Serial interface (COM port) to `linapse-service.exe`.
- **Physical Buttons** are sent over USB Serial to `linapse-service.exe`, just like Cap-Tap gestures, so they can be custom-mapped. When HID Emulation is enabled, a button left as **Native HID Button** is echoed back to the device's hardware to emit the real USB HID button press, so drivers like 3DxWare pick it up; any other mapping runs the custom action instead.
- **Cap-Tap Gestures** are detected by the firmware, sent over USB Serial, and simulated on the host OS by the service using the `pynput` library.
- **Browser CAD Applications** (such as OnShape or SketchUp Web) connect via the browser bridge built into `linapse-service` and the official Linapse Browser Connector extension.

---

## Installation Options

### Option 1: Automatic Setup (Recommended)

1. Download the latest `LinapseServiceSetup.exe` installer directly from the [latest release download link](https://github.com/spikeon/linapse-cad-mouse-v2/releases/latest/download/LinapseServiceSetup.exe).
2. Run the installer. It will:
   - Copy the service executable and the **Linapse Configurator** GUI files to your program files directory.
   - Configure the service to start automatically as a windowless background daemon (via the `Run` registry key) whenever you log into Windows.
   - Launch the service immediately in the background.
3. You will see a folder in your Start Menu under `Linapse CAD Mouse` containing shortcuts to the **Linapse Configurator** GUI, the background service, and an uninstaller. Since the service runs in the background with no console window, it starts invisibly.

### Option 2: Running from Source (Python)

If you prefer to run the daemon manually from source:

1. Ensure [Python 3](https://www.python.org/downloads/) is installed and added to your `PATH`.
2. Open PowerShell or Command Prompt and install the required dependencies:
   ```cmd
   pip install websockets pyserial pynput pycaw
   ```
3. Run the service:
   ```cmd
   python service/linapse-service
   ```
4. **Auto-Start on Boot (Optional)**:
   - Press `Win+R`, type `shell:startup`, and press Enter.
   - Create a shortcut to a batch script (e.g., `run_linapse.bat`) containing the run command inside this folder.

---

## Browser CAD Connector Setup (OnShape & SketchUp Web)

Browser-based CAD tools sandbox network connections. Install the official **Linapse Browser Connector** extension:

1. Run the Windows installer — it prints browser extension store links at the end (optional post-install step), or install manually from **[docs/BROWSER_EXTENSION.md](BROWSER_EXTENSION.md)**.
2. Click **Add** / **Install** in your browser.
3. Open or refresh OnShape (`https://cad.onshape.com`) or SketchUp Web. The device will be recognized immediately, allowing 6DoF camera motion.

---

## Tuning with the Electron Configurator

The configurator is an Electron app that interfaces with `linapse-service` over WebSocket (`ws://localhost:13000`):

1. Open the `configurator/` directory, install dependencies, and start the app:
   ```cmd
   cd configurator
   npm install
   npm start
   ```
3. Ensure the indicator in the top-left reads **CONNECTED** (red dot).
4. Use the **Motion** tab to adjust dead zones, Kalman filters, and axes inversion in real time. Use the **Lighting** tab to configure the SK6812 LED ring.

---

## Customization Differences on Windows

> [!IMPORTANT]
> - **Physical Buttons**: With **HID Emulation** enabled, the **Controls** tab's remappings for **Left Button**, **Right Button**, and the **Chord** (both buttons) *are* applied by the host service. Set a button's action to **Native HID Button** to instead pass it straight through to the device's native USB HID button (e.g. for 3DxWare).
> - **Taps & Gestures**: Taps (Top Tap, Front Tap, Back Tap, Left Tap, Right Tap) *are* processed by the service and can be bound to key combinations, mouse clicks, scrolls, macros, and profile modes.
