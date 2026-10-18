#ifndef PCNT_DRIVER_H
#define PCNT_DRIVER_H

#include <Arduino.h>

// RPM Configuration
#ifndef PULSES_PER_REV
#define PULSES_PER_REV 4
#endif

// Age after which a missing pulse counts as "stopped" rather than "slow".
// Normally supplied by config.h; defaulted here so this header stands alone.
#ifndef STALL_TIMEOUT_MS
#define STALL_TIMEOUT_MS 150
#endif

// Minimum integration window (microseconds) for stable RPM measurement.
// At 1440 RPM @ 4 PPR = 96 pulses/s. 40ms yields ~4 pulses (vs ~0.5 at 5ms).
// Longer window = less quantization noise, slightly higher measurement latency.
#ifndef RPM_SAMPLE_MIN_US
#define RPM_SAMPLE_MIN_US 40000
#endif

// Compute a fresh RPM estimate once this many pulses have accumulated (even
// before the full window elapses). Keeps the PID from running on a stale RPM
// between window boundaries. At 1440 RPM (96 pulses/s) 2 pulses ~= 20ms.
#ifndef RPM_MIN_PULSES
#define RPM_MIN_PULSES 2
#endif

static volatile uint32_t pulse_count = 0;
static unsigned long last_rpm_reset_time = 0;
static uint32_t accumulated_pulses = 0;
static float last_computed_rpm = 0.0;

// Timestamp of the most recent pulse, for stall/sensor-loss detection.
static volatile unsigned long last_pulse_micros = 0;

// Monotonic diagnostics. pulse_count is drained every control cycle, so these
// two survive it: they answer "did the ISR ever fire at all?" and "what is the
// period between pulses?", which is the only way to tell a dead Hall/sensor
// path from a stopped motor.
static volatile uint32_t total_pulses = 0;
static volatile unsigned long last_period_us = 0;
static volatile unsigned long prev_pulse_micros = 0;

// Ring of recent inter-pulse intervals. Real rotor commutation from a spinning
// motor is highly regular; electrical noise picked up off the phase wires is
// not. Comparing the spread of these values is what separates a genuinely
// turning motor from a sensor line that is merely being disturbed by PWM.
#define PERIOD_HISTORY 32
static volatile unsigned long period_hist[PERIOD_HISTORY];
static volatile uint8_t period_hist_idx = 0;

// Smoothed inter-pulse interval, used as the primary speed measurement.
//
// Counting pulses inside a fixed window quantises hard: at 1440 RPM with 12
// pulses/rev a 40ms window holds ~11.5 pulses, so one pulse of error is ~8.7%,
// or +-125 RPM. That noise floor is comparable to the PID's own tuning error and
// makes real stability impossible to judge. Timing the interval directly has
// microsecond resolution instead, roughly a hundred times finer.
//
// Fixed-point EMA, updated once per pulse, so the ISR cost stays a single
// subtract and shift.
#define PERIOD_EMA_SHIFT 2 // divide-by-4 smoothing per pulse
static volatile unsigned long period_ema_us = 0;

static void IRAM_ATTR pcnt_isr_handler() {
    unsigned long now = micros();
    last_period_us = now - prev_pulse_micros;
    prev_pulse_micros = now;
    last_pulse_micros = now;
    period_hist[period_hist_idx] = last_period_us;
    period_hist_idx = (uint8_t)((period_hist_idx + 1) % PERIOD_HISTORY);
    if (period_ema_us == 0) {
        period_ema_us = last_period_us;
    } else {
        // Signed difference: as the motor accelerates the interval shrinks, and
        // an unsigned subtraction there underflows to ~4e9 and wrecks the EMA.
        long diff = (long)last_period_us - (long)period_ema_us;
        period_ema_us += (unsigned long)(diff >> PERIOD_EMA_SHIFT);
    }
    pulse_count++;
    total_pulses++;
}

inline void pcnt_init(int gpio_num) {
    pinMode(gpio_num, INPUT_PULLUP);
    attachInterrupt(digitalPinToInterrupt(gpio_num), pcnt_isr_handler, RISING);
    last_rpm_reset_time = micros();
    last_pulse_micros = last_rpm_reset_time;
    prev_pulse_micros = last_rpm_reset_time;
    accumulated_pulses = 0;
    last_computed_rpm = 0.0;
    total_pulses = 0;
    last_period_us = 0;
    period_ema_us = 0;
    period_hist_idx = 0;
    for (int i = 0; i < PERIOD_HISTORY; i++) {
        period_hist[i] = 0;
    }
}

// Wipes the interval history so the next measurement only reflects pulses
// arriving from now on. Without this, `w` happily reports whatever the buffer
// happened to contain from an earlier trial, which reads as a live measurement
// and is worse than having no measurement at all.
inline void pcnt_clear_history() {
    noInterrupts();
    period_hist_idx = 0;
    for (int i = 0; i < PERIOD_HISTORY; i++) {
        period_hist[i] = 0;
    }
    interrupts();
}

