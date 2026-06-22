# HID Emulation Button Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In HID emulation mode (`custom_usb.enabled`), route physical buttons through the service so they become remappable, with native-mapped buttons echoed back to the firmware's USB HID for external drivers (3DxWare etc.), eliminating the native/custom double-fire.

**Architecture:** Firmware gains a `g_serviceButtonMode` flag and two serial commands (`service_buttons`, `hid_button`); when the flag is set it suppresses local native button emission and emits buttons only on command. The service detects each button's mapping in emulation mode: a new `hid_button` action type → write `hid_button <bits>` back to firmware; any other mapping → dispatch the action. The configurator exposes the new "Native HID Button" action type on single-press button slots.

**Tech Stack:** C++ (RP2040 / TinyUSB / PlatformIO, native unit tests via Unity), Python 3 (asyncio service, pytest), vanilla JS configurator.

---

## File Structure

**Firmware**
- Create `firmware/include/HidSerialCommand.h` — declares `handleHidSerialCommand(line, hid)`.
- Create `firmware/src/HidSerialCommand.cpp` — parses the HID/service command family (`service_hid`, `service_buttons`, `hid_button`, `hid_report`), moved out of `main.cpp` so it is testable.
- Modify `firmware/include/Controllers.h` — add `extern bool g_serviceButtonMode;`.
- Modify `firmware/src/main.cpp` — define `g_serviceButtonMode`; call `handleHidSerialCommand` from `handleSerial`; remove the now-extracted inline `service_hid`/`hid_report` blocks; bump version string.
- Modify `firmware/src/states/IdleState.cpp` — suppress local button emission when `g_serviceButtonMode`.
- Modify `firmware/test/mocks/Controllers.h` — add `extern bool g_serviceButtonMode;`.
- Modify `firmware/test/test_firmware/test_main.cpp` — define `g_serviceButtonMode`; add serial-handler tests.
- Modify `platformio.ini` — add `HidSerialCommand.cpp` to the native `build_src_filter`.

**Service**
- Modify `service/linapse/serial_port.py` — `route_button()` helper + native bit state; wire into the `BUTTON:` handler; emit `service_buttons` on connect/transition.
- Modify `service/linapse/hid.py` — `hid_thread` skips button dispatch when emulation is on.
- Modify `service/linapse/emulation.py` — `dispatch()` ignores `hid_button` defensively.
- Modify `service/test_serial_buttons.py` — tests for `route_button` and the skip guard.

**Configurator**
- Modify `configurator/index.html` — add the `hid_button` action type, sub-fields, collector, and slot filtering.

**Docs / version**
- Modify `README.md`, `VERSION`, `CHANGELOG.md`.

---

## Task 1: Service — `route_button()` helper (native bit logic)

**Files:**
- Modify: `service/linapse/serial_port.py`
- Test: `service/test_serial_buttons.py`

- [ ] **Step 1: Write the failing tests**

Append to `service/test_serial_buttons.py`:

```python
def _emu_actions(btn0_action):
    return {
        "custom_usb": {"enabled": True},
        "current_mode": "Default",
        "modes": {"Default": {"buttons": {"0": btn0_action, "1": {"action": "hid_button"}}, "taps": {}}},
    }

def test_route_button_native_sets_and_clears_bit(monkeypatch):
    import linapse.serial_port as sp
    sp._hid_button_bits = 0
    actions = _emu_actions({"action": "hid_button"})
    ser = MagicMock()

    assert sp.route_button(0, 1, actions, ser) is True
    ser.write.assert_called_with(b"hid_button 1\n")

    assert sp.route_button(1, 1, actions, ser) is True
    ser.write.assert_called_with(b"hid_button 3\n")

    assert sp.route_button(0, 0, actions, ser) is True
    ser.write.assert_called_with(b"hid_button 2\n")

def test_route_button_custom_dispatches_no_hid(monkeypatch):
    import linapse.serial_port as sp
    sp._hid_button_bits = 0
    actions = _emu_actions({"action": "key", "value": "ctrl+z"})
    ser = MagicMock()
    mock_press = MagicMock(); mock_release = MagicMock()
    with patch("linapse.serial_port._on_press", mock_press), \
         patch("linapse.serial_port._on_release", mock_release):
        assert sp.route_button(0, 1, actions, ser) is True
        mock_press.assert_called_once_with(0, actions)
        assert sp.route_button(0, 0, actions, ser) is True
        mock_release.assert_called_once_with(0, actions)
    for c in ser.write.call_args_list:
        assert b"hid_button" not in c.args[0]

def test_route_button_emulation_off_falls_through(monkeypatch):
    import linapse.serial_port as sp
    sp._hid_button_bits = 0
    actions = {"custom_usb": {"enabled": False}, "current_mode": "Default",
               "modes": {"Default": {"buttons": {}, "taps": {}}}}
    ser = MagicMock()
    assert sp.route_button(0, 1, actions, ser) is False
    ser.write.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd service && python -m pytest test_serial_buttons.py -k route_button -v`
