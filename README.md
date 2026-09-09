# BLDC Motor PID Controller

High-performance PID control system for maintaining precise RPM control of BLDC motors across multiple microcontroller platforms. Designed for reliability, efficiency, and ease of deployment from prototyping to production.

## Overview

This project provides complete PID controller implementations for BLDC motors, supporting three distinct microcontroller platforms. Each implementation is optimized for specific use cases: from initial development and tuning on Arduino, to cost-effective production deployment on ATtiny85, to advanced embedded applications on ESP32-C3 with wireless connectivity.

### Platform Variants

| Platform | Status | Use Case | Key Features |
|----------|--------|----------|--------------|
| **Arduino Uno** | Development | Prototyping, PID Tuning | Serial debugging, real-time tuning interface |
| **ATtiny85** | Production | Cost-optimized deployment | Minimal footprint, watchdog protection, dual variants |
| **ESP32-C3** | Modern Embedded | High-performance, IoT | FreeRTOS, BLE control, hardware PWM, 200Hz loop |

## Key Features

- **Precise RPM Control**: Advanced PID algorithm with anti-windup and derivative filtering
- **Multiple Filtering Options**: EMA, median, moving average, and sliding window filters
- **Soft-Start Protection**: Configurable ramp-up prevents mechanical stress and current spikes
- **Hardware Optimization**: Platform-specific drivers leverage hardware peripherals for maximum efficiency
- **Safety Features**: Emergency stop, watchdog timers, and input validation
- **Wireless Control**: Optional BLE interface on ESP32-C3 for remote monitoring and control
- **Production Ready**: Proven in real-world applications with comprehensive error handling

## Quick Start

### 1. Choose Your Platform

**For Initial Development**: Start with Arduino Uno to characterize your motor and tune PID constants.

**For Production Deployment**: Use ATtiny85 v1 for direct logic port, or v2 for optimized performance.

**For Advanced Applications**: Choose ESP32-C3 for wireless control, high-speed loops, and RTOS features.

### 2. Hardware Requirements

**Common Components**:
- 3-Phase BLDC Motor with Hall Effect sensors
- Electronic Speed Controller (ESC) with PWM input
- Power supply appropriate for motor voltage requirements
- Microcontroller (Arduino Uno, ATtiny85, or ESP32-C3)

**Platform-Specific**:
- **Arduino Uno**: USB cable for programming, optional potentiometers for tuning
- **ATtiny85**: Arduino Uno as ISP programmer, 10µF capacitor for programming
- **ESP32-C3**: Voltage divider (2.2kΩ/3.3kΩ) if using 5V Hall sensors

### 3. Installation Steps

```bash
git clone https://github.com/your-repo/PID_simple_controll.git
cd PID_simple_controll
```

**Select your platform directory**:
- `arduino_uno/` - Development and tuning platform
- `attiny85/` - Production deployment (v1 or v2)
- `esp32-c3/` - High-performance RTOS platform

**Configure for your motor**:
1. Edit `config.h` to set motor pole count and target RPM
2. Adjust PID gains if you have known values
3. Configure pin assignments if using custom wiring

**Upload firmware**:
- Arduino Uno: Use Arduino IDE directly
- ATtiny85: Program via Arduino as ISP
- ESP32-C3: Use Arduino IDE with ESP32 board support or PlatformIO

## Platform Details

### Arduino Uno (`arduino_uno/`)

**Processor**: ATmega328P @ 16MHz

**Purpose**: Development platform for initial motor characterization and PID tuning.

**Features**:
- Serial Monitor and Plotter output for real-time visualization
- Potentiometer-based live PID tuning (no code recompilation needed)
- Mode switching between normal operation and tuning mode
- Comprehensive debug output
- Emergency stop functionality

**Recommended Workflow**:
1. Connect motor and Hall sensor to Arduino Uno
2. Upload sketch and open Serial Plotter
3. Enable tuning mode and adjust potentiometers
4. Record optimal PID values
5. Transfer values to production platform

### ATtiny85 (`attiny85/`)

**Processor**: ATtiny85 @ 16MHz (PLL mode)

**Purpose**: Cost-effective production deployment with minimal component count.

**Variants**:

**v1 (Recommended)**: Direct logic port from Arduino Uno. If it works on Uno, it works on ATtiny85 v1. Uses floating-point math for identical behavior.

**v2 (Optimized)**: Advanced implementation using hardware timer capture and integer math. More efficient for resource-constrained or high-speed applications.

**Features**:
- Watchdog timer protection prevents system hangs
- Minimal power consumption
- 8-pin DIP package for easy PCB integration
- Emergency stop with automatic recovery
- Proven reliability in production environments

**Pin Configuration**:
- PB3 (Pin 2): Hall sensor input (interrupt capable)
- PB0 (Pin 5): PWM output to ESC
- VCC (Pin 8): 5V power
- GND (Pin 4): Ground

