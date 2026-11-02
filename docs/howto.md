# Hardware Assembly and Setup Guide

Complete guide for assembling, wiring, programming, and tuning the BLDC Motor PID Controller on the ESP32-C3.

## Table of Contents

- [Bill of Materials](#bill-of-materials)
- [Wiring](#wiring)
- [Software Setup](#software-setup)
- [PID Tuning Process](#pid-tuning-process)
- [Production Deployment](#production-deployment)
- [Safety Checklist](#safety-checklist)

## Bill of Materials

### Core Components

**Required**:
- **ESP32-C3 development board** (SuperMini or similar) + USB-C cable
- **BLDC Motor**: 3-phase brushless motor with Hall Effect sensors (sensored motor)
  - Common: 8-pole motor (4 pulses/revolution)
  - Alternative: 12-pole motor (6 pulses/revolution)
- **Electronic Speed Controller (ESC)**: PWM-compatible motor driver (e.g., JYQD V7.3E)
  - Voltage rating matching motor requirements (e.g., 12V, 24V, 36V)
  - Current rating 2x motor maximum current for safety margin
- **Power Supply**:
  - Motor power: Voltage matching ESC/motor requirements, 2-3x running current capacity
  - Logic power: 5V/3.3V for ESP32-C3

**If Using 5V Hall Sensors**:
- Resistors for voltage divider:
  - R1: 2.2kΩ (between sensor and GPIO)
  - R2: 3.3kΩ (between GPIO and GND)
  - Or pre-built logic level shifter module

**Optional but Recommended**:
- **Decoupling Capacitors**:
  - 0.1µF ceramic capacitors for Hall sensor inputs (noise reduction)
  - 1000µF electrolytic for motor power rail (startup surge protection)
- **Emergency Stop Switch**: For safe testing and operation
- **Mounting Hardware**: Secure motor during testing (prevents injuries from unexpected starts)
- 10kΩ potentiometer on GPIO 3 (bench build: sensitivity trim, always active)

**Typical Cost**: $3-7

## Wiring

### With 3.3V Hall Sensor (Direct Connection)

| Component | ESP32-C3 Pin | Notes |
|-----------|--------------|-------|
| Hall Sensor Output (3.3V) | GPIO 0 | Connect directly |
| ESC PWM Input | GPIO 1 | Connect directly |
| Hall Sensor VCC | 3.3V | Power from ESP32 |
| Hall Sensor GND | GND | Common ground |
| ESC GND | GND | Common ground |

### With 5V Hall Sensor (Voltage Divider Required)

**Voltage Divider Calculation**:
- Input: 5V Hall sensor signal
- Output: ~3V to GPIO 0 (safe for ESP32)
- R1 = 2.2kΩ, R2 = 3.3kΩ
- Vout = 5V × (3.3kΩ / (2.2kΩ + 3.3kΩ)) = 3.0V

```
Hall Sensor (5V)
     │
     │ 5V signal
     │
     ├─── R1 (2.2kΩ) ───┬─── GPIO 0 (ESP32-C3)
     │                  │
     │                  R2 (3.3kΩ)
     │                  │
    GND ────────────────┴─── GND (ESP32-C3)
```

**Wiring Table**:

| Component | Connection | Notes |
|-----------|------------|-------|
| Hall Sensor VCC | 5V supply | External 5V, not from ESP32 |
| Hall Sensor GND | Common GND | Shared with ESP32 |
| Hall Sensor Signal | R1 (2.2kΩ) | Start of divider |
| R1 other end | R2 (3.3kΩ) + GPIO 0 | Divider junction |
| R2 other end | GND | Complete divider |
| ESC PWM Input | GPIO 1 | Direct connection (3.3V compatible) |
| ESC GND | Common GND | Shared with ESP32 |

**Sensitivity Trim (Bench Build Only)**:

| Component | ESP32-C3 Pin | Notes |
|-----------|--------------|-------|
| Potentiometer wiper | GPIO 3 (ADC1_CH3) | Trims PID gain scale (0.75x-1.25x), always active |

Do not use GPIO 2 for the wiper: it is a boot strapping pin, and the pot pulls it
to 0 V at the low end of travel, which can prevent the board from booting.

## Software Setup

### Arduino IDE Installation

#### 1. Install Arduino IDE

Download from [arduino.cc](https://www.arduino.cc/en/software) (version 1.8.19+ or 2.x)

#### 2. Install Board Support

**For ESP32-C3**:
1. Go to File → Preferences
2. Add to "Additional Board Manager URLs":
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. Go to Tools → Board → Board Manager
4. Search for "esp32" by Espressif Systems
5. Click Install (version 2.0.0+)

### Programming the ESP32-C3

**Steps**:
1. Connect ESP32-C3 via USB-C
2. Open project: `esp32-c3/control/control.ino` (bench) or `esp32-c3/embedded/embedded.ino` (production)
3. Select: Tools → Board → ESP32 Arduino → ESP32C3 Dev Module
4. Select: Tools → Port → (your ESP32 port)
5. Select: Tools → Flash Size → 4MB
6. Click Upload button

Or with `arduino-cli`:

```bash
arduino-cli compile -b esp32:esp32:nologo_esp32c3_super_mini esp32-c3/control
arduino-cli upload  -p /dev/ttyACM0 -b esp32:esp32:nologo_esp32c3_super_mini esp32-c3/control
```

**Verification**:
- Open Serial Monitor (115200 baud)
- Should see "ESP32-C3 BLDC Controller Started"
- Bench build: console commands available (see [DIAGNOSTICS.md](../esp32-c3/DIAGNOSTICS.md))

## PID Tuning Process

### Method 1: Manual Tuning

**Setup**:
1. Edit `esp32-c3/control/config_common.h` and set initial values:
   ```cpp
   #define DEFAULT_KP  0.100
   #define DEFAULT_KI  0.000
   #define DEFAULT_KD  0.000
   ```
2. Upload and observe motor behavior via the bench console telemetry

**Ziegler-Nichols Method**:
1. **Find Ultimate Gain (Ku)**:
   - Set Ki and Kd to 0
   - Increase Kp until continuous oscillation occurs
   - Record Kp value as Ku
   - Record oscillation period as Tu (seconds)

2. **Calculate Initial Values**:
   - Kp = 0.6 × Ku
   - Ki = 1.2 × Ku / Tu
   - Kd = 0.075 × Ku × Tu

3. **Fine-Tune**:
   - Start with calculated values
   - Adjust each gain incrementally
   - Test under various loads and speeds

**Behavior Guidelines**:

| Symptom | Adjustment |
|---------|------------|
| Slow response | Increase Kp |
| Oscillation | Decrease Kp |
| Steady-state error | Increase Ki |
| Slow oscillation | Decrease Ki |
| Overshoot | Increase Kd (slightly) |
| High-frequency noise | Decrease Kd |

### Method 2: Live Sensitivity Trim (Bench Build)

**Setup**:
1. Wire a 10kΩ potentiometer wiper to GPIO 3 (see wiring section)
2. Upload the bench build (`esp32-c3/control/`)

**Procedure**:
1. Watch telemetry on the serial console
2. Adjust the potentiometer to scale PID gains live (0.75x-1.25x)
3. Find the sweet spot, then bake the resulting values into `config_common.h`

Note: the trim scales all gains together; individual Kp/Ki/Kd values must be set at compile time.

## Production Deployment

### ESP32-C3 Deployment Checklist

**Pre-Deployment**:
- [ ] Choose build: bench (`control/`) or production (`embedded/`)
- [ ] PID values configured in code
- [ ] Voltage divider installed if using 5V Hall sensor
- [ ] Target RPM set appropriately

**Programming**:
- [ ] Correct board selected (ESP32C3 Dev Module)
- [ ] Flash size set to 4MB
- [ ] Code compiled without errors
- [ ] Successfully uploaded via USB

**Installation**:
- [ ] Hall sensor connection verified (voltage level safe)
- [ ] ESC PWM output connected to GPIO 1
- [ ] Power supply adequate (5V, 500mA+ recommended)
- [ ] Common ground established

**Testing**:
- [ ] Serial Monitor confirms startup (bench build)
- [ ] Motor control responsive
- [ ] No voltage damage to GPIOs (check for heat)
- [ ] Extended runtime test (thermal monitoring)

## Safety Checklist

### Before First Power-On

**Mechanical Safety**:
- [ ] Motor securely mounted (cannot move or tip)
- [ ] Propeller or load REMOVED for initial testing
- [ ] Clear workspace (no loose items near motor)
- [ ] Eye protection available
- [ ] Emergency stop easily accessible

**Electrical Safety**:
- [ ] All connections verified against wiring diagrams
- [ ] No short circuits (visual inspection + continuity test)
- [ ] Voltage levels appropriate (3.3V logic, motor voltage for ESC)
- [ ] Voltage divider installed if using 5V sensors
- [ ] Current capacity adequate (power supply rated 2-3x motor current)
- [ ] Ground connections solid (common ground for all components)

**Software Safety**:
- [ ] `PULSES_PER_REV` configured correctly
- [ ] `PWM_MIN_THRESHOLD` not too high (motor won't run away)
- [ ] `PWM_MAX_VALUE` not exceeding ESC limits
- [ ] Target RPM reasonable for motor type

### During Operation

**Monitor**:
- Motor temperature (should be warm, not hot to touch)
- ESC temperature (check heat sink temperature)
- Power supply voltage (should remain stable)
- Abnormal sounds (grinding, clicking, high-pitched whine)

**Warning Signs**:
- Excessive vibration → Stop immediately, check balance
- Smoke or burning smell → Cut power, investigate
- Motor stalling → Reduce load or increase PWM threshold
- Erratic behavior → Check for loose connections or noise

### Emergency Procedures

**If Motor Runs Away** (accelerates uncontrollably):
1. Disconnect power immediately
2. Do not attempt to grab motor or propeller
3. Check wiring (especially Hall sensor polarity)
4. Verify PID output isn't inverted

**If No Response**:
1. Check PWM signal with oscilloscope or LED
2. Verify Hall sensor provides pulses (oscilloscope)
3. Test ESC separately (known-good PWM source)
4. Confirm microcontroller powered and running

**If Unstable**:
1. Reduce all PID gains by 50%
2. Add filtering (increase window size or IIR smoothing)
3. Check for electrical noise (capacitors on sensor inputs)
4. Verify solid ground connections

## Troubleshooting Common Setup Issues

### Programming Issues

**ESP32-C3 "Failed to Connect"**:
- Press and hold BOOT button, then press RESET
- Try different USB cable (must support data, not just power)
- Install USB serial drivers (CP210x or CH340)
- Select correct port

### Hardware Issues

**No RPM Reading**:
- Test Hall sensor separately (should output pulses when motor turns)
- Verify sensor powered correctly (5V or 3.3V depending on sensor)
- Check interrupt pin connection (ESP32 GPIO 0)
- Use oscilloscope to verify pulse signal

**Motor Doesn't Start**:
- Increase `PWM_MIN_THRESHOLD` in code (try 60-80)
- Test ESC separately with servo tester
- Verify ESC calibration (some ESCs need throttle range setup)
- Check power supply capacity (may brownout during startup)

**Incorrect RPM Reading** (off by factor of 2 or 3):
- Verify motor pole count
- Adjust `PULSES_PER_REV`:
  - 8-pole motor = 4
  - 12-pole motor = 6
  - 3-Hall sensors, reading 1 = poles/2
- Use tachometer to confirm actual RPM

For additional troubleshooting, see [Troubleshooting Guide](mitigation.md) and [Diagnostics Guide](../esp32-c3/DIAGNOSTICS.md).

## Next Steps

After successful assembly and tuning:

1. **Document Your Setup**: Record PID values, motor specs, and wiring
2. **Extended Testing**: Run for 30+ minutes, monitor temperatures
3. **Load Testing**: Gradually increase load, verify stability
4. **Production Deployment**: Flash the `embedded/` build for the enclosure
5. **Maintenance**: Periodic inspection of connections and components

## Additional Resources

- [Troubleshooting Guide](mitigation.md): Solve common problems
- [ESP32-C3 README](../esp32-c3/README.md): Architecture, firmware, and hardware setup
- [Builds](../esp32-c3/BUILDS.md): Which build to use, and how they share code
- [Diagnostics Guide](../esp32-c3/DIAGNOSTICS.md): Serial console commands and fault isolation
