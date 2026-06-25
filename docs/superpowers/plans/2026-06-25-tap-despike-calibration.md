# Tap De-spike + Calibration Wizard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop taps from jolting motion by replacing the tap-time translation-zeroing with an always-on per-axis de-spike, exposed as tunable Tap-tab sliders + a checkbox to revert, plus a calibration wizard that auto-tunes de-spike, sensitivity, and inversion while showing the 2D top-down preview.

**Architecture:** Tap detection stays on raw data (unchanged) so taps still register. A new per-axis spike clamp runs every frame on `motion[6]` in `IdleState`. Three EEPROM-backed params (`despikeEnabled/Threshold/Strength`) flow over the existing `sens set …` serial protocol and telemetry JSON. The configurator gains Tap-tab controls and a wizard that measures live motion via the existing `MOTION:` WebSocket broadcast.

**Tech Stack:** C++ (Arduino/RP2040, PlatformIO), native unit tests (`pio test -e native`), vanilla JS configurator (`configurator/index.html`), WebSocket telemetry.

## Global Constraints

- Spec: [docs/superpowers/specs/2026-06-25-tap-despike-calibration-design.md](2026-06-25-tap-despike-calibration-design.md). (verbatim source of truth)
- Do NOT change tap detection (`TapDetector`) — it must keep running on raw data before filtering.
- `despikeEnabled` default **true**; when false, keep today's `isTapping()` translation-zeroing exactly.
- New EEPROM addresses must not overlap existing ones (`kAddrTapSens = kBase+24`, `kAddrInvTapZ = kBase+28` are the current highest — start new fields at `kBase+32`).
- Telemetry JSON is emitted in **two** places in `main.cpp` (lines ~124 and ~151) — update both.
- `sens set` params are parsed in `main.cpp` (~line 179, the `else if (param == …)` chain), NOT in `HidSerialCommand.cpp`.
- Configurator: wire new controls through the existing `onSensChange`/`sens set` path and sync from telemetry in `applyDeviceConfig`. No new dependencies.
- Do NOT reflash hardware in this plan (user constraint). Validate firmware via native tests; validate UI via the preview.
- Release as part of **2.26.0** (bundled with the macro fix) — version bump handled at release time, not in these tasks.

---

### Task 1: De-spike config fields (SensConfig + Config defaults)

**Files:**
- Modify: `firmware/src/SensConfig.h` (add fields + accessor)
- Modify: `firmware/src/SensConfig.cpp` (EEPROM addrs, load/save/resetDefaults)
- Modify: firmware Config header (the one defining `Config::TAP_VELOCITY_THRESHOLD`; `grep -rl TAP_VELOCITY_THRESHOLD firmware/src`) — add defaults

**Interfaces:**
- Produces: `sensConfig.despikeEnabled` (bool), `sensConfig.despikeThreshold` (float), `sensConfig.despikeStrength` (float); `Config::DESPIKE_THRESHOLD_DEFAULT`, `Config::DESPIKE_STRENGTH_DEFAULT`.

