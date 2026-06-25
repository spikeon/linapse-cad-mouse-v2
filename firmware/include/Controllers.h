#pragma once

#include "controllers/EffectEngine.h"
#include "controllers/HIDController.h"
#include "controllers/InputController.h"
#include "controllers/LEDController.h"
#include "controllers/MotionController.h"
#include "controllers/SensorController.h"
#include "controllers/TapDetector.h"
#include "controllers/TelemetryController.h"

extern InputController     inputController;
extern LEDController       ledController;
extern SensorController    sensorController;
extern MotionController    motionController;
extern HIDController       hidController;
extern TelemetryController telemetryController;
extern TapDetector         tapDetector;
extern EffectEngine        effectEngine;

extern bool g_serviceHidMode;
extern bool g_serviceButtonMode;
extern unsigned long g_lastServicePacketMs;

extern long  g_sleepTimeoutMs;      // -1 = disabled; >0 = idle timeout in ms
extern float g_sleepWakeThreshold;  // raw sensor deviation magnitude to wake from sleep
