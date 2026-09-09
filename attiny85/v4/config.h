#ifndef CONFIG_H
#define CONFIG_H

// v5: v1 pinout/clock structure, deadband + oversampling, no failsafes.
// Chip is fused 8 MHz internal (lfuse 0xE2) -> F_CPU must be 8 MHz.
#define F_CPU 8000000UL

#define RPM_SENSOR_PIN 3
#define PWM_OUTPUT_PIN 0
#define POT_ENABLE_PIN 1
#define POT_SENSITIVITY_PIN A2

#define PID_SENSITIVITY_MIN 0.75f
#define PID_SENSITIVITY_MAX 1.25f

#include "config_common.h"

#define DEFAULT_PULSES_PER_REV 4

#define CONTROL_LOOP_HZ 200
#define CONTROL_PERIOD_MS (1000 / CONTROL_LOOP_HZ)

#define SOFT_START_DURATION_MS 1500

// Startup kick: fixed PWM for KICK_MS after boot to break static
// friction/cogging. Running floor stays at PWM_MIN_THRESHOLD.
#define KICK_PWM 130
#define KICK_MS 500

// Deadband: |error| below this -> hold PWM, freeze integrator.
#define DEADBAND_RPM 30.0f

// Oversampling: mean of N consecutive raw RPM readings before filtering.
#define OVERSAMPLE_N 4

#endif