- [ ] **Step 1:** In the Config header, beside the `TAP_*` constants add:
```cpp
constexpr float DESPIKE_THRESHOLD_DEFAULT = 40.0f;  // per-axis frame-delta clamp onset; tune on hardware
constexpr float DESPIKE_STRENGTH_DEFAULT  = 1.0f;   // 0 = off, 1 = full clamp
```
- [ ] **Step 2:** In `SensConfig.h`, add public fields next to `tapThreshold`:
```cpp
bool  despikeEnabled;
float despikeThreshold;
float despikeStrength;
```
- [ ] **Step 3:** In `SensConfig.cpp`, add EEPROM addresses after `kAddrInvTapZ`:
```cpp
constexpr int kAddrDespikeEnabled   = kBase + 32;
constexpr int kAddrDespikeThreshold = kBase + 36;
constexpr int kAddrDespikeStrength  = kBase + 40;
```
- [ ] **Step 4:** In `load()`, after the existing `EEPROM.get(kAddrInvTapZ, invertTapZ);`:
```cpp
EEPROM.get(kAddrDespikeEnabled,   despikeEnabled);
EEPROM.get(kAddrDespikeThreshold, despikeThreshold);
EEPROM.get(kAddrDespikeStrength,  despikeStrength);
```
- [ ] **Step 5:** In `save()`, after `EEPROM.put(kAddrInvTapZ, invertTapZ);`:
```cpp
EEPROM.put(kAddrDespikeEnabled,   despikeEnabled);
EEPROM.put(kAddrDespikeThreshold, despikeThreshold);
EEPROM.put(kAddrDespikeStrength,  despikeStrength);
```
- [ ] **Step 6:** In `resetDefaults()`, after `invertTapZ = false;`:
```cpp
despikeEnabled   = true;
despikeThreshold = Config::DESPIKE_THRESHOLD_DEFAULT;
despikeStrength  = Config::DESPIKE_STRENGTH_DEFAULT;
```
- [ ] **Step 7:** Build native to confirm it compiles: `~/.platformio/penv/bin/pio test -e native` (expected: existing tests still pass / compile clean).
- [ ] **Step 8:** Commit:
```bash
git add firmware/src/SensConfig.* firmware/src/Config.h
git commit -m "feat(firmware): add despike config fields (enabled/threshold/strength)"
```

---

### Task 2: De-spike clamp helper + native test

**Files:**
- Create: `firmware/src/controllers/Despike.h` (pure header, testable without Arduino)
- Test: `firmware/test/test_firmware/test_main.cpp` (add cases)

**Interfaces:**
- Produces: `void despikeAxes(float motion[6], float prev[6], float threshold, float strength);` — clamps each axis's frame delta; `prev` is updated to the post-clamp values.

- [ ] **Step 1: Write the failing test** in `test_main.cpp`:
```cpp
void test_despike_passes_sustained_motion() {
  float prev[6] = {0,0,0,0,0,0};
  float m[6]    = {10,10,10,10,10,10};   // below threshold delta
  despikeAxes(m, prev, 40.0f, 1.0f);
  for (int i=0;i<6;i++) TEST_ASSERT_FLOAT_WITHIN(0.001f, 10.0f, m[i]);
}
void test_despike_clamps_spike_on_all_axes() {
  float prev[6] = {0,0,0,0,0,0};
  float m[6]    = {200,-200,200,-200,200,-200};  // huge spike, all axes
  despikeAxes(m, prev, 40.0f, 1.0f);
  for (int i=0;i<6;i++) TEST_ASSERT_TRUE(fabsf(m[i]) <= 40.0f + 0.001f);
}
void test_despike_strength_zero_is_noop() {
  float prev[6] = {0,0,0,0,0,0};
  float m[6]    = {500,0,0,0,0,0};
  despikeAxes(m, prev, 40.0f, 0.0f);
  TEST_ASSERT_FLOAT_WITHIN(0.001f, 500.0f, m[0]);
}
```
Register them with `RUN_TEST(...)` in the test runner and `#include "controllers/Despike.h"`.
- [ ] **Step 2: Run to verify it fails:** `~/.platformio/penv/bin/pio test -e native` → FAIL ("despikeAxes not declared").
- [ ] **Step 3: Implement** `firmware/src/controllers/Despike.h`:
```cpp
#pragma once
#include <math.h>

// Per-axis frame-delta clamp. A fast spike (delta > threshold) is pulled back
// toward the previous value by `strength` (0=off,1=full); sustained motion
// (delta <= threshold) passes unchanged. prev[] is updated to the output.
inline void despikeAxes(float motion[6], float prev[6], float threshold, float strength) {
  for (int i = 0; i < 6; i++) {
    float d = motion[i] - prev[i];
    float ad = fabsf(d);
    if (ad > threshold) {
      float allowed = threshold + (ad - threshold) * (1.0f - strength);
      motion[i] = prev[i] + (d > 0 ? allowed : -allowed);
    }
    prev[i] = motion[i];
  }
}
```
- [ ] **Step 4: Run to verify pass:** `~/.platformio/penv/bin/pio test -e native` → PASS.
- [ ] **Step 5: Commit:**
```bash
git add firmware/src/controllers/Despike.h firmware/test/test_firmware/test_main.cpp
git commit -m "feat(firmware): add despikeAxes clamp + native tests"
```