// Copies the interval history out and reports its spread. A steady rotor gives
// a tight distribution around one value; a noisy or losing-sync rotor gives a
// wide one. Coherent commutation has low jitter, so this is the cheapest way to
// tell a motor that is actually turning from a line full of junk edges.
inline void pcnt_period_stats(float &meanUs, float &stddevUs, unsigned long &minUs,
                              unsigned long &maxUs, int &samples) {
    unsigned long snap[PERIOD_HISTORY];
    noInterrupts();
    uint8_t idx = period_hist_idx;
    for (int i = 0; i < PERIOD_HISTORY; i++) {
        snap[i] = period_hist[i];
    }
    interrupts();

    float sum = 0.0f;
    int n = 0;
    minUs = 0;
    maxUs = 0;
    for (int i = 0; i < PERIOD_HISTORY; i++) {
        if (snap[i] == 0) {
            continue; // unfilled slot
        }
        sum += (float)snap[i];
        n++;
        if (minUs == 0 || snap[i] < minUs) {
            minUs = snap[i];
        }
        if (snap[i] > maxUs) {
            maxUs = snap[i];
        }
    }
    samples = n;
    if (n == 0) {
        meanUs = stddevUs = 0.0f;
        return;
    }
    meanUs = sum / (float)n;
    float var = 0.0f;
    for (int i = 0; i < PERIOD_HISTORY; i++) {
        if (snap[i] == 0) {
            continue;
        }
        float d = (float)snap[i] - meanUs;
        var += d * d;
    }
    stddevUs = sqrtf(var / (float)n);
}

// Raw interval history, newest last. Printed as a list so the actual shape of
// the signal is visible rather than just its summary statistics.
inline void pcnt_dump_periods(unsigned long *out, int maxOut) {
    noInterrupts();
    uint8_t idx = period_hist_idx;
    for (int i = 0; i < maxOut; i++) {
        uint8_t src = (uint8_t)((idx + i) % PERIOD_HISTORY);
        out[i] = period_hist[src];
    }
    interrupts();
}

// Pulses seen since boot, never drained. Stays 0 => GPIO0 saw nothing: bad
// divider, no Hall power, wrong pin, or the motor genuinely never turned.
inline uint32_t pcnt_total_pulses() {
    noInterrupts();
    uint32_t t = total_pulses;
    interrupts();
    return t;
}

// Smoothed inter-pulse interval, the quantity RPM is actually derived from.
inline unsigned long pcnt_period_ema_us() {
    noInterrupts();
    unsigned long t = period_ema_us;
    interrupts();
    return t;
}

// Interval between the last two pulses. 0 until two pulses have landed. At 4
// PPR this is 60/(rpm*4) seconds, so 10.4ms => ~1440 RPM.
inline unsigned long pcnt_last_period_us() {
    noInterrupts();
    unsigned long t = last_period_us;
    interrupts();
    return t;
}

// Pulses accumulated since the previous call, for a live per-second rate.
inline uint32_t pcnt_pulses_since(uint32_t &mark) {
    uint32_t now = pcnt_total_pulses();
    uint32_t delta = now - mark;
    mark = now;
    return delta;
}

// Returns RPM from the smoothed inter-pulse interval.
//
//   RPM = 60e6 / (period_us * PULSES_PER_REV)
//
// Falls back to 0 once pulses stop arriving, so a stopped rotor reports a stop
// rather than freezing on its last known speed. STALL_TIMEOUT_MS is reused here
// as the "no fresh data" horizon.
inline float pcnt_get_rpm() {
    noInterrupts();
    unsigned long ema = period_ema_us;
    unsigned long last = last_pulse_micros;
    interrupts();

    if (ema == 0 || (micros() - last) > (unsigned long)STALL_TIMEOUT_MS * 1000UL) {
        return 0.0f;
    }
    // Guard against an implausibly short interval (glitch edge) producing an
    // absurd speed reading.
    if (ema < 200) {
        return 0.0f;
    }
    return 60000000.0f / ((float)ema * (float)PULSES_PER_REV);
}

// Pulse-counting estimator, retained purely as a cross-check for the waveform
// diagnostics. Not used by the control loop.
inline float pcnt_get_rpm_counted() {
    noInterrupts();
    uint32_t count = pulse_count;
    pulse_count = 0;
    unsigned long now = micros();
    interrupts();

    accumulated_pulses += count;
    unsigned long interval_us = now - last_rpm_reset_time;

    if (interval_us >= RPM_SAMPLE_MIN_US || accumulated_pulses >= RPM_MIN_PULSES) {
        if (interval_us > 0) {
            last_computed_rpm = ((float)accumulated_pulses * 60000000.0f) /
                                ((float)interval_us * (float)PULSES_PER_REV);
        }
        accumulated_pulses = 0;
        last_rpm_reset_time = now;
    }

    return last_computed_rpm;
}

// Microseconds since the last detected pulse. Used by the stall failsafe.
inline unsigned long pcnt_pulse_age_us() {
    noInterrupts();
    unsigned long t = last_pulse_micros;
    interrupts();
    return micros() - t;
}

#endif // PCNT_DRIVER_H
