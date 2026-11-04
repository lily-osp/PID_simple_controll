# BLDC Motor PID Controller (ESP32-C3)

Fixed-target PID controller for BLDC motors on the ESP32-C3, run bare-metal
for compute (no WiFi, no BLE). Holds 1440 RPM via a 200Hz FreeRTOS loop.

> History: this project previously shipped Arduino Uno and ATtiny85 variants.
> They were removed on 2026-10-31 (commit `396ade7`) and remain in git history.

## Overview

Single-platform implementation targeting the ESP32-C3 SuperMini. The C3 is
used for its 160MHz RISC-V core and hardware FPU; no wireless stack is used.
Two firmware builds share one set of drivers: a bench build for bring-up and
a production build for the enclosure.

| Build | Status | Use Case | Key Features |
|-------|--------|----------|--------------|
| **`esp32-c3/control/`** | Bench | Bring-up, service, Hall-line trials | Serial console, telemetry, trial scoring |
| **`esp32-c3/embedded/`** | Production | Enclosure deployment | Silent, autonomous, arming + stall failsafe |

## Key Features

- **200Hz Control Loop**: High-frequency PID updates via dedicated FreeRTOS task
- **Hardware-Accelerated PWM**: ESP32 LEDC peripheral generating smooth 5kHz motor control signals
- **Interrupt-Driven RPM**: High-precision pulse counting using IRAM-resident ISR
- **Sliding Window Filter**: 12-sample window + IIR smoothing for stable control input
- **ESC Arming + Soft-Start**: 2s zero-throttle arm, then 1.5s power ramp
- **FPU Utilization**: Full floating-point PID calculations for maximum precision
- **Safety Features**: Stall failsafe, emergency stop, input validation

## Quick Start

### 1. Hardware Requirements

- ESP32-C3 SuperMini (or compatible) + USB-C cable
- 3-Phase BLDC Motor with Hall Effect sensors
- PWM-compatible ESC / motor driver (e.g., JYQD V7.3E)
- Power supply appropriate for motor voltage requirements
- Voltage divider (2.2kΩ/3.3kΩ) if using 5V Hall sensors

### 2. Installation Steps

```bash
git clone https://github.com/your-repo/PID_simple_controll.git
cd PID_simple_controll
```

**Configure for your motor**:
1. Edit `esp32-c3/control/config.h` (pins, motor, PPR)
2. Edit `esp32-c3/control/config_common.h` (PID gains)
3. Configure pin assignments if using custom wiring

**Upload firmware**:
- Use Arduino IDE with ESP32 board support, or `arduino-cli`:

```bash
arduino-cli compile -b esp32:esp32:nologo_esp32c3_super_mini esp32-c3/embedded
arduino-cli upload  -p /dev/ttyACM0 -b esp32:esp32:nologo_esp32c3_super_mini esp32-c3/embedded
```

Which build to flash: see [BUILDS.md](../esp32-c3/BUILDS.md).

## Platform Details

### ESP32-C3 (`esp32-c3/`)

**Processor**: RISC-V @ 160MHz with hardware FPU

**Firmware Builds**:

**Bench (`control/`)**: Serial console for bring-up and service.
- Command parser, telemetry, diagnostics console
- Trial log auto-scores each power cycle to rank Hall permutations
- Full visibility into PID state and RPM estimation

**Production (`embedded/`)**: Silent, autonomous build for the enclosure.
- Control loop, ESC arming, soft-start, stall failsafe
- Shares the exact RPM estimator, PID, and LEDC drivers with the bench build

**Features**:
- Hardware FPU for fast floating-point calculations
- FreeRTOS ensures deterministic timing
- 3.3V logic level (requires voltage divider for 5V sensors)
- Comprehensive debugging via Serial Monitor (bench build)

Full architecture: [ESP32-C3 README](../esp32-c3/README.md).

### Custom Driver PCB (`PCB/V1/`)

Full-integration **64 × 98 mm, 4-layer** board combining the firmware above with its own
driver hardware — no external ESC needed:

- **JYQD-V7.3E3 architecture**: JY01 controller + JY213L gate driver + JY2605M
  half-bridges (same silicon as the reference driver board)
