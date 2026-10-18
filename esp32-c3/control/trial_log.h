#ifndef TRIAL_LOG_H
#define TRIAL_LOG_H

#include <Arduino.h>
#include <Preferences.h>

// Hall-permutation trial recorder.
//
// Swapping a Hall wire requires cutting power to be safe, and the useful
// observation happens after power comes back -- so RAM-scraped results are
// useless here. Each trial is therefore scored automatically during a fixed
// window after boot and appended to NVS, where a cold cycle cannot erase it.
// The operator ends up with a ranked table instead of a memory of what felt
// better.

#define TRIAL_MAX 10
#define TRIAL_LABEL_MAX 12
#define TRIAL_CAPTURE_MS 12000 // score over this window, starting after arming
#define TRIAL_START_MS 3000    // let the ESC arm and the soft-start begin first

struct TrialRecord {
    char label[TRIAL_LABEL_MAX];
    uint32_t bestPeriodUs; // fastest sustained => fastest real rotation
    uint32_t worstPeriodUs;
    uint32_t pulseCount;
    uint16_t uptimeMs;
    uint16_t jitterPct; // 0-1000 = 0.0-100.0%, period stddev / mean
    uint8_t valid;
};

// Capture accumulator, fed once per pulse rather than once per control cycle so
// every inter-pulse interval is measured exactly once.
struct TrialCapture {
    bool active;
    uint32_t samples;
    double sumUs;
    double sumSqUs;
    uint32_t minUs;
    uint32_t maxUs;
    uint32_t lastCount;
    uint32_t startMs;
};

static Preferences trialPrefs;
static TrialRecord trialRecords[TRIAL_MAX];
static TrialCapture trialCap;

static void trialLoad() {
    trialPrefs.begin("bldc", true);
    size_t n = trialPrefs.getBytesLength("trials");
    if (n == sizeof(trialRecords)) {
        trialPrefs.getBytes("trials", trialRecords, sizeof(trialRecords));
    } else {
        memset(trialRecords, 0, sizeof(trialRecords));
    }
    trialPrefs.end();
}

static void trialSave() {
    trialPrefs.begin("bldc", false);
    trialPrefs.putBytes("trials", trialRecords, sizeof(trialRecords));
    trialPrefs.end();
}

// Labels the configuration currently wired up. Persisted so it survives the
// power cycle that happens before the trial is scored.
static void trialSetLabel(const char *label) {
    char buf[TRIAL_LABEL_MAX];
    strncpy(buf, label, TRIAL_LABEL_MAX - 1);
    buf[TRIAL_LABEL_MAX - 1] = '\0';
    trialPrefs.begin("bldc", false);
    trialPrefs.putString("label", buf);
    trialPrefs.end();
    Serial.printf("next trial will be tagged \"%s\" -- now swap and power cycle\r\n", buf);
}

static void trialGetLabel(char *out) {
    trialPrefs.begin("bldc", true);
    String s = trialPrefs.getString("label", "untagged");
    trialPrefs.end();
    strncpy(out, s.c_str(), TRIAL_LABEL_MAX - 1);
    out[TRIAL_LABEL_MAX - 1] = '\0';
}

static void trialBeginCapture() {
    trialCap.active = true;
    trialCap.samples = 0;
    trialCap.sumUs = 0.0;
    trialCap.sumSqUs = 0.0;
    trialCap.minUs = 0;
    trialCap.maxUs = 0;
    trialCap.lastCount = pcnt_total_pulses();
    trialCap.startMs = millis();
}

