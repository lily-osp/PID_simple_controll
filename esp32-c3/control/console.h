#ifndef CONSOLE_H
#define CONSOLE_H

#include <Arduino.h>
#include <math.h>
#include <stdlib.h>

#include "config.h"
#include "config_common.h"
#include "control_state.h"
#include "pcnt_driver.h"
#include "trial_log.h"

// Telemetry cadence. 5Hz is fast enough to read as a trend and slow enough that
// serial TX never meaningfully loads the 115200 baud link.
#define TELEMETRY_DEFAULT_HZ 5.0f
#define TELEMETRY_MAX_HZ 50.0f

// Boot transient recorder. Jitter and stall cut-out both happen within the
// first few seconds after power-up, which is exactly when a USB serial link is
// least likely to be attached and reading. Sampling into RAM and printing on
// demand means the interesting window survives the cable being reconnected.
//
// Slots are appended until BOOT_TRACE_SLOTS or the capture window closes.
#define BOOT_TRACE_SLOTS 48
#define BOOT_TRACE_INTERVAL_MS 250
#define BOOT_TRACE_WINDOW_MS 12000

struct BootTraceSlot {
    uint16_t elapsedMs;
    uint32_t pulses;
    unsigned long periodUs;
    uint16_t pwm;
};

static BootTraceSlot bootTrace[BOOT_TRACE_SLOTS];
static uint8_t bootTraceCount = 0;

static void bootTraceReset() {
    noInterrupts();
    bootTraceCount = 0;
    interrupts();
}

// Called every control cycle; samples on the interval until the window closes.
static void bootTraceTick() {
    if (bootTraceCount >= BOOT_TRACE_SLOTS) {
        return;
    }
    unsigned long elapsed = millis() - ctrl.bootMillis;
    if (elapsed > BOOT_TRACE_WINDOW_MS) {
        return;
    }
    uint16_t slotTime = (uint16_t)(elapsed / BOOT_TRACE_INTERVAL_MS);
    if (bootTraceCount > 0 && bootTrace[bootTraceCount - 1].elapsedMs == slotTime) {
        return; // already sampled this slot
    }
    noInterrupts();
    bootTrace[bootTraceCount].elapsedMs = (uint16_t)(elapsed / BOOT_TRACE_INTERVAL_MS);
    bootTrace[bootTraceCount].pulses = pcnt_total_pulses();
    bootTrace[bootTraceCount].periodUs = pcnt_last_period_us();
    bootTrace[bootTraceCount].pwm = (uint16_t)ctrl.telPWM;
    bootTraceCount++;
    interrupts();
}

static char cmdLine[32];
static uint8_t cmdLen = 0;

// Reads a float from just past the command letter. Returns false when the
// argument is missing or unparseable, so callers can reject bad input instead
// of silently writing garbage to a command word.
static bool parseArg(const char *p, float &out) {
    while (*p == ' ' || *p == '\t') {
        p++;
    }
    if (*p == '\0') {
        return false;
    }
    char *end = nullptr;
    float v = strtof(p, &end);
    if (end == p) {
        return false;
    }
    out = v;
    return true;
}

static void printHelp() {
    Serial.println(F("\r\n=== BLDC PID CONSOLE ===\r\n"
                     "  ?          this help\r\n"
                     "  m <0-255>  MANUAL raw duty (PID bypassed) -- hardware test\r\n"
                     "  a <rpm>    AUTO closed loop at target rpm\r\n"
                     "  s          STOP (idle, will not self-start)\r\n"
                     "  g          RUN / re-arm soft-start\r\n"
                     "  f <0-255>  PID minimum duty floor (0 = full authority)\r\n"
                     "  k <p> <i> <d>  set Kp/Ki/Kd live\r\n"
                     "  z          reset integral + RPM filter\r\n"
                     "  t <hz>     telemetry rate (0=off, max 50)\r\n"
                     "  d          dump sensor + PID diagnostics\r\n"
                     "  p          dump pin states\r\n"
                     "  w          pulse waveform + jitter analysis\r\n"
                     "  bt         boot transient trace (first 12s after power-up)\r\n"
                     "  t <label> tag the current Hall wiring (survives power cycle)\r\n"
                     "  r         ranked table of every recorded Hall permutation\r\n"
                     "  c         clear recorded trials\r\n"));
}

