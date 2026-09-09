#ifndef ISR_COMMON_H
#define ISR_COMMON_H

#include <Arduino.h>

// Shared ISR functions for period measurement

// Generic RPM sensor ISR with rollover protection
// Updates pulseInterval with the measured period between pulses
inline void rpmSensorISR_common(unsigned long currentTime, volatile unsigned long &lastPulseMicros,
                                volatile unsigned long &pulseInterval,
                                unsigned long minPulseWidthUs) {
    // Handle timer rollover
    unsigned long interval;
    if (currentTime >= lastPulseMicros) {
        // Normal case: no rollover
        interval = currentTime - lastPulseMicros;
    } else {
        // Rollover occurred: timer wrapped from 0xFFFFFFFF to 0
        interval = (0xFFFFFFFFUL - lastPulseMicros) + currentTime + 1;
    }

    if (interval > minPulseWidthUs) {
        pulseInterval = interval;
        lastPulseMicros = currentTime;
    }
}

#endif // ISR_COMMON_H