---

### Task 3: Apply de-spike in IdleState (gated by checkbox)

**Files:**
- Modify: `firmware/src/states/IdleState.cpp` (the `isTapping()` block ~line 45) + the IdleState class header (add `prevMotion_`)

**Interfaces:**
- Consumes: `despikeAxes(...)` (Task 2), `sensConfig.despike*` (Task 1).

- [ ] **Step 1:** In the IdleState header, add private member `float prevMotion_[6] = {0,0,0,0,0,0};` and `#include "controllers/Despike.h"`.
- [ ] **Step 2:** Replace the block at `IdleState.cpp:45-52` (`if (tapDetector.isTapping()) { motion[0..2]=0 }`) with:
```cpp
  if (sensConfig.despikeEnabled) {
    // Always-on per-axis de-spike: the tap impulse is clamped on every axis,
    // so taps don't jolt diagonal motion. Tap detection already ran on raw
    // data above, so taps still register.
    despikeAxes(motion, prevMotion_, sensConfig.despikeThreshold, sensConfig.despikeStrength);
  } else if (tapDetector.isTapping()) {
    // Legacy behavior: zero translation during a tap (rotation passes through).
    motion[0] = 0.0f; motion[1] = 0.0f; motion[2] = 0.0f;
  }
```
- [ ] **Step 3:** Build: `~/.platformio/penv/bin/pio run` (expected: compiles for device; no flash).
- [ ] **Step 4: Commit:**
```bash
git add firmware/src/states/IdleState.*
git commit -m "feat(firmware): apply always-on de-spike (checkbox reverts to legacy)"
```

---

### Task 4: Serial protocol — `sens set despike_*` + telemetry

**Files:**
- Modify: `firmware/src/main.cpp` (sens-set parse ~line 179; telemetry JSON lines ~124 and ~151 — both copies)

**Interfaces:**
- Produces: serial commands `sens set despike_enabled <0|1>`, `sens set despike_threshold <f>`, `sens set despike_strength <f>`; telemetry keys `despike_enabled`, `despike_threshold`, `despike_strength`.

- [ ] **Step 1:** In the `sens set` `else if (param == …)` chain (~line 179), add:
```cpp
    else if (param == "despike_enabled")   sensConfig.despikeEnabled  = (val > 0.5f);
    else if (param == "despike_threshold") sensConfig.despikeThreshold = val;
    else if (param == "despike_strength")  sensConfig.despikeStrength  = val;
```
(then ensure the existing `sensConfig.save()` after the chain persists them.)
- [ ] **Step 2:** In BOTH telemetry `snprintf` format strings (lines ~124 and ~151), extend the JSON before the closing `}`:
```
...,\"spring_head\":%d,\"despike_enabled\":%d,\"despike_threshold\":%.2f,\"despike_strength\":%.2f}\n"
```
and add the matching args after `sensConfig.springHead ? 1 : 0`:
```cpp
             sensConfig.springHead ? 1 : 0,
             sensConfig.despikeEnabled ? 1 : 0,
             sensConfig.despikeThreshold,
             sensConfig.despikeStrength);
```
- [ ] **Step 3:** Build: `~/.platformio/penv/bin/pio run` (compiles, no flash).
- [ ] **Step 4: Commit:**
```bash
git add firmware/src/main.cpp
git commit -m "feat(firmware): despike sens-set commands + telemetry"
```

---

### Task 5: Tap-tab controls (sliders + revert checkbox)

**Files:**
- Modify: `configurator/index.html` — inside `#sens-section-tap`; JS handlers + `applyDeviceConfig` sync