// Consumes any newly arrived pulse each control cycle and finalises the record
// once the capture window closes.
static void trialTick() {
    if (!trialCap.active) {
        return;
    }
    uint32_t count = pcnt_total_pulses();
    if (count != trialCap.lastCount) {
        uint32_t period = pcnt_last_period_us();
        trialCap.lastCount = count;
        if (period > 500 && period < 200000) { // reject glitch-length edges
            trialCap.samples++;
            trialCap.sumUs += (double)period;
            trialCap.sumSqUs += (double)period * (double)period;
            if (trialCap.minUs == 0 || period < trialCap.minUs) {
                trialCap.minUs = period;
            }
            if (period > trialCap.maxUs) {
                trialCap.maxUs = period;
            }
        }
    }

    if (millis() - trialCap.startMs < TRIAL_CAPTURE_MS) {
        return;
    }
    trialCap.active = false;

    uint32_t uptime = millis() - trialCap.startMs;
    uint8_t slot = TRIAL_MAX;
    for (uint8_t i = 0; i < TRIAL_MAX; i++) {
        if (!trialRecords[i].valid) {
            slot = i;
            break;
        }
        if (i == TRIAL_MAX - 1) {
            slot = i; // overwrite the oldest when full
        }
    }
    if (slot == TRIAL_MAX) {
        return;
    }

    TrialRecord &r = trialRecords[slot];
    trialGetLabel(r.label);
    r.pulseCount = trialCap.samples;
    r.uptimeMs = (uint16_t)uptime;
    r.bestPeriodUs = trialCap.minUs;
    r.worstPeriodUs = trialCap.maxUs;
    r.valid = 1;

    if (trialCap.samples >= 2) {
        double mean = trialCap.sumUs / (double)trialCap.samples;
        double var = trialCap.sumSqUs / (double)trialCap.samples - mean * mean;
        if (var < 0.0) {
            var = 0.0;
        }
        double sd = sqrt(var);
        long pct = (long)((sd / mean) * 1000.0);
        r.jitterPct = (uint16_t)(pct > 1000 ? 1000 : pct);
    } else {
        r.jitterPct = 1000; // effectively no signal
    }

    trialSave();
    Serial.printf("[trial] \"%s\" recorded: %lu pulses, best %.1f ms, jitter %.1f%%\r\n", r.label,
                  (unsigned long)r.pulseCount, r.bestPeriodUs / 1000.0f, r.jitterPct / 10.0f);
}

// Ranking rule: a configuration that never produced a usable signal ranks last,
// then faster rotations win, with jitter as the tie-breaker. Lowest jitter means
// the Hall sequence lines up with the windings, which is what actually
// determines commutation quality.
static bool trialBetter(const TrialRecord &a, const TrialRecord &b) {
    bool aDead = (a.pulseCount < 5 || a.bestPeriodUs == 0);
    bool bDead = (b.pulseCount < 5 || b.bestPeriodUs == 0);
    if (aDead != bDead) {
        return !aDead;
    }
    if (aDead && bDead) {
        return false;
    }
    if (a.bestPeriodUs != b.bestPeriodUs) {
        return a.bestPeriodUs < b.bestPeriodUs;
    }
    return a.jitterPct < b.jitterPct;
}

// Ranks trials: fastest first, and jittery ones sink. This is the answer to
// "which Hall permutation do I solder", without relying on feel.
static void trialPrintTable() {
    int found = 0;
    for (uint8_t i = 0; i < TRIAL_MAX; i++) {
        if (trialRecords[i].valid) {
            found++;
        }
    }
    if (found == 0) {
        Serial.println(F("no trials recorded yet"));
        return;
    }

    // Insertion sort on a copy; TRIAL_MAX is tiny.
    TrialRecord sorted[TRIAL_MAX];
    memcpy(sorted, trialRecords, sizeof(sorted));
    for (uint8_t i = 1; i < TRIAL_MAX; i++) {
        TrialRecord key = sorted[i];
        int8_t j = i - 1;
        while (j >= 0 && trialBetter(key, sorted[j])) {
            sorted[j + 1] = sorted[j];
            j--;
        }
        sorted[j + 1] = key;
    }

    Serial.println(F("\r\n  rank  label       pulses  best(ms)  jitter%   true RPM"));
    Serial.println(F("  ---------------------------------------------------------------"));
    for (uint8_t i = 0; i < TRIAL_MAX; i++) {
        if (!sorted[i].valid) {
            continue;
        }
        float rpm = (sorted[i].bestPeriodUs > 0)
                        ? (60.0e6f / (float)sorted[i].bestPeriodUs / (float)PULSES_PER_REV)
                        : 0.0f;
        Serial.printf("  %4d  %-10s %6lu  %8.2f  %6.1f%%  %8.0f\n", i + 1, sorted[i].label,
                      (unsigned long)sorted[i].pulseCount, sorted[i].bestPeriodUs / 1000.0f,
                      sorted[i].jitterPct / 10.0f, rpm);
    }
    Serial.println(F("  ---------------------------------------------------------------"));
    Serial.println(F("  lowest jitter + highest true RPM = correct Hall permutation"));
    Serial.println();
}

#endif // TRIAL_LOG_H
