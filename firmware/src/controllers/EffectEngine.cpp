#include "controllers/EffectEngine.h"
#include "controllers/LEDController.h"
#include "Config.h"
#include <math.h>

extern LEDController ledController;

void EffectEngine::configure(LedEffect effect, uint32_t color, uint8_t brightness) {
  effect_     = effect;
  color_      = color;
  brightness_ = brightness;
  swirlPos_   = 0.0f;
  lastMs_     = 0;
  // Don't reset reactiveLevel_ — abrupt jump on effect switch looks bad
}

void EffectEngine::update(unsigned long now, float motionMag) {
  switch (effect_) {
    case LedEffect::Solid:         doSolid();                      break;
    case LedEffect::Breathing:     doBreathing(now);               break;
    case LedEffect::Reactive:      doReactive(now, motionMag);     break;
    case LedEffect::DotSwirl:      doDotSwirl(now);                break;
    case LedEffect::GradientSwirl: doGradientSwirl(now);           break;
    case LedEffect::RainbowSwirl:  doRainbowSwirl(now);            break;
    case LedEffect::Volume:        doVolume();                     break;
    default:                       doSolid();                      break;
  }
  lastMs_ = now;
}

// ── Effect implementations ────────────────────────────────────────────────────

void EffectEngine::doSolid() {
  uint32_t c = scaledColor(1.0f);
  ledController.effectBegin();
  for (int i = 0; i < ledController.numPixels(); i++) {
    ledController.effectPixel(i, c);
  }
  ledController.effectCommit();
}

void EffectEngine::doBreathing(unsigned long now) {
  const unsigned long periodMs = (unsigned long)(1000.0f / Config::EFFECT_BREATHE_SPEED);
  const float t    = (now % periodMs) / (float)periodMs;
  const float sine = (sinf(t * 2.0f * (float)M_PI - (float)M_PI / 2.0f) + 1.0f) / 2.0f;
  const float factor = 0.2f + 0.8f * cbrtf(sine);  // 20% min, cbrtf skews bright

  uint32_t c = scaledColor(factor);
  ledController.effectBegin();
  for (int i = 0; i < ledController.numPixels(); i++) {
    ledController.effectPixel(i, c);
  }
  ledController.effectCommit();
}

void EffectEngine::doReactive(unsigned long now, float motionMag) {
  float dt = (lastMs_ == 0) ? 0.0f : (now - lastMs_) / 1000.0f;
  dt = (dt > 0.1f) ? 0.1f : dt;  // cap to avoid large jumps on first frame

  float target = (motionMag > 0.0f) ? 1.0f : Config::EFFECT_REACTIVE_DIM;
  float rate   = (motionMag > 0.0f) ? Config::EFFECT_REACTIVE_RISE : Config::EFFECT_REACTIVE_FALL;
  reactiveLevel_ += (target - reactiveLevel_) * rate * dt;
  if (reactiveLevel_ < Config::EFFECT_REACTIVE_DIM) reactiveLevel_ = Config::EFFECT_REACTIVE_DIM;
  if (reactiveLevel_ > 1.0f) reactiveLevel_ = 1.0f;

  uint32_t c = scaledColor(reactiveLevel_);
  ledController.effectBegin();
  for (int i = 0; i < ledController.numPixels(); i++) {
    ledController.effectPixel(i, c);
  }
  ledController.effectCommit();
}

void EffectEngine::doDotSwirl(unsigned long now) {
  float dt = (lastMs_ == 0) ? 0.0f : (now - lastMs_) / 1000.0f;
  swirlPos_ += dt * Config::EFFECT_SWIRL_SPEED;
  if (swirlPos_ >= 1.0f) swirlPos_ -= 1.0f;

  const int n   = ledController.numPixels();
  const int lit = (int)(swirlPos_ * n) % n;
  uint32_t c = scaledColor(1.0f);

  ledController.effectBegin();
  for (int i = 0; i < n; i++) {
    ledController.effectPixel(i, (i == lit) ? c : 0);
  }
  ledController.effectCommit();
}

