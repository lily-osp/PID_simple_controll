/**
 * ESP32-C3 BLDC PID controller - PRODUCTION
 *
 * Closed-loop speed hold at DEFAULT_TARGET_RPM for a 42BLF on a JYQD-V7.3E3.
 * Runs standalone with no console, no telemetry and no external intervention:
 * power it and it arms, ramps, and holds speed indefinitely.
 *
 * Sequence at power-up:
 *   1. hold zero throttle for ESC_ARM_DURATION_MS so the driver arms
 *   2. ramp from PWM_MIN_THRESHOLD over SOFT_START_DURATION_MS
 *   3. close the loop, holding DEFAULT_TARGET_RPM
 *
 * Stall handling cuts drive immediately and re-arms once the rotor turns again
 * (soft-start, never a hard kick). It retries indefinitely, so a jam that
 * clears itself does not require a power cycle.
 *
 * Hardware:
 *   GPIO 0 -> driver Signal, via 2.2k/3.3k divider (5V -> 3.3V). The C3 pins
 *             are not 5V tolerant. Signal is the XOR of the three Halls.
 *   GPIO 1 -> driver VR, direct.
 *   GPIO 2 -> trim pot wiper, GPIO 3 pulled LOW to enable trimming.
 *   GND   -> common with the driver. Never feed 24V to the ESP32.
 *
 * The driver, motor and 24V supply are wired exactly as the Hall permutation
 * that was validated during bring-up. Do not swap Hall lines on this build.
 */

#include <Arduino.h>
#include <string.h>

#include "config.h"
#include "config_common.h"

// Driver and control maths are shared with the bench/diagnostic build in
// ../control so there is exactly one implementation of the RPM estimator, the
// PID and the LEDC setup. Only this main loop and the config are production
// specific. If you change a driver header, change it in ../control only.
#include "../control/ledc_driver.h"
#include "../control/pcnt_driver.h"
#include "../control/pid_common.h"
#include "../control/rpm_common.h"

#if ENABLE_SERIAL_LOG
#define LOG(...)                                                                                   \
    do {                                                                                           \
        Serial.printf(__VA_ARGS__);                                                                \
        Serial.print("\r\n");                                                                      \
    } while (0)
#else
#define LOG(...)                                                                                   \
    do {                                                                                           \
    } while (0)
#endif

static RPMFilter rpmFilter;
static float integral = 0.0f;
static float prevMeasurement = 0.0f;
static float filteredDerivative = 0.0f;

static bool softStarting = true;
static unsigned long softStartStartTime = 0;
static bool stalled = false;
static bool hasValidFeedback = false;

static unsigned long bootTime = 0;

#if ENABLE_SERIAL_LOG
// Latest control-loop output, published for the idle task to print.
struct Telemetry {
    float rpm;
    float target;
    float error;
    uint16_t duty;
    bool stalled;
    bool ramping;
};
static Telemetry telSnapshot = {0.0f, 0.0f, 0.0f, 0, false, false};
#endif

static float readSensitivityScale() {
    int raw = analogRead(POT_SENSITIVITY_PIN);
    return PID_SENSITIVITY_MIN +
           ((float)raw / 4095.0f) * (PID_SENSITIVITY_MAX - PID_SENSITIVITY_MIN);
}

static void applySoftStart() {
    if (!softStarting) {
        return;
    }
    if (softStartStartTime == 0) {
        softStartStartTime = millis();
    }
    if (millis() - softStartStartTime >= SOFT_START_DURATION_MS) {
        softStarting = false;
    }
}

// Duty actually driven: ramps up from PWM_MIN_THRESHOLD, then passes straight
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

// Clears every piece of accumulated state so a restart is bumpless: no carried
// integral, no derivative spike, no stale filter history.
static void resetControlState() {
    integral = 0.0f;
    filteredDerivative = 0.0f;
    prevMeasurement = rpmFilter.update(pcnt_get_rpm());
    stalled = false;
    softStarting = true;
    softStartStartTime = 0;
}

