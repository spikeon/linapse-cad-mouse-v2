#include <Arduino.h>

#include "Config.h"
#include "Controllers.h"
#include "LedConfig.h"
#include "SensConfig.h"
#include "StateMachine.h"

InputController    inputController;
LEDController      ledController;
SensorController   sensorController;
MotionController   motionController;
HIDController      hidController;
TelemetryController telemetryController;
TapDetector        tapDetector;
EffectEngine       effectEngine;

// ── Serial command handler ────────────────────────────────────────────────────
// Commands:
//   led show                    — print brightness/color/effect
//   led brightness <0-255>      — set brightness
//   led color <RRGGBB>          — set idle color
//   led effect <name>           — set effect (see below)
//   led reset                   — restore defaults
//   config get                  — JSON dump of all config
//   config reset                — factory reset

bool g_debugAxes = false;  // accessed by IdleState
int g_currentVolume = 50;  // accessed by EffectEngine
int g_bassLevel = 0;       // accessed by EffectEngine
int g_trebleLevel = 0;     // accessed by EffectEngine
bool g_serviceHidMode = false;
unsigned long g_lastServicePacketMs = 0;

namespace {
String serialBuf;

const char* effectName(LedEffect fx) {
  switch (fx) {
    case LedEffect::Solid:         return "solid";
    case LedEffect::Breathing:     return "breathing";
    case LedEffect::Reactive:      return "reactive";
    case LedEffect::DotSwirl:      return "dot_swirl";
    case LedEffect::GradientSwirl: return "gradient_swirl";
    case LedEffect::RainbowSwirl:  return "rainbow_swirl";
    case LedEffect::Volume:        return "volume";
    case LedEffect::Equalizer:     return "equalizer";
    default:                       return "unknown";
  }
}

LedEffect effectFromName(const String& name) {
  if (name == "solid")          return LedEffect::Solid;
  if (name == "breathing")      return LedEffect::Breathing;
  if (name == "reactive")       return LedEffect::Reactive;
  if (name == "dot_swirl")      return LedEffect::DotSwirl;
  if (name == "gradient_swirl") return LedEffect::GradientSwirl;
  if (name == "rainbow_swirl")  return LedEffect::RainbowSwirl;
  if (name == "volume")         return LedEffect::Volume;
  if (name == "equalizer")      return LedEffect::Equalizer;
  return LedEffect::kCount;  // invalid sentinel
}

void applyAndSave() {
  ledConfig.save();
  effectEngine.configure(ledConfig.effect, ledConfig.idleColor, ledConfig.brightness);
}

void handleLedCommand(const String& args) {
  if (args == "show") {
    char buf[64];
    snprintf(buf, sizeof(buf), "brightness=%d color=%06lX effect=%s\n",
             ledConfig.brightness, (unsigned long)ledConfig.idleColor,
             effectName(ledConfig.effect));
    Serial.print(buf);
    return;
  }
  if (args == "reset") {
    ledConfig.reset();
    applyAndSave();
    Serial.println("OK reset");
    return;
  }
  if (args.startsWith("brightness ")) {
    int val = args.substring(11).toInt();
    if (val < 0 || val > 255) { Serial.println("ERR brightness 0-255"); return; }
    ledConfig.brightness = (uint8_t)val;
    applyAndSave();
    Serial.println("OK");
    return;
  }
  if (args.startsWith("color ")) {
    String hex = args.substring(6); hex.trim();
    if (hex.length() != 6) { Serial.println("ERR color RRGGBB"); return; }
    ledConfig.idleColor = (uint32_t)strtoul(hex.c_str(), nullptr, 16);
    applyAndSave();
    Serial.println("OK");
    return;
  }
  if (args.startsWith("effect ")) {
    String name = args.substring(7); name.trim();
    LedEffect fx = effectFromName(name);
    if (fx == LedEffect::kCount) {
      Serial.println("ERR effect: solid|breathing|reactive|dot_swirl|gradient_swirl|rainbow_swirl|volume|equalizer");
      return;
    }
    ledConfig.effect = fx;
    applyAndSave();
    Serial.println("OK");
    return;
  }
  Serial.println("ERR unknown: led show|brightness N|color RRGGBB|effect NAME|reset");
}

void handleConfigCommand(const String& args) {
  if (args == "get") {
    char buf[200];
    snprintf(buf, sizeof(buf),
             "{\"brightness\":%d,\"color\":\"%06lX\",\"effect\":\"%s\","
             "\"dead_t\":%.2f,\"dead_r\":%.2f,\"kalman_q\":%.3f,\"kalman_r\":%.3f,\"exp\":%.2f}\n",
             ledConfig.brightness, (unsigned long)ledConfig.idleColor,
             effectName(ledConfig.effect),
             sensConfig.deadT, sensConfig.deadR,
             sensConfig.kalmanQ, sensConfig.kalmanR,
             sensConfig.sensitivityExp);
    Serial.print(buf);
    return;
  }
  if (args == "reset") {
    ledConfig.reset();
    applyAndSave();
    Serial.println("OK reset");
    return;
  }
  Serial.println("ERR unknown: config get|reset");
}

void handleSensCommand(const String& args) {
  if (args == "get") {
    char buf[128];
    snprintf(buf, sizeof(buf),
             "{\"dead_t\":%.2f,\"dead_r\":%.2f,\"kalman_q\":%.3f,\"kalman_r\":%.3f,\"exp\":%.2f}\n",
             sensConfig.deadT, sensConfig.deadR,
             sensConfig.kalmanQ, sensConfig.kalmanR,
             sensConfig.sensitivityExp);
    Serial.print(buf);
    return;
  }
  if (args == "reset") {
    sensConfig.reset();
    sensConfig.save();
    Serial.println("OK reset");
    return;
  }
  if (args.startsWith("set ")) {
    String rest = args.substring(4);
    int sp = rest.indexOf(' ');
    if (sp < 0) { Serial.println("ERR sens set <param> <value>"); return; }
    String param = rest.substring(0, sp);
    float  val   = rest.substring(sp + 1).toFloat();
    if      (param == "dead_t")   sensConfig.deadT = val;
    else if (param == "dead_r")   sensConfig.deadR = val;
    else if (param == "kalman_q") sensConfig.kalmanQ = val;
    else if (param == "kalman_r") sensConfig.kalmanR = val;
    else if (param == "exp")      sensConfig.sensitivityExp = val;
    else { Serial.println("ERR unknown param: dead_t|dead_r|kalman_q|kalman_r|exp"); return; }
    sensConfig.save();
    Serial.println("OK");
    return;
  }
  Serial.println("ERR unknown: sens get|set <param> <val>|reset");
}

void handleDebugCommand(const String& args) {
  if (args == "axes on")  { g_debugAxes = true;  Serial.println("OK debug axes on");  return; }
  if (args == "axes off") { g_debugAxes = false; Serial.println("OK debug axes off"); return; }
  Serial.println("ERR unknown: debug axes on|off");
}

void handleSerial() {
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      serialBuf.trim();
      if      (serialBuf.startsWith("led "))    handleLedCommand(serialBuf.substring(4));
      else if (serialBuf.startsWith("config ")) handleConfigCommand(serialBuf.substring(7));
      else if (serialBuf.startsWith("sens "))   handleSensCommand(serialBuf.substring(5));
      else if (serialBuf.startsWith("debug "))  handleDebugCommand(serialBuf.substring(6));
      else if (serialBuf == "version")          { Serial.println("version=2.10.7"); }
      else if (serialBuf.startsWith("service_hid ")) {
        int val = serialBuf.substring(12).toInt();
        g_serviceHidMode = (val != 0);
        g_lastServicePacketMs = millis();
        Serial.println("OK");
      }
      else if (serialBuf.startsWith("hid_report ")) {
        g_lastServicePacketMs = millis();
        String args = serialBuf.substring(11);
        float motion[6] = {0};
        int parsed = 0;
        int startIdx = 0;
        for (int i = 0; i < 6; i++) {
          int commaIdx = args.indexOf(',', startIdx);
          if (commaIdx == -1 && i < 5) {
            break;
          }
          String valStr;
          if (commaIdx == -1) {
            valStr = args.substring(startIdx);
          } else {
            valStr = args.substring(startIdx, commaIdx);
            startIdx = commaIdx + 1;
          }
          valStr.trim();
          motion[i] = valStr.toFloat();
          parsed++;
        }
        if (parsed == 6) {
          hidController.sendAxesReport(motion);
          Serial.println("OK");
        } else {
          Serial.println("ERR hid_report requires 6 comma-separated floats");
        }
      }
      else if (serialBuf.startsWith("volume ")) {
        int val = serialBuf.substring(7).toInt();
        if (val >= 0 && val <= 100) {
          g_currentVolume = val;
          Serial.println("OK");
        } else {
          Serial.println("ERR volume 0-100");
        }
      }
      else if (serialBuf.startsWith("eq ")) {
        int spaceIdx = serialBuf.indexOf(' ', 3);
        if (spaceIdx != -1) {
          int bass = serialBuf.substring(3, spaceIdx).toInt();
          int treble = serialBuf.substring(spaceIdx + 1).toInt();
          if (bass >= 0 && bass <= 100 && treble >= 0 && treble <= 100) {
            g_bassLevel = bass;
            g_trebleLevel = treble;
            Serial.println("OK");
          } else {
            Serial.println("ERR eq 0-100 0-100");
          }
        } else {
          Serial.println("ERR eq <bass> <treble>");
        }
      }
      serialBuf = "";
    } else {
      serialBuf += c;
    }
  }
}
}  // namespace

// ── Arduino entry points ──────────────────────────────────────────────────────

void setup() {
  pinMode(Config::PIN_LEFT_BTN, INPUT_PULLUP);
  pinMode(Config::PIN_RIGHT_BTN, INPUT_PULLUP);
  if (digitalRead(Config::PIN_LEFT_BTN) == LOW && digitalRead(Config::PIN_RIGHT_BTN) == LOW) {
    rp2040.rebootToBootloader();
  }

  hidController.begin();
  Serial.begin(115200);
  if (Config::ENABLE_TELEMETRY) { delay(200); }

  ledConfig.load();
  sensConfig.load();
  effectEngine.configure(ledConfig.effect, ledConfig.idleColor, ledConfig.brightness);

  inputController.begin();
  ledController.begin();
  sensorController.begin();
  motionController.reset();
  tapDetector.reset();
  telemetryController.begin();

  stateMachine.changeState(&StateMachine::calibratingState);
}

void loop() {
  hidController.task();
  handleSerial();

  static unsigned long lastUpdate = 0;
  unsigned long now = millis();
  if (now - lastUpdate >= 10) {  // 100Hz polling rate
    lastUpdate = now;
    stateMachine.update();
  }
}