void EffectEngine::doGradientSwirl(unsigned long now) {
  float dt = (lastMs_ == 0) ? 0.0f : (now - lastMs_) / 1000.0f;
  swirlPos_ += dt * Config::EFFECT_SWIRL_SPEED;
  if (swirlPos_ >= 1.0f) swirlPos_ -= 1.0f;

  const int n    = ledController.numPixels();
  const int head = (int)(swirlPos_ * n) % n;
  const int trail = 4;  // trailing LEDs

  ledController.effectBegin();
  for (int i = 0; i < n; i++) {
    int dist = (head - i + n) % n;
    float factor = 0.0f;
    if (dist == 0) {
      factor = 1.0f;
    } else if (dist <= trail) {
      float t = 1.0f - (float)dist / (float)(trail + 1);
      factor = t * t;  // quadratic fade
    }
    ledController.effectPixel(i, scaledColor(factor));
  }
  ledController.effectCommit();
}

void EffectEngine::doRainbowSwirl(unsigned long now) {
  float dt = (lastMs_ == 0) ? 0.0f : (now - lastMs_) / 1000.0f;
  swirlPos_ += dt * Config::EFFECT_SWIRL_SPEED;
  if (swirlPos_ >= 1.0f) swirlPos_ -= 1.0f;

  const int   n = ledController.numPixels();
  const float v = brightness_ / 255.0f;

  ledController.effectBegin();
  for (int i = 0; i < n; i++) {
    float hue = fmodf((swirlPos_ + (float)i / n) * 360.0f, 360.0f);
    ledController.effectPixel(i, hsvToRgb(hue, 1.0f, v));
  }
  ledController.effectCommit();
}

void EffectEngine::doVolume() {
  extern int g_currentVolume;
  float vol = (float)g_currentVolume;
  if (vol < 0.0f) vol = 0.0f;
  if (vol > 100.0f) vol = 100.0f;

  float active_leds = (vol / 100.0f) * 8.0f;
  const int n = ledController.numPixels();

  ledController.effectBegin();
  for (int i = 0; i < n; i++) {
    float factor = 0.0f;
    if (active_leds >= (float)(i + 1)) {
      factor = 1.0f;
    } else if (active_leds > (float)i) {
      factor = active_leds - (float)i;
    } else {
      factor = 0.0f;
    }
    ledController.effectPixel(i, scaledColor(factor));
  }
  ledController.effectCommit();
}

// ── Helpers ───────────────────────────────────────────────────────────────────

uint32_t EffectEngine::scaledColor(float factor) const {
  float scale = factor * (brightness_ / 255.0f);
  // sRGB gamma decode. R uses 1.8 (SK6812 red LED is less efficient vs green,
  // so 2.2 under-drives it relative to perceived brightness).
  auto ch = [scale](uint32_t v, float gamma) -> uint8_t {
    return (uint8_t)(powf(v / 255.0f, gamma) * scale * 255.0f + 0.5f);
  };
  return ((uint32_t)ch((color_ >> 16) & 0xFF, 1.8f) << 16)
       | ((uint32_t)ch((color_ >>  8) & 0xFF, 2.2f) <<  8)
       |  (uint32_t)ch( color_        & 0xFF,  2.2f);
}

uint32_t EffectEngine::hsvToRgb(float h, float s, float v) {
  if (s <= 0.0f) {
    uint8_t g = (uint8_t)(v * 255.0f);
    return ((uint32_t)g << 16) | ((uint32_t)g << 8) | g;
  }
  h = fmodf(h, 360.0f);
  if (h < 0.0f) h += 360.0f;
  float c = v * s;
  float x = c * (1.0f - fabsf(fmodf(h / 60.0f, 2.0f) - 1.0f));
  float m = v - c;
  float r = 0, g = 0, b = 0;
  if      (h < 60)  { r=c; g=x; b=0; }
  else if (h < 120) { r=x; g=c; b=0; }
  else if (h < 180) { r=0; g=c; b=x; }
  else if (h < 240) { r=0; g=x; b=c; }
  else if (h < 300) { r=x; g=0; b=c; }
  else              { r=c; g=0; b=x; }
  return ((uint32_t)((r+m)*255) << 16)
       | ((uint32_t)((g+m)*255) << 8)
       |  (uint32_t)((b+m)*255);
}
