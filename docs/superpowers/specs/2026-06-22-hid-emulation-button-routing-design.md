# HID Emulation Button Routing — Design

**Date:** 2026-06-22
**Status:** Approved
**Branch:** `feat/hid-emulation-button-routing`

## Problem

In HID emulation mode (`custom_usb.enabled` — device flashed with custom VID/PID so
3DxWare / Fusion 360 / Blender native see a SpaceMouse-compatible device), physical
buttons are emitted directly by the firmware as native USB HID button reports (report
ID 3), in addition to the firmware streaming `BUTTON:idx:state` over serial.

Consequences:

- Buttons cannot be remapped in emulation mode — the native bit always fires.
- Custom-mapped buttons **double-fire**: the native HID button reaches 3DxWare AND the
  serial `BUTTON:` line triggers the service's custom action.

## Goal

Route physical buttons through the service in emulation mode, exactly like taps. The
service decides **per button**:

- **Native passthrough** — button is configured as "Native HID Button". Service commands
  the firmware to emit the HID button report so the external driver (3DxWare etc.) picks
  it up.
- **Custom mapping** — service dispatches the mapped action only; firmware emits nothing.

Net result: no double-fire; buttons become remappable while emulation is on.

## Decisions (locked)

1. **Designation:** new **"Native HID Button"** action type in the configurator. Unmapped /
   None retains today's meaning (scroll default). Explicit, per-button, per-mode.
2. **Scope:** routing changes apply **only when `custom_usb.enabled` is ON**. Applies on
   every OS that enables emulation. Non-emulation behavior is unchanged.
3. **Firmware emission:** firmware emits native HID buttons **only on service command** in
   emulation mode. No short-timeout auto-revert to local native buttons.

## Architecture

### Current flow

- Firmware `InputController` reads physical buttons → always `sendButtonsReport(buttonBits)`
  (native USB HID report 3) AND prints `BUTTON:idx:state` over serial.
- Service button consumers:
  - **Linux:** `hid_thread` reads native report 3 from hidraw → custom actions.
  - **Windows/macOS:** serial `BUTTON:` line → `_on_press`/`_on_release` → custom actions.
- Emulation mode adds `hid_report x,y,z,...` (service-driven axes); buttons still native.

### New flow (emulation ON)

- Firmware suppresses local native button emission; sole button source on all platforms is
  the serial `BUTTON:` path in the service.
- Per button: native → service writes `hid_button <bits>` back → firmware emits report 3;
  custom → service dispatches action.

## Component changes

### 1. Firmware

New global `g_serviceButtonMode` (mirrors `g_serviceHidMode`):
- Declared `extern` in `firmware/include/Controllers.h`, defined in `firmware/src/main.cpp`,
  added to `firmware/test/mocks/Controllers.h` and `firmware/test/test_firmware/test_main.cpp`.

New serial commands in `main.cpp` `handleSerial()`:
- **`service_buttons <0|1>`** — set `g_serviceButtonMode`. On `1`, call
  `hidController.sendButtonsReport(0)` once to clear any stuck native bit. Reply `OK`.
  No timeout auto-revert (distinct from `service_hid`).
- **`hid_button <bits>`** — `hidController.sendButtonsReport(bits & 0x03)`; updates
  `g_lastServicePacketMs`. Reply `OK` (or `ERR` on parse failure).

`firmware/src/states/IdleState.cpp` `runMotionPipeline()`: when `g_serviceButtonMode` is set,
**do not** call the local `sendButtonsReport(buttonBits)`. Physical state still streams as
`BUTTON:` serial lines (unchanged path in `InputController`).

### 2. Service — `serial_port.py`

- `BUTTON:` handler runs the dispatch path when `custom_usb.enabled` **OR**
  `sys.platform in ("win32","darwin")` (today it is win32/darwin only).
- New module-level `_hid_button_bits = 0`.
- In emulation mode, per `BUTTON:btn:val`:
  - Look up the button's action in the active mode config.
  - `action == "hid_button"` → set/clear `1<<btn` in `_hid_button_bits`, write
    `hid_button <bits>\n` to serial, broadcast `BUTTON:btn:val` for the configurator
    live-highlight.
  - otherwise → existing `_on_press`/`_on_release` custom path.
  - On release, always clear that button's bit (guards against a mapping change mid-hold
    leaving a stuck bit).
- `serial_thread`: send `service_buttons 1` on connect and on enable-transition when
  `custom_usb.enabled`; send `service_buttons 0` on disable-transition and on clean shutdown.

### 3. Service — `hid.py`

`hid_thread` (Linux only) **skips button dispatch when `custom_usb.enabled`**. Required:
the service-driven native reports (from `hid_button`) are emitted as report 3 and would be
read back by `hid_thread`, causing a double-dispatch. In emulation mode the serial path is
the sole button source.

### 4. Configurator — `index.html`

- Add `{ id:'hid_button', label:'Native HID Button' }` to `ACTION_TYPES`.
- Offered only on single-press button slots (`btn-0`, `btn-1`). Hidden for taps, the chord
  slot, and double-click slots — native = raw press/release, no multi-click semantics.
- No extra parameters; the bit index is derived from the slot. Persisted as
  `{"action":"hid_button"}`.

### 5. `emulation.py`

`dispatch()` must ignore `action == "hid_button"` gracefully (it is intercepted in
`serial_port.py` and should never reach `dispatch()`; verify the default-none path is safe).

### 6. Docs + version

- Rewrite the README "Physical Buttons" bullet under "How It Works on Windows" to describe
  service routing with native echo-back in emulation mode.
- Bump `VERSION` and `CHANGELOG.md`.

## Testing

Extend `service/test_serial_buttons.py`:
- emulation ON + native-mapped button → `hid_button <bits>` written, bit set on press /
  cleared on release.
- emulation ON + custom-mapped button → action dispatched, no `hid_button` write.
- emulation OFF → unchanged legacy behavior on each platform.
- `service_buttons` enable/disable transitions emit the right serial commands.
- Linux `hid_thread` skips button dispatch when `custom_usb.enabled`.

Firmware native tests (`test_main.cpp`): `service_buttons 1` suppresses local button
emission; `hid_button <bits>` drives `sendButtonsReport`.

## Tradeoff (accepted)

If the service process dies while emulation is ON, native buttons go dead — firmware
suppresses local emission and receives no `hid_button` commands — until the service
restarts and re-sends `service_buttons 1`, after which physical presses resume flowing
through serial and recovery is automatic.

## Out of scope

- Chord (both-buttons) gestures across mixed native/custom configs. Chord remains a custom
  action requiring both buttons mapped to the custom path.
- Non-emulation button behavior on any platform — unchanged.
