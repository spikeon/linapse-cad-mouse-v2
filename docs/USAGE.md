# Using the Linapse Configurator

The Linapse configurator is a browser-based control panel for the CAD Mouse MK2. It talks to `linapse-service` over a WebSocket (`ws://localhost:13000`) and lets you remap buttons and taps, design RGB lighting, and tune the motion filter — all applied to the device live over the serial link.

This guide walks through each tab. For install/setup, see the [main README](../README.md) and [linux/README.md](../linux/README.md). For configuring specific 3D/CAD applications, see the **[Application Integrations Guide](INTEGRATIONS.md)**.

## Before you start

1. Plug in the device and confirm `linapse-service` is running (`systemctl --user status linapse-service`).
2. Serve the configurator and open it:
   ```bash
   cd configurator
   python3 -m http.server 7890
   # open http://localhost:7890
   ```
3. The header shows the connection state. **CONNECTED** (red dot, top-left) means the configurator is talking to the device. If it reads **Disconnected**, start `linapse-service` and reload.

The three tabs — **Customize**, **Lighting**, **Sensitivity** — run across the top. **Load Profile** / **Save Profile** in the footer persist the full device config (all three tabs) to a JSON file.

---

## Customize — buttons & taps

![Customize tab](images/configurator-customize-tap.png)

The 3D device is annotated with every input zone. Click a callout to open its action panel on the right.

### Action Configuration Screens

- **Key Combo Configuration**:
  ![Key Combo Action Configuration](images/configurator-customize-key.png)
- **Scroll Configuration**:
  ![Scroll Action Configuration](images/configurator-customize-scroll.png)
- **Tap & Mouse Configuration**:
  ![Tap & Mouse Action Configuration](images/configurator-customize-tap.png)
- **Macro Configuration**:
  ![Macro Action Configuration](images/configurator-customize-macro.png)

**Input zones (8):**

| Zone | What triggers it |
|------|------------------|
| **Left Button** / **Right Button** | The two physical buttons. |
| **Both Buttons** | Chord — press both buttons together. |
| **Top Tap** | Tap the top of the cap. |
| **Front / Back / Left / Right Tap** | Tap a side of the cap (gesture detected in firmware). |

**Action types** — assign any of these to a zone:

| Action | Effect |
|--------|--------|
| **None** | Disable the zone. |
| **Key Combo** | Send a keystroke or shortcut (e.g. `Esc`, `Ctrl+Z`). |
| **Mouse Click** | Left / middle / right click. |
| **Scroll** | Scroll by an amount/direction. |
| **Mouse Move** | Move the cursor. |
| **Run Command** | Execute a shell command on the host. |
| **Scroll Up** / **Scroll Down** | One-shot scroll step. |
| **Macro** | A sequence of steps with per-step delays. |

Pick the action type, fill in its parameters, then hit **Apply** to write the mapping to the device.

> Tap zones rely on firmware tap detection. If taps misfire or don't register, recalibrate with the tools in [`linux/`](../linux/) — see [linux/README.md](../linux/README.md).

---

## Lighting — RGB effects

![Lighting tab](images/configurator-lighting.gif)

Controls the SK6812 LED ring. Pick an **Effect**, watch the **LED Preview** ring update, then **Apply to Device**.

**Effects (6):**

| Effect | Behavior |
|--------|----------|
| **Solid** | Single static color. |
| **Breathing** | Color fades in and out. |
| **Reactive** | Lights respond to device motion. |
| **Dot Swirl** | A dot chases around the ring. |
| **Gradient** | Color gradient across the ring. |
| **Rainbow** | Full-spectrum cycle (shown above). |

- **Color** — picker for effects that use a base color (Solid, Breathing, Dot Swirl, Gradient).
- **Brightness** — `0–255`. Lower it if the ring is too bright.

The **LED Preview** ring is a live mock of what the device will show before you apply.

> Per-LED color math and the effect engine are documented in [firmware/LED_COLOR_CONFIG.md](../firmware/LED_COLOR_CONFIG.md).

---

## Sensitivity — motion tuning

![Sensitivity tab](images/configurator-sensitivity.gif)

Tune the 6DoF motion filter against a live 3D **Benchy** test model. **Changes apply live** — there's no Apply button; drag the puck and feel the difference immediately. The viewport prompt reads **MOVE PUCK TO TEST**.

**Dead Zones** — ignore tiny unintended motion:

| Control | Range | Default |
|---------|-------|---------|
| **Translation** | 0 – 50 | 16 |
| **Rotation** | 0 – 50 | 20 |

**Kalman Filter** — trade responsiveness against smoothness:

| Control | Range | Default | Notes |
|---------|-------|---------|-------|
| **Responsiveness (Q)** | 0.05 – 2 | 0.5 | Higher = snappier, more jitter. |
| **Smoothness (R)** | 0.5 – 15 | 4 | Higher = smoother, more lag. |

**Curve** — input-to-output response shaping:

| Control | Range | Default |
|---------|-------|---------|
| **Exponent** | 1 – 5 | 3 |

The exponent slider is labelled **Linear → Cubic → Steep**: low values give linear 1:1 response, high values make small movements gentle and large movements aggressive.

**Reset to Defaults** restores every slider on this tab.

> These values map to the firmware defaults in `firmware/include/Config.h`. The configurator pushes them over serial at runtime; to change the boot defaults, edit `Config.h` and reflash — see [firmware/README.md](../firmware/README.md).

---

## Profiles

The footer's **Save Profile** / **Load Profile** export and import the complete configuration — button/tap maps, lighting, and sensitivity — as a single JSON file. Save a profile per workflow (e.g. one for OnShape, one for FreeCAD) and load on demand.