Expected: FAIL with `AttributeError: module 'linapse.serial_port' has no attribute 'route_button'`.

- [ ] **Step 3: Implement `route_button`**

In `service/linapse/serial_port.py`, add `import sys` to the top imports, and after the `_rx_volume_accumulator = 0.0` line add:

```python
_hid_button_bits = 0

def route_button(btn, val, actions, ser):
    """Handle a physical button event in HID emulation mode.

    Returns True if handled here (emulation path). Returns False when emulation
    is off, so the caller can fall back to the legacy per-platform dispatch.
    """
    global _hid_button_bits
    emulation = bool((actions or {}).get("custom_usb", {}).get("enabled", False))
    if not emulation:
        return False

    mode_buttons = get_active_mode_config(actions, "buttons")
    act = mode_buttons.get(f"{btn}:1") or mode_buttons.get(str(btn)) or {}
    is_native = act.get("action") == "hid_button"
    mask = 1 << btn

    if val == 0:
        # Always clear the bit on release to avoid a stuck native button if the
        # mapping changed mid-hold.
        if _hid_button_bits & mask:
            _hid_button_bits &= ~mask
            if ser:
                ser.write(f"hid_button {_hid_button_bits}\n".encode())
        if is_native:
            state.broadcast_from_thread(f"BUTTON:{btn}:0")
        else:
            _on_release(btn, actions)
        return True

    if is_native:
        _hid_button_bits |= mask
        if ser:
            ser.write(f"hid_button {_hid_button_bits}\n".encode())
        state.broadcast_from_thread(f"BUTTON:{btn}:1")
    else:
        _on_press(btn, actions)
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd service && python -m pytest test_serial_buttons.py -k route_button -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add service/linapse/serial_port.py service/test_serial_buttons.py
git commit -m "feat(service): add route_button helper for emulation-mode button routing"
```

---

## Task 2: Service — wire `route_button` into the serial `BUTTON:` handler

**Files:**
- Modify: `service/linapse/serial_port.py:154-168`

- [ ] **Step 1: Replace the `BUTTON:` handler block**

Replace the existing block (currently lines ~154-168):

```python
                elif line.startswith("BUTTON:"):
                    parts = line.split(":")
                    if len(parts) == 3:
                        _, btn_str, state_str = parts
                        try:
                            btn = int(btn_str)
                            val = int(state_str)
                            import sys
                            if sys.platform in ("win32", "darwin"):
                                if val == 1:
                                    _on_press(btn, actions_ref[0])
                                else:
                                    _on_release(btn, actions_ref[0])
                        except Exception as e:
                            print(f"[serial] button parse error: {e}")
```

with:

```python
                elif line.startswith("BUTTON:"):
                    parts = line.split(":")
                    if len(parts) == 3:
                        _, btn_str, state_str = parts
                        try:
                            btn = int(btn_str)
                            val = int(state_str)
                            if not route_button(btn, val, actions_ref[0], ser):
                                # Legacy path: serial buttons drive custom actions
                                # only on Windows/macOS when emulation is off.
                                if sys.platform in ("win32", "darwin"):
                                    if val == 1:
                                        _on_press(btn, actions_ref[0])
                                    else:
                                        _on_release(btn, actions_ref[0])
                        except Exception as e:
                            print(f"[serial] button parse error: {e}")
```

