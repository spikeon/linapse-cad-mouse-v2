# Linapse CAD Mouse — Application Integrations

Guide on how to configure and verify 6DoF motion for various 3D, CAD, and game engine software on Linux.

## Support Matrix

| Application | Platform/Type | Support Status | Method |
|---|---|---|---|
| **Blender** | Native Linux | Fully Supported | UNIX Socket (`libspnav`) |
| **OrcaSlicer** | Native Linux | Fully Supported | UNIX Socket (`libspnav`) |
| **FreeCAD** | Native Linux | Fully Supported | UNIX Socket (`libspnav`) |
| **OpenSCAD** | Native Linux | Fully Supported | UNIX Socket (`libspnav`) |
| **Autodesk Maya** | Native Linux | Fully Supported | UNIX Socket (`libspnav`) + Plugin |
| **Substance 3D Painter** | Native Linux | Fully Supported | UNIX Socket (`libspnav`) |
| **OnShape** | Browser/Web | Fully Supported | Linapse Browser Connector + built-in browser bridge |
| **SketchUp Web** | Browser/Web | Fully Supported | Linapse Browser Connector + built-in browser bridge |
| **Unreal Engine** | Game Engine | Community Plugin | `OpenUnrealSpaceMouse` plugin |
| **Unity** | Game Engine | Custom Package | Raw HID / Custom input scripts |

---

## Native Linux Applications

Native Linux applications connect to the local SpaceMouse daemon via `libspnav`.

### Prerequisites
1. Run `./setup.sh` or `service/install.sh`. This installs the systemd environment config at `~/.config/environment.d/99-spnav.conf`.
2. **You must log out and back in** (or reboot) to apply this environment configuration to your desktop environment.
3. Verify that the env variable is active: `echo $SPNAV_SOCKET`. It should output `/run/user/<UID>/spnav.sock`.

### Application Configuration

#### Blender
- Connection: Automatic.
- Setup:
  1. Open Blender.
  2. Navigate to `Edit -> Preferences -> Input -> NDOF`.
  3. Enable and tune NDOF settings (sensitivity, pan/zoom options).

#### OrcaSlicer
- Connection: Automatic.
- Setup:
  1. Open OrcaSlicer.
  2. Go to `Preferences` and verify 3D Mouse is enabled.
  
  > [!NOTE]
  > The official Linux builds (AppImage and Flatpak) of Bambu Studio are compiled without `libspnav` support. OrcaSlicer (a popular fork) retains this support and works out of the box with Linapse.

#### FreeCAD
- Connection: Automatic.
- Setup:
  1. Open FreeCAD.
  2. Go to `Edit -> Preferences -> Display -> 3D Navigation`.
  3. Ensure navigation style or "Spaceball" is enabled.

#### OpenSCAD
- Connection: Automatic.
- Setup:
  1. Go to `Edit -> Preferences -> Input` to enable and configure the 3D mouse.

#### Autodesk Maya
- Connection: Plugin-based.
- Setup:
  1. Open Maya.
  2. Open the Plug-in Manager via `Window -> Settings/Preferences -> Plug-in Manager`.
  3. Check the `Loaded` and `Auto Load` checkboxes for the 3Dconnexion plugin.

#### Substance 3D Painter
- Connection: Automatic.
- Setup:
  1. Open Substance 3D Painter and tune navigation under preferences.

---

## Browser / Web Applications

Web applications run in sandboxed browsers and cannot read the UNIX socket. They communicate via the browser bridge built into `linapse-service` (`wss://127.51.68.120:8181`).

### Setup Steps
1. Make sure `linapse-service` is running: `systemctl --user status linapse-service`.
2. Install the **Linapse Browser Connector** extension from your browser's store. See **[docs/BROWSER_EXTENSION.md](BROWSER_EXTENSION.md)** for links and enterprise install options.
   - The extension spoofs `navigator.platform` to `'Win32'` on `cad.onshape.com` and `*.sketchup.com`.

#### OnShape
- Open any document on `https://cad.onshape.com`. Motion should work instantly.

#### SketchUp Web
- Open a design on `https://sketchup.com` or `https://app.sketchup.com`. Spoofing activates connection to WebSocket proxy.

---

## Game Engines

Game engines require plugin-based integrations.

#### Unreal Engine (Native Linux)
1. Download `OpenUnrealSpaceMouse` from GitHub (https://github.com/microcosm/OpenUnrealSpaceMouse).
2. Build and copy the plugin to your project's `Plugins/` folder.
3. Enable under `Edit -> Plugins` in Unreal Editor.
4. Ensure `SPNAV_SOCKET` is exported before launching Unreal Editor.

#### Unity (Native Linux)
1. The Linapse installer sets up udev rules that grant user-read access to `/dev/hidraw*`.
2. Use a C# Unity package (e.g. `Unity-SpaceMouse`) to read raw HID reports.
3. Map HID axes to camera control scripts in your project.