**Interfaces:**
- Consumes: telemetry keys from Task 4.
- Produces: `onDespikeThreshold(v)`, `onDespikeStrength(v)`, `onDespikeEnabled(el)` (send `sens set despike_*`); a `#despikeEnabled` checkbox, `#despikeThreshold`/`#despikeStrength` sliders.

- [ ] **Step 1:** In `#sens-section-tap`, add a field-group (mirror the existing sens slider markup):
```html
<div class="field-group">
  <div class="field-label" style="color:var(--green);letter-spacing:2px;font-size:10px;font-family:'Barlow Condensed',sans-serif">TAP DE-SPIKE</div>
  <div class="toggle-row" style="padding:4px 0;border:none">
    <span class="toggle-label">Use de-spike filter</span>
    <div class="toggle on" id="despikeEnabled" onclick="onDespikeEnabled(this)"></div>
  </div>
  <div id="despikeFields">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;margin-top:8px">
      <span class="field-label" style="margin:0">Spike Threshold</span>
      <input type="number" id="despikeThresholdVal" min="5" max="200" step="1" value="40" style="width:48px;background:var(--border2);border:1px solid var(--border);color:var(--text);font-size:10px;text-align:right;padding:1px 3px;border-radius:3px;font-family:inherit" oninput="onDespikeThreshold(this.value)">
    </div>
    <input type="range" id="despikeThreshold" min="5" max="200" step="1" value="40" oninput="onDespikeThreshold(this.value)">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:2px;margin-top:10px">
      <span class="field-label" style="margin:0">Strength</span>
      <input type="number" id="despikeStrengthVal" min="0" max="100" step="1" value="100" style="width:48px;background:var(--border2);border:1px solid var(--border);color:var(--text);font-size:10px;text-align:right;padding:1px 3px;border-radius:3px;font-family:inherit" oninput="onDespikeStrength(this.value)">
    </div>
    <input type="range" id="despikeStrength" min="0" max="100" step="1" value="100" oninput="onDespikeStrength(this.value)">
  </div>
  <button class="btn-apply" onclick="openCalibrateWizard()" style="margin-top:10px">Calibrate…</button>
</div>
```
- [ ] **Step 2:** Add JS handlers (near `onSensChange`):
```javascript
function onDespikeThreshold(v) {
  v = parseFloat(v); if (isNaN(v)) return;
  document.getElementById('despikeThreshold').value = v;
  document.getElementById('despikeThresholdVal').value = v;
  sendCmd(`sens set despike_threshold ${v}`);
}
function onDespikeStrength(v) {
  v = parseFloat(v); if (isNaN(v)) return;
  document.getElementById('despikeStrength').value = v;
  document.getElementById('despikeStrengthVal').value = v;
  sendCmd(`sens set despike_strength ${(v/100).toFixed(2)}`);  // UI 0-100 -> 0-1
}
function onDespikeEnabled(el) {
  el.classList.toggle('on');
  const on = el.classList.contains('on');
  document.getElementById('despikeFields').style.opacity = on ? '1' : '0.4';
  document.getElementById('despikeFields').style.pointerEvents = on ? '' : 'none';
  sendCmd(`sens set despike_enabled ${on ? 1 : 0}`);
}
```
- [ ] **Step 3:** In `applyDeviceConfig(cfg)`, sync from telemetry:
```javascript
if (cfg.despike_enabled !== undefined) {
  document.getElementById('despikeEnabled')?.classList.toggle('on', !!cfg.despike_enabled);
  const f = document.getElementById('despikeFields');
  if (f) { f.style.opacity = cfg.despike_enabled ? '1' : '0.4'; f.style.pointerEvents = cfg.despike_enabled ? '' : 'none'; }
}
if (cfg.despike_threshold !== undefined) {
  const t = cfg.despike_threshold;
  const s = document.getElementById('despikeThreshold'), sv = document.getElementById('despikeThresholdVal');
  if (s) s.value = t; if (sv) sv.value = Math.round(t);
}
if (cfg.despike_strength !== undefined) {
  const p = Math.round(cfg.despike_strength * 100);
  const s = document.getElementById('despikeStrength'), sv = document.getElementById('despikeStrengthVal');
  if (s) s.value = p; if (sv) sv.value = p;
}
```
- [ ] **Step 4: Verify in preview:** start the configurator preview, eval that the sliders exist, the checkbox toggles `#despikeFields` opacity, and `applyDeviceConfig({despike_threshold:80,despike_strength:0.5,despike_enabled:1})` updates the controls.
- [ ] **Step 5: Commit:**
```bash
git add configurator/index.html
git commit -m "feat(ui): Tap-tab de-spike sliders + revert checkbox"
```

