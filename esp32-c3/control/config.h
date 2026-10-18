#ifndef CONFIG_H
#define CONFIG_H

// Hardware Pins (ESP32-C3 SuperMini)
#define RPM_INPUT_PIN 0       // GPIO 0 (Requires Voltage Divider 5V->3.3V)
#define PWM_OUTPUT_PIN 1      // GPIO 1
#define POT_ENABLE_PIN 3      // GPIO 3 - Pull LOW to enable sensitivity trim (INPUT_PULLUP)
#define POT_SENSITIVITY_PIN 2 // GPIO 2 (ADC1_CH2) - trims PID gain scale

// Pot maps a multiplier on DEFAULT_KP / DEFAULT_KI / DEFAULT_KD (target RPM stays 1440)
#define PID_SENSITIVITY_MIN 0.75f
#define PID_SENSITIVITY_MAX 1.25f

// Motor Configuration
//
// Pulses per revolution of the JYQD Signal output, derived from the motor
// datasheet (docs/motor_specification/):
//   42BLF: 8 poles = 4 pole pairs, 3-phase, Hall effect angle 120 deg electrical.
//
// The driver XORs Ha/Hb/Hc together into one square wave. XOR of three 120 deg
// halls alternates across all six valid states, so the output completes 3 full
// cycles per electrical revolution. With 4 pole pairs that is 4 x 3 = 12 cycles
// per mechanical revolution, i.e. 12 signal periods per turn.
//
//   PPR = 3 x pole_pairs = 3 x (poles / 2)
//
// The previous value of 4 was wrong and inflated every RPM reading by 25%.
#define PULSES_PER_REV 12

// RPM measurement: min integration window (us). 40ms captures ~12 pulses at
// 1500 RPM with PPR 12, which keeps quantization noise low without adding
// enough lag to hurt PID stability.
#define RPM_SAMPLE_MIN_US 40000

// Soft-Start
#define SOFT_START_DURATION_MS 1500 // 1.5 seconds

// ESC arming: hold zero throttle this long after boot so the ESC arms
// before the soft-start ramp begins. Increase to 2500-3000 if your ESC
// needs a longer arming window.
#define ESC_ARM_DURATION_MS 2000

// Stall / sensor-loss failsafe: if no pulse arrives for this long while the
// motor has reached near-target speed, power is cut to protect the motor/driver.
// 150ms is ~14x the target pulse period (10.4ms @ 1440 RPM).
#define STALL_TIMEOUT_MS 150

#endif // CONFIG_H
