#ifndef CONFIG_H
#define CONFIG_H

// Hardware Pins (ESP32-C3 SuperMini)
#define RPM_INPUT_PIN 0       // GPIO 0, via 2.2k/3.3k divider (5V -> 3.3V)
#define PWM_OUTPUT_PIN 1      // GPIO 1 -> driver VR
#define POT_ENABLE_PIN 3      // GPIO 3, pull LOW to enable gain trim
#define POT_SENSITIVITY_PIN 2 // GPIO 2, ADC pot scaling Kp/Ki/Kd

// Pot maps a multiplier on the PID gains (target RPM is unaffected).
#define PID_SENSITIVITY_MIN 0.75f
#define PID_SENSITIVITY_MAX 1.25f

// Motor configuration, from docs/motor_specification/42BLF.pdf:
// 8 poles (4 pole pairs), 3-phase, Hall effect angle 120 deg electrical.
// Pulses per rev of the driver's XOR'd Hall output = 3 x pole_pairs.
#define PULSES_PER_REV 12

// RPM measurement: kept for the pulse-counting cross-check only. The control
// path uses interval timing, which is far more precise. 40ms captures ~12
// pulses at 1500 RPM.
#define RPM_SAMPLE_MIN_US 40000

// Soft-start ramp duration, applied on every re-arm.
#define SOFT_START_DURATION_MS 1500

// Zero-throttle window held after boot so the driver arms before it sees load.
#define ESC_ARM_DURATION_MS 2000

// Sensor-loss / stall detection. 150ms is ~14x the pulse period at 1440 RPM,
// so it cannot trip on normal ripple, but does catch a genuine loss of signal.
#define STALL_TIMEOUT_MS 150

#endif // CONFIG_H
