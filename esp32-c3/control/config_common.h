#ifndef CONFIG_COMMON_H
#define CONFIG_COMMON_H

// Control Loop
#define CONTROL_LOOP_HZ 200
#define CONTROL_PERIOD_MS (1000 / CONTROL_LOOP_HZ)

// PID Constants. Output is DIRECTLY in PWM counts (0-255):
//   kp: PWM per RPM of error        (100 RPM err * 0.040 = 4 PWM)
//   ki: PWM per (RPM*s) integrated  (100 RPM err => ~0.04 PWM/cycle at 200Hz)
//   kd: PWM per (RPM/s) of slope    (500 RPM/s slope * 0.001 = 0.5 PWM)
//
// These were re-derived empirically once two upstream faults were fixed, and
// the old values are not comparable:
//   1. PULSES_PER_REV was 4 instead of 12, so every RPM reading was 25% high.
//   2. Speed was measured by pulse counting over a 40ms window, which at
//      1440 RPM with 12 pulses/rev quantises to ~+-125 RPM. The loop was
//      chasing its own sensor. Measurement is now interval-based (see
//      pcnt_get_rpm) with microsecond resolution.
//
// Measured at 1440 RPM with correct Hall wiring (Ha/Hb transposed), free
// shaft, 24V: mean 1440, sd ~7 RPM, ~+-20 RPM ripple, duty 129/255.
#define DEFAULT_TARGET_RPM 1440.0
#define DEFAULT_KP 0.040
#define DEFAULT_KI 0.080
#define DEFAULT_KD 0.001

// Limits (PWM-count domain)
#define PID_OUTPUT_MIN 0
#define PID_OUTPUT_MAX 255
#define INTEGRAL_WINDUP_MIN 0
#define INTEGRAL_WINDUP_MAX 255

// PWM Limits (8-bit resolution 0-255 for compatibility logic)
#define PWM_MIN_VALUE 0
#define PWM_MAX_VALUE 255
#define PWM_MIN_THRESHOLD 45 // Kickstart torque
#define PWM_IDLE 0           // Safe output when stalled (motor off)

// RPM calibration offset. The ESP32-C3 external/main crystal is far more
// accurate than the ATtiny RC, but a small trim still helps hit exact RPM.
// DEFAULT_TARGET_RPM is multiplied by this. 1.0 = no correction.
#define RPM_CAL_SCALE 1.0f

#endif // CONFIG_COMMON_H
