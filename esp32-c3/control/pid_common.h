#ifndef PID_COMMON_H
#define PID_COMMON_H

#include <Arduino.h>

#ifndef D_TERM_FILTER_ALPHA
#define D_TERM_FILTER_ALPHA 0.30f
#endif

// Positional PID, dt-correct, output directly in PWM counts.
//
// Units:
//   kp: PWM per RPM of error
//   ki: PWM per (RPM * second) of integrated error
//   kd: PWM per (RPM/second) of measured-speed slope
//
// Derivative acts on MEASUREMENT (not error) so the fixed 1440 setpoint
// never causes derivative kick. Setpoint is constant, so d(error)/dt
// equals -d(meas)/dt anyway, minus the kick.
inline float computePID_float(float error, float measurement, float &integral,
                              float &prevMeasurement, float &filteredDerivative, float kp,
                              float ki, float kd, float dt, float integral_min,
                              float integral_max, float output_min, float output_max) {
    float proportional = kp * error;

    integral += ki * error * dt;
    integral = constrain(integral, integral_min, integral_max);

    float rawSlope = (measurement - prevMeasurement) / dt;
    prevMeasurement = measurement;
    filteredDerivative =
        D_TERM_FILTER_ALPHA * rawSlope + (1.0f - D_TERM_FILTER_ALPHA) * filteredDerivative;
    float derivative = -kd * filteredDerivative;

    float output = proportional + integral + derivative;
    output = constrain(output, output_min, output_max);

    return output;
}

#endif // PID_COMMON_H
