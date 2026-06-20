#include <unity.h>
#include <Arduino.h>
#include <math.h>
#include "Config.h"
#include "LedConfig.h"
#include "SensConfig.h"
#include "StateMachine.h"
#include "Controllers.h"

// Define the external instances required by the linker
InputController     inputController;
LEDController       ledController;
SensorController    sensorController;
MotionController    motionController;
HIDController       hidController;
TelemetryController telemetryController;
TapDetector         tapDetector;
EffectEngine        effectEngine;

// Define global variables required by the linker
bool g_debugAxes = false;
int g_currentVolume = 50;
int g_bassLevel = 0;
int g_trebleLevel = 0;
bool g_serviceHidMode = false;
unsigned long g_lastServicePacketMs = 0;


void setUp(void) {
    inputController.setButtonBits(0);
    inputController.setBothHeld(false);
    inputController.setCalibrationRequest(false);
    inputController.setColorConfigRequest(false);
    inputController.setLeftClick(false);
    inputController.setRightClick(false);
    inputController.setActivity(false);
}

void tearDown(void) {}

// ── MotionController Tests ───────────────────────────────────────────────────

void test_motion_controller_geometric_decomp(void) {
    float raw[9] = {1.0f, 2.0f, 3.0f, 4.0f, 5.0f, 6.0f, 7.0f, 8.0f, 9.0f};
    float baseline[9] = {0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f};
    float out[6] = {0.0f};

    MotionController::geometricDecomp(raw, baseline, out);

    // Calculated expected values:
    // TX = 3.5, TY = 4.5, TZ = 5.5
    // RX = 5.1961524, RY = 3.0, RZ = -1.098076165
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, 3.5f, out[0]);
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, 4.5f, out[1]);
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, 5.5f, out[2]);
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, 5.1961524f, out[3]);
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, 3.0f, out[4]);
    TEST_ASSERT_FLOAT_WITHIN(1e-4f, -1.098076165f, out[5]);
}

void test_motion_controller_kalman_convergence(void) {
    motionController.reset();
    sensConfig.reset();

    // TX deadzone is deadT = 16.0
    // Gain for TX is GAIN_T[0] = 28.0, SIGN_AXIS[0] = -1.
    // Steady post-gain input value of 50.0.
    // Since geometricDecomp averages over three sensors, we set raw values
    // on all three sensors to match -50.0f / 28.0f.
    float val = -50.0f / 28.0f;
    float raw[9] = { val, 0, 0, val, 0, 0, val, 0, 0 };
    float baseline[9] = {0};
    float out[6] = {0};

    // Run compute repeatedly to converge
    for (int i = 0; i < 100; ++i) {
        motionController.compute(raw, baseline, 0.01f, out);
    }
    
    // Expected output after convergence (sensitivityCurve(50.0, deadT=16.0, AXIS_LIMIT=350.0))
    // norm = (50.0 - 16.0) / 334.0 = 0.101796.
    // expected = pow(0.101796, 3.0) * 350.0 = 0.36906.
    TEST_ASSERT_FLOAT_WITHIN(0.01f, 0.369f, out[0]);
}

void test_motion_controller_deadzones(void) {
    motionController.reset();
    sensConfig.reset();

    // Input below dead-zone (TX = 15.0 < 16.0)
    float val_below = -15.0f / 28.0f;
    float raw_below[9] = { val_below, 0, 0, val_below, 0, 0, val_below, 0, 0 };
    float baseline[9] = {0};
    float out[6] = {999.0f, 999.0f, 999.0f, 999.0f, 999.0f, 999.0f};

    motionController.compute(raw_below, baseline, 0.01f, out);
    
    for (int i = 0; i < 6; i++) {
        TEST_ASSERT_EQUAL_FLOAT(0.0f, out[i]);
    }

    // Input above dead-zone (TX = 20.0 > 16.0)
    float val_above = -20.0f / 28.0f;
    float raw_above[9] = { val_above, 0, 0, val_above, 0, 0, val_above, 0, 0 };
    for (int i = 0; i < 20; ++i) {
        motionController.compute(raw_above, baseline, 0.01f, out);
    }
    TEST_ASSERT_TRUE(out[0] != 0.0f);
}

