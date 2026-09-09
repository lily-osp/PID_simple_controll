#ifndef PID_COMMON_H
#define PID_COMMON_H

#include <Arduino.h>

// Shared PID computation functions with overflow protection

// Floating-point PID computation with overflow protection
// Used by auto_tune and arduino_uno projects
inline float computePID_float(float error, float &integral, float &previousError, float kp,
                              float ki, float kd, float integral_min, float integral_max,
                              float output_min, float output_max) {
    // Proportional term with overflow protection
    float proportional = 0.0;
    if (isfinite(kp) && isfinite(error) && fabs(kp) < 1e6 && fabs(error) < 1e6) {
        proportional = kp * error;
        if (!isfinite(proportional))
            proportional = 0.0;
    }

    // Integral term with anti-windup and overflow protection
    if (isfinite(ki) && isfinite(error) && fabs(ki) < 1e6 && fabs(error) < 1e6) {
        float integral_increment = ki * error;
        if (isfinite(integral_increment)) {
            integral += integral_increment;
        }
    }

    // Clamp integral to prevent windup
    integral = constrain(integral, integral_min, integral_max);

    // Derivative term with overflow protection
    float derivative = 0.0;
    if (isfinite(kd) && isfinite(error) && isfinite(previousError) && fabs(kd) < 1e6 &&
        fabs(error) < 1e6 && fabs(previousError) < 1e6) {
        float error_diff = error - previousError;
        if (isfinite(error_diff)) {
            derivative = kd * error_diff;
            if (!isfinite(derivative))
                derivative = 0.0;
        }
    }
    previousError = error;

    // Calculate total PID output
    float output = proportional + integral + derivative;

    // Check for output overflow
    if (!isfinite(output)) {
        output = 0.0;   // Reset on overflow
        integral = 0.0; // Reset integral accumulator
    }

    // Clamp output to safe range
    output = constrain(output, output_min, output_max);

    return output;
}

// Fixed-point PID computation with overflow protection
// Used by attiny85 project
inline int computePID_fixed(int error_scaled, long &integral_scaled, int &previousError_scaled,
                            int kp_scaled, int ki_scaled, int kd_scaled, int integral_min,
                            int integral_max, int output_min, int output_max) {
    // Proportional term with overflow protection: kp_scaled * error_scaled / 1000
    long proportional = 0;
    if (abs(kp_scaled) < 32767 && abs(error_scaled) < 32767) { // Prevent overflow in multiplication
        long temp = (long)kp_scaled * error_scaled;
        if (temp / 1000 < 2147483647L && temp / 1000 > -2147483648L) { // Check division result
            proportional = temp / 1000;
        }
    }

    // Integral term with anti-windup and overflow protection: integral_scaled += ki_scaled *
    // error_scaled / 100
    if (abs(ki_scaled) < 32767 && abs(error_scaled) < 32767) { // Prevent overflow in multiplication
        long temp = (long)ki_scaled * error_scaled;
        if (temp < 2147483647L && temp > -2147483648L) { // Check division result
            integral_scaled += temp;
        }
    }

    // Clamp integral to prevent windup
    long integral_max_scaled = (long)integral_max * 1000;
    long integral_min_scaled = (long)integral_min * 1000;
    if (integral_scaled > integral_max_scaled)
        integral_scaled = integral_max_scaled;
    if (integral_scaled < integral_min_scaled)
        integral_scaled = integral_min_scaled;

    // Derivative term with overflow protection: kd_scaled * (error_scaled - previousError_scaled) /
    // 1000
    long derivative = 0;
    long error_diff = (long)error_scaled - previousError_scaled;
    if (abs(kd_scaled) < 32767 && abs(error_diff) < 2147483647L) { // Prevent overflow
        long temp = (long)kd_scaled * error_diff;
        if (temp / 1000 < 2147483647L && temp / 1000 > -2147483648L) { // Check division result
            derivative = temp / 1000;
        }
    }
    previousError_scaled = error_scaled;

    // Calculate total PID output: proportional + (integral_scaled/1000) + derivative
    long output = proportional + (integral_scaled / 1000) + derivative;

    // Clamp output to safe range
    if (output > output_max)
        output = output_max;
    if (output < output_min)
        output = output_min;

    return (int)output;
}

#endif // PID_COMMON_H