- [ ] **Step 2: Verify the existing suite still passes**

Run: `cd service && python -m pytest test_serial_buttons.py -v`
Expected: PASS (existing + Task 1 tests).

- [ ] **Step 3: Commit**

```bash
git add service/linapse/serial_port.py
git commit -m "feat(service): route serial BUTTON events through route_button"
```

---

## Task 3: Service — emit `service_buttons` on connect and on toggle

**Files:**
- Modify: `service/linapse/serial_port.py` (the `serial_thread` while-loop, near the `last_invert_z` sync)

- [ ] **Step 1: Initialize the tracker**

Find `last_invert_z = None` (just before the inner `while True:` loop) and add a line after it:

```python
            last_invert_z = None
            last_custom_usb = None
```

- [ ] **Step 2: Add the transition sync**

Immediately after the existing `invert_tap_z` sync block (the `if last_invert_z is None ...` block inside the loop), add:

```python
                # Tell the firmware to suppress local native button emission while
                # HID emulation is on; the service drives buttons via hid_button.
                custom_usb = actions.get("custom_usb", {}) if actions else {}
                current_custom_usb = bool(custom_usb.get("enabled", False))
                if last_custom_usb is None or current_custom_usb != last_custom_usb:
                    last_custom_usb = current_custom_usb
                    try:
                        ser.write(b"service_buttons 1\n" if current_custom_usb
                                  else b"service_buttons 0\n")
                    except Exception as e:
                        print(f"[serial] failed to write service_buttons: {e}")
```

- [ ] **Step 3: Write the transition test**

Append to `service/test_serial_buttons.py`:

```python
def test_service_buttons_transition_logic():
    # Mirrors the serial_thread transition guard.
    writes = []
    def emit(current, last):
        if last is None or current != last:
            writes.append(b"service_buttons 1\n" if current else b"service_buttons 0\n")
            return current
        return last
    last = None
    last = emit(True, last)   # enable
    last = emit(True, last)   # no change
    last = emit(False, last)  # disable
    assert writes == [b"service_buttons 1\n", b"service_buttons 0\n"]
```

- [ ] **Step 4: Run the test**

Run: `cd service && python -m pytest test_serial_buttons.py -k service_buttons_transition -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add service/linapse/serial_port.py service/test_serial_buttons.py
git commit -m "feat(service): emit service_buttons on emulation enable/disable"
```

---

## Task 4: Service — `hid_thread` skips button dispatch in emulation mode

**Files:**
- Modify: `service/linapse/hid.py:167-180`
- Test: `service/test_serial_buttons.py`

- [ ] **Step 1: Write the failing test**

Append to `service/test_serial_buttons.py`:

```python
def test_hid_thread_skip_guard():
    # The guard expression used inside hid_thread to ignore service-driven
    # native reports when emulation is on.
    def should_skip(actions):
        return bool((actions or {}).get("custom_usb", {}).get("enabled", False))
    assert should_skip({"custom_usb": {"enabled": True}}) is True
    assert should_skip({"custom_usb": {"enabled": False}}) is False
    assert should_skip({}) is False
    assert should_skip(None) is False
```

- [ ] **Step 2: Run it (passes trivially; it documents the guard contract)**

Run: `cd service && python -m pytest test_serial_buttons.py -k hid_thread_skip_guard -v`
Expected: PASS.

- [ ] **Step 3: Add the skip guard in `hid_thread`**

In `service/linapse/hid.py`, inside the `while True:` report loop, after the `bits = data[1] & 0x03` / `if bits == prev_bits: continue` lines and before the `for btn in range(2):` dispatch loop, insert:

```python
                    # In HID emulation mode the serial BUTTON path is the sole
                    # button source; ignore reports here (they are service-driven
                    # native echoes and would double-dispatch).
                    if bool((actions_ref[0] or {}).get("custom_usb", {}).get("enabled", False)):
                        prev_bits = bits
                        continue
```

- [ ] **Step 4: Run the full button suite**

Run: `cd service && python -m pytest test_serial_buttons.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add service/linapse/hid.py service/test_serial_buttons.py
git commit -m "feat(service): hid_thread ignores button reports in emulation mode"
```

