#ifndef CONTROL_STATE_H
#define CONTROL_STATE_H

#include <Arduino.h>

// Operating modes. The diagnostic build adds MANUAL so a human can bypass the
// PID entirely and push raw duty at the ESC -- that single command separates
// "PID is wrong" from "the hardware chain is broken".
enum CtrlMode : uint8_t {
    MODE_ARMING = 0, // zero throttle, waiting out ESC_ARM_DURATION_MS
    MODE_STOPPED,    // zero throttle, not restarting on its own
    MODE_MANUAL,     // raw PWM from cmdManualPWM, PID bypassed
    MODE_AUTO,       // closed-loop PID toward cmdTargetRPM
};

// Telemetry flags published by the control task (read by the console).
#define FLAG_STALLED 0x01   // stall failsafe tripped, motor power cut
#define FLAG_VALID_FB 0x02  // feedback believed sane at least once
#define FLAG_SOFTSTART 0x04 // soft-start ramp in progress
#define FLAG_ARMED 0x08     // past the ESC arming window
#define FLAG_TELEMETRY 0x10 // periodic telemetry enabled

// Single source of truth shared between the 200Hz control task (writer) and
// the low-priority console task (reader). The C3 is single-core, so every
// field is touched under noInterrupts() by whichever side needs a consistent
// snapshot; single-word reads/writes are atomic anyway on RV32.
struct ControlState {
    // --- command channel: console -> control task ---
    volatile uint8_t mode;
    volatile int cmdManualPWM; // duty applied in MODE_MANUAL
    volatile float cmdTargetRPM;
    volatile int cmdPwmFloor; // minimum duty the PID may output; 0 = full authority
    volatile float cmdKp, cmdKi, cmdKd;
    volatile bool requestIntegralReset; // one-shot, cleared by the control task
    volatile bool requestSoftStart;     // one-shot, clears soft-start state

    // --- telemetry channel: control task -> console ---
    volatile float telRPM;
    volatile float telRawRPM; // pre-filter, for spotting a dead sensor
    volatile float telTarget;
    volatile float telError;
    volatile float telIntegral;
    volatile float telDerivative;
    volatile int telPWM;
    volatile uint8_t telFlags;

    // --- console-owned ---
    volatile float telHz;
    volatile bool telemetryEnabled;

    volatile unsigned long bootMillis;
    volatile uint32_t ctrlLoopMaxPeriodUs; // worst observed control-loop period
};

extern ControlState ctrl;

static inline const char *modeName(uint8_t m) {
    switch (m) {
    case MODE_ARMING:
        return "ARM";
    case MODE_STOPPED:
        return "STOP";
    case MODE_MANUAL:
        return "MAN";
    case MODE_AUTO:
        return "AUTO";
    default:
        return "?";
    }
}

#endif // CONTROL_STATE_H
