# ATtiny85 v4 — Deadband + Oversampling PID

Minimal BLDC controller. v1 spin path (single-period PCINT ISR, median+EMA,
kickstart soft-start, float PID) plus loop-side oversampling and deadband.
No emergency-stop, no stall state machine, no trim pot.

| Mechanism | Param | Value | Why |
|---|---|---|---|
| Oversampling | `OVERSAMPLE_N` | 4 raw RPMs | mean rejects single-pulse jitter before median+EMA |
| Deadband | `DEADBAND_RPM` | ±30 rpm | hold last PWM + freeze integrator inside band; stops hunting |
| PID | Kp 0.15 / Ki 0.08 / Kd 0.015 | Uno-proven | clamp anti-windup only |
| Test target | `DEFAULT_TARGET_RPM` | 300 (debug) | production: 1440 |
| Pulses/rev | `DEFAULT_PULSES_PER_REV` | 1 (test) | external single-magnet hall; internal 8-pole hall = 4 |

Tune: oscillation → widen deadband (40–50); slow settle → narrow (15–20)
or raise N to 8.

## Pinout (DIP-8, notch/dot at top)

```
        ┌──◡──┐
  VCC ──┤1  8 ├── VCC (5V / RST — leave as programmer had it)
  PB3 ──┤2  7 ├── PB2 (NC)
  PB4 ──┤3  6 ├── PB1 (debug LED → GND via 220Ω–1k, or meter)
  GND ──┤4  5 ├── PB0 (PWM → ESC signal, white/yellow)
        └─────┘
```

| Pin | Name | Connects to |
|-----|------|-------------|
| 1 | VCC | 5V supply |
| 2 | PB3 | Hall sensor signal (INPUT_PULLUP enabled in firmware) |
| 3 | PB4 | unused |
| 4 | GND | **common GND** — PSU, ESC, sensor, LED all tied together |
| 5 | PB0 | ESC signal wire |
| 6 | PB1 | debug heartbeat: HIGH = pulses arriving, LOW = sensor silent |
| 7 | PB2 | unused |
| 8 | PB5/RST | 5V (programmer manages this — don't rewire) |

GND must be common between ATtiny, ESC/battery, and hall sensor. The hall
module needs its own VCC/GND supply wires, not just the signal wire.

## Debug LED

`DEBUG_PULSE_LED 1` mirrors "pulses seen in last 500 ms" on PB1. Delete
(`DEBUG_PULSE_LED 0`) once the sensor path is verified.
