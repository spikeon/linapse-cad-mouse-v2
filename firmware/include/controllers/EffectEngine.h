#pragma once

#include <Arduino.h>
#include "LedConfig.h"

class EffectEngine {
 public:
  // Call when effect, color, or brightness changes. Resets animation state.
  void configure(LedEffect effect, uint32_t color, uint8_t brightness);

  // Call every frame from IdleState/ColorConfigState.
  // motionMag: 0.0 = idle, >0.0 = active (used by Reactive effect).
  void update(unsigned long now, float motionMag = 0.0f);

 private:
  LedEffect effect_     = LedEffect::Solid;
  uint32_t  color_      = 0xFFFFFF;
  uint8_t   brightness_ = 255;

  unsigned long lastMs_    = 0;
  float swirlPos_          = 0.0f;  // [0, 1) fraction of revolution
  float reactiveLevel_     = 0.15f; // [dim, 1.0]

  void doSolid();
  void doBreathing(unsigned long now);
  void doReactive(unsigned long now, float motionMag);
  void doDotSwirl(unsigned long now);
  void doGradientSwirl(unsigned long now);
  void doRainbowSwirl(unsigned long now);
  void doVolume();

  // Returns color scaled by factor [0..1], premultiplied with brightness_/255
  uint32_t scaledColor(float factor) const;
  // HSV → packed 0xRRGGBB; h 0–360, s & v 0–1
  static uint32_t hsvToRgb(float h, float s, float v);
};
