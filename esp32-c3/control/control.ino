/**
 * BLDC Motor PID Controller - ESP32-C3 SuperMini, DIAGNOSTIC BUILD
 *
 * Same closed-loop PID as the production firmware, plus a serial console that
 * exposes live telemetry and takes runtime commands. The point is to answer
 * "why isn't the motor spinning?" without a scope:
 *
 *   - `m <duty>` drives raw PWM, bypassing PID entirely. If the motor does not
 *     spin on manual duty, the PID is irrelevant and the fault is in the
 *     hardware chain (VR wiring, 24V supply, phase/hall order, EL/Z-F pins).
 *   - `d` reports whether the Hall ISR has ever fired. Pulses never arriving
 *     while the motor turns means the sensor path is broken, which would also
 *     explain a PID that refuses to hold speed.
 *
 * Hardware Connections:
 * - GPIO 0 -> RPM Input via divider (5V -> ~3.3V)
 * - GPIO 1 -> PWM Output direct to ESC VR
 * - GPIO 2 -> trim pot ADC; GPIO 3 -> LOW enables trim (scales Kp/Ki/Kd)
 *
 * Serial: 115200 baud, one command per line.
 */

#include <Arduino.h>

#include "config.h"
#include "config_common.h"
#include "control_state.h"

// Drivers
#include "ledc_driver.h"
#include "pcnt_driver.h"

// Core logic
#include "pid_common.h"
#include "rpm_common.h"

#include "console.h"
#include "trial_log.h"

ControlState ctrl;

// Filter & PID state
static RPMFilter rpmFilter;
static float integral = 0.0f;
static float prevMeasurement = 0.0f;
static float filteredDerivative = 0.0f;

// Soft-start state
static bool softStarting = true;
static unsigned long softStartStartTime = 0;

// Failsafe state
static bool stalled = false;
static bool hasValidFeedback = false;

static float readSensitivityScale();

static void resetPidState() {
    integral = 0.0f;
    filteredDerivative = 0.0f;
    rpmFilter.reset();
    stalled = false;
    hasValidFeedback = false;
    softStarting = true;
    softStartStartTime = 0;
}

static void publishTelemetry(float rpm, float rawRPM, float target, float error, int pwm) {
    uint8_t flags = 0;
    if (stalled) {
        flags |= FLAG_STALLED;
    }
    if (hasValidFeedback) {
        flags |= FLAG_VALID_FB;
    }
    if (softStarting) {
        flags |= FLAG_SOFTSTART;
    }
    if (millis() - ctrl.bootMillis >= ESC_ARM_DURATION_MS) {
        flags |= FLAG_ARMED;
    }

    noInterrupts();
    ctrl.telRPM = rpm;
    ctrl.telRawRPM = rawRPM;
    ctrl.telTarget = target;
    ctrl.telError = error;
    ctrl.telIntegral = integral;
    ctrl.telDerivative = filteredDerivative;
    ctrl.telPWM = pwm;
    ctrl.telFlags = flags;
    interrupts();
}

// Returns the duty actually driven: ramps from PWM_MIN_THRESHOLD up to
// targetPWM over SOFT_START_DURATION_MS, then passes targetPWM straight
// through. Collapses to a passthrough once the ramp has completed.
static int rampedPWM(int targetPWM) {
    if (!softStarting) {
        return targetPWM;
    }
    if (softStartStartTime == 0) {
        softStartStartTime = millis();
    }
    unsigned long elapsed = millis() - softStartStartTime;
    if (elapsed >= SOFT_START_DURATION_MS) {
        softStarting = false;
        return targetPWM;
    }
    float progress = (float)elapsed / SOFT_START_DURATION_MS;
    int ramped = PWM_MIN_THRESHOLD + (int)((targetPWM - PWM_MIN_THRESHOLD) * progress);
    return (ramped > targetPWM) ? targetPWM : ramped;
}

