/**
 * ATtiny85 BLDC PID v4 — v1 spin path + deadband + oversampling.
 *
 * v1-proven parts kept verbatim: single-period PCINT ISR on PB3,
 * median + EMA filter chain, kickstart soft-start from PWM_MIN_THRESHOLD,
 * float PID via computePID_float(), 8 MHz clock matching lfuse 0xE2.
 *
 * Added: loop-side oversampling (mean of OVERSAMPLE_N raw RPMs feeds the
 * filter chain) and deadband (hold last PWM, freeze integrator).
 * Removed: emergency-stop, stall failsafe, sensitivity trim pot.
 *
 * Pins: PB3 (pin 2) -> Hall, PB0 (pin 5) -> ESC/motor driver.
 */

#ifndef F_CPU
#define F_CPU 8000000UL
#endif

#include "config.h"
#include "isr_common.h"
#include "pid_common.h"
#include "rpm_common.h"

#include <avr/interrupt.h>
#include <avr/io.h>

volatile unsigned long pulseInterval = 0;
volatile unsigned long lastPulseMicros = 0;
volatile unsigned long pulseCount = 0;
unsigned long lastRPMCalcTime = 0;

float currentRPM = 0.0;
const float targetRPM = DEFAULT_TARGET_RPM;

float integral = 0.0;
float previousError = 0.0;
float pidOutput = 0.0;
int holdPWM = PWM_MIN_THRESHOLD;

float rpmFiltered = 0.0;
float rpmMedianBuffer[MEDIAN_SIZE] = {0};
int rpmMedianIndex = 0;
#define EMA_ALPHA 0.25

// Oversampling accumulator (loop-side, ISR stays v1-minimal)
float ovBuf[OVERSAMPLE_N] = {0};
uint8_t ovIdx = 0;

unsigned long softStartStartTime = 0;
bool softStarting = true;

int applySoftStart(int targetPWM);

ISR(PCINT0_vect) {
    if (digitalRead(RPM_SENSOR_PIN) == HIGH) {
        unsigned long currentMicros = micros();
        unsigned long before = lastPulseMicros;
        rpmSensorISR_common(currentMicros, lastPulseMicros, pulseInterval, MIN_PULSE_WIDTH_US);
        if (lastPulseMicros != before)
            pulseCount++;
    }
}

void setup() {
    pinMode(PWM_OUTPUT_PIN, OUTPUT);
    pinMode(RPM_SENSOR_PIN, INPUT_PULLUP);
#if DEBUG_PULSE_LED
    pinMode(DEBUG_LED_PIN, OUTPUT);
    digitalWrite(DEBUG_LED_PIN, LOW);
#else
    pinMode(POT_ENABLE_PIN, INPUT_PULLUP);
#endif

    GIMSK |= (1 << PCIE);
    PCMSK |= (1 << PCINT3);

    analogWrite(PWM_OUTPUT_PIN, PWM_MIN_VALUE);
    delay(1000);
}

void loop() {
    unsigned long currentTime = millis();

    // --- 1. RPM: v1 single-period read + oversample mean + median + EMA ---
    if (currentTime - lastRPMCalcTime >= RPM_CALC_INTERVAL) {
        noInterrupts();
        unsigned long interval = pulseInterval;
        interrupts();

        float rawRPM = 0.0;
        if (micros() - lastPulseMicros > RPM_TIMEOUT_US) {
            rawRPM = 0.0;
        } else if (interval > 0) {
            rawRPM = 60000000.0 / interval / DEFAULT_PULSES_PER_REV;
        }

        // Oversampling: running mean of last N raw readings.
        ovBuf[ovIdx] = rawRPM;
        ovIdx = (ovIdx + 1) % OVERSAMPLE_N;
        float ovMean = 0.0;
        for (uint8_t i = 0; i < OVERSAMPLE_N; i++)
            ovMean += ovBuf[i];
        ovMean /= OVERSAMPLE_N;

        float medianRPM = getMedian(ovMean, rpmMedianBuffer, rpmMedianIndex);

        if (rpmFiltered == 0.0 && medianRPM > 0.0) {
            rpmFiltered = medianRPM;
            for (int i = 0; i < MEDIAN_SIZE; i++)
                rpmMedianBuffer[i] = medianRPM;
        } else {
            updateEMA(rpmFiltered, medianRPM, EMA_ALPHA);
        }
        currentRPM = rpmFiltered;
        lastRPMCalcTime = currentTime;
    }

    // --- 2. Control loop ---
    static unsigned long lastControlTime = 0;
    static unsigned long lastDbgTime = 0;
    static unsigned long lastDbgCount = 0;
    static unsigned long bootTime = 0;
    if (bootTime == 0)
        bootTime = currentTime;
    if (currentTime - lastControlTime >= CONTROL_PERIOD_MS) {
        lastControlTime = currentTime;

        // Startup kick: brute-force breakaway before PID takes over.
        if (currentTime - bootTime < KICK_MS) {
            holdPWM = KICK_PWM;
            analogWrite(PWM_OUTPUT_PIN, KICK_PWM);
            previousError = targetRPM - currentRPM;
            return;
        }

#if DEBUG_PULSE_LED
        // Heartbeat: LED on = pulses arriving, off = sensor silent.
        if (currentTime - lastDbgTime >= 500) {
            noInterrupts();
            unsigned long n = pulseCount;
            interrupts();
            digitalWrite(DEBUG_LED_PIN, (n != lastDbgCount) ? HIGH : LOW);
            lastDbgCount = n;
            lastDbgTime = currentTime;
        }
#endif

        float error = targetRPM - currentRPM;

        // Deadband: hold last PWM, freeze integrator. No chatter.
        if (error > -DEADBAND_RPM && error < DEADBAND_RPM) {
            previousError = error;
            analogWrite(PWM_OUTPUT_PIN, holdPWM);
            return;
        }

        pidOutput = computePID_float(error, integral, previousError,
                                     DEFAULT_KP, DEFAULT_KI, DEFAULT_KD,
                                     INTEGRAL_WINDUP_MIN, INTEGRAL_WINDUP_MAX,
                                     PID_OUTPUT_MIN, PID_OUTPUT_MAX);

        int pwmValue = map(pidOutput, PID_OUTPUT_MIN, PID_OUTPUT_MAX,
                           PWM_MIN_VALUE, PWM_MAX_VALUE);
        pwmValue = constrain(pwmValue, PWM_MIN_THRESHOLD, PWM_MAX_VALUE);
        pwmValue = applySoftStart(pwmValue);

        holdPWM = pwmValue;
        analogWrite(PWM_OUTPUT_PIN, pwmValue);
    }
}

int applySoftStart(int targetPWM) {
    if (!softStarting)
        return targetPWM;

    if (softStartStartTime == 0)
        softStartStartTime = millis();

    unsigned long elapsed = millis() - softStartStartTime;
    if (elapsed >= SOFT_START_DURATION_MS) {
        softStarting = false;
        return targetPWM;
    }

    float progress = (float)elapsed / SOFT_START_DURATION_MS;
    int kickstartPWM = PWM_MIN_THRESHOLD + (int)((targetPWM - PWM_MIN_THRESHOLD) * progress);

    if (kickstartPWM > targetPWM)
        return targetPWM;
    return kickstartPWM;
}
