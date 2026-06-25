#include "states/SleepState.h"

#include <Arduino.h>

#include "Config.h"
#include "Controllers.h"
#include "StateMachine.h"

void SleepState::enter() {
  ledController.off();
}

void SleepState::update() {
  inputController.update();

  if (inputController.takeActivity()) {
    stateMachine.changeState(&StateMachine::idleState);
    return;
  }

  // Wake on motion: sum abs deviation of raw sensor readings from calibration baseline.
  // This fires even if the user never presses a button — the original firmware only
  // checked buttons, which is why sleep wouldn't wake on Linux where no button is pressed.
  float raw[9] = {};
  if (sensorController.readRaw(raw)) {
    const float* bl = sensorController.baseline();
    float mag = 0;
    for (int i = 0; i < 9; i++) mag += fabsf(raw[i] - bl[i]);
    if (mag > g_sleepWakeThreshold) {
      stateMachine.changeState(&StateMachine::idleState);
      return;
    }
  }
}

void SleepState::exit() {}
