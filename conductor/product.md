# BLDC Motor PID Controller — Product Definition

> **History:** this project previously shipped Arduino Uno and ATtiny85 variants.
> They were removed on 2026-10-31 (commit `396ade7`) and remain in git history.
> The product is now **ESP32-C3 only**, with its own driver PCB.

## Summary

Closed-loop PID speed control for a 3-phase BLDC motor (default
`DEFAULT_TARGET_RPM = 1440.0`), running on an **ESP32-C3 Super Mini** that sits on
a **custom 64 × 98 mm 4-layer driver PCB**. The board carries the whole driver
chain — JY01 controller, JY213L gate driver, JY2605M half-bridges, Hall signal
conditioner and power tree — so no external ESC is needed.

Precision comes from anti-windup PID, derivative filtering and a filtered RPM
measurement over the ESP32's hardware PCNT counter. Telemetry is local only:
USB serial, plus the driver's own FG/VR/EL interface.

## Vision

One board, one firmware family: characterise the motor on the bench, then deploy
the *same* control maths to production without re-architecting. The two firmware
variants (`control/` and `embedded/`) share `pid_common.h`, `rpm_common.h`,
`pcnt_driver.h` and `ledc_driver.h` — they differ only in telemetry and console
surface, never in control behaviour.

## Target Users

- **Primary:** makers and low-volume builders (1–10 units) building a BLDC
  spindle or pump drive with a single-Hall or FG-tacho motor.
- **Secondary:** anyone replacing a JYQD-V7.3E3 driver board with an equivalent
  that can be closed-loop controlled over USB serial.
- **Workflow:** flash over USB → open the bench console → tune → bake the values
  into `config_common.h` → flash the production build.

## Goals

1. **RPM stability at 1440 RPM:** ±1–2 % steady-state error, fast settling, no
   sustained oscillation; validated through the soft-start ramp and filtered RPM.
2. **Self-contained hardware:** mains-to-motor on one board — power input, bulk
   capacitance, gate drive, half-bridges, Hall conditioning, 12 V/5 V/3.3 V rails.
3. **Tunability:** live gain trim from the on-board potentiometer (0.75×–1.25×,
   applied to all three gains) without recompiling.
4. **Safety and robustness:** soft-start, stall detection with automatic
   re-arm, task watchdog, and a boot-safe pin map (no strapping-pin conflicts).
5. **Reproducibility:** both firmware variants compile in CI on every push, and
   the PCB produces a verified fabrication package from one script.

## Non-Goals

- **Cloud / fleet platform:** no hosted dashboard or Wi-Fi management. USB serial
  is the only telemetry surface.
- **FOC / sensorless vector control:** trapezoidal commutation only this cycle.
- **New MCU ports:** freeze at ESP32-C3. No STM32, RP2040 or ESP32-S3.

## Constraints

- Motor: 3-phase BLDC with Hall sensors and an FG tacho output.
- `PULSES_PER_REV = N_poles / 2` (8-pole → 4).
- Logic is 3.3 V (ESP32-C3); the driver interface is 5 V, so the FG line is
  divided 2.2 kΩ / 3.3 kΩ and the VR node is driven open-drain.
- Firmware must stay Arduino IDE and PlatformIO compatible (`.ino` + `.h`).
- Board: 64 × 98 mm, 4 layers, 2 oz outer copper, DRC-clean at 0.2 mm
  clearance; see `PCB/V1/README.md`.

## Success Metrics

- RPM stays within ±20 RPM of target under a load step.
- Bench-to-production transfer needs no re-tune.
- CI: `arduino-cli compile` passes for both variants on every push.
- PCB: 0 DRC violations, 0 unconnected items, fab package verified before order.

## Platforms (in-scope)

| Variant | Role | Notable |
|---|---|---|
| `esp32-c3/control` | Bench / bring-up | Full serial console, manual/auto/stop modes, 0–50 Hz telemetry |
| `esp32-c3/embedded` | Production | Silent by default, soft-start, stall re-arm, task watchdog |
| `PCB/V1` | Hardware | 64 × 98 mm 4-layer, JY01 + JY213L + JY2605M, Hall amp, 14 test points |
