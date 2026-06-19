#pragma once

#include <Adafruit_TinyUSB.h>
#include <Arduino.h>

class HIDController {
 public:
  void begin();
  void task();
  bool sendReports(const float motion[6], uint16_t buttonBits);
  bool sendAxesReport(const float motion[6]);
  bool sendButtonsReport(uint16_t buttonBits);

 private:
  struct __attribute__((packed)) ReportAxes {
    int16_t x, y, z, rx, ry, rz;
  };

  struct __attribute__((packed)) ReportButtons {
    uint16_t bits;
  };

  static ReportAxes makeAxesReport(const float motion[6]);
  bool axesReportChanged(const ReportAxes& axes) const;

  Adafruit_USBD_HID usbHid_;
  uint16_t buttonBitsSent_ = 0;
  ReportAxes lastSentAxes_{};
};
