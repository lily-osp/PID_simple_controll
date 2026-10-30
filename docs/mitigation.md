# Troubleshooting and Problem Resolution Guide

Comprehensive diagnosis and resolution strategies for common issues encountered with the BLDC PID Controller system. This guide provides systematic approaches to identify and fix hardware, software, and operational problems.

## Table of Contents

- [Diagnostic Approach](#diagnostic-approach)
- [Motor Control Issues](#motor-control-issues)
- [RPM Measurement Issues](#rpm-measurement-issues)
- [Electrical and Power Issues](#electrical-and-power-issues)
- [Platform-Specific Issues](#platform-specific-issues)
- [Performance Issues](#performance-issues)
- [System Recovery](#system-recovery)

## Diagnostic Approach

### Systematic Troubleshooting Method

1. **Isolate the Problem**: Determine if issue is hardware, software, or configuration
2. **Gather Data**: Use Serial Monitor, oscilloscope, or multimeter
3. **Check Basics**: Power, ground, connections before complex diagnostics
4. **Test Incrementally**: Change one variable at a time
5. **Document**: Record what works and what doesn't

### Essential Diagnostic Tools

**Minimum**:
- Multimeter (voltage, continuity testing)
- Serial Monitor (software debugging)
- Visual inspection

**Recommended**:
- Oscilloscope (signal analysis)
- Tachometer (RPM verification)
- Current meter (power analysis)

**Professional**:
- Logic analyzer (timing analysis)
- Thermal camera (heat distribution)

## Motor Control Issues

### Motor Does Not Start

**Symptoms**: Motor remains stationary despite power and control signals. ESC may emit beeping sounds.

**Diagnostic Steps**:

1. **Verify PWM Signal**:
   - ESP32-C3: Check GPIO 1 with oscilloscope
   - Expected: PWM signal present (varying duty cycle)

2. **Check ESC Connection**:
   - Verify ESC signal wire connected to correct pin
   - Confirm ESC powered correctly (motor voltage)
   - Test ESC separately with servo tester

3. **Verify Configuration**:
   - Check `PWM_MIN_THRESHOLD` in config (should be 45-80)
   - Confirm target RPM is set (not 0)
   - Verify ESC throttle range calibration

**Resolution**:

| Cause | Solution |
|-------|----------|
| No PWM signal | Check microcontroller power, verify code uploaded correctly |
| PWM threshold too low | Increase `PWM_MIN_THRESHOLD` to 60-80 in `config_common.h` |
| ESC not calibrated | Calibrate ESC (max throttle, then min throttle procedure) |
| Insufficient power | Verify power supply can deliver 2-3x motor running current |
| ESC damaged | Test with known-good ESC or replace |
| Motor wiring issue | Check motor phase wiring, ensure Hall sensors connected |

**Code Fix for Low Starting Torque**:

```cpp
// In config_common.h
#define PWM_MIN_THRESHOLD   60  // Increased from 45

// Or adjust soft-start
#define SOFT_START_DURATION_MS  2000  // Slower ramp
```

### Motor Starts Then Stalls

**Symptoms**: Motor begins rotation but stops under load or after a few seconds.

**Diagnostic Steps**:

1. **Monitor RPM Readings**: Check if RPM sensor losing signal
2. **Check Power Supply**: Measure voltage during operation (brownout detection)
3. **Observe PID Output**: Use Serial Monitor to see if PID output decreasing

**Resolution**:

| Cause | Solution |
|-------|----------|
| Load too high | Reduce mechanical load, increase motor power rating |
| Power supply insufficient | Upgrade to higher current capacity supply |
| RPM signal lost | Check Hall sensor wiring, add capacitor for noise reduction |
| PID integral windup | Verify `INTEGRAL_WINDUP_MIN/MAX` limits set correctly |
| Overheating ESC | Add cooling, reduce sustained load |

### Unstable RPM / Oscillation

**Symptoms**: Motor speed oscillates continuously, hunting behavior, unable to maintain steady RPM.

**Diagnostic Steps**:

1. **Identify Oscillation Frequency**:
   - Fast (>5 Hz): Proportional gain too high or derivative issues
   - Slow (<1 Hz): Integral gain too high
   - Random: Electrical noise

2. **Check Console Telemetry**: Plot RPM, target, and error over time (bench build)

3. **Test Without Load**: Remove propeller, check if oscillation persists

**Resolution**:

**For Proportional Oscillation** (fast, regular):

```cpp
// Reduce Kp by 30-50%
#define DEFAULT_KP  0.100  // Was 0.150
```

**For Integral Oscillation** (slow, gradual):

```cpp
// Reduce Ki and check integral windup limits
#define DEFAULT_KI  0.040  // Was 0.080

// Tighten integral limits
#define INTEGRAL_WINDUP_MIN -500  // Was -1000
#define INTEGRAL_WINDUP_MAX  500  // Was 1000
```

**For Derivative Issues** (high-frequency noise):

```cpp
// Reduce or eliminate Kd
#define DEFAULT_KD  0.005  // Was 0.015
```

**For Electrical Noise**:
- Add 0.1µF ceramic capacitor between Hall sensor input and ground
- Use shielded cable for Hall sensor connection
- Increase filtering:

```cpp
// For ESP32-C3
#define RPM_FILTER_SIZE  15  // Was 10, longer averaging
```

### Motor Runs Away (Overspeed)

**Symptoms**: Motor accelerates beyond target RPM, does not stabilize, potentially dangerous situation.

**IMMEDIATE ACTION**: Cut power immediately. Do not attempt to stop motor manually.

**Diagnostic Steps** (After Safe Shutdown):

1. **Check PID Output Polarity**: Verify error calculation correct direction
2. **Verify RPM Reading**: Confirm sensor providing correct values
3. **Inspect Wiring**: Check for crossed connections (Hall sensor inverted)

**Resolution**:

| Cause | Solution |
|-------|----------|
| PID output inverted | Check error calculation: `error = target - current` (not reversed) |
| RPM reading inverted | Verify Hall sensor wiring and polarity |
| No integral windup limit | Add `INTEGRAL_WINDUP_MAX` limit in config |
| PID gains incorrect sign | Ensure Kp, Ki, Kd are positive values |
| Runaway loop logic | Review control loop, add safety max RPM check |

**Safety Code Addition**:

```cpp
// Add to control loop
#define MAX_SAFE_RPM  5000

if (currentRPM > MAX_SAFE_RPM) {
    motor_set_pwm(0);  // Emergency stop
    while(1);  // Halt system, requires power cycle
}
```

### Soft-Start Kickstart Failure

**Symptoms**: Motor hums but fails to rotate initially, requires manual assistance to start.

**Diagnostic Steps**:

1. **Monitor PWM Value**: Check if reaching sufficient threshold
2. **Test Without Soft-Start**: Temporarily disable to verify motor can start
3. **Check Static Friction**: Manually rotate motor, should turn freely

**Resolution**:

```cpp
// Increase minimum threshold
#define PWM_MIN_THRESHOLD   70  // Was 45

// Extend soft-start duration
#define SOFT_START_DURATION_MS  2500  // Was 1500

// Or boost initial kickstart
// In applySoftStart() function, modify:
int kickstartPWM = PWM_MIN_THRESHOLD + 20 + (int)((targetPWM - PWM_MIN_THRESHOLD) * progress);
// Adds +20 initial boost
```

## RPM Measurement Issues

### No RPM Reading (Shows 0 or Erratic)

**Symptoms**: RPM value remains at 0, or shows random values not correlating with motor speed.

**Diagnostic Steps**:

1. **Verify Hall Sensor Power**:
   - Measure voltage at sensor VCC pin (should be 5V or 3.3V)
   - Check ground connection solid

2. **Test Sensor Output**:
   - Use oscilloscope on sensor output while manually rotating motor
   - Should see pulses (HIGH/LOW transitions)
   - Frequency increases with rotation speed

3. **Check Microcontroller Input**:
   - Verify signal reaching interrupt pin (ESP32 GPIO 0)
   - For ESP32-C3 with 5V sensor: verify voltage divider present and correct

**Resolution**:

| Cause | Solution |
|-------|----------|
| Sensor not powered | Check VCC connection, verify power supply working |
| Ground not common | Connect sensor GND to microcontroller GND |
| Wrong pin | Verify sensor output connected to correct interrupt pin |
| Voltage mismatch | ESP32-C3: Add voltage divider for 5V sensor |
| Sensor damaged | Test sensor with multimeter or replace |
| No `attachInterrupt()` | Verify code includes interrupt setup for RPM pin |

### Incorrect RPM Reading (Constant Offset)

**Symptoms**: RPM reading consistently wrong by factor of 2, 3, or other multiple.

**Diagnostic Steps**:

1. **Measure Actual RPM**: Use external tachometer or count rotations manually
2. **Compare to Displayed RPM**: Calculate ratio (displayed / actual)
3. **Check Motor Specifications**: Verify pole count and sensor configuration

**Resolution**:

**If Reading is 2x Actual**:
```cpp
// Motor is 8-pole but config says 16-pole equivalent
#define PULSES_PER_REV  4  // Change from 8
```

**If Reading is 0.5x Actual**:
```cpp
// Motor is 16-pole but config says 8-pole equivalent
#define PULSES_PER_REV  8  // Change from 4
```

**Common Motor Configurations**:

| Motor Type | Poles | Hall Sensors | PULSES_PER_REV |
|------------|-------|--------------|----------------|
| Small drone motor | 12 | 3 | 6 |
| Standard BLDC | 8 | 3 | 4 |
| High-speed | 6 | 3 | 3 |
| Gimbal motor | 14 | 3 | 7 |

**Calculation**: `PULSES_PER_REV = (Motor Poles / 2)` when reading single Hall sensor

### Erratic RPM (Spikes and Drops)

**Symptoms**: RPM value jumps randomly (e.g., 1440 → 7000 → 1440), unstable readings.

**Diagnostic Steps**:

1. **Oscilloscope Analysis**: Observe Hall sensor signal for noise
2. **Check Wiring**: Look for loose connections or interference
3. **Test With/Without Motor Running**: If noise only when running, EMI from motor

**Resolution**:

**Hardware Fixes**:
- Add 0.1µF ceramic capacitor directly at Hall sensor input pin to GND
- Use shielded cable for Hall sensor connection
- Route sensor wires away from motor power lines
- Add RC low-pass filter: 1kΩ resistor + 10nF capacitor

**Circuit for RC Filter**:
```
Hall Sensor ─── 1kΩ ───┬─── Microcontroller Pin
                       │
                      10nF
                       │
                      GND
```

**Software Fixes**:

For ESP32-C3:
```cpp
// Increase sliding window size
#define RPM_FILTER_SIZE  20  // Was 10
```

### RPM Lag (Slow Response)

**Symptoms**: RPM reading changes slowly, doesn't track actual motor speed quickly.

**Cause**: Over-filtering, too much smoothing applied.

**Resolution**:

For sliding window:
```cpp
#define RPM_FILTER_SIZE  5  // Was 10, shorter window
```

**Trade-off**: Faster response = more noise. Adjust based on application needs.

## Electrical and Power Issues

### Power Supply Conflicts

**Symptoms**: Onboard regulator overheating, erratic logic levels, random resets.

**Cause**: Simultaneous USB (5V) and external power connection, or insufficient current capacity.

**Resolution**:

**During Development**:
- Use USB power only for logic
- Disconnect motor power during upload

**During Operation**:
- Power logic and motor from separate rails sharing a common ground
- Ensure supply can deliver 500mA+ for logic + 2-3A for motor

**Best Practice**:
- Separate logic power from motor power
- Use two power supplies sharing common ground
- Prevents motor current spikes from affecting logic

**Wiring**:
```
Logic Supply ─── ESP32 5V Pin
                  └─── Common GND ───┬─── Motor Supply GND
                                     │
Motor Supply (+V) ─── ESC Power      │
                  └─── ESC GND ──────┘
```

### ESP32-C3 Voltage Damage

**Symptoms**: ESP32 GPIO damaged (always HIGH or LOW), overheating, or complete failure.

**Cause**: 5V signal applied directly to 3.3V-tolerant GPIO pins.

**Prevention**:

**Before Connecting Any 5V Signal**:
1. Verify sensor output voltage with multimeter
2. If 5V, install voltage divider BEFORE connecting to ESP32
3. Never assume - always measure

**Voltage Divider Installation**:

```
Hall Sensor (5V Output)
     │
     └─── R1 (2.2kΩ) ───┬─── GPIO 0 (ESP32)
                        │
                        R2 (3.3kΩ)
                        │
                       GND
```

**Verification**:
- With 5V input: Measure voltage at GPIO connection point
- Should read ~3.0V (safe for ESP32)

**If Already Damaged**:
- Test GPIO with multimeter (should show 3.3V when HIGH, 0V when LOW)
- If stuck HIGH or LOW: GPIO permanently damaged
- Use different GPIO pin and update pin assignment in code
- Or replace ESP32 module

### Brown-Out During Motor Start

**Symptoms**: Microcontroller resets when motor starts, system unstable during load changes.

**Cause**: Power supply voltage dips below minimum operating voltage due to motor startup current.

**Diagnostic**:
- Measure VCC voltage during motor start (oscilloscope or fast multimeter)
- If drops below 4.5V (for 5V logic) or 2.8V (for 3.3V logic): brownout occurring

**Resolution**:

**Immediate**:
- Add 1000-2200µF electrolytic capacitor across power supply
- Install as close to microcontroller as possible

**Long-Term**:
- Upgrade power supply to 2-3x current capacity
- Use separate supplies for logic and motor
- Add bulk capacitance (0.1µF + 10µF) near microcontroller

**Capacitor Placement**:
```
Power Supply
     │
     ├─── 1000µF (bulk storage)
     │
     ├─── Logic Circuit
     │      └─── 10µF + 0.1µF (local bypass)
     │
     └─── Motor ESC
            └─── 470µF (motor smoothing)
```

### Ground Loop Issues

**Symptoms**: Erratic behavior, noise on signals, occasional resets.

**Cause**: Multiple ground paths creating voltage differences between components.

**Resolution**:

**Star Ground Configuration**:
```
                Power Supply GND (central point)
                        │
         ┌──────────────┼──────────────┐
         │              │              │
    Microcontroller   ESC          Sensor
```

**Best Practices**:
- Single point ground (star configuration)
- Thick ground wires (minimize resistance)
- Keep logic ground separate from motor power ground until star point
- Use twisted pairs for long signal runs

## Platform-Specific Issues

### ESP32-C3 Issues

#### Failed to Connect / Upload Error

**Solution**:
1. Press and hold BOOT button
2. Press and release RESET button
3. Release BOOT button
4. Immediately click Upload

**Or**:
- Try different USB cable (must be data cable, not charge-only)
- Install CP210x or CH340 USB drivers
- Select correct port (may change each connection)
- Reduce upload speed: Tools → Upload Speed → 115200

#### Serial Monitor Shows Garbage

**Cause**: Baud rate mismatch

**Solution**:
- Set Serial Monitor to 115200 baud

#### Serial Monitor Spam

**Symptoms**: Too many debug messages, hard to read

**Solution**:
```cpp
// Reduce output frequency
#define SERIAL_DEBUG_INTERVAL 1000  // Print every 1000ms

unsigned long lastDebug = 0;
if (millis() - lastDebug > SERIAL_DEBUG_INTERVAL) {
    Serial.println(status);
    lastDebug = millis();
}
```

## Performance Issues

### Slow PID Response

**Symptoms**: Takes too long to reach target RPM or recover from disturbances

**Solution**:
- Increase Kp (more aggressive response)
- Verify control loop frequency adequate (should be ≥100Hz)
- Check for delays in control loop (remove any `delay()` calls)
- Reduce filtering (faster response, more noise)

### High Steady-State Error

**Symptoms**: Motor settles at RPM offset from target (e.g., target 1440, actual 1400)

**Solution**:
- Increase Ki (integral gain eliminates steady-state error)
- Verify integral not saturated (check windup limits)
- Check for mechanical issues (friction, binding)

## System Recovery

### Hard Reset Procedure

**When to Use**: System completely unresponsive, erratic behavior, or suspected corruption

**Procedure**:
1. Disconnect all power sources (USB, external power, batteries)
2. Wait 30 seconds (allow capacitors to fully discharge)
3. Visually inspect all connections
4. Reconnect logic power only (no motor)
5. Verify basic operation (Serial Monitor output)
6. If working, reconnect motor power

### Factory Reset (Software)

**When to Use**: PID tuning experiments gone wrong, unknown configuration state

**Procedure**:
1. Open fresh copy of code from repository
2. Reset `config.h` to default values:
   ```cpp
   #define DEFAULT_KP  0.150
   #define DEFAULT_KI  0.080
   #define DEFAULT_KD  0.015
   #define DEFAULT_TARGET_RPM 1440.0
   #define PWM_MIN_THRESHOLD 45
   ```
3. Upload to microcontroller
4. Test with known-good configuration
5. Re-tune if needed

### Emergency Stop Implementation

**For Production Systems**: Add hardware emergency stop

**Circuit**:
```
Emergency Stop Switch (N.O.)
     │
     └─── PWM Pin ─── 10kΩ to GND
```

When pressed, pulls PWM pin LOW, stopping motor immediately.

**Software**:
```cpp
// Check for emergency stop
if (digitalRead(EMERGENCY_STOP_PIN) == LOW) {
    motor_set_pwm(0);
    while(digitalRead(EMERGENCY_STOP_PIN) == LOW) {
        delay(100);  // Wait for release
    }
    // Reset PID state
    integral = 0;
    previousError = 0;
}
```

## Advanced Diagnostics

### Using Oscilloscope

**Key Signals to Monitor**:
- Hall sensor output: Should show clean pulses, frequency proportional to RPM
- PWM output: Should show varying duty cycle (5-95%)
- Power supply voltage: Should remain stable (±5% maximum)

**Common Patterns**:
- Noisy Hall signal: Add filtering (hardware or software)
- Irregular PWM: Check control loop timing
- Voltage spikes: Add capacitors, check grounding

### Using Logic Analyzer

**Capture**:
- Hall sensor pulses
- PWM output
- Control loop timing

**Analysis**:
- Verify pulse count matches expected (PULSES_PER_REV)
- Check for missed interrupts (gaps in capture)
- Validate timing consistency

### Thermal Analysis

**Warning Signs**:
- ESC heatsink >80°C: Reduce load or improve cooling
- Motor >70°C: Check for binding, reduce duty cycle
- Microcontroller hot: Check for short circuits or excessive current draw

## Preventive Maintenance

**Regular Checks** (Every 50 Hours Operation):
- Visual inspection of all connections
- Verify no loose wires or components
- Check for signs of overheating (discoloration, melted plastic)
- Test emergency stop functionality
- Backup PID configuration values

**Replacement Schedule**:
- Capacitors: Replace every 2-3 years (electrolytic degrade)
- Connectors: Replace if oxidation or damage observed
- Motor bearings: Lubricate or replace per motor manufacturer spec

## When to Seek Additional Help

**Beyond DIY Troubleshooting**:
- Smoke or fire (stop immediately, do not restart)
- Repeated component failures (indicates design issue)
- Unexplained behavior after exhausting this guide
- Safety concerns

**Resources**:
- GitHub Issues: Report bugs and seek community help
- Motor/ESC manufacturer support: For hardware-specific issues
- Electrical engineer consultation: For custom or high-power applications

## Summary Checklist

Before reporting an issue, verify:
- [ ] All connections correct per wiring diagram
- [ ] Power supply adequate (voltage and current)
- [ ] Ground connections solid (common ground)
- [ ] Configuration values appropriate (PULSES_PER_REV, PID gains)
- [ ] Software uploaded successfully
- [ ] Voltage levels appropriate (3.3V logic)
- [ ] Motor and ESC compatible and working separately
- [ ] No physical damage to components
- [ ] Tried basic troubleshooting (power cycle, check connections)

Include when asking for help:
- Build used (`esp32-c3/control` or `esp32-c3/embedded`)
- Motor specifications (pole count, voltage, current)
- ESC model and specifications
- Power supply details
- PID configuration values
- Detailed description of problem
- Serial Monitor output (if available)
- Photos of physical setup