void test_motion_controller_sensitivity_curve(void) {
    motionController.reset();
    sensConfig.reset();

    // Input of 183.0 (midway of 16.0 and 350.0)
    // With linear curve (exp = 1.0)
    sensConfig.sensitivityExp = 1.0f;
    float val = -183.0f / 28.0f;
    float raw[9] = { val, 0, 0, val, 0, 0, val, 0, 0 };
    float baseline[9] = {0};
    float out[6] = {0};
    
    for (int i = 0; i < 100; ++i) {
        motionController.compute(raw, baseline, 0.01f, out);
    }
    // Expected: (183 - 16) / 334 * 350 = 175.0
    TEST_ASSERT_FLOAT_WITHIN(1.0f, 175.0f, out[0]);

    // With cubic curve (exp = 3.0)
    sensConfig.sensitivityExp = 3.0f;
    motionController.reset();
    for (int i = 0; i < 100; ++i) {
        motionController.compute(raw, baseline, 0.01f, out);
    }
    // Expected: pow(0.5, 3.0) * 350 = 43.75
    TEST_ASSERT_FLOAT_WITHIN(1.0f, 43.75f, out[0]);
}

// ── TapDetector Tests ────────────────────────────────────────────────────────

void simulateTap(TapDetector& detector, TapDir expectedDir, int axisIndex, float directionSign, unsigned long& timeMs) {
    float baseline[9] = {0.0f};
    float raw[9] = {0.0f};
    float zero[9] = {0.0f};

    // First frame to establish prevAxes_
    detector.update(zero, baseline, timeMs);
    timeMs += 10;

    // Second frame: velocity spike
    float targetVal = 30.0f * directionSign;
    if (axisIndex == 0) {
        raw[0] = raw[3] = raw[6] = targetVal;
    } else if (axisIndex == 1) {
        raw[1] = raw[4] = raw[7] = targetVal;
    } else if (axisIndex == 2) {
        raw[2] = raw[5] = raw[8] = targetVal;
    }
    detector.update(raw, baseline, timeMs);
    timeMs += 10;

    // Third frame: return to zero
    detector.update(zero, baseline, timeMs);
}

void test_tap_detector_directions(void) {
    TapDetector detector;
    unsigned long timeMs = 1000;
    float zero[9] = {0};

    // PosX
    detector.reset();
    simulateTap(detector, TapDir::PosX, 0, 1.0f, timeMs);
    timeMs += Config::TAP_MULTI_WINDOW_MS + 10;
    detector.update(zero, zero, timeMs);
    TEST_ASSERT_TRUE(detector.hasTap());
    TEST_ASSERT_EQUAL((int)TapDir::PosX, (int)detector.takeTap().dir);

    // NegX
    detector.reset();
    simulateTap(detector, TapDir::NegX, 0, -1.0f, timeMs);
    timeMs += Config::TAP_MULTI_WINDOW_MS + 10;
    detector.update(zero, zero, timeMs);
    TEST_ASSERT_TRUE(detector.hasTap());
    TEST_ASSERT_EQUAL((int)TapDir::NegX, (int)detector.takeTap().dir);

    // PosY
    detector.reset();
    simulateTap(detector, TapDir::PosY, 1, 1.0f, timeMs);
    timeMs += Config::TAP_MULTI_WINDOW_MS + 10;
    detector.update(zero, zero, timeMs);
    TEST_ASSERT_TRUE(detector.hasTap());
    TEST_ASSERT_EQUAL((int)TapDir::PosY, (int)detector.takeTap().dir);

    // NegY
    detector.reset();
    simulateTap(detector, TapDir::NegY, 1, -1.0f, timeMs);
    timeMs += Config::TAP_MULTI_WINDOW_MS + 10;
    detector.update(zero, zero, timeMs);
    TEST_ASSERT_TRUE(detector.hasTap());
    TEST_ASSERT_EQUAL((int)TapDir::NegY, (int)detector.takeTap().dir);

    // NegZ
    detector.reset();
    simulateTap(detector, TapDir::NegZ, 2, -1.0f, timeMs);
    timeMs += Config::TAP_MULTI_WINDOW_MS + 10;
    detector.update(zero, zero, timeMs);
    TEST_ASSERT_TRUE(detector.hasTap());
    TEST_ASSERT_EQUAL((int)TapDir::NegZ, (int)detector.takeTap().dir);

    // PosZ (should be suppressed!)
    detector.reset();
    simulateTap(detector, TapDir::PosZ, 2, 1.0f, timeMs);
    timeMs += Config::TAP_MULTI_WINDOW_MS + 10;
    detector.update(zero, zero, timeMs);
    TEST_ASSERT_FALSE(detector.hasTap());
}

