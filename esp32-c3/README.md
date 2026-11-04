# ESP32-C3 BLDC PID Controller

Fixed-target PID controller for BLDC motors on the ESP32-C3, run bare-metal
for compute (no WiFi, no BLE). Holds 1440 RPM via a 200Hz FreeRTOS loop.

## Table of Contents

- [Overview](#overview)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
- [Hardware Setup](#hardware-setup)
- [Firmware](#firmware)
- [Software Architecture](#software-architecture)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Builds](BUILDS.md) — production vs bench firmware, and how they share code
- [Diagnostics Guide](DIAGNOSTICS.md) — serial console commands and fault isolation

## Overview

This project implements a fixed-target (1440 RPM) PID controller for BLDC
motors on the ESP32-C3 platform. It uses hardware-accelerated PWM,
interrupt-driven RPM sensing, and a real-time control loop. No wireless
stack is used; the C3 is here for its 160MHz RISC-V core and hardware FPU.

### Key Features

- **200Hz Control Loop**: High-frequency PID updates via dedicated FreeRTOS task
- **Hardware-Accelerated PWM**: ESP32 LEDC peripheral generating smooth 5kHz motor control signals
- **Interrupt-Driven RPM**: High-precision pulse counting using IRAM-resident ISR
- **Sliding Window Filter**: 12-sample window + IIR smoothing for stable control input
- **ESC Arming + Soft-Start**: 2s zero-throttle arm, then 1.5s power ramp
- **FPU Utilization**: Full floating-point PID calculations for maximum precision

## Project Structure

```
esp32-c3/
├── embedded/              # PRODUCTION build: silent, autonomous, for the enclosure
│   ├── embedded.ino       # Control loop, arming, soft-start, stall failsafe
│   ├── config.h           # Pins, motor, PPR, arming and failsafe timing
│   └── config_common.h    # Tuned gains + ENABLE_SERIAL_LOG flag
├── control/               # BENCH build: serial console for bring-up and service
│   ├── control.ino        # Main entry point + mode state machine
│   ├── console.h          # Command parser, telemetry, diagnostics
│   ├── control_state.h    # Shared state between control task and console
│   ├── trial_log.h        # Auto-scores each power cycle to rank Hall permutations
│   ├── config.h           # Hardware pins and motor settings
│   ├── config_common.h    # PID gains and control loop constants
│   ├── ledc_driver.h      # ESP32 LEDC PWM driver (5 kHz, 8-bit)     [shared]
│   ├── pcnt_driver.h      # Interval-based RPM measurement + GPIO ISR [shared]
│   ├── pid_common.h       # Floating-point PID, dt-correct            [shared]
│   └── rpm_common.h       # Sliding window + IIR RPM filter           [shared]
├── BUILDS.md              # Which build to use, and how they share code
├── DIAGNOSTICS.md         # Console reference and fault isolation
└── README.md              # This documentation
```

The four `[shared]` headers are included by `embedded/embedded.ino` via
`../control/`, so there is exactly one implementation of the RPM estimator, the
PID and the LEDC setup. Change them in `control/` only.

## Quick Start

> ⚠️ **Two things that will waste an afternoon if you skip them.** The Hall line
> sequence on the driver may not match your motor — transposition of two Hall
> lines took this project from 570 RPM with heavy jitter to stable closed-loop
> operation. And the ESP32 must **not** be powered from the driver's 5V output;
> the datasheet forbids it and the 3.3V rail sags badly enough to cause visible
> jitter whenever USB is absent. See [DIAGNOSTICS.md](DIAGNOSTICS.md).

1. **Hardware Setup**: RPM on GPIO 0 (divider if 5V), ESC on GPIO 1; trim pot on GPIO 3
2. **Configure**: Review `config.h` and `config_common.h` for motor-specific parameters
3. **Upload**: Flash using Arduino IDE or PlatformIO
4. **Monitor**: Open Serial Monitor at 115200 baud to verify startup

## Hardware Setup

### Required Components

- **ESP32-C3 SuperMini** (or any ESP32-C3 dev board)
- **JYQD-V7.3E3 BLDC driver board** (12–36V, ≤15A peak)
- **42BLF-series BLDC motor** (8-pole, 24V; e.g. 42BLF01 4000 RPM)
- **24V DC supply** for the motor (≥3A recommended)
- **5V supply or USB** for the ESP32-C3 logic
- **Resistors 2.2kΩ + 3.3kΩ** (Signal divider, see below)
- Optional: **10kΩ potentiometer** (gain trim)

### Tested combination

| Item | Spec |
|------|------|
| Driver | JYQD-V7.3E3, VR = PWM speed input (1–20 kHz range, we use 5 kHz) |
| Motor | 42BLF, 8-pole → `PULSES_PER_REV 4`, 24V, 4000 RPM max |
| Target | 1440 RPM ≈ 36% of max → operating PWM duty ≈ 25–35% |

### Full wiring diagram

Wire everything with **power OFF**. There are three separate
sub-circuits: high-current motor side, Hall sensors, and logic.

```
                        ┌──────────────────────┐
 Motor phases (thick)   │     JYQD-V7.3E3      │   Control port (logic)
 MA ─────────────────── │                      │
 MB ─────────────────── │     driver board     │   Signal ──[2.2k]──┬── GPIO 0 (ESP32-C3)
 MC ─────────────────── │                      │                    └──[3.3k]── GND
                        │                      │   VR ───────────────── GPIO 1
 Hall connector         │                      │   GND ──────────────── GND (common!)
 Ha ─────────────────── │                      │   Z/F ── NC (forward) / GND (reverse)
 Hb ─────────────────── │                      │   EL ── NC (floating = run)
 Hc ─────────────────── │                      │
 5V ─────────────────── │                      │   ESP32-C3 powered via USB
 GND ────────────────── │                      │   (or 5V pin) — separate from 24V
                        │                      │
 P+ ◄── 24V+ (thick)    │                      │   Trim pot:
 P- ◄── 24V- (thick)    │                      │   3V3──[10k pot]──GND, wiper→GPIO 3
                        └──────────────────────┘
```

### Wire-by-wire checklist

**High current (use thick wire, keep short):**

| From | To | Notes |
|------|----|-------|
| 24V supply + | JYQD `P+` | 12–36V motor bus |
| 24V supply − | JYQD `P−` | Common with Hall GND inside board |
| JYQD `MA` / `MB` / `MC` | Motor phases | Any order to start; if motor runs rough, swap two wires |

**Hall sensors (5-wire connector):**

| From | To | Notes |
|------|----|-------|
| JYQD `Ha` / `Hb` / `Hc` | Motor Hall outputs | Must match phase order |
| JYQD `5V` | Motor Hall VCC | Powers the motor's Hall sensors |
| JYQD `GND` | Motor Hall GND | |

**Control port (logic, thin wire OK):**

| JYQD pin | Connect to | Function |
|----------|-----------|----------|
| `VR` | ESP32 **GPIO 1** | PWM speed input. Firmware outputs 5 kHz, 0–255 duty |
| `Signal` | ESP32 **GPIO 0** via divider (below) | Speed pulse output, 4 pulses/rev |
| `GND` | ESP32 **GND** | ⚠️ Mandatory common ground |
| `Z/F` | Leave floating (forward), or tie to GND for reverse | Direction select |
| `EL` | Leave floating (= run) | Tie to GND to brake/stop (future: stall hard-cut) |

**ESP32-C3 power:** USB cable, or 5V into the `5V` pin + GND.
Never feed 24V into the ESP32. Never power the motor from the ESP32's 3V3 pin.

### Signal divider (5V → 3.3V)

The ESP32-C3 GPIOs are **NOT 5V tolerant**. The JYQD `Signal` pin
swings up to 5V, so it MUST go through a divider before GPIO 0:

```
JYQD Signal ──[ R1: 2.2kΩ ]──┬── GPIO 0
                             └──[ R2: 3.3kΩ ]── GND
```

Vout = 5V × 3.3 / (2.2 + 3.3) = **3.0V** (safe). If your board's
`Signal` already measures ≤3.3V on a scope, you may connect directly.

### VR logic-level note (3.3V vs 5V)

The JYQD `VR` input is designed around 5V logic, but it accepts PWM directly
(1–20 kHz, 0–100 % duty) and averages it internally, so a 3.3 V PWM through a
series resistor works: 0 % duty = 0 V = stop, 100 % duty = 3.3 V ≈ 66 % speed.

If you need the full 5 V range, add a **non-inverting** level shifter (e.g. a
TXS0102 or a proper gate-driver buffer). Do **not** use a single N-MOSFET with a
pull-up — that inverts the signal, so idle becomes full speed and the PID turns
into positive feedback. An earlier PCB revision made exactly that mistake.

### Layout rules (from the driver datasheet)

- Keep driver-to-motor wires **< 50 cm**; use **shielded cable**
  beyond that, ground the shield at one end.
- Route logic wiring (GPIO 0/1, GND) **away** from MA/MB/MC phase wires.
- Add a **0.1µF ceramic capacitor** between GPIO 0 and GND, close to
  the ESP32, if RPM readings are noisy.
- Verify with a cold motor: phases and PCB should stay cool;
  re-check MA/MB/MC + Ha/Hb/Hc order if the motor coggs or overheats.

### PID sensitivity trim

Target speed remains `DEFAULT_TARGET_RPM` (1440). The pot only
scales all three gains by the same factor so you can fine-tune
stability and steady-state error on the bench or on a production PCB.

Wire a 10K potentiometer wiper to GPIO 3:

```
3.3V ----[ Pot 10K ]---- GND
              |
           GPIO 3 (wiper)
```

The pot is always active and maps ≈ 0.75x–1.25x on `DEFAULT_KP`,
`DEFAULT_KI`, `DEFAULT_KD` (`PID_SENSITIVITY_MIN/MAX` in `config.h`).
Mid-travel is ≈ 1.0x, which is also what a board with no pot fitted
sees (a floating ADC input is clamped to the same range).

⚠️ GPIO 3 is `ADC1_CH3` and is **not** a strapping pin. Do not move the
wiper to GPIO 2: that is a boot strapping pin and the pot pulls it to
0 V at the low end of travel, which can stop the board from booting.
The PCB (`PCB/V1`) is wired for GPIO 3.

### Power-up sequence

1. Wiring done, motor shaft free, USB serial open at 115200.
2. Apply 24V motor supply, then USB (either order is safe; firmware
   holds zero throttle for `ESC_ARM_DURATION_MS` = 2 s so the driver arms).
3. Soft-start ramps power over `SOFT_START_DURATION_MS` = 1.5 s.
4. PID takes over and holds **1440 RPM**. Expect `pwm ≈ 65–90`
   (duty ≈ 25–35%) at steady state on 24V.

## Firmware

`control/` is the single production firmware: always-on fixed-target
control. On power-up it holds zero throttle for `ESC_ARM_DURATION_MS`
(so the ESC arms), ramps via soft-start over `SOFT_START_DURATION_MS`,
then the PID loop holds 1440 RPM. No start/stop commands, no wireless.

**Upload**: Flash `control/control.ino`

## Software Architecture

### Control Loop Architecture

The controller runs in a dedicated FreeRTOS task with highest priority (`configMAX_PRIORITIES - 1`), ensuring strict 5ms (200Hz) timing regardless of other system activities.

```
//   Main Loop (Low Priority)
//   - Serial heartbeat (1 Hz status print)
//   - Yields to the control task
//            ↓ (yields CPU)
//   Control Task (Highest Priority)
//   ┌─────────────────────────────┐
//   │ 1. Sensitivity scale (pot)  │
//   │ 2. Read RPM (pcnt_driver)   │
//   │ 3. Filter RPM (sliding win) │
//   │ 4. Compute PID (PWM units)  │
//   │ 5. Apply Soft-Start         │
//   │ 6. Output PWM (ledc_driver) │
//   └─────────────────────────────┘
//   vTaskDelayUntil(5ms)
// ```

### Core Drivers

**`pcnt_driver.h`**
- Interrupt-driven pulse counting via GPIO ISR (no PCNT peripheral dependency)
- Minimum integration window (40ms default) for low quantization noise
- At 1440 RPM @ 4 PPR: ~4 pulses per sample vs ~0.5 with 5ms window

**`ledc_driver.h`**
- Configures ESP32 LEDC peripheral for 5kHz PWM
- 8-bit resolution (0-255) for smooth control
- Direct hardware output, no software overhead

**`pid_common.h`**
- Floating-point PID, dt-correct, output directly in PWM counts (0-255)
- Anti-windup with integral clamping (0-255)
- Derivative on measurement (no setpoint kick), low-pass filtered

**`rpm_common.h`**
- Sliding window (12 samples) with IIR smoothing
- Decoupled from control period for stable averaging
- Real-time filtering with low latency

## Configuration

### Motor Settings (`config.h`)

```cpp
#define RPM_INPUT_PIN       0   // Hall sensor input
#define PWM_OUTPUT_PIN      1   // ESC control output
#define POT_SENSITIVITY_PIN   3   // Pot scales Kp/Ki/Kd (ADC1_CH3, always active)
#define PID_SENSITIVITY_MIN   0.75f
#define PID_SENSITIVITY_MAX   1.25f
#define PULSES_PER_REV        4   // Set to motor pole count / 2
#define RPM_SAMPLE_MIN_US     40000  // 40ms integration window
```

**PULSES_PER_REV**: For an 8-pole motor, use 4. Adjust based on your motor specifications.

**RPM_SAMPLE_MIN_US**: Minimum time to accumulate pulses before computing RPM. Longer = less fluctuation, higher latency. 40000 (40ms) yields ~4 pulses at 1440 RPM.

**PID_SENSITIVITY_MIN / MAX**: Gain multiplier range of the trim pot. Mid-travel is near 1.0 (nominal gains).

### PID Tuning (`config_common.h`)

```cpp
#define DEFAULT_TARGET_RPM 1440.0  // Target speed (fixed)
#define DEFAULT_KP         0.150   // PWM per RPM of error
#define DEFAULT_KI         0.120   // PWM per (RPM*s) integrated
#define DEFAULT_KD         0.004   // PWM per (RPM/s) of speed slope
```

**Tuning Guidelines**:
1. Start with Kp only (set Ki and Kd to 0)
2. Increase Kp until oscillation occurs, then reduce by 30%
3. Add Ki slowly to eliminate steady-state error
4. Add small Kd if overshoot occurs

### Control Parameters

```cpp
#define CONTROL_LOOP_HZ     200    // 200Hz update rate
#define PWM_MIN_THRESHOLD   45     // Minimum PWM for motor start
#define SOFT_START_DURATION_MS 1500 // Ramp-up time
```

### PWM Limits

```cpp
#define PWM_MIN_VALUE       0      // 0% throttle
#define PWM_MAX_VALUE       255    // 100% throttle
```

## Troubleshooting

### No RPM Signal

**Symptoms**: RPM reading stays at 0, motor doesn't respond

**Solutions**:
- Verify voltage divider connections (if using 5V sensor)
- Check Hall sensor power supply
- Confirm `PULSES_PER_REV` matches motor specifications
- Test Hall sensor output with oscilloscope or multimeter
- Ensure GND is common between ESP32 and sensor

### Motor Stutters on Start

**Symptoms**: Motor jerks, fails to spin smoothly at startup

**Solutions**:
- Increase `PWM_MIN_THRESHOLD` in `config_common.h` (try 60-80)
- Extend `SOFT_START_DURATION_MS` to 2000-3000ms
- Check driver state: JYQD needs the 2 s zero-throttle arm window — don't touch wiring mid-boot
- Verify power supply can handle startup current

### Unstable Speed / Oscillation

**Symptoms**: RPM fluctuates significantly, motor speed hunts

**Solutions**:
- Reduce `DEFAULT_KP` by 30-50% (too much proportional gain)
- Decrease `DEFAULT_KD` if high-frequency oscillation occurs
- Reduce `DEFAULT_KI` if slow oscillation with overshoot
- Check for electrical noise on RPM input (add 0.1µF capacitor near GPIO 0)
- Verify stable power supply (voltage drops cause instability)

### Incorrect RPM Reading

**Symptoms**: RPM reading is 2x or 0.5x expected value

**Solutions**:
- Adjust `PULSES_PER_REV` in `config.h`
- For 8-pole motor: typically 4 pulses/rev
- For 12-pole motor: typically 6 pulses/rev
- Use tachometer to verify actual RPM and calibrate accordingly

### Motor Runs Away (Overspeeds)

**Symptoms**: Motor accelerates beyond target RPM, doesn't stabilize

**Solutions**:
- IMMEDIATE: Power off system
- Check wiring polarity (RPM input might be reading inverted signal)
- Verify PID output isn't inverted (`DEFAULT_KP` should be positive)
- Reduce all PID gains and retune from scratch
- Add `PID_OUTPUT_MAX` limit in `config_common.h`

### Serial Monitor Shows No Output

**Symptoms**: No debug messages appear after upload

**Solutions**:
- Verify Serial Monitor baud rate is 115200
- Check USB cable supports data (not power-only)
- Try different USB port or cable
- Some ESP32-C3 boards require manual reset after upload
- Comment out `Serial.begin()` if not needed for production

## Performance Notes

### Timing Accuracy

The FreeRTOS task scheduler guarantees 5ms ±1µs control loop timing under normal conditions. Serial debug output may add jitter if used excessively.

### Memory Usage

- Firmware: ~302KB flash (23%), ~14.7KB RAM (measured Arduino build, includes core + FreeRTOS)

### Power Consumption

- Idle (no motor): ~40mA @ 3.3V
- Active control: ~60mA @ 3.3V

## Safety Considerations

1. **Voltage Protection**: Always use voltage divider for 5V Hall sensors
2. **Power Supply**: Ensure adequate current capacity for ESP32 and ESC
3. **Thermal**: Monitor ESC temperature during extended high-speed operation
4. **Emergency Stop**: Keep power disconnection easily accessible
5. **Testing**: Start with the motor unloaded and verify RPM on Serial before applying load

## License

This project is provided as-is for educational and commercial use.

## Contributing

Improvements welcome. Focus areas:
- Advanced filtering algorithms
- Auto-tuning PID implementation
- Additional motor types support
- Performance optimizations
