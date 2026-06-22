#include "states/IdleState.h"

#include <Arduino.h>

#include "Config.h"
#include "Controllers.h"
#include "LedConfig.h"
#include "StateMachine.h"

void IdleState::enter() {
  lastUpdateMs_  = 0;
  lastActivityMs_ = millis();
  lastMotionMag_ = 0.0f;
  tapDetector.reset();
  effectEngine.configure(ledConfig.effect, ledConfig.idleColor, ledConfig.brightness);
}

bool IdleState::handleCalibrationRequest() {
  if (inputController.takeCalibrationRequest()) {
    stateMachine.changeState(&StateMachine::calibratingState);
    return true;
  }
  return false;
}

void IdleState::runMotionPipeline(float dt, unsigned long now) {
  float raw[9] = {};
  if (!sensorController.readRaw(raw)) return;

  // Tap detection runs on unfiltered data before Kalman
  tapDetector.update(raw, sensorController.baseline(), now);

  // Debug streaming: output raw TX/TY/TZ and their frame deltas for tap calibration
  if (g_debugAxes) {
    float axes[6] = {};
    MotionController::geometricDecomp(raw, sensorController.baseline(), axes);
    char buf[48];
    snprintf(buf, sizeof(buf), "AX:%.1f,%.1f,%.1f\n", axes[0], axes[1], axes[2]);
    Serial.print(buf);
  }

  float motion[6] = {};
  motionController.compute(raw, sensorController.baseline(), dt, motion);

  if (tapDetector.isTapping()) {
    for (int i = 0; i < 6; i++) {
      motion[i] = 0.0f;
    }
  }

  if (motionController.hasMotionActivity()) {
    lastActivityMs_ = now;
  }

  // Compute motion magnitude for Reactive effect (sum of abs translation axes)
  float mag = (fabsf(motion[0]) + fabsf(motion[1]) + fabsf(motion[2])) / (3.0f * Config::AXIS_LIMIT);
  if (mag > 1.0f) mag = 1.0f;
  lastMotionMag_ = mag;

  const uint16_t buttonBits   = inputController.buttonBits();

  if (g_serviceHidMode) {
    if (now - g_lastServicePacketMs > 2000) {
      g_serviceHidMode = false;
      Serial.println("service_hid timeout, reverting to local_hid");
    }
  }

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

  if (telemetryController.enabled()) {
    telemetryController.publish(motion, buttonBits, hidReportSent);
  }
}

void IdleState::handleTaps() {
  while (tapDetector.hasTap()) {
    TapEvent evt = tapDetector.takeTap();

    // Report via serial for Linux-side action dispatch
    const char* dirs[] = { "None", "PosX", "NegX", "PosY", "NegY", "PosZ", "NegZ" };
    uint8_t idx = (uint8_t)evt.dir;
    if (idx < 7) {
      Serial.print("TAP:");
      Serial.print(dirs[idx]);
      Serial.print(":");
      Serial.println(evt.count);
    }
  }
}

void IdleState::handleSleepTransition(unsigned long now) {
  if (Config::IDLE_SLEEP_TIMEOUT_MS < 0) return;
  const unsigned long inactiveMs = now - lastActivityMs_;
  if (inactiveMs >= (unsigned long)Config::IDLE_SLEEP_TIMEOUT_MS) {
    stateMachine.changeState(&StateMachine::sleepState);
  }
}

void IdleState::update() {
  inputController.update();

  if (handleCalibrationRequest()) return;

  const unsigned long now = millis();
  if (inputController.takeActivity()) lastActivityMs_ = now;

  const float dt = (lastUpdateMs_ == 0) ? 0.01f : ((now - lastUpdateMs_) / 1000.0f);
  lastUpdateMs_ = now;

  runMotionPipeline(dt, now);
  handleTaps();
  effectEngine.update(now, lastMotionMag_);
  handleSleepTransition(now);
}

void IdleState::exit() {}