// Prints what the sensor saw during the first seconds after power-up. This is
// the window in which the motor jitters and the driver may latch off, so it is
// only observable in a recording rather than live.
static void printBootTrace() {
    Serial.println(F("\r\n--- BOOT TRANSIENT (250ms slots) ---"));
    if (bootTraceCount == 0) {
        Serial.println(F("no trace captured"));
        Serial.println();
        return;
    }
    uint32_t prev = 0;
    Serial.println(F("  t(s)  pulses   d/s   period(ms)  rpm   pwm"));
    for (uint8_t i = 0; i < bootTraceCount; i++) {
        unsigned long t = bootTrace[i].elapsedMs * BOOT_TRACE_INTERVAL_MS;
        uint32_t d = bootTrace[i].pulses - prev;
        prev = bootTrace[i].pulses;
        float per = bootTrace[i].periodUs / 1000.0f;
        float rpm = (bootTrace[i].periodUs > 0)
                        ? (60.0e6f / (float)bootTrace[i].periodUs / (float)PULSES_PER_REV)
                        : 0.0f;
        Serial.printf("%6.2f %7lu %6.1f %11.2f %5.0f %5u\n", t / 1000.0, (unsigned long)d,
                      d / (BOOT_TRACE_INTERVAL_MS / 1000.0f), per, rpm, bootTrace[i].pwm);
    }
    Serial.println();
}

// Dumps the inter-pulse interval distribution. Coherent commutation from a
// turning rotor is tight; noise off the phase wires is not. Low jitter with a
// believable mean means the motor really is spinning and the sensor is honest.
static void printWaveform() {
    // Sample fresh: wiping first means the report can only ever describe pulses
    // that arrived during the capture window, never leftovers from earlier runs.
    pcnt_clear_history();
    unsigned long startMs = millis();
    while (millis() - startMs < 1500) {
        delay(10);
    }

    float mean, sd;
    unsigned long min, max;
    int n;
    pcnt_period_stats(mean, sd, min, max, n);

    Serial.println(F("\r\n--- PULSE WAVEFORM (fresh 1.5s capture) ---"));
    if (n < 2) {
        Serial.println(F("NO PULSES in 1.5s -- sensor line is silent"));
        Serial.println(F("(low duty, motor stopped, or the sensor path is dead)"));
        Serial.println();
        return;
    }
    Serial.printf("samples    : %d\r\n", n);
    Serial.printf("mean       : %.0f us  (%.2f ms)\r\n", mean, mean / 1000.0f);
    Serial.printf("jitter sd  : %.0f us  (%.1f%% of mean)\r\n", sd, (sd / mean) * 100.0f);
    Serial.printf("min / max  : %lu / %lu us\r\n", min, max);
    float implied = (mean > 0) ? (60.0e6f / mean / (float)PULSES_PER_REV) : 0.0f;
    Serial.printf("implied rpm: %.0f @ %d PPR\r\n", implied, PULSES_PER_REV);

    unsigned long hist[16];
    pcnt_dump_periods(hist, 16);
    Serial.print(F("last 16 (us): "));
    for (int i = 0; i < 16; i++) {
        Serial.printf("%lu ", hist[i]);
    }
    Serial.println();
    Serial.println();
}

static void printDiagnostics() {
    uint32_t total = pcnt_total_pulses();
    unsigned long age = pcnt_pulse_age_us();
    unsigned long period = pcnt_last_period_us();
    float implied = (period > 0) ? (60.0e6f / (float)period / (float)PULSES_PER_REV) : 0.0f;

    Serial.println(F("\r\n--- HALL / RPM SENSOR (GPIO 0) ---"));
    Serial.printf("pulses since boot : %lu\n", (unsigned long)total);
    Serial.printf("pulse age         : %.2f ms%s\n", age / 1000.0f,
                  total == 0 ? "   <-- ISR HAS NEVER FIRED" : "");
    Serial.printf("last period       : %.2f ms", period / 1000.0f);
    if (period > 0) {
        Serial.printf("  => %.0f RPM implied @ %d PPR\n", implied, PULSES_PER_REV);
    } else {
        Serial.println(F("   (need >=2 pulses)"));
    }
    Serial.printf("filtered RPM      : %.1f\n", ctrl.telRPM);
    Serial.printf("raw RPM           : %.1f\n", ctrl.telRawRPM);
    Serial.printf("EMA period        : %lu us\n", pcnt_period_ema_us());

    Serial.println(F("\r\n--- OUTPUT ---"));
    Serial.printf("mode              : %s\n", modeName(ctrl.mode));
    Serial.printf("applied duty      : %d / 255 (%.1f%%)\n", ctrl.telPWM,
                  (ctrl.telPWM * 100.0f) / 255.0f);
    Serial.printf("duty floor        : %d\n", ctrl.cmdPwmFloor);

    Serial.println(F("\r\n--- PID ---"));
    Serial.printf("Kp/Ki/Kd          : %.4f / %.4f / %.4f\n", ctrl.cmdKp, ctrl.cmdKi, ctrl.cmdKd);
    Serial.printf("target / error    : %.0f / %+.1f\n", ctrl.telTarget, ctrl.telError);
    Serial.printf("integral          : %+.2f\n", ctrl.telIntegral);
    Serial.printf("filt. derivative  : %+.2f\n", ctrl.telDerivative);
    Serial.printf("state flags       : %s%s%s%s\n",
                  (ctrl.telFlags & FLAG_STALLED) ? "STALLED " : "",
                  (ctrl.telFlags & FLAG_VALID_FB) ? "FEEDBACK_OK " : "",
                  (ctrl.telFlags & FLAG_SOFTSTART) ? "SOFTSTART " : "",
                  (ctrl.telFlags & FLAG_ARMED) ? "ARMED" : "");
    Serial.println();
}

