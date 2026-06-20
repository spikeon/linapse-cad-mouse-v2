#include "controllers/MotionController.h"

#include <Arduino.h>
#include <math.h>

#include "Config.h"
#include "SensConfig.h"
#include "Controllers.h"

namespace {
enum RawIndex {
  RAW_MAG1_X = 0,
  RAW_MAG1_Y,
  RAW_MAG1_Z,
  RAW_MAG2_X,
  RAW_MAG2_Y,
  RAW_MAG2_Z,
  RAW_MAG3_X,
  RAW_MAG3_Y,
  RAW_MAG3_Z
};

enum AxisIndex {
  AXIS_TX = 0,
  AXIS_TY,
  AXIS_TZ,
  AXIS_RX,
  AXIS_RY,
  AXIS_RZ
};

// Precomputed geometric constants for the equilateral sensor triangle.
const float kOneThird = 1.0f / 3.0f;
const float kSqrt3 = 1.7320508f;          // sqrt(3)
const float kSqrt3Over6 = 0.28867513f;    // sqrt(3)/6
const float kSqrt3Over3 = 0.57735027f;    // sqrt(3)/3
const float kMag2PosX = -0.5f;
const float kMag2PosY = kSqrt3Over6;
const float kMag3PosX = 0.5f;
const float kMag3PosY = kSqrt3Over6;
const float kMag1PosX = 0.0f;
const float kMag1PosY = -kSqrt3Over3;
}  // namespace

void MotionController::geometricDecomp(const float raw[9], const float* baseline, float out[6]) {
  float m1x = raw[0] - baseline[0];
  float m1y = raw[1] - baseline[1];
  float m1z = raw[2] - baseline[2];
  float m2x = raw[3] - baseline[3];
  float m2y = raw[4] - baseline[4];
  float m2z = raw[5] - baseline[5];
  float m3x = raw[6] - baseline[6];
  float m3y = raw[7] - baseline[7];
  float m3z = raw[8] - baseline[8];

  if (sensorController.magnetsFlipped()) {
    m1x = -m1x; m1y = -m1y; m1z = -m1z;
    m2x = -m2x; m2y = -m2y; m2z = -m2z;
    m3x = -m3x; m3y = -m3y; m3z = -m3z;
  }

  out[AXIS_TX] = (m1x + m2x + m3x) * kOneThird;
  out[AXIS_TY] = (m1y + m2y + m3y) * kOneThird;
  out[AXIS_TZ] = (m1z + m2z + m3z) * kOneThird;
  out[AXIS_RX] = (kSqrt3 * (m2z + m3z - 2.0f * m1z)) * kOneThird;
  out[AXIS_RY] = m3z - m2z;
  out[AXIS_RZ] = (kMag2PosX * m2y - kMag2PosY * m2x)
               + (kMag3PosX * m3y - kMag3PosY * m3x)
               + (kMag1PosX * m1y - kMag1PosY * m1x);
}

void MotionController::reset() {
  for (int i = 0; i < 6; i++) {
    kalmanX_[i] = 0.0f;
    kalmanP_[i] = 1.0f;
  }
  motionActive_ = false;
}

float MotionController::clampf(float v, float lo, float hi) {
  if (v < lo) return lo;
  if (v > hi) return hi;
  return v;
}

float MotionController::kalmanStep(int axis, float measurement) {
  // Predict step: uncertainty grows by process noise
  kalmanP_[axis] += sensConfig.kalmanQ;

  // Update step: compute Kalman gain
  const float K = kalmanP_[axis] / (kalmanP_[axis] + sensConfig.kalmanR);

  // Correct estimate with measurement
  kalmanX_[axis] += K * (measurement - kalmanX_[axis]);

  // Update uncertainty
  kalmanP_[axis] *= (1.0f - K);

  return kalmanX_[axis];
}

float MotionController::axisBaseDead(int i) {
  return (i < 3) ? sensConfig.deadT : sensConfig.deadR;
}

float MotionController::sensitivityCurve(float value, float dead, float limit) {
  // Map the post-dead-zone range [dead, limit] onto [0, limit] with a power curve.
  // This gives fine control at small deflections and fast motion at large ones.
  const float sign = (value >= 0.0f) ? 1.0f : -1.0f;
  const float abs_val = fabs(value);
  if (abs_val <= dead) return 0.0f;

  // Normalize to 0..1 within the active range
  const float range = limit - dead;
  if (range <= 0.0f) return 0.0f;
  const float normalized = clampf((abs_val - dead) / range, 0.0f, 1.0f);

  // Apply power curve and scale back to output range
  return sign * powf(normalized, sensConfig.sensitivityExp) * limit;
}