---

## Task 5: Service — `dispatch()` ignores `hid_button` defensively

**Files:**
- Modify: `service/linapse/emulation.py:171`

- [ ] **Step 1: Add the explicit no-op branch**

In `dispatch()`, change:

```python
    if act == "none":
        pass
```

to:

```python
    if act == "none":
        pass
    elif act == "hid_button":
        # Native HID passthrough is handled in serial_port.route_button; it must
        # never reach OS-level dispatch.
        pass
```

- [ ] **Step 2: Verify nothing regressed**

Run: `cd service && python -m pytest test_serial_buttons.py -v`
Expected: PASS.

- [ ] **Step 3: Commit**

```bash
git add service/linapse/emulation.py
git commit -m "feat(service): dispatch ignores hid_button action"
```

---

## Task 6: Firmware — add `g_serviceButtonMode` global + externs

**Files:**
- Modify: `firmware/include/Controllers.h:21`
- Modify: `firmware/src/main.cpp:31`
- Modify: `firmware/test/mocks/Controllers.h:21`
- Modify: `firmware/test/test_firmware/test_main.cpp:24`

- [ ] **Step 1: Add the extern in the real header**

In `firmware/include/Controllers.h`, after `extern bool g_serviceHidMode;` add:

```cpp
extern bool g_serviceButtonMode;
```

- [ ] **Step 2: Add the extern in the mock header**

In `firmware/test/mocks/Controllers.h`, after `extern bool g_serviceHidMode;` add:

```cpp
extern bool g_serviceButtonMode;
```

- [ ] **Step 3: Define it in main.cpp**

In `firmware/src/main.cpp`, after `bool g_serviceHidMode = false;` add:

```cpp
bool g_serviceButtonMode = false;
```

- [ ] **Step 4: Define it in the test harness**

In `firmware/test/test_firmware/test_main.cpp`, after `bool g_serviceHidMode = false;` add:

```cpp
bool g_serviceButtonMode = false;
```

- [ ] **Step 5: Commit**

```bash
git add firmware/include/Controllers.h firmware/test/mocks/Controllers.h firmware/src/main.cpp firmware/test/test_firmware/test_main.cpp
git commit -m "feat(firmware): add g_serviceButtonMode global"
```

---

## Task 7: Firmware — extract the HID/service command family into `HidSerialCommand`

**Files:**
- Create: `firmware/include/HidSerialCommand.h`
- Create: `firmware/src/HidSerialCommand.cpp`
- Modify: `platformio.ini` (native `build_src_filter`)
- Modify: `firmware/src/main.cpp` (`handleSerial` — call the new function, remove old inline blocks)

- [ ] **Step 1: Create the header**

Create `firmware/include/HidSerialCommand.h`:

```cpp
#pragma once

#include <Arduino.h>

#include "controllers/HIDController.h"

// Parses the HID/service command family:
//   service_hid <0|1>
//   service_buttons <0|1>
//   hid_button <bits>
//   hid_report <f0,f1,f2,f3,f4,f5>
//
// Mutates g_serviceHidMode / g_serviceButtonMode / g_lastServicePacketMs and
// drives `hid` as required, printing an OK/ERR response over Serial. Returns
// true if the line belonged to this family (handled), false otherwise.
bool handleHidSerialCommand(const String& line, HIDController& hid);
```

- [ ] **Step 2: Create the implementation**

Create `firmware/src/HidSerialCommand.cpp`:

