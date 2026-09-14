#ifndef RPM_COMMON_H
#define RPM_COMMON_H

// Window + IIR combo. 12 samples @ 200Hz ~= 60ms averaging: enough to
// smooth the ~20ms pcnt updates at 1440 RPM without the ~150ms lag a
// 24-sample window adds (phase lag directly hurts PID stability).
#define RPM_FILTER_SIZE 12

// IIR coefficient (0.0-1.0). Lower = smoother, higher = more responsive.
#define RPM_IIR_ALPHA 0.45f

class RPMFilter {
  private:
    float buffer[RPM_FILTER_SIZE];
    int index;
    int count;
    float sum;
    float iir_state;

  public:
    RPMFilter() : index(0), count(0), sum(0.0f), iir_state(0.0f) {
        for (int i = 0; i < RPM_FILTER_SIZE; i++) {
            buffer[i] = 0.0f;
        }
    }

    float update(float newValue) {
        sum -= buffer[index];
        buffer[index] = newValue;
        sum += newValue;
        index = (index + 1) % RPM_FILTER_SIZE;

        if (count < RPM_FILTER_SIZE) {
            count++;
        }
        float ma = sum / (float)count;
        iir_state = RPM_IIR_ALPHA * ma + (1.0f - RPM_IIR_ALPHA) * iir_state;
        return iir_state;
    }

    void reset() {
        index = 0;
        count = 0;
        sum = 0.0f;
        iir_state = 0.0f;
        for (int i = 0; i < RPM_FILTER_SIZE; i++) {
            buffer[i] = 0.0f;
        }
    }
};

#endif // RPM_COMMON_H