void test_tap_detector_multi_tap(void) {
    TapDetector detector;
    unsigned long timeMs = 1000;
    float zero[9] = {0};

    detector.reset();

    // First tap
    simulateTap(detector, TapDir::PosX, 0, 1.0f, timeMs);
    TEST_ASSERT_FALSE(detector.hasTap());

    // Wait 100ms and simulate second tap
    timeMs += 100;
    simulateTap(detector, TapDir::PosX, 0, 1.0f, timeMs);
    TEST_ASSERT_FALSE(detector.hasTap());

    // Wait more than TAP_MULTI_WINDOW_MS (300ms)
    timeMs += Config::TAP_MULTI_WINDOW_MS + 10;
    detector.update(zero, zero, timeMs);

    TEST_ASSERT_TRUE(detector.hasTap());
    TapEvent evt = detector.takeTap();
    TEST_ASSERT_EQUAL((int)TapDir::PosX, (int)evt.dir);
    TEST_ASSERT_EQUAL(2, evt.count);
}

void test_tap_detector_cooldowns(void) {
    TapDetector detector;
    unsigned long timeMs = 1000;
    float zero[9] = {0};

    detector.reset();

    // Trigger and complete first tap
    simulateTap(detector, TapDir::PosX, 0, 1.0f, timeMs);
    
    // Feed a velocity spike immediately (during cooldown)
    timeMs += 10;
    float rawSpike[9] = { 30.0f, 0, 0, 30.0f, 0, 0, 30.0f, 0, 0 };
    detector.update(rawSpike, zero, timeMs);

    // Return to zero
    timeMs += 10;
    detector.update(zero, zero, timeMs);
    
    // Wait for the multi-tap window to expire
    timeMs += Config::TAP_MULTI_WINDOW_MS + 200;
    detector.update(zero, zero, timeMs);

    // Should only have 1 tap
    TEST_ASSERT_TRUE(detector.hasTap());
    TapEvent evt = detector.takeTap();
    TEST_ASSERT_EQUAL(1, evt.count);
    TEST_ASSERT_FALSE(detector.hasTap());
}

void test_tap_detector_spring_return_timeout(void) {
    TapDetector detector;
    unsigned long timeMs = 1000;
    float zero[9] = {0};

    detector.reset();

    // First frame
    detector.update(zero, zero, timeMs);
    timeMs += 10;

    // Spike to start the tap
    float rawSpike[9] = { 30.0f, 0, 0, 30.0f, 0, 0, 30.0f, 0, 0 };
    detector.update(rawSpike, zero, timeMs);

    // Stay at 30.0 for 300ms (exceeding Config::TAP_MAX_DURATION_MS = 250ms)
    timeMs += 300;
    detector.update(rawSpike, zero, timeMs);

    // Return to zero
    timeMs += 10;
    detector.update(zero, zero, timeMs);

    // Wait for multi-tap window
    timeMs += Config::TAP_MULTI_WINDOW_MS + 10;
    detector.update(zero, zero, timeMs);

    TEST_ASSERT_FALSE(detector.hasTap());
}

// ── EffectEngine Tests ───────────────────────────────────────────────────────

void test_effect_engine_color_scaling(void) {
    effectEngine.configure(LedEffect::Solid, 0x804020, 255);
    effectEngine.update(100);
    
    uint32_t c = ledController.getPixelColor(0);
    TEST_ASSERT_EQUAL_HEX32(0x4A0C03, c);
}

void test_effect_engine_hsv_to_rgb(void) {
    effectEngine.configure(LedEffect::RainbowSwirl, 0xFFFFFF, 255);
    effectEngine.update(100);
    
    uint32_t c0 = ledController.getPixelColor(0);
    TEST_ASSERT_EQUAL_HEX32(0xFF0000, c0);

    uint32_t c2 = ledController.getPixelColor(2);
    int r = (c2 >> 16) & 0xFF;
    int g = (c2 >> 8) & 0xFF;
    int b = c2 & 0xFF;
    TEST_ASSERT_INT_WITHIN(2, 127, r);
    TEST_ASSERT_INT_WITHIN(2, 255, g);
    TEST_ASSERT_EQUAL_INT(0, b);
}

