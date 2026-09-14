/**
 * BLDC Motor PID Controller - ESP32-C3 SuperMini Production Version
 *
 * High-performance PID controller for ESP32-C3
 * Leverages hardware peripherals (PCNT, LEDC) and FPU for ultra-stable control
 *
 * Hardware Connections:
 * - 5V -> 5V (Vin)
 * - GND -> GND
 * - GPIO 0 -> RPM Input (via Voltage Divider! 5V -> ~3.3V)
 * - GPIO 1 -> PWM Output (Direct to ESC)
 * - GPIO 2 -> Sensitivity pot (ADC); GPIO 3 -> pull LOW to enable trim (scales Kp/Ki/Kd)
 */

#include <Arduino.h>

// Configuration
#include "config.h"
#include "config_common.h"

// Drivers
#include "ledc_driver.h"
#include "pcnt_driver.h"

// Core Logic
#include "pid_common.h"
#include "rpm_common.h"

// Global Variables
volatile float currentRPM = 0.0;
volatile float targetRPM = DEFAULT_TARGET_RPM * RPM_CAL_SCALE;
volatile float pidOutput = 0.0;
volatile int lastPWMValue = 0;

// Filter & PID State
RPMFilter rpmFilter;
float integral = 0.0;
float prevMeasurement = 0.0;
float filteredDerivative = 0.0;

// Startup State
bool arming = true;
unsigned long bootTime = 0;
bool softStarting = true;
unsigned long softStartStartTime = 0;

// Failsafe state (mirrors ATtiny v3)
bool stalled = false;
bool hasValidFeedback = false;

// Function Prototypes
void controlLoop(void *parameter);
int applySoftStart(int targetPWM);
float readSensitivityScale();

void setup() {
    Serial.begin(115200);

    pinMode(POT_ENABLE_PIN, INPUT_PULLUP);

    // Initialize Drivers
    pcnt_init(RPM_INPUT_PIN);
    ledc_init(PWM_OUTPUT_PIN);

    // Create Control Loop Task (high priority; single-core C3, no wireless
    // stack running, so nothing preempts the 5ms cadence)
    xTaskCreatePinnedToCore(controlLoop,              // Function
                            "ControlLoop",            // Name
                            4096,                     // Stack size
                            NULL,                     // Parameters
                            configMAX_PRIORITIES - 3, // Priority (high, but not starving the stack)
                            NULL,                     // Task handle
                            0                         // Core ID (0 for ESP32-C3 single core)
    );

    Serial.println("ESP32-C3 BLDC Controller Started");
}

void loop() {
    // Main loop is empty, work is done in high-priority task
    vTaskDelay(pdMS_TO_TICKS(1000));
}

void controlLoop(void *parameter) {
    TickType_t xLastWakeTime;
    const TickType_t xFrequency = pdMS_TO_TICKS(CONTROL_PERIOD_MS);
    const float dt = (float)CONTROL_PERIOD_MS / 1000.0f;
    xLastWakeTime = xTaskGetTickCount();
    bootTime = millis();

    while (true) {
        bool trimActive = (digitalRead(POT_ENABLE_PIN) == LOW);
        float sens = trimActive ? readSensitivityScale() : 1.0f;
        float kp = DEFAULT_KP * sens;
        float ki = DEFAULT_KI * sens;
        float kd = DEFAULT_KD * sens;
        targetRPM = DEFAULT_TARGET_RPM * RPM_CAL_SCALE;

        // 0. ESC arming: hold zero throttle so the ESC arms on power-up.
        // Skipped automatically after ESC_ARM_DURATION_MS.
        if (arming) {
            if (millis() - bootTime < ESC_ARM_DURATION_MS) {
                motor_set_pwm(PWM_IDLE);
                lastPWMValue = PWM_IDLE;
                // Keep filter/derivative state warm so PID starts bumpless.
                currentRPM = rpmFilter.update(pcnt_get_rpm());
                prevMeasurement = currentRPM;
                vTaskDelayUntil(&xLastWakeTime, xFrequency);
                continue;
            }
            arming = false;
        }

        // 1. Calculate RPM
        float rawRPM = pcnt_get_rpm();

        // 2. Apply sliding window filter
        float filteredRPM = rpmFilter.update(rawRPM);
        currentRPM = filteredRPM;

        // 2b. Failsafe: mark feedback valid once we've genuinely reached speed
        if (currentRPM >= targetRPM * 0.7 && currentRPM <= targetRPM * 1.3) {
            hasValidFeedback = true;
        }

        // If stalled, wait for the motor to be moving again near speed, then
        // re-arm via soft-start (no hard kick). Otherwise hold the motor off.
        if (stalled) {
            if (currentRPM >= targetRPM * 0.7 && currentRPM <= targetRPM * 1.3) {
                stalled = false;
                softStarting = true;
                softStartStartTime = 0;
                integral = 0.0f;
                filteredDerivative = 0.0f;
                prevMeasurement = currentRPM;
            } else {
                motor_set_pwm(PWM_IDLE);
                lastPWMValue = PWM_IDLE;
                prevMeasurement = currentRPM;
                vTaskDelayUntil(&xLastWakeTime, xFrequency);
                continue;
            }
        }

        // Stall detection: valid feedback gained, then pulses lost too long.
        if (hasValidFeedback && !stalled &&
            pcnt_pulse_age_us() > (unsigned long)STALL_TIMEOUT_MS * 1000UL) {
            stalled = true;
            integral = 0.0f;
            filteredDerivative = 0.0f;
            prevMeasurement = currentRPM;
            motor_set_pwm(PWM_IDLE);
            lastPWMValue = PWM_IDLE;
            vTaskDelayUntil(&xLastWakeTime, xFrequency);
            continue;
        }

        // 3. Compute PID (output is directly PWM 0-255, no map() step:
        // map() from +/-5000 quantised away all fine corrections, <1 PWM
        // step per ~40 RPM of error, so the loop could never settle).
        float error = targetRPM - currentRPM;
        pidOutput = computePID_float(error, currentRPM, integral, prevMeasurement,
                                     filteredDerivative, kp, ki, kd, dt,
                                     INTEGRAL_WINDUP_MIN, INTEGRAL_WINDUP_MAX, PID_OUTPUT_MIN,
                                     PID_OUTPUT_MAX);

        // 4. Clamp to usable ESC range. NOTE: PWM_MIN_THRESHOLD must sit
        // below the PWM needed for 1440 RPM, or the motor can never slow
        // down to target. Measure your operating point and keep margin.
        int targetPWM = (int)(pidOutput + 0.5f);
        targetPWM = constrain(targetPWM, PWM_MIN_THRESHOLD, PWM_MAX_VALUE);

        // 5. Apply Soft Start (Kickstart)
        int finalPWM = applySoftStart(targetPWM);

        // 6. Output to ESC
        motor_set_pwm(finalPWM);
        lastPWMValue = finalPWM;

        // Wait for next cycle
        vTaskDelayUntil(&xLastWakeTime, xFrequency);
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
    return (kickstartPWM > targetPWM) ? targetPWM : kickstartPWM;
}

float readSensitivityScale() {
    int raw = analogRead(POT_SENSITIVITY_PIN);
    return PID_SENSITIVITY_MIN +
           ((float)raw / 4095.0f) * (PID_SENSITIVITY_MAX - PID_SENSITIVITY_MIN);
}