static void controlLoop(void *parameter) {
    const TickType_t xFrequency = pdMS_TO_TICKS(CONTROL_PERIOD_MS);
    const float dt = (float)CONTROL_PERIOD_MS / 1000.0f;
    TickType_t xLastWakeTime = xTaskGetTickCount();
    unsigned long lastIterationUs = micros();
    float target = DEFAULT_TARGET_RPM * RPM_CAL_SCALE;
    bool trialStarted = false;

    bootTraceReset();
    trialLoad();

    while (true) {
        // Start scoring this power cycle's wiring once the driver has armed and
        // had time to reach a steady state. Must be re-checked every iteration:
        // it cannot be hoisted out, since elapsed time is zero on the first pass.
        if (!trialStarted && millis() - ctrl.bootMillis >= TRIAL_START_MS) {
            trialStarted = true;
            trialBeginCapture();
        }
        unsigned long nowUs = micros();
        uint32_t period = nowUs - lastIterationUs;
        if (period > ctrl.ctrlLoopMaxPeriodUs) {
            ctrl.ctrlLoopMaxPeriodUs = period;
        }
        lastIterationUs = nowUs;

        // Consume one-shot console requests.
        if (ctrl.requestIntegralReset) {
            noInterrupts();
            ctrl.requestIntegralReset = false;
            interrupts();
            resetPidState();
        }
        if (ctrl.requestSoftStart) {
            noInterrupts();
            ctrl.requestSoftStart = false;
            interrupts();
            softStarting = true;
            softStartStartTime = 0;
        }

        uint8_t mode = ctrl.mode;
        int floor = ctrl.cmdPwmFloor;
        float rawRPM = pcnt_get_rpm();
        float rpm = rpmFilter.update(rawRPM);

        switch (mode) {
        case MODE_ARMING:
            // Hold zero throttle until the ESC has had its arming window.
            motor_set_pwm(PWM_IDLE);
            target = ctrl.cmdTargetRPM;
            integral = 0.0f;
            prevMeasurement = rpm;
            filteredDerivative = 0.0f;
            if (millis() - ctrl.bootMillis >= ESC_ARM_DURATION_MS) {
                ctrl.mode = MODE_AUTO;
                softStarting = true;
                softStartStartTime = 0;
            }
            publishTelemetry(rpm, rawRPM, target, target - rpm, PWM_IDLE);
            break;

        case MODE_STOPPED:
            motor_set_pwm(PWM_IDLE);
            target = ctrl.cmdTargetRPM;
            prevMeasurement = rpm;
            integral = 0.0f;
            filteredDerivative = 0.0f;
            stalled = false;
            publishTelemetry(rpm, rawRPM, target, target - rpm, PWM_IDLE);
            break;

        case MODE_MANUAL: {
            // Direct duty, no PID, no floor, no stall trip. The operator
            // owns the motor here; this is a bench tool.
            target = 0.0f;
            int duty = constrain(ctrl.cmdManualPWM, PWM_MIN_VALUE, PWM_MAX_VALUE);
            motor_set_pwm(duty);
            prevMeasurement = rpm;
            integral = 0.0f;
            filteredDerivative = 0.0f;
            publishTelemetry(rpm, rawRPM, target, -rpm, duty);
            break;
        }

        case MODE_AUTO:
        default: {
            // Gain trim: the pot is always active; its midpoint is the nominal gain.
            float sens = readSensitivityScale();
            float kp = ctrl.cmdKp * sens;
            float ki = ctrl.cmdKi * sens;
            float kd = ctrl.cmdKd * sens;
            target = ctrl.cmdTargetRPM;

            if (rpm >= target * 0.7f && rpm <= target * 1.3f) {
                hasValidFeedback = true;
            }

            // Stall re-arm: wait for genuine motion near target, then
            // soft-start back in instead of hard-kicking.
            if (stalled) {
                if (rpm >= target * 0.7f && rpm <= target * 1.3f) {
                    stalled = false;
                    softStarting = true;
                    softStartStartTime = 0;
                    integral = 0.0f;
                    filteredDerivative = 0.0f;
                    prevMeasurement = rpm;
                } else {
                    motor_set_pwm(PWM_IDLE);
                    prevMeasurement = rpm;
                    publishTelemetry(rpm, rawRPM, target, target - rpm, PWM_IDLE);
                    vTaskDelayUntil(&xLastWakeTime, xFrequency);
                    continue;
                }
            }

            if (hasValidFeedback && !stalled &&
                pcnt_pulse_age_us() > (unsigned long)STALL_TIMEOUT_MS * 1000UL) {
                stalled = true;
                integral = 0.0f;
                filteredDerivative = 0.0f;
                prevMeasurement = rpm;
                motor_set_pwm(PWM_IDLE);
                publishTelemetry(rpm, rawRPM, target, target - rpm, PWM_IDLE);
                vTaskDelayUntil(&xLastWakeTime, xFrequency);
                continue;
            }

            float error = target - rpm;
            float pidOutput = computePID_float(
                error, rpm, integral, prevMeasurement, filteredDerivative, kp, ki, kd, dt,
                INTEGRAL_WINDUP_MIN, INTEGRAL_WINDUP_MAX, PID_OUTPUT_MIN, PID_OUTPUT_MAX);

            int targetPWM = constrain((int)(pidOutput + 0.5f), floor, PWM_MAX_VALUE);
            int finalPWM = rampedPWM(targetPWM);

            motor_set_pwm(finalPWM);
            publishTelemetry(rpm, rawRPM, target, error, finalPWM);
            break;
        }
        }

        vTaskDelayUntil(&xLastWakeTime, xFrequency);
        bootTraceTick();
        trialTick();
    }
}