void test_effect_solid(void) {
    effectEngine.configure(LedEffect::Solid, 0x00FF00, 255);
    effectEngine.update(100);
    for (int i = 0; i < ledController.numPixels(); i++) {
        TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(i));
    }
}

void test_effect_breathing(void) {
    effectEngine.configure(LedEffect::Breathing, 0x00FF00, 255);
    
    effectEngine.update(0);
    TEST_ASSERT_EQUAL_HEX32(0x003300, ledController.getPixelColor(0)); // 51 is 0x33

    effectEngine.update(1000); // 1000ms later (half-period)
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(0));
}

void test_effect_reactive(void) {
    effectEngine.configure(LedEffect::Reactive, 0x00FF00, 255);
    
    // Settle to target 1.0 (active motion)
    unsigned long timeMs = 100;
    for (int i = 0; i < 100; i++) {
        timeMs += 100;
        effectEngine.update(timeMs, 1.0f);
    }
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(0));

    // Settle to target 0.0 (idle) — needs 250 steps for complete decay
    for (int i = 0; i < 250; i++) {
        timeMs += 100;
        effectEngine.update(timeMs, 0.0f);
    }
    TEST_ASSERT_EQUAL_HEX32(0x000000, ledController.getPixelColor(0));
}

void test_effect_dot_swirl(void) {
    effectEngine.configure(LedEffect::DotSwirl, 0x00FF00, 255);
    
    effectEngine.update(100); // first update establishes lastMs_=100
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(0));
    for (int i = 1; i < 8; i++) {
        TEST_ASSERT_EQUAL_HEX32(0x000000, ledController.getPixelColor(i));
    }

    effectEngine.update(350); // dt = 0.25s, swirlPos_ = 0.25
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(2));
    for (int i = 0; i < 8; i++) {
        if (i != 2) {
            TEST_ASSERT_EQUAL_HEX32(0x000000, ledController.getPixelColor(i));
        }
    }
}

void test_effect_gradient_swirl(void) {
    effectEngine.configure(LedEffect::GradientSwirl, 0x00FF00, 255);
    effectEngine.update(100);

    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(0));
    TEST_ASSERT_EQUAL_HEX32(0x00A300, ledController.getPixelColor(7));
    TEST_ASSERT_EQUAL_HEX32(0x000000, ledController.getPixelColor(3));
}

void test_effect_volume(void) {
    effectEngine.configure(LedEffect::Volume, 0x00FF00, 255);

    g_currentVolume = 50;
    effectEngine.update(100);
    // Logical indices 0,1,2,3 map to physical (3-L+8)%8 -> 3,2,1,0
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(3));
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(2));
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(1));
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(0));
    TEST_ASSERT_EQUAL_HEX32(0x000000, ledController.getPixelColor(4));
    TEST_ASSERT_EQUAL_HEX32(0x000000, ledController.getPixelColor(5));
    TEST_ASSERT_EQUAL_HEX32(0x000000, ledController.getPixelColor(6));
    TEST_ASSERT_EQUAL_HEX32(0x000000, ledController.getPixelColor(7));

    g_currentVolume = 75; // active_leds = 6.0
    effectEngine.update(200);
    // Logical indices 0,1,2,3,4,5 map to physical -> 3,2,1,0,7,6
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(3));
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(2));
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(1));
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(0));
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(7));
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(6));
    TEST_ASSERT_EQUAL_HEX32(0x000000, ledController.getPixelColor(4));
    TEST_ASSERT_EQUAL_HEX32(0x000000, ledController.getPixelColor(5));
}

void test_effect_equalizer(void) {
    effectEngine.configure(LedEffect::Equalizer, 0x00FF00, 255);

    // 50% Bass (active: 3, 2) & 75% Treble (active: 4, 5, 6)
    g_bassLevel = 50;
    g_trebleLevel = 75;
    effectEngine.update(100);

    // Bass: active L_bass=0,1 -> physical 3, 2
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(3));
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(2));
    TEST_ASSERT_EQUAL_HEX32(0x000000, ledController.getPixelColor(1));
    TEST_ASSERT_EQUAL_HEX32(0x000000, ledController.getPixelColor(0));

    // Treble: active L_treble=0,1,2 -> physical 4, 5, 6
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(4));
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(5));
    TEST_ASSERT_EQUAL_HEX32(0x00FF00, ledController.getPixelColor(6));
    TEST_ASSERT_EQUAL_HEX32(0x000000, ledController.getPixelColor(7));
}