```cpp
#include "HidSerialCommand.h"

#include <stdlib.h>

extern bool g_serviceHidMode;
extern bool g_serviceButtonMode;
extern unsigned long g_lastServicePacketMs;

bool handleHidSerialCommand(const String& line, HIDController& hid) {
  if (line.startsWith("service_hid ")) {
    int val = atoi(line.c_str() + 12);
    g_serviceHidMode = (val != 0);
    g_lastServicePacketMs = millis();
    Serial.println("OK");
    return true;
  }

  if (line.startsWith("service_buttons ")) {
    int val = atoi(line.c_str() + 16);
    g_serviceButtonMode = (val != 0);
    g_lastServicePacketMs = millis();
    if (g_serviceButtonMode) {
      // Clear any stuck native bit on entry; the service drives buttons now.
      hid.sendButtonsReport(0);
    }
    Serial.println("OK");
    return true;
  }

  if (line.startsWith("hid_button ")) {
    g_lastServicePacketMs = millis();
    const char* p = line.c_str() + 11;
    char* next;
    long bits = strtol(p, &next, 10);
    if (p == next) {
      Serial.println("ERR hid_button requires integer bits");
      return true;
    }
    hid.sendButtonsReport((uint16_t)(bits & 0x0003));
    Serial.println("OK");
    return true;
  }

  if (line.startsWith("hid_report ")) {
    g_lastServicePacketMs = millis();
    const char* p = line.c_str() + 11;
    float motion[6] = {0};
    int parsed = 0;
    for (int i = 0; i < 6; i++) {
      while (*p == ' ') p++;
      if (*p == '\0') break;
      char* nx;
      float v = strtof(p, &nx);
      if (p == nx) break;
      motion[i] = v;
      parsed++;
      p = nx;
      while (*p == ' ' || *p == ',') p++;
    }
    if (parsed == 6) {
      hid.sendAxesReport(motion);
      Serial.println("OK");
    } else {
      Serial.println("ERR hid_report requires 6 comma-separated floats");
    }
    return true;
  }

  return false;
}
```

- [ ] **Step 3: Add the file to the native build**

In `platformio.ini`, under `[env:native]` `build_src_filter`, add a line after `+<states/SleepState.cpp>`:

```
	+<HidSerialCommand.cpp>
```

- [ ] **Step 4: Rewire `main.cpp` `handleSerial` and remove the old inline blocks**

In `firmware/src/main.cpp`:

(a) Add the include near the top with the other includes:

```cpp
#include "HidSerialCommand.h"
```

(b) In `handleSerial()`, change the dispatch chain. Replace:

```cpp
      serialBuf.trim();
      if      (serialBuf.startsWith("led "))    handleLedCommand(serialBuf.substring(4));
      else if (serialBuf.startsWith("config ")) handleConfigCommand(serialBuf.substring(7));
      else if (serialBuf.startsWith("sens "))   handleSensCommand(serialBuf.substring(5));
      else if (serialBuf.startsWith("debug "))  handleDebugCommand(serialBuf.substring(6));
      else if (serialBuf == "version")          { Serial.println("version=2.16.8"); }
      else if (serialBuf.startsWith("service_hid ")) {
```

with:

```cpp
      serialBuf.trim();
      if      (handleHidSerialCommand(serialBuf, hidController)) { /* handled */ }
      else if (serialBuf.startsWith("led "))    handleLedCommand(serialBuf.substring(4));
      else if (serialBuf.startsWith("config ")) handleConfigCommand(serialBuf.substring(7));
      else if (serialBuf.startsWith("sens "))   handleSensCommand(serialBuf.substring(5));
      else if (serialBuf.startsWith("debug "))  handleDebugCommand(serialBuf.substring(6));
      else if (serialBuf == "version")          { Serial.println("version=2.18.0"); }
      else if (serialBuf.startsWith("volume ")) {
```

Then **delete** the two now-duplicated inline blocks that previously handled `service_hid ` and `hid_report ` (the `else if (serialBuf.startsWith("service_hid ")) { ... }` and `else if (serialBuf.startsWith("hid_report ")) { ... }` blocks). The `volume ` branch that previously followed them is now reached directly from the `version` branch above. Verify the resulting chain reads: `... version ... → volume → eq → (end)`.

- [ ] **Step 5: Build the firmware to confirm it compiles**

Run: `pio run -e seeed_xiao_rp2040`
Expected: SUCCESS (`Building .pio/build/.../firmware.uf2` / no errors). If the toolchain is unavailable locally, note that and rely on CI.

- [ ] **Step 6: Commit**

```bash
git add firmware/include/HidSerialCommand.h firmware/src/HidSerialCommand.cpp platformio.ini firmware/src/main.cpp
git commit -m "refactor(firmware): extract HID serial command family into testable unit"
```