float readSensitivityScale() {
    int raw = analogRead(POT_SENSITIVITY_PIN);
    return PID_SENSITIVITY_MIN +
           ((float)raw / 4095.0f) * (PID_SENSITIVITY_MAX - PID_SENSITIVITY_MIN);
}

void setup() {
    Serial.begin(115200);
    unsigned long wait = millis();
    while (!Serial && millis() - wait < 1500) {
        delay(10);
    }

    ctrl.mode = MODE_ARMING;
    ctrl.cmdManualPWM = PWM_IDLE;
    ctrl.cmdTargetRPM = DEFAULT_TARGET_RPM * RPM_CAL_SCALE;
    ctrl.cmdPwmFloor = PWM_MIN_THRESHOLD;
    ctrl.cmdKp = DEFAULT_KP;
    ctrl.cmdKi = DEFAULT_KI;
    ctrl.cmdKd = DEFAULT_KD;
    ctrl.requestIntegralReset = false;
    ctrl.requestSoftStart = false;
    ctrl.telemetryEnabled = true;
    ctrl.telHz = TELEMETRY_DEFAULT_HZ;
    ctrl.bootMillis = millis();

    pinMode(POT_SENSITIVITY_PIN, INPUT);
    analogReadResolution(12);

    pcnt_init(RPM_INPUT_PIN);
    ledc_init(PWM_OUTPUT_PIN);

    xTaskCreatePinnedToCore(controlLoop, "ControlLoop", 4096, NULL, configMAX_PRIORITIES - 3, NULL,
                            0);

    Serial.println();
    Serial.println(F("ESP32-C3 BLDC Controller - DIAGNOSTIC BUILD"));
    Serial.printf("sensor GPIO%d | pwm GPIO%d | %d pulses/rev | loop %d Hz\r\n", RPM_INPUT_PIN,
                  PWM_OUTPUT_PIN, PULSES_PER_REV, CONTROL_LOOP_HZ);
    Serial.printf("target %.0f RPM | Kp %.4f Ki %.4f Kd %.4f | floor %d\r\n", ctrl.cmdTargetRPM,
                  ctrl.cmdKp, ctrl.cmdKi, ctrl.cmdKd, ctrl.cmdPwmFloor);
    Serial.println(F("arming ESC for 2s... send ? for commands"));
    Serial.println();
}

void loop() {
    consolePoll();

    if (ctrl.telemetryEnabled && ctrl.telHz > 0.0f) {
        static unsigned long lastPrint = 0;
        unsigned long period = (unsigned long)(1000.0f / ctrl.telHz);
        if (period == 0) {
            period = 1;
        }
        unsigned long now = millis();
        if (now - lastPrint >= period) {
            lastPrint = now;
            printTelemetry();
        }
    }

    vTaskDelay(pdMS_TO_TICKS(5));
}
