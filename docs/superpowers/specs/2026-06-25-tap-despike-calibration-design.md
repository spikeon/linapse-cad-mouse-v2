# Tap-aware input de-spike + calibration wizard

**Date:** 2026-06-25
**Status:** Draft for review

## Goal

Stop taps from jolting motion output — especially when moving diagonally. A tap
is a physical impulse that spikes the sensor; today the firmware hard-zeros only
the translation axes during a tap, so (a) the impulse bleeds into rotation and
passes through, and (b) zeroing translation mid-diagonal kills the legitimate
motion component. End goal: **taps register while moving diagonally, without
jolting** — on every axis.

## Approach (agreed)

Decouple detection from output:

- **Tap detection stays on raw data**, before filtering. It already runs there
  ([`IdleState.cpp:31`](../../../firmware/src/states/IdleState.cpp) →
  `tapDetector.update(raw, …)`), so taps still register from the spike.
- **Output gets an always-on per-axis de-spike** applied to `motion[6]`. The
  fast tap transient is clamped on all six axes; sustained intentional motion
  passes through. No tap-window logic, so no boundary jolt.

A checkbox reverts to today's behavior (translation-zeroing during `isTapping()`)
for users who prefer it.

## Firmware

### De-spike filter (`IdleState::onMotion`, replaces the zeroing block)

Add `float prevMotion_[6]` state. Each frame, after `motionController.compute`:

- If de-spike enabled: per axis `i`, `d = motion[i] - prevMotion_[i]`; if
  `|d| > despikeThreshold`, clamp the change toward the threshold, scaled by
  `despikeStrength` (0–1, how hard to clamp). Normal motion (delta ≤ threshold)
  passes untouched, so fast *intentional* flicks aren't dulled.
- If de-spike disabled: keep the current `if (tapDetector.isTapping()) { zero
  TX/TY/TZ }` path verbatim.
- Update `prevMotion_` after.

Pseudocode (final form TBD in implementation):
```
for i in 0..6:
  d = motion[i] - prevMotion_[i]
  if |d| > T: motion[i] = prevMotion_[i] + sign(d) * (T + (|d|-T)*(1-strength))
  prevMotion_[i] = motion[i]
```

### Config / protocol

New EEPROM-backed fields in `SensConfig` (mirror `tapThreshold`/`invertTapZ`
pattern: addr constant, `load`/`save`, `resetDefaults`):

- `despikeEnabled` (bool, default **true**)
- `despikeThreshold` (float, default in `Config.h`)
- `despikeStrength` (float 0–1, default in `Config.h`)

Serial commands in `HidSerialCommand` (`sens set …` family):
`despike_enabled <0|1>`, `despike_threshold <f>`, `despike_strength <f>`.

Telemetry: add the three to the `sens` JSON in `main.cpp` so the configurator
reflects current values (same place as `spring_head`, `tap_sens`).

### Test

Native `pio test -e native`: a unit test for the clamp math — a synthetic spike
gets attenuated below threshold; a sustained ramp passes unchanged; strength=0
is a no-op, strength=1 fully clamps.

## Configurator — Tap tab (`#sens-section-tap`)

Add to the existing Tap sub-tab (not a new tab):

- **Spike Threshold** slider — `sens set despike_threshold` (via `onSensChange`).
- **Strength** slider (0–100%) — `sens set despike_strength`.
- **"Use de-spike filter"** checkbox — `sens set despike_enabled`; unchecked
  reverts to the legacy translation-zeroing. Sliders disabled when unchecked.
- **Calibrate** button — launches the wizard.

Sliders/checkbox sync from the telemetry JSON like the other sens controls.

## Calibration wizard

Modal/overlay launched from the Tap tab. Reads **live 6-axis motion from the
existing `MOTION:x,y,z,rx,ry,rz` WebSocket broadcast** (already streamed to the
configurator). Shows the **2D top-down preview** (reuse the existing
`controller2d` scene/canvas) so the user sees the jitter and watches it settle as
values are applied — this is where the jitter was first visible.

Three sequential steps, each "follow the prompt → wizard measures → applies":

1. **De-spike.** Temporarily set `despike_enabled=0` to measure the raw signal.
   - "Hold still and tap a few times" → record peak frame-to-frame delta = tap
     spike magnitude.
   - "Move diagonally, don't tap" → record peak delta = normal-motion magnitude.
   - Set `despike_threshold` between the two (above motion, below spike); set
     `despike_strength` to clear the residual jolt. Re-enable.
2. **Sensitivity.** "Move each axis through its full comfortable range" → measure
   peak per axis → scale per-axis sensitivity so full physical motion maps to
   full output range.
3. **Inversion.** Per axis, "push forward / tilt right / …" (one directed motion)
   → compare measured sign to expected → flip the inversion flag when they
   disagree.

End screen: summary of the values it set, with Apply / Tweak / Cancel. Cancel
restores the pre-wizard config snapshot.

## Out of scope / assumptions

- The wizard reads the post-`compute` `MOTION` stream (the signal the de-spike
  operates on), not firmware `g_debugAxes` (`AX:` is translation-only).
- Spike clamp is a simple per-axis delta clamp; if hardware tuning shows it's
  insufficient (e.g. multi-frame spikes), revisit with a median/slew hybrid.
- No hardware feel-testing here (no device reflash); validated by the native
  clamp test + configurator preview of the UI/wizard flow.

## Touch list

- `firmware/src/states/IdleState.cpp`, `firmware/src/controllers/` (de-spike),
  `firmware/src/SensConfig.{h,cpp}`, `firmware/src/HidSerialCommand.cpp`,
  `firmware/src/main.cpp`, `firmware/src/Config.h`, `firmware/test/` (native test)
- `configurator/index.html` (Tap-tab sliders + checkbox + wizard)