---

### Task 6: Wizard scaffold (modal + 2D preview + MOTION sampler)

**Files:**
- Modify: `configurator/index.html` — wizard overlay markup + `openCalibrateWizard()`, a live MOTION sampler, embed the existing `controller2d` 2D scene.

**Interfaces:**
- Consumes: the `MOTION:x,y,z,rx,ry,rz` WS broadcast (already parsed where previews read it); `init2dScene()`/`controller2d` (existing 2D scene); `controllerStick`/`controllerAxes` feed.
- Produces: `openCalibrateWizard()`, `wizardSample()` (returns `{peakDelta[6], peakAbs[6]}` over a capture window), `wizardSetStep(n)`, a `#calibrateWizard` overlay with a `#wizard2dHost` canvas host.

- [ ] **Step 1:** Add the overlay markup (hidden by default) with a host element for the 2D canvas, a prompt area `#wizardPrompt`, a Next/Cancel footer, and a progress label. Move (or clone) the `controller2dCanvas` into `#wizard2dHost` while the wizard is open so the user sees the top-down preview; restore on close.
- [ ] **Step 2:** Implement `openCalibrateWizard()`: snapshot current config (`JSON.parse(JSON.stringify(actions))` + current despike values) for Cancel-restore, show the overlay, start the 2D scene (`init2dScene(); controller2d.start()`), set step 1.
- [ ] **Step 3:** Implement a sampler that, over a capture window (e.g. 2.5 s), tracks per-axis peak frame-delta and peak abs value from the incoming MOTION frames (hook the same place that already updates `controllerStick`/`controllerAxes`). Provide `wizardCapture(ms)` returning a Promise of `{peakDelta:[6], peakAbs:[6]}`.
- [ ] **Step 4: Verify in preview:** eval `openCalibrateWizard()` → overlay visible, 2D canvas hosted, then feed synthetic MOTION via the WS handler and confirm `wizardCapture` resolves with non-zero peaks.
- [ ] **Step 5: Commit:**
```bash
git add configurator/index.html
git commit -m "feat(ui): calibration wizard scaffold (modal + 2D preview + sampler)"
```

---

### Task 7: Wizard step 1 — de-spike calibration

**Files:** Modify `configurator/index.html` (wizard step logic).

**Interfaces:** Consumes `wizardCapture` (Task 6), `sens set despike_*` (Task 5).

- [ ] **Step 1:** Step 1a — set `sens set despike_enabled 0` (measure raw). Prompt "Hold still and tap a few times." On Next, `const tap = await wizardCapture(3000)`.
- [ ] **Step 2:** Step 1b — prompt "Move diagonally, don't tap." On Next, `const move = await wizardCapture(3000)`.
- [ ] **Step 3:** Compute: `threshold = clamp( max(move.peakDelta)*1.3 , 5, 200 )` and ensure it's below `min over tapped axes of tap.peakDelta`; `strength = 1.0`. Apply via `onDespikeThreshold`/`onDespikeStrength`, then `sens set despike_enabled 1`. Show the chosen values; the 2D preview now shows reduced jitter.
- [ ] **Step 4: Verify in preview** with synthetic high-delta "tap" samples vs low-delta "move" samples → resulting threshold sits between them; despike re-enabled.
- [ ] **Step 5: Commit:** `git commit -am "feat(ui): wizard step 1 — de-spike auto-calibrate"`