void MotionController::compute(const float raw[9], const float* baseline, float dt,
                               float out[6]) {
  // Baseline subtraction converts magnetic deltas around the calibrated rest pose.
  float mag1x = raw[RAW_MAG1_X] - baseline[RAW_MAG1_X];
  float mag1y = raw[RAW_MAG1_Y] - baseline[RAW_MAG1_Y];
  float mag1z = raw[RAW_MAG1_Z] - baseline[RAW_MAG1_Z];
  float mag2x = raw[RAW_MAG2_X] - baseline[RAW_MAG2_X];
  float mag2y = raw[RAW_MAG2_Y] - baseline[RAW_MAG2_Y];
  float mag2z = raw[RAW_MAG2_Z] - baseline[RAW_MAG2_Z];
  float mag3x = raw[RAW_MAG3_X] - baseline[RAW_MAG3_X];
  float mag3y = raw[RAW_MAG3_Y] - baseline[RAW_MAG3_Y];
  float mag3z = raw[RAW_MAG3_Z] - baseline[RAW_MAG3_Z];

  if (sensorController.magnetsFlipped()) {
    mag1x = -mag1x; mag1y = -mag1y; mag1z = -mag1z;
    mag2x = -mag2x; mag2y = -mag2y; mag2z = -mag2z;
    mag3x = -mag3x; mag3y = -mag3y; mag3z = -mag3z;
  }

  // Translation: average of all three sensors.
  const float tx = (mag1x + mag2x + mag3x) * kOneThird;
  const float ty = (mag1y + mag2y + mag3y) * kOneThird;
  const float tz = (mag1z + mag2z + mag3z) * kOneThird;

  // Rotation estimates from sensor triangle geometry.
  //   Ry: side-to-side tilt (right sensor minus left)
  //   Rx: front/back tilt (top pair minus bottom)
  //   Rz: twist (cross-product per sensor position)
  const float rx = (kSqrt3 * (mag2z + mag3z - 2.0f * mag1z)) * kOneThird;
  const float ry = (mag3z - mag2z);
  const float rz =
      (kMag2PosX * mag2y - kMag2PosY * mag2x) +
      (kMag3PosX * mag3y - kMag3PosY * mag3x) +
      (kMag1PosX * mag1y - kMag1PosY * mag1x);

  // Apply sign fixes and gains
  float y[6];
  y[AXIS_TX] = Config::SIGN_AXIS[AXIS_TX] * tx * Config::GAIN_T[AXIS_TX];
  y[AXIS_TY] = Config::SIGN_AXIS[AXIS_TY] * ty * Config::GAIN_T[AXIS_TY];
  y[AXIS_TZ] = Config::SIGN_AXIS[AXIS_TZ] * tz * Config::GAIN_T[AXIS_TZ];
  y[AXIS_RX] = Config::SIGN_AXIS[AXIS_RX] * rx * Config::GAIN_R[AXIS_RX - 3];
  y[AXIS_RY] = Config::SIGN_AXIS[AXIS_RY] * ry * Config::GAIN_R[AXIS_RY - 3];
  y[AXIS_RZ] = Config::SIGN_AXIS[AXIS_RZ] * rz * Config::GAIN_R[AXIS_RZ - 3];

  // Kalman filter, sensitivity curve, dead zones, and clamp.
  motionActive_ = false;
  for (int i = 0; i < 6; i++) {
    const float dead = axisBaseDead(i);

    if (fabs(y[i]) < dead) {
      // Below dead zone: decay Kalman estimate toward zero gradually.
      // Preserve covariance so the filter doesn't jitter at the boundary.
      kalmanX_[i] *= 0.8f;
      kalmanP_[i] = fmin(kalmanP_[i] + sensConfig.kalmanQ * 0.1f, 1.0f);
    } else {
      kalmanStep(i, y[i]);
    }

    // Apply sensitivity curve to filtered output
    out[i] = sensitivityCurve(kalmanX_[i], dead, Config::AXIS_LIMIT);
    if (out[i] != 0.0f) {
      motionActive_ = true;
    }
  }
}

bool MotionController::hasMotionActivity() const { return motionActive_; }