---

## Task 8: Firmware — unit-test the serial handler (the new commands + regression)

**Files:**
- Modify: `firmware/test/test_firmware/test_main.cpp`

- [ ] **Step 1: Include the header and reset globals in setUp**

In `firmware/test/test_firmware/test_main.cpp`:

(a) Add to the includes:

```cpp
#include "HidSerialCommand.h"
```

(b) In `setUp()`, reset the service globals so tests are independent. Add at the end of `setUp()`:

```cpp
    g_serviceHidMode = false;
    g_serviceButtonMode = false;
    g_lastServicePacketMs = 0;
    hidController.lastSentButtons_ = 0;
```

- [ ] **Step 2: Write the failing tests**

Add this test section (before the `setup()`/`main` runner block at the bottom of the file):

```cpp
// ── HID serial command handler tests ─────────────────────────────────────────

void test_service_buttons_enables_and_clears() {
    hidController.lastSentButtons_ = 3;  // pretend a bit is stuck
    bool handled = handleHidSerialCommand(String("service_buttons 1"), hidController);
    TEST_ASSERT_TRUE(handled);
    TEST_ASSERT_TRUE(g_serviceButtonMode);
    TEST_ASSERT_EQUAL_UINT16(0, hidController.lastSentButtons_);  // cleared on entry
}

void test_service_buttons_disables() {
    g_serviceButtonMode = true;
    bool handled = handleHidSerialCommand(String("service_buttons 0"), hidController);
    TEST_ASSERT_TRUE(handled);
    TEST_ASSERT_FALSE(g_serviceButtonMode);
}

void test_hid_button_drives_report() {
    bool handled = handleHidSerialCommand(String("hid_button 3"), hidController);
    TEST_ASSERT_TRUE(handled);
    TEST_ASSERT_EQUAL_UINT16(3, hidController.lastSentButtons_);

    handleHidSerialCommand(String("hid_button 2"), hidController);
    TEST_ASSERT_EQUAL_UINT16(2, hidController.lastSentButtons_);
}

void test_hid_button_masks_to_two_bits() {
    handleHidSerialCommand(String("hid_button 255"), hidController);
    TEST_ASSERT_EQUAL_UINT16(3, hidController.lastSentButtons_);
}

void test_hid_button_bad_arg_does_not_change_report() {
    hidController.lastSentButtons_ = 1;
    bool handled = handleHidSerialCommand(String("hid_button x"), hidController);
    TEST_ASSERT_TRUE(handled);  // recognized command, just bad arg
    TEST_ASSERT_EQUAL_UINT16(1, hidController.lastSentButtons_);
}

void test_service_hid_still_handled_after_extraction() {
    bool handled = handleHidSerialCommand(String("service_hid 1"), hidController);
    TEST_ASSERT_TRUE(handled);
    TEST_ASSERT_TRUE(g_serviceHidMode);
}

void test_non_hid_command_not_handled() {
    bool handled = handleHidSerialCommand(String("led brightness 5"), hidController);
    TEST_ASSERT_FALSE(handled);
}

void test_hid_report_drives_axes() {
    bool handled = handleHidSerialCommand(String("hid_report 1,2,3,4,5,6"), hidController);
    TEST_ASSERT_TRUE(handled);
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, 1.0f, hidController.lastSentMotion_[0]);
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, 6.0f, hidController.lastSentMotion_[5]);
}
```

- [ ] **Step 3: Register the tests in the runner**

In the `setup()` runner block (where `RUN_TEST(...)` calls live), add:

```cpp
    RUN_TEST(test_service_buttons_enables_and_clears);
    RUN_TEST(test_service_buttons_disables);
    RUN_TEST(test_hid_button_drives_report);
    RUN_TEST(test_hid_button_masks_to_two_bits);
    RUN_TEST(test_hid_button_bad_arg_does_not_change_report);
    RUN_TEST(test_service_hid_still_handled_after_extraction);
    RUN_TEST(test_non_hid_command_not_handled);
    RUN_TEST(test_hid_report_drives_axes);
```

- [ ] **Step 4: Run the native test suite — verify it fails first if run before Task 7, else passes**