// ── StateMachine Tests ───────────────────────────────────────────────────────

void test_state_machine_transitions(void) {
    // Reset inputs
    inputController.setButtonBits(0);
    inputController.setBothHeld(false);
    inputController.setCalibrationRequest(false);
    inputController.setColorConfigRequest(false);
    inputController.setLeftClick(false);
    inputController.setRightClick(false);
    inputController.setActivity(false);

    // Transition to CalibratingState
    stateMachine.changeState(&StateMachine::calibratingState);
    
    // Verify enter hooks:
    TEST_ASSERT_TRUE(sensorController.calibrationActive_);
    TEST_ASSERT_FALSE(sensorController.calibrationDone_);

    // Set unique ledConfig to verify transitioning to IdleState
    ledConfig.effect = LedEffect::Solid;
    ledConfig.idleColor = 0x123456;
    ledConfig.brightness = 100;
    
    sensorController.calibrationDone_ = true;
    inputController.setBothHeld(false);
    stateMachine.update(); // transitions to IdleState!
    
    effectEngine.update(100);
    uint32_t c = ledController.getPixelColor(0);
    TEST_ASSERT_TRUE(c != 0); // successfully transitioned and configured!

    // Transition to CalibratingState from IdleState
    inputController.setCalibrationRequest(true);
    stateMachine.update();
    TEST_ASSERT_TRUE(sensorController.calibrationActive_);

    // Transition to ColorConfigState from CalibratingState
    sensorController.calibrationDone_ = true;
    inputController.setColorConfigRequest(true);
    stateMachine.update();

    // From ColorConfigState, click left to cancel and exit to IdleState
    inputController.setLeftClick(true);
    stateMachine.update();
}

// ── Config Management Tests ──────────────────────────────────────────────────

void test_config_management(void) {
    // Reset values
    ledConfig.reset();
    TEST_ASSERT_EQUAL_INT(Config::LED_BRIGHTNESS, ledConfig.brightness);
    TEST_ASSERT_EQUAL_HEX32(Config::LED_IDLE_COLOR, ledConfig.idleColor);
    TEST_ASSERT_EQUAL((int)LedEffect::Breathing, (int)ledConfig.effect);

    sensConfig.reset();
    TEST_ASSERT_EQUAL_FLOAT(Config::DEAD_T, sensConfig.deadT);
    TEST_ASSERT_EQUAL_FLOAT(Config::DEAD_R, sensConfig.deadR);
    TEST_ASSERT_EQUAL_FLOAT(Config::KALMAN_Q, sensConfig.kalmanQ);
    TEST_ASSERT_EQUAL_FLOAT(Config::KALMAN_R, sensConfig.kalmanR);
    TEST_ASSERT_EQUAL_FLOAT(Config::SENSITIVITY_EXP, sensConfig.sensitivityExp);

    // Save and load serialization
    ledConfig.brightness = 85;
    ledConfig.idleColor = 0xAABBCC;
    ledConfig.effect = LedEffect::RainbowSwirl;

    sensConfig.deadT = 12.3f;
    sensConfig.deadR = 45.6f;
    sensConfig.kalmanQ = 0.12f;
    sensConfig.kalmanR = 3.45f;
    sensConfig.sensitivityExp = 2.5f;

    ledConfig.save();
    sensConfig.save();

    ledConfig.reset();
    sensConfig.reset();

    ledConfig.load();
    sensConfig.load();

    TEST_ASSERT_EQUAL_INT(85, ledConfig.brightness);
    TEST_ASSERT_EQUAL_HEX32(0xAABBCC, ledConfig.idleColor);
    TEST_ASSERT_EQUAL((int)LedEffect::RainbowSwirl, (int)ledConfig.effect);

    TEST_ASSERT_EQUAL_FLOAT(12.3f, sensConfig.deadT);
    TEST_ASSERT_EQUAL_FLOAT(45.6f, sensConfig.deadR);
    TEST_ASSERT_EQUAL_FLOAT(0.12f, sensConfig.kalmanQ);
    TEST_ASSERT_EQUAL_FLOAT(3.45f, sensConfig.kalmanR);
    TEST_ASSERT_EQUAL_FLOAT(2.5f, sensConfig.sensitivityExp);
}

