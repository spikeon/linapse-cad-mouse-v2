#pragma once

#include <Arduino.h>

namespace Config {

const bool ENABLE_TELEMETRY = true;

// Hardware pins (XIAO RP2040)
const int PIN_RIGHT_BTN = D0;
const int PIN_LEFT_BTN = D2;
const int PIN_LED_DATA = D3;
const int PIN_LED_LS = D1;
const int PIN_MAG1_LS = D10;
const int PIN_MAG2_LS = D9;
const int PIN_MAG3_LS = D8;

// Samples for calibration offset
const int ZERO_SAMPLES = 200;

// Gains and sign fixes
const float GAIN_T[3] = {28.0, 28.0, 24.0};
const float GAIN_R[3] = {18.0, 18.0, 20.0};
const int SIGN_AXIS[6] = {-1, +1, -1, +1, +1, +1};

// Spring head gains: magnets mounted further from sensors, asymmetric Z spring.
const float SPRING_HEAD_GAIN_T_POS[3] = {120.0f, 120.0f,  85.0f};
const float SPRING_HEAD_GAIN_T_NEG[3] = {120.0f, 120.0f, 130.0f};
const float SPRING_HEAD_GAIN_R_POS[3] = { 50.0f,  50.0f,  60.0f};
const float SPRING_HEAD_GAIN_R_NEG[3] = { 50.0f,  50.0f,  60.0f};

// Dead zones
const float DEAD_T = 16.0;
const float DEAD_R = 20.0;

// Kalman filter tuning
// Process noise: how much we expect the true value to change per step.
// Higher = more responsive but noisier.
const float KALMAN_Q = 0.5;
// Measurement noise: how noisy the sensor readings are.
// Higher = smoother but more latency.
const float KALMAN_R = 4.0;

// Sensitivity curve exponent.
// 1.0 = linear, 3.0 = cubic (fine control at small deflections, fast at large).
const float SENSITIVITY_EXP = 3.0;

// Final axis output range
const float AXIS_LIMIT = 350.0;

// Total EEPROM bytes (LedConfig=0-15, SensConfig=16-63)
constexpr int EEPROM_SIZE = 64;

// RGB LEDs
const int LED_COUNT = 8;
const int LED_BRIGHTNESS = 128;
const unsigned long LED_IDLE_COLOR = 0xFF2400;
const unsigned long LED_CALIBRATING_COLOR = 0x0000FF;

// Tap detection — velocity threshold is in raw axis units per frame.
// A tap on the head registers as a spike in TX (left/right), TY (forward/back),
// or TZ (top/down) before the spring returns the head to center.
const float TAP_VELOCITY_THRESHOLD = 3.0f;   // tune on hardware; lower = more sensitive
// De-spike: per-axis frame-delta clamp on motion output. A delta above the
// threshold is a spike (e.g. a tap impulse) and gets clamped; sustained motion
// passes. Output axis units run to AXIS_LIMIT (350). Tune on hardware.
const float DESPIKE_THRESHOLD_DEFAULT = 40.0f;
const float DESPIKE_STRENGTH_DEFAULT  = 1.0f;   // 0 = off, 1 = full clamp
const float TAP_RETURN_ZONE        = 25.0f;  // axis must return within this of zero to confirm
const unsigned long TAP_MAX_DURATION_MS  = 250;  // longer impulse treated as intentional motion
const unsigned long TAP_COOLDOWN_MIN_MS  = 50;   // minimum lockout after tap
const unsigned long TAP_COOLDOWN_MAX_MS  = 300;  // hard ceiling (undampened worst case)
const unsigned long TAP_REBOUND_MS       = 400;  // suppress opposite-direction spike after a tap
const float         TAP_SETTLE_VELOCITY  = 2.0f; // early-exit cooldown when vel drops below this
const unsigned long TAP_MULTI_WINDOW_MS  = 300;  // window to accumulate multi-taps

// LED effect parameters
const float EFFECT_BREATHE_SPEED  = 0.5f;    // cycles/sec (2 s full period)
const float EFFECT_SWIRL_SPEED    = 1.0f;    // revolutions/sec
const float EFFECT_REACTIVE_RISE  = 6.0f;    // brightness rise rate (0..1)/sec on motion
const float EFFECT_REACTIVE_FALL  = 0.4f;    // brightness fall rate (0..1)/sec at rest
const float EFFECT_REACTIVE_DIM   = 0.0f;    // minimum reactive brightness factor

// FSM timing
const long IDLE_SLEEP_TIMEOUT_MS = -1;

}  // namespace Config
