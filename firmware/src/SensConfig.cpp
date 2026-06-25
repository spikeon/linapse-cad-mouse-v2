#include "SensConfig.h"
#include "Config.h"
#include <EEPROM.h>

SensConfig sensConfig;

namespace {
constexpr uint32_t kMagic      = 0xCAD30003;
constexpr int      kBase       = 16;  // LedConfig occupies bytes 0-15
constexpr int      kAddrMagic  = kBase + 0;
constexpr int      kAddrDeadT  = kBase + 4;
constexpr int      kAddrDeadR  = kBase + 8;
constexpr int      kAddrKalQ   = kBase + 12;
constexpr int      kAddrKalR   = kBase + 16;
constexpr int      kAddrSExp   = kBase + 20;
constexpr int      kAddrTapSens = kBase + 24;
constexpr int      kAddrInvTapZ   = kBase + 28;
constexpr int      kAddrSpherical = kBase + 29;
constexpr int      kAddrSpringHead = kBase + 30;
constexpr int      kAddrDespikeEnabled   = kBase + 31;
constexpr int      kAddrDespikeThreshold = kBase + 32;
constexpr int      kAddrDespikeStrength  = kBase + 36;
}

void SensConfig::load() {
  EEPROM.begin(Config::EEPROM_SIZE);
  uint32_t magic = 0;
  EEPROM.get(kAddrMagic, magic);
  if (magic != kMagic) { reset(); return; }
  EEPROM.get(kAddrDeadT, deadT);
  EEPROM.get(kAddrDeadR, deadR);
  EEPROM.get(kAddrKalQ,  kalmanQ);
  EEPROM.get(kAddrKalR,  kalmanR);
  EEPROM.get(kAddrSExp,  sensitivityExp);
  EEPROM.get(kAddrTapSens, tapThreshold);
  EEPROM.get(kAddrInvTapZ, invertTapZ);
  EEPROM.get(kAddrSpherical, sphericalMode);
  EEPROM.get(kAddrSpringHead, springHead);
  EEPROM.get(kAddrDespikeEnabled,   despikeEnabled);
  EEPROM.get(kAddrDespikeThreshold, despikeThreshold);
  EEPROM.get(kAddrDespikeStrength,  despikeStrength);
  // Added after kMagic 0xCAD30003: on older devices these bytes are
  // uninitialized, so clamp the floats back to defaults when out of range.
  // (despikeEnabled defaults on; erased flash reads non-zero = true.)
  if (!(despikeThreshold > 0.0f && despikeThreshold < 1000.0f)) despikeThreshold = Config::DESPIKE_THRESHOLD_DEFAULT;
  if (!(despikeStrength >= 0.0f && despikeStrength <= 1.0f))    despikeStrength  = Config::DESPIKE_STRENGTH_DEFAULT;
}

void SensConfig::save() {
  EEPROM.begin(Config::EEPROM_SIZE);
  uint32_t magic = kMagic;
  EEPROM.put(kAddrMagic, magic);
  EEPROM.put(kAddrDeadT, deadT);
  EEPROM.put(kAddrDeadR, deadR);
  EEPROM.put(kAddrKalQ,  kalmanQ);
  EEPROM.put(kAddrKalR,  kalmanR);
  EEPROM.put(kAddrSExp,  sensitivityExp);
  EEPROM.put(kAddrTapSens, tapThreshold);
  EEPROM.put(kAddrInvTapZ, invertTapZ);
  EEPROM.put(kAddrSpherical, sphericalMode);
  EEPROM.put(kAddrSpringHead, springHead);
  EEPROM.put(kAddrDespikeEnabled,   despikeEnabled);
  EEPROM.put(kAddrDespikeThreshold, despikeThreshold);
  EEPROM.put(kAddrDespikeStrength,  despikeStrength);
  EEPROM.commit();
}

void SensConfig::reset() {
  deadT          = Config::DEAD_T;
  deadR          = Config::DEAD_R;
  kalmanQ        = Config::KALMAN_Q;
  kalmanR        = Config::KALMAN_R;
  sensitivityExp = Config::SENSITIVITY_EXP;
  tapThreshold   = Config::TAP_VELOCITY_THRESHOLD;
  invertTapZ     = false;
  sphericalMode  = false;
  springHead     = false;
  despikeEnabled   = true;
  despikeThreshold = Config::DESPIKE_THRESHOLD_DEFAULT;
  despikeStrength  = Config::DESPIKE_STRENGTH_DEFAULT;
}
