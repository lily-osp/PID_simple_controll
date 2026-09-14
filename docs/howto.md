# Hardware Assembly and Setup Guide

Complete guide for assembling, wiring, programming, and tuning the BLDC Motor PID Controller across all supported platforms.

## Table of Contents

- [Bill of Materials](#bill-of-materials)
- [Platform-Specific Wiring](#platform-specific-wiring)
- [Software Setup](#software-setup)
- [PID Tuning Process](#pid-tuning-process)
- [Production Deployment](#production-deployment)
- [Safety Checklist](#safety-checklist)

## Bill of Materials

### Core Components (All Platforms)

**Required**:
- **BLDC Motor**: 3-phase brushless motor with Hall Effect sensors (sensored motor)
  - Common: 8-pole motor (4 pulses/revolution)
  - Alternative: 12-pole motor (6 pulses/revolution)
- **Electronic Speed Controller (ESC)**: PWM-compatible motor driver
  - Voltage rating matching motor requirements (e.g., 12V, 24V, 36V)
  - Current rating 2x motor maximum current for safety margin
- **Power Supply**:
  - Motor power: Voltage matching ESC/motor requirements, 2-3x running current capacity
  - Logic power: 5V for Arduino/ATtiny85, or 5V/3.3V for ESP32-C3
- **Microcontroller**: Choose one platform (see below)

**Optional but Recommended**:
- **Decoupling Capacitors**:
  - 0.1µF ceramic capacitors for Hall sensor inputs (noise reduction)
  - 1000µF electrolytic for motor power rail (startup surge protection)
- **Emergency Stop Switch**: For safe testing and operation
- **Mounting Hardware**: Secure motor during testing (prevents injuries from unexpected starts)

### Platform-Specific Components

#### Arduino Uno Development Setup

**Required**:
- Arduino Uno board (or compatible ATmega328P board)
- USB Type-B cable (for programming and monitoring)

**For Tuning Mode** (Optional):
- 4x 10kΩ linear potentiometers (for Kp, Ki, Kd, Target RPM adjustment)
- Breadboard and jumper wires
- Push button or switch (mode selection)

**Typical Cost**: $25-30

#### ATtiny85 Production Setup

**Required**:
- ATtiny85 microcontroller (DIP-8 package recommended)
- Arduino Uno (as ISP programmer)
- 10µF electrolytic capacitor (for programming: between Arduino Reset and GND)
- Jumper wires (6 wires for ISP connection)

**Optional**:
- 8-pin DIP socket (for easier replacement)
- PCB or perfboard for permanent installation
- Crystal oscillator (if not using internal PLL)

**Typical Cost**: $1-3 per ATtiny85 + Arduino Uno (reusable)

#### ESP32-C3 Setup

**Required**:
- ESP32-C3 development board (SuperMini or similar)
- USB-C cable (for programming and serial monitoring)

**If Using 5V Hall Sensors**:
- Resistors for voltage divider:
  - R1: 2.2kΩ (between sensor and GPIO)
  - R2: 3.3kΩ (between GPIO and GND)
  - Or pre-built logic level shifter module

**Optional**:
- BLE-compatible mobile device (for control_ble variant)
- Second ESP32-C3 (for simulator variant)

**Typical Cost**: $3-7

## Platform-Specific Wiring

### Arduino Uno Wiring

#### Standard Configuration

| Component | Arduino Pin | Physical Connection | Notes |
|-----------|-------------|---------------------|-------|
| Hall Sensor Output | Digital Pin 2 | Connect directly | 5V logic compatible, interrupt capable |
| ESC PWM Input | Digital Pin 9 | Connect directly | Timer1 PWM output |
| Mode Switch | Digital Pin 3 | Switch to GND | Pull-up enabled, GND = tuning mode |
| Potentiometer Kp | Analog A0 | Center pin to A0, ends to 5V/GND | Optional: live tuning |
| Potentiometer Ki | Analog A1 | Center pin to A1, ends to 5V/GND | Optional: live tuning |
| Potentiometer Kd | Analog A2 | Center pin to A2, ends to 5V/GND | Optional: live tuning |
| Target RPM Pot | Analog A3 | Center pin to A3, ends to 5V/GND | Optional: live tuning |
| Arduino 5V | ESC 5V (if available) | Optional | Powers Arduino from ESC BEC |
| Arduino GND | ESC GND | **REQUIRED** | Common ground essential |

#### Wiring Diagram

```
Hall Sensor (5V)                Arduino Uno               ESC (PWM)
┌────────────┐                 ┌──────────┐              ┌─────────┐
│  VCC   GND │                 │          │              │ Signal  │
│   │     │  │                 │          │              │    │    │
│   │     │  │                 │          │              │    │    │
└───┼─────┼──┘                 │          │              └────┼────┘
    │     │                    │          │                   │
    │     └────────────────────┤ GND      │                   │
    │                          │          │                   │
    └──────────────────────────┤ Pin 2    │                   │
                               │          │                   │
                               │ Pin 9    ├───────────────────┘
                               │          │
                Mode Switch ───┤ Pin 3    │
                    │          │          │
                    └──────────┤ GND      │
                               │          │
                    5V ────────┤ 5V       │
                    GND ───────┤ GND      │
                               └──────────┘
```

### ATtiny85 Wiring

#### Production Circuit

| Component | ATtiny85 Pin | Physical Pin | Notes |
|-----------|--------------|--------------|-------|
| Hall Sensor Output | PB3 | Pin 2 | External interrupt INT0 |
| ESC PWM Input | PB0 | Pin 5 | Timer0 PWM output |
| VCC (5V) | VCC | Pin 8 | Power supply positive |
| Ground | GND | Pin 4 | Power supply ground |

#### Pin Diagram

```
          ATtiny85 (Top View)
          ┌────┴────┐
  Reset ──┤1       8├── VCC (5V)
  PB3/2 ──┤2       7├── PB2 (unused)
  PB4/3 ──┤3       6├── PB1 (unused)
    GND ──┤4       5├── PB0 (PWM Out)
          └─────────┘

Connection Details:
- Pin 2 (PB3): Hall Sensor Signal Input
- Pin 5 (PB0): PWM Signal to ESC
- Pin 8 (VCC): 5V Power
- Pin 4 (GND): Ground
```

#### Programming Wiring (Arduino as ISP)

| ATtiny85 | Physical Pin | Arduino Uno | Notes |
|----------|--------------|-------------|-------|
| MOSI | Pin 5 (PB0) | Pin 11 | ISP data to ATtiny |
| MISO | Pin 6 (PB1) | Pin 12 | ISP data from ATtiny |
| SCK | Pin 7 (PB2) | Pin 13 | ISP clock |
| RESET | Pin 1 | Pin 10 | ISP reset |
| VCC | Pin 8 | 5V | Power during programming |
| GND | Pin 4 | GND | Ground |
| - | - | RESET-GND | 10µF capacitor (positive to RESET) |

**Important**: 10µF capacitor between Arduino Reset and GND prevents Arduino from resetting during ISP.

### ESP32-C3 Wiring

#### With 3.3V Hall Sensor (Direct Connection)

| Component | ESP32-C3 Pin | Notes |
|-----------|--------------|-------|
| Hall Sensor Output (3.3V) | GPIO 0 | Connect directly |
| ESC PWM Input | GPIO 1 | Connect directly |
| Hall Sensor VCC | 3.3V | Power from ESP32 |
| Hall Sensor GND | GND | Common ground |
| ESC GND | GND | Common ground |

#### With 5V Hall Sensor (Voltage Divider Required)

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

#### ESP32-C3 Simulator Wiring (Two Boards)

**Board 1: Controller** | **Board 2: Simulator**
- GPIO 1 (PWM Out) → GPIO 0 (PWM In)
- GPIO 0 (RPM In) ← GPIO 1 (RPM Out)
- GND → GND (common ground)

Both boards use 3.3V logic, so no voltage divider needed for board-to-board communication.

## Software Setup

### Arduino IDE Installation

#### 1. Install Arduino IDE

Download from [arduino.cc](https://www.arduino.cc/en/software) (version 1.8.19+ or 2.x)

#### 2. Install Board Support

**For ATtiny85**:
1. Open Arduino IDE
2. Go to File → Preferences
3. Add to "Additional Board Manager URLs":
   ```
   http://drazzy.com/package_drazzy.com_index.json
   ```
4. Go to Tools → Board → Board Manager
5. Search for "ATTinyCore" by Spence Konde
6. Click Install

**For ESP32-C3**:
1. Go to File → Preferences
2. Add to "Additional Board Manager URLs":
   ```
   https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
   ```
3. Go to Tools → Board → Board Manager
4. Search for "esp32" by Espressif Systems
5. Click Install (version 2.0.0+)

### Programming Each Platform

#### Arduino Uno

**Steps**:
1. Connect Arduino Uno via USB
2. Open project: `arduino_uno/arduino_uno.ino`
3. Select: Tools → Board → Arduino Uno
4. Select: Tools → Port → (your Arduino port)
5. Click Upload button

**Verification**:
- Open Serial Monitor (115200 baud)
- Should see "System Initialized" message
- RPM readings should appear

#### ATtiny85

**Steps**:
1. **Setup Arduino as ISP**:
   - Open: File → Examples → 11.ArduinoISP → ArduinoISP
   - Upload to Arduino Uno
   - Wire ATtiny85 to Arduino Uno (see wiring section)
   - Add 10µF capacitor: Arduino RESET to GND (positive to RESET)

2. **Configure ATtiny85**:
   - Select: Tools → Board → ATtinyCore → ATtiny25/45/85
   - Select: Tools → Chip → ATtiny85
   - Select: Tools → Clock → 16 MHz (PLL)
   - Select: Tools → Programmer → Arduino as ISP

3. **Burn Bootloader** (sets fuses, only needed once):
   - Click: Tools → Burn Bootloader
   - Wait for "Done burning bootloader"

4. **Upload Sketch**:
   - Open: `attiny85/v1/attiny85_v1.ino` (or v2)
   - Click: Sketch → Upload Using Programmer
   - Wait for "Done uploading"

**Verification**:
- Disconnect from Arduino Uno
- Wire to motor circuit (power separately)
- Motor should respond to RPM pulses

#### ESP32-C3

**Steps**:
1. Connect ESP32-C3 via USB-C
2. Open project: `esp32-c3/control/control.ino` (or control_ble)
3. Select: Tools → Board → ESP32 Arduino → ESP32C3 Dev Module
4. Select: Tools → Port → (your ESP32 port)
5. Select: Tools → Flash Size → 4MB
6. Click Upload button

**Verification**:
- Open Serial Monitor (115200 baud)
- Should see "ESP32-C3 BLDC Controller Started"
- For BLE version: Should see "BLE Advertising Started"

## PID Tuning Process

### Method 1: Arduino Uno Live Tuning (Recommended)

**Setup**:
1. Wire 4 potentiometers to A0-A3 (see wiring section)
2. Connect mode switch to Pin 3 (switch to GND = tuning mode)
3. Upload Arduino Uno sketch
4. Open Serial Plotter: Tools → Serial Plotter (115200 baud)

**Procedure**:
1. **Enable Tuning Mode**:
   - Close mode switch (connect Pin 3 to GND)
   - Serial Plotter shows: Current RPM, Target RPM, PWM Value

2. **Set Target RPM**:
   - Adjust A3 potentiometer
   - Watch target line change on plotter

3. **Tune Kp (Proportional)**:
   - Start with Kp pot at minimum
   - Slowly increase until motor reaches target RPM
   - Continue increasing until oscillation occurs
   - Reduce by 30-50% for stability
   - Record value from Serial Plotter

4. **Tune Ki (Integral)**:
   - Start with Ki pot at minimum
   - Slowly increase until steady-state error disappears
   - If oscillation occurs, reduce slightly
   - Record value

5. **Tune Kd (Derivative)**:
   - Usually keep low (10-20% of Kp)
   - Increase slightly if overshoot occurs
   - Too much Kd causes instability
   - Record value

6. **Verify**:
   - Test various target RPMs
   - Apply load changes (manually slow motor)
   - Ensure quick recovery without overshoot

7. **Record Values**:
   - Note optimal Kp, Ki, Kd from Serial Plotter
   - Update `config.h` for production deployment

### Method 2: Manual Tuning (All Platforms)

**Setup**:
1. Edit `config.h` and set initial values:
   ```cpp
   #define DEFAULT_KP  0.100
   #define DEFAULT_KI  0.000
   #define DEFAULT_KD  0.000
   ```
2. Upload and observe motor behavior

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

### Method 3: BLE Tuning (ESP32-C3 BLE Only)

**Setup**:
1. Upload `esp32-c3/control_ble/control_ble.ino`
2. Install nRF Connect (Android) or LightBlue (iOS)

**Procedure**:
1. Scan for "BLDC-PID" device
2. Connect to device
3. Navigate to Target characteristic
4. Write new RPM value (e.g., "1800")
5. Monitor Status characteristic for real-time feedback
6. Adjust target repeatedly to test response
7. Update PID gains in code if needed (requires reflash)

Note: BLE variant allows target RPM adjustment but not live PID tuning (PID values must be set at compile time).

## Production Deployment

### ATtiny85 Deployment Checklist

**Pre-Deployment**:
- [ ] PID values tuned and verified on Arduino Uno
- [ ] ATtiny85 code updated with tuned values
- [ ] `PULSES_PER_REV` set correctly for your motor
- [ ] Target RPM configured appropriately

**Programming**:
- [ ] Arduino Uno configured as ISP
- [ ] 10µF capacitor between Arduino Reset and GND
- [ ] All ISP wiring verified (MOSI, MISO, SCK, RESET)
- [ ] Bootloader burned (only first time or after fuse change)
- [ ] Sketch uploaded using "Upload Using Programmer"

**Installation**:
- [ ] ATtiny85 removed from ISP programmer
- [ ] Installed in production circuit or socket
- [ ] Hall sensor connected to PB3 (Pin 2)
- [ ] ESC PWM connected to PB0 (Pin 5)
- [ ] Power and ground connected (Pin 8 and Pin 4)
- [ ] Decoupling capacitors installed (0.1µF near ATtiny85)

**Testing**:
- [ ] Visual inspection of all connections
- [ ] Power-on test (no propeller attached)
- [ ] Motor responds to Hall sensor pulses
- [ ] RPM control verified with tachometer
- [ ] Load test with propeller (gradually increase load)
- [ ] Extended runtime test (thermal monitoring)

### ESP32-C3 Deployment Checklist

**Pre-Deployment**:
- [ ] Choose variant: standard or BLE
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
- [ ] Serial Monitor confirms startup
- [ ] BLE advertising visible (if using BLE variant)
- [ ] Motor control responsive
- [ ] No voltage damage to GPIOs (check for heat)
- [ ] BLE connection stable (if applicable)
- [ ] Status notifications working (if applicable)

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
- [ ] Voltage levels appropriate (5V for logic, motor voltage for ESC)
- [ ] ESP32-C3: Voltage divider installed if using 5V sensors
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
2. Add filtering (increase EMA alpha or enable median filter)
3. Check for electrical noise (capacitors on sensor inputs)
4. Verify solid ground connections

## Troubleshooting Common Setup Issues

### Programming Issues

**ATtiny85 "Programmer Not Responding"**:
- Verify 10µF capacitor between Arduino Reset and GND
- Check ISP wiring (MOSI, MISO, SCK, RESET)
- Try lower baud rate: Tools → Programmer → "Arduino as ISP (slow)"
- Ensure Arduino has ArduinoISP sketch uploaded

**ESP32-C3 "Failed to Connect"**:
- Press and hold BOOT button, then press RESET
- Try different USB cable (must support data, not just power)
- Install USB serial drivers (CP210x or CH340)
- Select correct port (may be different from Arduino Uno)

### Hardware Issues

**No RPM Reading**:
- Test Hall sensor separately (should output pulses when motor turns)
- Verify sensor powered correctly (5V or 3.3V depending on sensor)
- Check interrupt pin connection (Arduino Pin 2, ATtiny PB3, ESP32 GPIO 0)
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

For additional troubleshooting, see [Troubleshooting Guide](mitigation.md).

## Next Steps

After successful assembly and tuning:

1. **Document Your Setup**: Record PID values, motor specs, and wiring
2. **Extended Testing**: Run for 30+ minutes, monitor temperatures
3. **Load Testing**: Gradually increase load, verify stability
4. **Production Deployment**: Transfer to ATtiny85 or ESP32-C3
5. **Maintenance**: Periodic inspection of connections and components

## Additional Resources

- [Platform Comparison](COMPARISON.md): Choose the right platform
- [Troubleshooting Guide](mitigation.md): Solve common problems
- Platform READMEs: Detailed information for each implementation
