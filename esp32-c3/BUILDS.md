# ESP32-C3 BLDC Controller — Builds

Two firmware builds against the same hardware. Both compile for
`esp32:esp32:nologo_esp32c3_super_mini`.

| | `embedded/` | `control/` |
|---|---|---|
| Purpose | Production, goes in the enclosure | Bench / bring-up |
| Serial | Silent (opt-in flag) | Full console |
| Live control | None | Manual / auto / stop |
| Telemetry | None | 0–50 Hz |
| Flash | 295 KB (22%) | 325 KB (24%) |
| RAM | 14.2 KB | 15.1 KB |

The driver and control maths — `pcnt_driver.h`, `pid_common.h`, `rpm_common.h`,
`ledc_driver.h` — are **shared**, not copied. `embedded/embedded.ino` includes
them via `../control/`. Change them in `control/` only.

## `embedded/` — production

Power it and it runs. No console, no logging, no external input of any kind.

1. Zero throttle for `ESC_ARM_DURATION_MS` so the driver arms
2. Soft-start ramp over `SOFT_START_DURATION_MS`
3. Hold `DEFAULT_TARGET_RPM`

On stall it cuts drive immediately, waits for the rotor to turn again, then
soft-starts back in — **indefinitely**, so a self-clearing jam recovers without a
power cycle.

To service a unit in the field, set `ENABLE_SERIAL_LOG` to 1 in
`config_common.h` and rebuild. It logs at 4Hz from the idle task.

⚠️ **Never put blocking serial writes in the control task.** A ~90-character line
at 115200 baud occupies the task for ~8ms. Doing that inside the 5ms loop
inflated measured speed spread from sd 7.7 to sd 33.5 — the instrumentation was
the noise source. The telemetry snapshot is published under `noInterrupts()` and
printed from `loop()` instead.

## `control/` — bench

The bring-up and service tool. See [DIAGNOSTICS.md](DIAGNOSTICS.md) for the full
command reference and fault-isolation procedures.

## Flash

```sh
# production
arduino-cli compile -b esp32:esp32:nologo_esp32c3_super_mini esp32-c3/embedded
arduino-cli upload  -p /dev/ttyACM0 -b esp32:esp32:nologo_esp32c3_super_mini esp32-c3/embedded

# bench
arduino-cli compile -b esp32:esp32:nologo_esp32c3_super_mini esp32-c3/control
arduino-cli upload  -p /dev/ttyACM0 -b esp32:esp32:nologo_esp32c3_super_mini esp32-c3/control
```

## Verified performance

Production build, 24V, free shaft, no intervention after power-up:

| metric | value |
|--------|-------|
| mean speed | 1440.2 RPM (target 1440) |
| sd | 7.7 RPM |
| range | 1407–1457 RPM (~±1.7%) |
| steady duty | 130/255 (51%) |
| stalls | 0 over 40s |

## Before it goes in the box

- [ ] **Disconnect the driver's 5V from the ESP32.** ⚠️ Do this first — it is a
      known fault, not a precaution. The JYQD datasheet states the control-port
      5V "prohibits connect external power equipment" and exists only for the
      board's own pot and switch. Running the ESP32 from it causes visible
      jitter whenever USB is absent, because that output cannot supply the C3's
      load and the 3.3V rail sags. Power the ESP32 from USB or a proper 5V
      supply and share **only GND** with the driver.
- [ ] **Never connect two 5V sources at once.** Driving the ESP32 from USB and the
      driver's 5V simultaneously ties two voltage sources together; current flows
      between them through protection diodes whenever their voltages differ.
- [ ] **Tune under load.** These gains were derived free-shaft. A loaded motor has
      different inertia and damping; expect the tuning to move. Add `Kd` before
      `Kp` if it oscillates under torque.
- [ ] **Decide on the VR ceiling.** A 3.3V signal into the driver's 0–5V, 20kΩ
      input can never command more than 66% of range. Fine at 51% duty today,
      but the top third is unreachable without a level shifter.
- [ ] **Confirm Hall supply.** Motor spec requires +5 to +20V; the driver sits at
      the bottom of that range at 5V.
- [ ] **Confirm the Hall permutation is the validated one.** Do not re-solder
      Ha/Hb on the production unit.