---

### Task 8: Wizard step 2 — sensitivity calibration

**Files:** Modify `configurator/index.html`.

**Interfaces:** Consumes `wizardCapture`; writes `ctrlCfg()`/`actions.sensitivity` via existing sens setters; sends `actions`.

- [ ] **Step 1:** Prompt "Move each axis through its full comfortable range." `const r = await wizardCapture(5000)`.
- [ ] **Step 2:** For each axis, set per-axis sensitivity so `peakAbs * sens ≈ AXIS_LIMIT target` (scale = target/peakAbs, clamped to the slider's [0.1,3] range). Write to the relevant config (global `sensitivity` for CAD/Mouse axes; document which axes map to which sens key, matching `serial_port.py`).
- [ ] **Step 3:** Push via `sendCmd('actions ' + JSON.stringify(actions))` (and `sens set …` if a firmware-side sens applies); refresh the sliders.
- [ ] **Step 4: Verify in preview** with synthetic ranges → computed sensitivities land in range and are clamped.
- [ ] **Step 5: Commit:** `git commit -am "feat(ui): wizard step 2 — sensitivity auto-calibrate"`

---

### Task 9: Wizard step 3 — inversion + finish (apply/cancel)

**Files:** Modify `configurator/index.html`.

**Interfaces:** Consumes `wizardCapture`; writes inversion flags (`actions.inversion` / `ctrlCfg().invert`); snapshot restore from Task 6.

- [ ] **Step 1:** Per axis pair, prompt the directed motion ("Push forward", "Tilt right", …). Capture; if the measured sign of the dominant axis is opposite to expected, set that axis's inversion flag true (else false).
- [ ] **Step 2:** Finish screen: list everything set (threshold, strength, per-axis sensitivity, inverted axes) with **Apply** (keep + `sendCmd('actions …')`, close), **Tweak** (back to step 1), **Cancel** (restore the Task-6 snapshot: `actions = snapshot`, re-send, re-sync sliders, close).
- [ ] **Step 3:** On close (any path): stop `controller2d`, restore the `controller2dCanvas` to its original parent, hide the overlay.
- [ ] **Step 4: Verify in preview:** full happy path with synthetic samples → Apply persists; Cancel restores the pre-wizard `actions`.
- [ ] **Step 5: Commit:** `git commit -am "feat(ui): wizard step 3 — inversion + apply/cancel"`

---

## Self-Review

**Spec coverage:** firmware de-spike (T2/T3) ✓; checkbox revert (T3/T5) ✓; EEPROM params (T1) ✓; sens-set + telemetry (T4) ✓; Tap-tab sliders (T5) ✓; wizard 3 steps (T7/T8/T9) ✓; 2D preview during wizard (T6) ✓; native test (T2) ✓. All spec sections mapped.

**Placeholders:** firmware code is complete and exact. Wizard tasks (6–9) give concrete steps + the measurement/compute logic but describe some DOM wiring at the step level rather than full markup, because the overlay markup mirrors existing modal patterns in `index.html` — the implementer copies an existing modal's structure. Sensitivity axis→key mapping (T8) references `serial_port.py` as the authority rather than restating it (avoids drift).

**Type consistency:** `despikeAxes(motion, prev, threshold, strength)` signature consistent T2↔T3; telemetry keys `despike_enabled/threshold/strength` consistent T4↔T5; element ids `despikeThreshold/Strength/Enabled` consistent T5↔T7.

## Open notes for the implementer

- Confirm the exact Config header path (`grep -rl TAP_VELOCITY_THRESHOLD firmware/src`) before Task 1.
- `EEPROM.get` on `bool` works via the native mock and the RP2040 EEPROM emulation; if the mock rejects `bool`, store as `uint8_t`.
- The wizard's sensitivity/inversion axis mapping must match `service/linapse/serial_port.py` so previews and gamepad agree.