Run: `pio test -e native`
Expected: PASS, including the 8 new tests. (If `pio` is unavailable locally, note it and rely on CI; the tests are self-contained against the mock `HIDController`.)

- [ ] **Step 5: Commit**

```bash
git add firmware/test/test_firmware/test_main.cpp
git commit -m "test(firmware): cover service_buttons/hid_button serial commands"
```

---

## Task 9: Firmware — suppress local button emission in emulation mode

**Files:**
- Modify: `firmware/src/states/IdleState.cpp:69-74`

- [ ] **Step 1: Update the emission branch**

In `runMotionPipeline()`, replace:

```cpp
  bool hidReportSent = false;
  if (g_serviceHidMode) {
    hidReportSent = hidController.sendButtonsReport(buttonBits);
  } else {
    hidReportSent = hidController.sendReports(motion, buttonBits);
  }
```

with:

```cpp
  bool hidReportSent = false;
  if (g_serviceHidMode) {
    // In emulation mode the service drives buttons via hid_button; suppress the
    // local native button report to avoid double-firing.
    if (!g_serviceButtonMode) {
      hidReportSent = hidController.sendButtonsReport(buttonBits);
    }
  } else {
    hidReportSent = hidController.sendReports(motion, buttonBits);
  }
```

- [ ] **Step 2: Build native (IdleState is compiled in the native suite)**

Run: `pio test -e native`
Expected: PASS (no regressions; `g_serviceButtonMode` resolves via the test global).

- [ ] **Step 3: Commit**

```bash
git add firmware/src/states/IdleState.cpp
git commit -m "feat(firmware): suppress local button HID when service drives buttons"
```

---

## Task 10: Configurator — "Native HID Button" action type

**Files:**
- Modify: `configurator/index.html` (`ACTION_TYPES`, `renderActionEditor`, `renderSubFields`, `collectAction`, `renderBtnPanel` call sites)

- [ ] **Step 1: Add the action type**

In `ACTION_TYPES` (around line 1636), add an entry after `{ id: 'none', label: 'None' },`:

```javascript
  { id: 'hid_button',  label: 'Native HID Button' },
```

- [ ] **Step 2: Filter the chip to single-press button slots**

Change `renderActionEditor`'s signature and chip loop. Replace:

```javascript
function renderActionEditor(act, container, onSave) {
```

with:

```javascript
function renderActionEditor(act, container, onSave, allowHidButton = false) {
```

and replace the `ACTION_TYPES.forEach(...)` loop opener:

```javascript
  ACTION_TYPES.forEach(({ id, label }) => {
```

with:

```javascript
  ACTION_TYPES.forEach(({ id, label }) => {
    if (id === 'hid_button' && !allowHidButton) return;
```

- [ ] **Step 3: Render no sub-fields for `hid_button`**

In `renderSubFields`, after the `if (type === 'none') { return; }` line, add:

```javascript
  if (type === 'hid_button') {
    area.innerHTML = `
      <div class="field-group">
        <div style="font-size: 11px; color: var(--text3); line-height: 1.4; font-family: sans-serif;">
          Passes this button straight through to the device's native USB HID button
          (for 3DxWare / Fusion native and other drivers). Only active in HID Emulation mode.
        </div>
      </div>`;
    return;
  }
```

- [ ] **Step 4: Collect the action**

In `collectAction`, after `if (type === 'none')        return { action: 'none' };` add:

```javascript
  if (type === 'hid_button')  return { action: 'hid_button' };
```

- [ ] **Step 5: Pass `allowHidButton` from the single-press button slots only**

In `renderBtnPanel`, the two `renderActionEditor(...)` calls for `btnKey` `0`/`1` must allow it only when `currentCount === 1`. Update the count-tab handler call (around line 2179):

```javascript
        renderActionEditor(act, editorArea, (newAct) => {
          getActiveMode().buttons[fullKey] = newAct;
          if (currentCount === 1) {
            delete getActiveMode().buttons[btnKey];
          }
        }, currentCount === 1);
```

and the initial render call (around line 2223):