- **ESP32-C3 Super Mini** onboard as the controller (FG/PWM/VR/EL/trim pot)
- **Hall signal conditioner**: RC filter → LM324 (×11) → 74HC14 Schmitt trigger
- **Power tree**: V_IN → 7812 → +12V → 7805 → +5V

Design files, port pinouts, and build scripts: [PCB README](../PCB/V1/README.md).

## Documentation

### Guides

- **[Hardware Assembly](howto.md)**: Wiring guide, pin assignments, and connection diagrams
- **[Troubleshooting](mitigation.md)**: Comprehensive diagnosis and solutions for common issues
- **[ESP32-C3 README](../esp32-c3/README.md)**: Architecture, firmware, and hardware setup
- **[Builds](../esp32-c3/BUILDS.md)**: Production vs bench firmware, and how they share code
- **[Diagnostics Guide](../esp32-c3/DIAGNOSTICS.md)**: Serial console commands and fault isolation
- **[Driver PCB](../PCB/V1/README.md)**: 64 × 98 mm 4-layer ESP32-C3 + JYQD-architecture driver board
- **[PCB Test Plan](../PCB/V1/TESTPLAN.md)**: Staged bring-up procedure and failure diagnosis

## Configuration

### Motor Configuration

Settings live in `esp32-c3/*/config.h`:

```cpp
#define PULSES_PER_REV  4     // Set based on motor pole count
#define DEFAULT_TARGET_RPM 1440.0  // Target speed in RPM
```

**Calculating PULSES_PER_REV**: For a motor with N poles using single Hall sensor: `PULSES_PER_REV = N / 2`

Example: 8-pole motor = 4 pulses per revolution

### PID Tuning

PID constants are defined in `esp32-c3/control/config_common.h`:

```cpp
#define DEFAULT_KP  0.150  // Proportional gain
#define DEFAULT_KI  0.080  // Integral gain
#define DEFAULT_KD  0.015  // Derivative gain
```

**Tuning Process**:
1. Begin with Kp only (set Ki and Kd to 0)
2. Increase Kp until oscillation occurs, then reduce by 30%
3. Add Ki gradually to eliminate steady-state error
4. Add small Kd if overshoot occurs
5. Watch the bench console telemetry to verify stability

## Safety Considerations

1. **Electrical Isolation**: Keep logic power separate from motor power (common ground only)
2. **Voltage Protection**: Use voltage dividers when interfacing 5V sensors with 3.3V logic
3. **Mechanical Safety**: Secure motor firmly and remove propellers during initial testing
4. **Emergency Stop**: Keep power disconnect easily accessible during testing
5. **Current Rating**: Ensure power supply can handle motor startup current (typically 2-3x running current)
6. **Thermal Management**: Monitor ESC and motor temperatures during extended operation

## Troubleshooting Quick Reference

| Issue | Likely Cause | Solution |
|-------|--------------|----------|
| Motor doesn't start | Insufficient PWM threshold | Increase `PWM_MIN_THRESHOLD` to 60-80 |
| RPM reading 2x actual | Wrong `PULSES_PER_REV` | Divide current value by 2 |
| Unstable speed | Poor PID tuning or noise | Reduce Kp by 30%, add filtering |
| Random RPM spikes | Electrical noise | Add 0.1µF capacitor to Hall input |
| ESP32-C3 damaged | 5V applied to GPIO | Use voltage divider for all 5V signals |

See [Troubleshooting Guide](mitigation.md) for comprehensive solutions.

## Contributing

Contributions are welcome. Areas of interest:
- Advanced PID algorithms (adaptive, fuzzy logic)
- Enhanced filtering techniques
- PCB designs for production deployment
- Test cases and validation procedures

Please read [CONTRIBUTING.md](../CONTRIBUTING.md) for guidelines.

## License

MIT License - See [LICENSE](../LICENSE) file for details.

This project is provided as-is for educational and commercial use. No warranty is provided for fitness for any particular purpose.

## Support

- **Issues**: Report bugs and request features via GitHub Issues
- **Discussions**: Ask questions and share experiences in GitHub Discussions
- **Documentation**: Comprehensive guides available in this directory

## Acknowledgments

Built with focus on reliability, performance, and practical deployment. Tested in real-world applications across multiple motor types and configurations.