```
        ┌──◡──┐
  VCC ──┤1  8 ├── VCC (5V / RST — programmer manages this)
  PB3 ──┤2  7 ├── PB2 (NC)
  PB4 ──┤3  6 ├── PB1 (v4 debug heartbeat: HIGH = pulses seen)
  GND ──┤4  5 ├── PB0 (PWM → ESC/driver)
        └─────┘
```

GND must be common between MCU, driver/battery, and sensor. For driver
boards with a `VR` analog speed pin, feed PB0 through an RC low-pass
(220 Ω + 220 µF near the VR pin) instead of raw PWM. Full wiring notes:
[`attiny85/v4/README.md`](attiny85/v4/README.md).

### ESP32-C3 (`esp32-c3/`)

**Processor**: RISC-V @ 160MHz with hardware FPU

**Purpose**: High-performance applications requiring fast control loops, wireless connectivity, or RTOS task management.

**Firmware Variants**:

**Standard (`control/`)**: Always-on motor control with maximum performance.
- 200Hz PID control loop via dedicated FreeRTOS task
- Hardware-accelerated PWM (LEDC peripheral, 5kHz)
- Interrupt-driven RPM sensing with IRAM-resident ISR
- Sliding window filter for stable RPM readings
- Immediate startup on power application

**BLE-Enabled (`control_ble/`)**: Wireless control interface with start/stop commands.
- All features from standard variant
- Bluetooth Low Energy interface (no WiFi interference)
- Real-time status notifications (500ms interval)
- Remote RPM target adjustment
- Thread-safe shared state with spinlock protection
- JSON status format for easy integration

**Motor Simulator (`simulator/`)**: Virtual motor for safe testing and development.
- Simulates motor physics (inertia, acceleration)
- Configurable max RPM and response characteristics
- Optional noise injection for filter testing
- Eliminates need for real motor during algorithm development

**Features**:
- Hardware FPU for fast floating-point calculations
- FreeRTOS ensures deterministic timing
- 3.3V logic level (requires voltage divider for 5V sensors)
- Optional wireless connectivity (BLE)
- Comprehensive debugging via Serial Monitor

## Documentation

### Comprehensive Guides

- **[Hardware Assembly Guide](docs/howto.md)**: Complete wiring guide, pin assignments, and connection diagrams for all platforms
- **[Troubleshooting Guide](docs/mitigation.md)**: Comprehensive diagnosis and solutions for common issues including electrical, mechanical, and software problems
- **[Platform Comparison](docs/COMPARISON.md)**: Detailed technical comparison of features, performance, and use cases

### Platform-Specific Documentation

- **[Arduino Uno](arduino_uno/README.md)**: Development setup and tuning procedures
- **[ATtiny85](attiny85/README.md)**: Production deployment guide and programming instructions
- **[ESP32-C3](esp32-c3/README.md)**: Advanced features, BLE interface, and RTOS architecture

## Configuration

### Motor Configuration

All platforms use a `config.h` file for motor-specific settings:

```cpp
#define PULSES_PER_REV  4     // Set based on motor pole count
#define DEFAULT_TARGET_RPM 1440.0  // Target speed in RPM
```

**Calculating PULSES_PER_REV**: For a motor with N poles using single Hall sensor: `PULSES_PER_REV = N / 2`

Example: 8-pole motor = 4 pulses per revolution

### PID Tuning

PID constants are defined in platform-specific configuration:

```cpp
#define DEFAULT_KP  0.150  // Proportional gain
#define DEFAULT_KI  0.080  // Integral gain
#define DEFAULT_KD  0.015  // Derivative gain
```

**Tuning Process**:
1. Start with Arduino Uno tuning mode using potentiometers
2. Begin with Kp only (set Ki and Kd to 0)
3. Increase Kp until oscillation occurs, then reduce by 30%
4. Add Ki gradually to eliminate steady-state error
5. Add small Kd if overshoot occurs
6. Transfer final values to production platform

## Safety Considerations

1. **Electrical Isolation**: Keep logic power separate from motor power (common ground only)
2. **Voltage Protection**: Use voltage dividers when interfacing 5V sensors with 3.3V logic (ESP32-C3)
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
| ATtiny85 won't program | Missing reset capacitor | Add 10µF between Arduino Reset and GND |
| ESP32-C3 damaged | 5V applied to GPIO | Use voltage divider for all 5V signals |

See [Troubleshooting Guide](docs/mitigation.md) for comprehensive solutions.

## Contributing

Contributions are welcome. Areas of interest:
- Additional microcontroller platform support
- Advanced PID algorithms (adaptive, fuzzy logic)
- Enhanced filtering techniques
- PCB designs for production deployment
- Test cases and validation procedures

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - See [LICENSE](LICENSE) file for details.

This project is provided as-is for educational and commercial use. No warranty is provided for fitness for any particular purpose.

## Support

- **Issues**: Report bugs and request features via GitHub Issues
- **Discussions**: Ask questions and share experiences in GitHub Discussions
- **Documentation**: Comprehensive guides available in `docs/` directory

## Acknowledgments

Built with focus on reliability, performance, and practical deployment. Tested in real-world applications across multiple motor types and configurations.