```javascript
  renderActionEditor(act, editorArea, (newAct) => {
    getActiveMode().buttons[fullKey] = newAct;
    if (currentCount === 1) {
      delete getActiveMode().buttons[btnKey];
    }
  }, currentCount === 1);
```

Leave the chord call (line ~2152) and both tap calls (lines ~2250, ~2284) unchanged — they default `allowHidButton` to `false`, so the chip stays hidden there.

- [ ] **Step 6: Manually verify in a browser**

Run: open `configurator/index.html` (or the packaged app). Click button 0 at `1×` → "Native HID Button" chip appears; select it, Apply, confirm the live config shows `"0": {"action": "hid_button"}`. Click a tap callout or the `2×` tab → chip is absent.

- [ ] **Step 7: Commit**

```bash
git add configurator/index.html
git commit -m "feat(configurator): add Native HID Button action for single-press buttons"
```

---

## Task 11: Docs — rewrite the Windows "Physical Buttons" bullet

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Replace the bullet**

Find the "How It Works on Windows" → "Physical Buttons" bullet:

```markdown
*   **Physical Buttons** are handled as standard USB HID mouse buttons directly from the device's hardware, meaning they do not pass through the host service for custom mapping.
```

Replace with:

```markdown
*   **Physical Buttons** are sent over USB Serial to `linapse-service.exe`, just like Cap-Tap gestures, so they can be custom-mapped. When HID Emulation is enabled, a button left as **Native HID Button** is echoed back to the device's hardware to emit the real USB HID button press, so drivers like 3DxWare pick it up; any other mapping runs the custom action instead.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: describe service-routed buttons with native HID passthrough"
```

---

## Task 12: Version + changelog bump

**Files:**
- Modify: `VERSION`
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Bump VERSION**

Set `VERSION` file contents to:

```
2.18.0
```

- [ ] **Step 2: Add a changelog entry**

In `CHANGELOG.md`, add above the `## [2.17.0] - 2026-06-22` heading:

```markdown
## [2.18.0] - 2026-06-22

### Added
- **Remappable Buttons in HID Emulation Mode**: Physical buttons now route through the service in HID emulation mode (`custom_usb.enabled`) like Cap-Tap gestures, so they can be custom-mapped. A new **Native HID Button** action passes a button straight through to the device's USB HID button (echoed back to the firmware via a new `hid_button` serial command) for drivers like 3DxWare; any other mapping runs the custom action. New firmware `service_buttons`/`hid_button` serial commands and a `g_serviceButtonMode` flag suppress local native button emission while the service drives buttons.

### Changed
- Extracted the firmware HID/service serial command family into a unit-tested `HidSerialCommand` module.
```

- [ ] **Step 3: Confirm the version string matches the firmware**

Verify `firmware/src/main.cpp` `version=` string reads `2.18.0` (set in Task 7, Step 4).

- [ ] **Step 4: Commit**

```bash
git add VERSION CHANGELOG.md
git commit -m "chore: bump version to 2.18.0"
```

---

## Final verification

- [ ] **Run the full service suite**

Run: `cd service && python -m pytest -q`
Expected: PASS (no regressions across the service tests).

- [ ] **Run the firmware native suite**

Run: `pio test -e native`
Expected: PASS, including the new serial-handler tests. (If unavailable locally, rely on CI.)

- [ ] **Build the device firmware**

Run: `pio run -e seeed_xiao_rp2040`
Expected: SUCCESS.

- [ ] **Manual hardware smoke test (with device)**

  1. Flash firmware; enable HID Emulation with a custom VID/PID in the configurator.
  2. Map button 0 → "Native HID Button", button 1 → a key combo.
  3. Confirm button 0 reaches 3DxWare/native software as the device button; button 1 fires the key combo and does **not** double-fire a native button.
  4. Disable HID Emulation; confirm legacy behavior returns.

---

## Notes / accepted tradeoff

If the service process dies while HID Emulation is on, native buttons go dead (firmware suppresses local emission and receives no `hid_button` commands) until the service restarts and re-sends `service_buttons 1`. Recovery is automatic on service restart. This was an explicit design decision (no short-timeout auto-revert for buttons, unlike `service_hid` motion).