void test_motion_controller_flipped_magnets(void) {
    sensorController.setMagnetsFlipped(false);
    float raw_normal[9] = {1.0f, 2.0f, 3.0f, 4.0f, 5.0f, 6.0f, 7.0f, 8.0f, 9.0f};
    float baseline_normal[9] = {0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f, 0.5f};
    float out_normal[6] = {0.0f};
    MotionController::geometricDecomp(raw_normal, baseline_normal, out_normal);

    // Flipped magnets reverse the sign of raw and baseline values.
    sensorController.setMagnetsFlipped(true);
    float raw_flipped[9];
    float baseline_flipped[9];
    for (int i = 0; i < 9; i++) {
        raw_flipped[i] = -raw_normal[i];
        baseline_flipped[i] = -baseline_normal[i];
    }
    float out_flipped[6] = {0.0f};
    MotionController::geometricDecomp(raw_flipped, baseline_flipped, out_flipped);

    // Verify output is identical to normal!
    for (int i = 0; i < 6; i++) {
        TEST_ASSERT_FLOAT_WITHIN(1e-4f, out_normal[i], out_flipped[i]);
    }

    // Reset magnetsFlipped for other tests
    sensorController.setMagnetsFlipped(false);
}

void test_config_layout_boundaries(void) {
    int ledConfigEnd = 9 + 1; // kAddrEffect + sizeof(uint8_t)
    int sensConfigStart = 16; // kBase
    int sensConfigEnd = 36 + 4; // kAddrSExp + sizeof(float)

    TEST_ASSERT_TRUE(ledConfigEnd <= sensConfigStart);
    TEST_ASSERT_TRUE(sensConfigEnd <= Config::EEPROM_SIZE);
}

// ── Main Entry Point ─────────────────────────────────────────────────────────

#ifdef ARDUINO
void setup() {
    UNITY_BEGIN();

    // MotionController
    RUN_TEST(test_motion_controller_geometric_decomp);
    RUN_TEST(test_motion_controller_kalman_convergence);
    RUN_TEST(test_motion_controller_deadzones);
    RUN_TEST(test_motion_controller_sensitivity_curve);
    RUN_TEST(test_motion_controller_flipped_magnets);

    // TapDetector
    RUN_TEST(test_tap_detector_directions);
    RUN_TEST(test_tap_detector_multi_tap);
    RUN_TEST(test_tap_detector_cooldowns);
    RUN_TEST(test_tap_detector_spring_return_timeout);

    // EffectEngine
    RUN_TEST(test_effect_engine_color_scaling);
    RUN_TEST(test_effect_engine_hsv_to_rgb);
    RUN_TEST(test_effect_solid);
    RUN_TEST(test_effect_breathing);
    RUN_TEST(test_effect_reactive);
    RUN_TEST(test_effect_dot_swirl);
    RUN_TEST(test_effect_gradient_swirl);
    RUN_TEST(test_effect_volume);

    // StateMachine
    RUN_TEST(test_state_machine_transitions);

    // Config Management
    RUN_TEST(test_config_management);
    RUN_TEST(test_config_layout_boundaries);

    UNITY_END();
}

void loop() {}
#else
int main(int argc, char **argv) {
    UNITY_BEGIN();

    // MotionController
    RUN_TEST(test_motion_controller_geometric_decomp);
    RUN_TEST(test_motion_controller_kalman_convergence);
    RUN_TEST(test_motion_controller_deadzones);
    RUN_TEST(test_motion_controller_sensitivity_curve);
    RUN_TEST(test_motion_controller_flipped_magnets);

    // TapDetector
    RUN_TEST(test_tap_detector_directions);
    RUN_TEST(test_tap_detector_multi_tap);
    RUN_TEST(test_tap_detector_cooldowns);
    RUN_TEST(test_tap_detector_spring_return_timeout);

    // EffectEngine
    RUN_TEST(test_effect_engine_color_scaling);
    RUN_TEST(test_effect_engine_hsv_to_rgb);
    RUN_TEST(test_effect_solid);
    RUN_TEST(test_effect_breathing);
    RUN_TEST(test_effect_reactive);
    RUN_TEST(test_effect_dot_swirl);
    RUN_TEST(test_effect_gradient_swirl);
    RUN_TEST(test_effect_volume);
    RUN_TEST(test_effect_equalizer);

    // StateMachine
    RUN_TEST(test_state_machine_transitions);

    // Config Management
    RUN_TEST(test_config_management);
    RUN_TEST(test_config_layout_boundaries);

    return UNITY_END();
}
#endif
