#pragma once

#include <Arduino.h>

enum class LedEffect : uint8_t {
  Solid         = 0,
  Breathing     = 1,
  Reactive      = 2,  // dims when idle, brightens on motion
  DotSwirl      = 3,  // single LED orbiting the ring
  GradientSwirl = 4,  // comet with fading trail
  RainbowSwirl  = 5,  // full rainbow rotating around ring
  Volume        = 6,  // show volume 0-100% on LEDs 1-8
  kCount
};

// Runtime LED configuration, persisted to flash via EEPROM emulation.
// Serial commands:
//   led show                    — print current settings
//   led brightness <0-255>      — set brightness
//   led color <RRGGBB>          — set idle color
//   led effect <name>           — set effect (solid/breathing/reactive/dot_swirl/gradient_swirl/rainbow_swirl)
//   led reset                   — restore firmware defaults
//   config get                  — dump all config as JSON
class LedConfig {
 public:
  uint8_t   brightness;
  uint32_t  idleColor;
  LedEffect effect;

  void load();
  void save();
  void reset();
};

extern LedConfig ledConfig;
