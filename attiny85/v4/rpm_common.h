#ifndef RPM_COMMON_H
#define RPM_COMMON_H

#include <Arduino.h>

// Shared RPM calculation functions with period measurement

// Timer rollover safe interval calculation
inline unsigned long safeInterval(unsigned long current, unsigned long previous) {
    if (current >= previous) {
        return current - previous;
    } else {
        return (0xFFFFFFFFUL - previous) + current + 1;
    }
}

// Exponential Moving Average (EMA) filter update (Float)
// alpha: Smoothing factor between 0 and 1. Lower = smoother but slower response.
inline void updateEMA(float &filteredValue, float newValue, float alpha) {
    filteredValue = (alpha * newValue) + ((1.0 - alpha) * filteredValue);
}

// Exponential Moving Average (EMA) filter update for integer values
// alpha_scaled: Smoothing factor scaled by 100 (e.g. 25 = 0.25)
inline void updateEMAInt(int &filteredValue, int newValue, int alpha_scaled) {
    // filtered = (alpha * new) + ((100 - alpha) * old) / 100
    filteredValue =
        (int)(((long)alpha_scaled * newValue + (long)(100 - alpha_scaled) * filteredValue) / 100);
}

// Median Filter: Eliminates spikes by picking the middle value of recent readings
// Perfect for removing "shot noise" from interrupt timing jitter
#define MEDIAN_SIZE 3
inline float getMedian(float newValue, float history[], int &index) {
    // Add new value to circular buffer
    history[index] = newValue;
    index = (index + 1) % MEDIAN_SIZE;

    // Copy to temp array for sorting
    float sorted[MEDIAN_SIZE];
    for (int i = 0; i < MEDIAN_SIZE; i++)
        sorted[i] = history[i];

    // Bubble sort (fastest for very small arrays like 5)
    for (int i = 0; i < MEDIAN_SIZE - 1; i++) {
        for (int j = 0; j < MEDIAN_SIZE - i - 1; j++) {
            if (sorted[j] > sorted[j + 1]) {
                float temp = sorted[j];
                sorted[j] = sorted[j + 1];
                sorted[j + 1] = temp;
            }
        }
    }

    // Return the middle element
    return sorted[MEDIAN_SIZE / 2];
}

#endif // RPM_COMMON_H