static void controlLoop(void *parameter) {
    const TickType_t period = pdMS_TO_TICKS(CONTROL_PERIOD_MS);
    const float dt = (float)CONTROL_PERIOD_MS / 1000.0f;
    TickType_t lastWake = xTaskGetTickCount();
    bootTime = millis();

    for (;;) {
        float rpm = rpmFilter.update(pcnt_get_rpm());

        // Gain trim is opt-in via GPIO 3, so a unit with no pot fitted simply
        // runs the nominal gains.
        float trim = (digitalRead(POT_ENABLE_PIN) == LOW) ? readSensitivityScale() : 1.0f;
        float kp = DEFAULT_KP * trim;
        float ki = DEFAULT_KI * trim;
        float kd = DEFAULT_KD * trim;
        float target = DEFAULT_TARGET_RPM * RPM_CAL_SCALE;

        // Arming window. Hold zero throttle and keep the filter fed so the PID
        // starts from a warm, bumpless state.
        if (millis() - bootTime < ESC_ARM_DURATION_MS) {
            motor_set_pwm(PWM_IDLE);
            prevMeasurement = rpm;
            integral = 0.0f;
            filteredDerivative = 0.0f;
            vTaskDelayUntil(&lastWake, period);
            continue;
        }

        // Feedback is only trusted once the rotor has demonstrably been near
        // target, so a stationary rotor at power-up cannot arm the stall timer.
        if (rpm >= target * 0.7f && rpm <= target * 1.3f) {
            hasValidFeedback = true;
        }

        // Stalled: cut drive, wait for the rotor to be moving again, then
        // soft-start back in. Indefinitely, so a self-clearing jam recovers
        // without a power cycle.
        if (stalled) {
            if (rpm >= target * 0.7f && rpm <= target * 1.3f) {
                resetControlState();
            } else {
                motor_set_pwm(PWM_IDLE);
                prevMeasurement = rpm;
                vTaskDelayUntil(&lastWake, period);
                continue;
            }
        }

        // Hall signal lost while the motor was believed to be running.
        // Order matters: resetControlState() clears `stalled`, so the latch has
        // to be set afterwards or it is undone on the same cycle.
        if (hasValidFeedback && pcnt_pulse_age_us() > (unsigned long)STALL_TIMEOUT_MS * 1000UL) {
            motor_set_pwm(PWM_IDLE);
            resetControlState();
            stalled = true;
            vTaskDelayUntil(&lastWake, period);
            continue;
        }

        float error = target - rpm;
        float output = computePID_float(error, rpm, integral, prevMeasurement, filteredDerivative,
                                        kp, ki, kd, dt, INTEGRAL_WINDUP_MIN, INTEGRAL_WINDUP_MAX,
                                        PID_OUTPUT_MIN, PID_OUTPUT_MAX);

        applySoftStart();
        int duty = constrain((int)(output + 0.5f), PWM_MIN_THRESHOLD, PWM_MAX_VALUE);
        duty = rampedPWM(duty);
        motor_set_pwm(duty);

#if ENABLE_SERIAL_LOG
        // Publish only. The blocking serial write happens in loop() below: a
        // ~90 character line at 115200 baud occupies the task for ~8ms, which
        // would show up as a once-per-interval jitter spike in the very
        // measurement this is here to report.
        Telemetry t = {rpm, target, error, (uint16_t)duty, stalled, softStarting};
        noInterrupts();
        memcpy((void *)&telSnapshot, &t, sizeof(t));
        interrupts();
#endif

        vTaskDelayUntil(&lastWake, period);
    }
}

void setup() {
#if ENABLE_SERIAL_LOG
    Serial.begin(115200);
    unsigned long waitStart = millis();
    while (!Serial && millis() - waitStart < 1500) {
        delay(10);
    }
    LOG("ESP32-C3 BLDC controller: target %.0f RPM, Kp %.3f Ki %.3f Kd %.3f, %d pulses/rev",
        DEFAULT_TARGET_RPM * RPM_CAL_SCALE, DEFAULT_KP, DEFAULT_KI, DEFAULT_KD, PULSES_PER_REV);
#endif

    pinMode(POT_ENABLE_PIN, INPUT_PULLUP);

    pcnt_init(RPM_INPUT_PIN);
    ledc_init(PWM_OUTPUT_PIN);

    // Highest practical priority on the single C3 core: nothing else is running
    // a timing-critical job, and the loop must hold its 5ms cadence.
    xTaskCreatePinnedToCore(controlLoop, "ControlLoop", 4096, NULL, configMAX_PRIORITIES - 3, NULL,
                            0);
}

void loop() {
    // All control work happens in the control task.
#if ENABLE_SERIAL_LOG
    static unsigned long lastLog = 0;
    if (millis() - lastLog >= 250) {
        lastLog = millis();
        Telemetry t;
        noInterrupts();
        t = telSnapshot;
        interrupts();
        Serial.printf("[%6lu ms] rpm %7.1f  tgt %5.0f  err %+8.1f  duty %3d%s%s\r\n",
                      millis() - bootTime, t.rpm, t.target, t.error, t.duty,
                      t.stalled ? "  STALLED" : "", t.ramping ? "  ramping" : "");
    }
#endif
    vTaskDelay(pdMS_TO_TICKS(5));
}