static void printPinState() {
    Serial.println(F("\r\n--- PINS ---"));
    Serial.printf("GPIO %d (RPM in)  : %s\n", RPM_INPUT_PIN,
                  digitalRead(RPM_INPUT_PIN) ? "HIGH" : "LOW");
    Serial.printf("GPIO %d (PWM out) : %s\n", PWM_OUTPUT_PIN,
                  digitalRead(PWM_OUTPUT_PIN) ? "HIGH" : "LOW");
    Serial.printf("GPIO %d (trim)    : %s\n", POT_SENSITIVITY_PIN,
                  digitalRead(POT_SENSITIVITY_PIN) ? "HIGH" : "LOW");
    Serial.printf("GPIO %d (trim en) : %s (%s)\n", POT_ENABLE_PIN,
                  digitalRead(POT_ENABLE_PIN) ? "HIGH" : "LOW",
                  digitalRead(POT_ENABLE_PIN) == LOW ? "trim active" : "nominal gains");
    if (POT_ENABLE_PIN == LOW) {
        Serial.printf("  raw ADC         : %d of 4095 -> scale %.3f\n",
                      analogRead(POT_SENSITIVITY_PIN),
                      (float)analogRead(POT_SENSITIVITY_PIN) / 4095.0f);
    }
    Serial.printf("uptime           : %.1f s\n", (millis() - ctrl.bootMillis) / 1000.0);
    Serial.println();
}

// One telemetry line. Kept under ~80 chars so a 115200 baud link spends only a
// few ms per line and never backs up against the 5ms control period.
static void printTelemetry() {
    const char *sig;
    uint32_t total = pcnt_total_pulses();
    if (total == 0) {
        sig = "NO-PULSE";
    } else if (pcnt_pulse_age_us() > (unsigned long)STALL_TIMEOUT_MS * 1000UL) {
        sig = "STALE";
    } else {
        sig = "ok";
    }
    Serial.printf("[%5.1fs][%-5s] rpm:%7.1f tgt:%5.0f pwm:%3d/%3d int:%+7.2f err:%+8.1f sig:%s\r\n",
                  (millis() - ctrl.bootMillis) / 1000.0, modeName(ctrl.mode), ctrl.telRPM,
                  ctrl.telTarget, ctrl.telPWM, ctrl.cmdPwmFloor, ctrl.telIntegral, ctrl.telError,
                  sig);
}

