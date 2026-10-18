#ifndef CONFIG_COMMON_H
#define CONFIG_COMMON_H

// Build options
//
// Production defaults are silent: there is no console in the enclosure and
// periodic printing would only perturb control timing. Define ENABLE_SERIAL_LOG
// to 1 when bench-testing a unit before it goes into its case.
#ifndef ENABLE_SERIAL_LOG
#define ENABLE_SERIAL_LOG 0
#endif

// Control loop
#define CONTROL_LOOP_HZ 200
#define CONTROL_PERIOD_MS (1000 / CONTROL_LOOP_HZ)

// Target speed
#define DEFAULT_TARGET_RPM 1440.0

// PID gains, output directly in PWM counts (0-255).
//
// Empirically determined on a 42BLF with the Hall sequence transposed and the
// correct 12 pulses/rev measurement. The values previously in the repository
// (0.150 / 0.120 / 0.004) are not comparable: they were calibrated against a
// pulse count that was 3x wrong AND a sensor quantised to ~+-125 RPM.
//
// Measured, free shaft, 24V, verified over a 60s soak and from cold boot:
// mean 1440, sd ~7 RPM, ~+-1.4% ripple, duty 129/255.
//
// These were tuned unloaded. If the motor ever drives a load, expect the
// tuning to shift; add Kd before Kp if it oscillates under torque.
#define DEFAULT_KP 0.040
#define DEFAULT_KI 0.080
#define DEFAULT_KD 0.001

// Output limits (PWM-count domain)
#define PID_OUTPUT_MIN 0
#define PID_OUTPUT_MAX 255
#define INTEGRAL_WINDUP_MIN 0
#define INTEGRAL_WINDUP_MAX 255

// PWM limits (8-bit, 0-255)
#define PWM_MIN_VALUE 0
#define PWM_MAX_VALUE 255
#define PWM_MIN_THRESHOLD 45 // kickstart torque, applied during the ramp
#define PWM_IDLE 0           // safe output whenever the motor must not turn

// Speed calibration multiplier applied to the target.
#define RPM_CAL_SCALE 1.0f

#endif // CONFIG_COMMON_H