static void handleCommand(char *line) {
    // Strip trailing whitespace, then take the first non-space as the verb.
    while (*line == ' ' || *line == '\t') {
        line++;
    }
    if (*line == '\0') {
        return;
    }
    char verb = *line;
    const char *rest = line + 1;
    float arg = 0.0f;

    switch (verb) {
    case '?':
    case 'h':
        printHelp();
        break;

    case 'm': // manual duty -- the key diagnostic
        if (!parseArg(rest, arg)) {
            Serial.println(F("ERR usage: m <0-255>"));
            break;
        }
        ctrl.requestIntegralReset = true;
        ctrl.requestSoftStart = true; // clear stale ramp state before direct drive
        ctrl.cmdManualPWM = constrain((int)arg, PWM_MIN_VALUE, PWM_MAX_VALUE);
        ctrl.mode = MODE_MANUAL;
        Serial.printf("MANUAL duty=%d (%.1f%%)\r\n", ctrl.cmdManualPWM,
                      (ctrl.cmdManualPWM * 100.0f) / 255.0f);
        break;

    case 'a': // closed loop at a new target
        if (!parseArg(rest, arg)) {
            Serial.println(F("ERR usage: a <rpm>"));
            break;
        }
        ctrl.cmdTargetRPM = constrain(arg, 0.0f, 8000.0f);
        ctrl.requestIntegralReset = true;
        ctrl.requestSoftStart = true;
        ctrl.mode = MODE_AUTO;
        Serial.printf("AUTO target=%.0f RPM\r\n", ctrl.cmdTargetRPM);
        break;

    case 's':
        ctrl.mode = MODE_STOPPED;
        Serial.println(F("STOPPED (send g to run)"));
        break;

    case 'g':
        ctrl.requestIntegralReset = true;
        ctrl.requestSoftStart = true;
        ctrl.mode = MODE_AUTO;
        Serial.printf("RUN target=%.0f RPM\r\n", ctrl.cmdTargetRPM);
        break;

    case 'f':
        if (!parseArg(rest, arg)) {
            Serial.println(F("ERR usage: f <0-255>"));
            break;
        }
        ctrl.cmdPwmFloor = constrain((int)arg, PWM_MIN_VALUE, PWM_MAX_VALUE);
        Serial.printf("duty floor=%d\r\n", ctrl.cmdPwmFloor);
        break;

    case 'k': {
        char *p = (char *)rest;
        float kp = strtof(p, &p);
        float ki = strtof(p, &p);
        float kd = strtof(p, &p);
        ctrl.cmdKp = kp;
        ctrl.cmdKi = ki;
        ctrl.cmdKd = kd;
        Serial.printf("Kp=%.4f Ki=%.4f Kd=%.4f\r\n", ctrl.cmdKp, ctrl.cmdKi, ctrl.cmdKd);
        break;
    }

    case 'z':
        ctrl.requestIntegralReset = true;
        Serial.println(F("integral + filter reset"));
        break;

    case 't': {
        // Tagging a configuration and setting telemetry share a prefix, so
        // dispatch on whether the argument parses as a number.
        float probe;
        const char *p = rest;
        while (*p == ' ') {
            p++;
        }
        if (*p != '\0' && !parseArg(p, probe)) {
            trialSetLabel(p);
        } else if (parseArg(p, probe)) {
            ctrl.telHz = constrain(probe, 0.0f, TELEMETRY_MAX_HZ);
            ctrl.telemetryEnabled = ctrl.telHz > 0.0f;
            Serial.printf("telemetry %s @ %.1f Hz\r\n", ctrl.telemetryEnabled ? "ON" : "OFF",
                          ctrl.telHz);
        } else {
            ctrl.telemetryEnabled = !ctrl.telemetryEnabled;
            Serial.printf("telemetry %s @ %.1f Hz\r\n", ctrl.telemetryEnabled ? "ON" : "OFF",
                          ctrl.telHz);
        }
        break;
    }

    case 'r':
        trialPrintTable();
        break;

    case 'c':
        memset(trialRecords, 0, sizeof(trialRecords));
        trialSave();
        Serial.println(F("trial history cleared"));
        break;

    case 'd':
        printDiagnostics();
        break;

    case 'p':
        printPinState();
        break;

    case 'w':
        printWaveform();
        break;

    case 'b':
        // 'bt' and 'b' both dump the boot trace; 'b' is just a shorter alias
        printBootTrace();
        break;

    default:
        Serial.printf("ERR unknown '%c' -- send ? for help\r\n", verb);
        break;
    }
}

// Non-blocking: drains whatever Serial has buffered and returns immediately,
// so it can live in the idle Arduino task without touching control timing.
static void consolePoll() {
    while (Serial.available() > 0) {
        char c = (char)Serial.read();
        if (c == '\r') {
            continue;
        }
        if (c == '\n') {
            cmdLine[cmdLen] = '\0';
            handleCommand(cmdLine);
            cmdLen = 0;
        } else if (cmdLen < sizeof(cmdLine) - 1) {
            cmdLine[cmdLen++] = c;
        } else {
            cmdLen = 0; // overflow: drop the line rather than run off the buffer
            Serial.println(F("ERR line too long"));
        }
    }
}

#endif // CONSOLE_H
