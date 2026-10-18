# ESP32-C3 Diagnostics Guide

Companion to the diagnostic firmware in `control/`. Everything here is
reachable from the serial console at 115200 baud.

## Why this build exists

The production firmware prints one line at boot and then holds a fixed target.
When the motor doesn't spin you get no information: you cannot tell a wiring
fault from a tuning fault, and both look identical ("nothing happens"). This
build adds live telemetry and a command console so you can bisect the problem
in one session.

## Commands

| Command | Effect |
|---|---|
| `?` | Print the command list |
| `m <0-255>` | **Manual mode** — drive raw duty, PID bypassed. The key diagnostic. |
| `a <rpm>` | Closed-loop PID at a new target |
| `s` | Stop (zero duty, will not self-start) |
| `g` | Run / re-arm soft-start |
| `f <0-255>` | PID minimum duty floor (`0` = full authority) |
| `k <p> <i> <d>` | Set Kp / Ki / Kd live |
| `z` | Reset integral and RPM filter |
| `t <hz>` | Telemetry rate. A number sets Hz; a word tags the wiring |
| `w` | Fresh 1.5s pulse waveform + jitter analysis |
| `bt` | Boot transient trace (first 12s after power-up) |
| `t <label>` | Tag the current Hall wiring — survives the power cycle |
| `r` | Ranked table of every recorded Hall permutation |
| `c` | Clear recorded trials |
| `d` | Dump Hall sensor + PID diagnostics |
| `p` | Dump GPIO pin states and uptime |

## Telemetry format

```
[  6.8s][MAN  ] rpm:  965.6 tgt:    0 pwm: 60/ 45 int:  +0.00 err:  -965.6 sig:ok
   uptime     mode      measured     target  duty/floor  integral   error    sensor
```

`sig` field:
- `ok` — Hall pulses arriving within the stall window
- `STALE` — pulses stopped, but the ISR fired earlier
- `NO-PULSE` — the ISR has **never** fired since boot; the sensor path is dead

## The bisect

Work top-down. Each step eliminates a layer.

### 1. Is the sensor path alive?

```
s
d
```

Zero duty. `pulses since boot` frozen and `pulse age` climbing means the line is
quiet — healthy. `NO-PULSE` in telemetry means GPIO 0 has never seen an edge:
check the divider, Hall power, and that you're on the right pin.

### 2. Does raw duty turn the motor?

```
s          # full stop, wait 2s
m 150
t 20
```

Bypasses the PID entirely. Watch RPM:

- **Turns and holds steady** → hardware chain is fine, the fault is in the PID
- **Never starts at any duty** → hardware fault: phases, halls, VR, or 24V
- **Runs at low duty, dies at high duty** → Hall/phase misalignment
- **RPM jumps around at a fixed duty** → commutation is unstable, see below

### 3. Back to closed loop

```
s
f 0         # remove the duty floor so PID has full authority
a 1440
```

Lower the floor to 0 while tuning. `PWM_MIN_THRESHOLD` (45) forces the motor to
be driven even at zero speed error, which hides what the PID actually wants to
do and prevents it from ever slowing down.

## Reading the symptoms

| Symptom | Likely cause |
|---|---|
| No pulses at any duty | Divider open, no Hall power, wrong pin, motor not turning |
| Won't start below ~140, dead above ~220 | **Hall/phase misalignment** |
| Dead still at every duty, 24V present | **No starting torque** — hand-spin the shaft |
| RPM wanders at fixed duty | Commutation instability — check Hall order, then phase order |
| RPM reads 0 but you can see the shaft turning | Signal path: divider, pull-up, or Hall VCC mismatch |
| Integral pegs at +255 then overshoots | Windup. Reduce Ki, or `z` and re-run |
| Motor stutters only under load | Insufficient `PWM_MIN_THRESHOLD`, or low Kp |

## Why high duty failing points at Hall misalignment

Hall sensors sit at a fixed electrical angle to the windings. The driver reads
them to decide which phase pair to energize. If the phase order and Hall order
disagree by 60° electrical, the driver commutates one sector late:

- At low duty the rotor has enough inertia to coast through the wrong sector
- As duty rises the current phase jumps become large enough that the wrong
  commutation produces torque that opposes the rotor instead of driving it
- Result: won't break away from rest, or breaks away and then stalls as speed
  climbs

That non-monotonic curve — dead at low duty, alive mid-range, dead at high duty
— is not physical motor behaviour and does not have a tuning explanation.

**However**, check the stall cut-out first. A board that latches off after a
stall timeout produces the same curve, and it is far more common than actual
misalignment. Hand-spin the shaft to distinguish them.

## Controller facts (JYQD-V7.3E3)

Established from the vendor documentation and independent teardowns, not
assumed. These constrain what the firmware can ever achieve.

### The Signal line is XOR of the three halls

The driver takes Ha/Hb/Hc and emits a single square wave that is the XOR of all
three. XOR of three 120° Hall signals alternates across all six valid states,
completing **3 full cycles per electrical revolution**. So:

```
pulses_per_rev = 3 x pole_pairs = 3 x (poles / 2)
```

For the 42BLF at 8 poles that is **12**, which is what `config.h` now sets. The
old value of 4 inflated every RPM reading by 25% — a reading of 168 was really
126.

| Motor poles | pole pairs | Signal pulses/rev |
|-------------|-----------|-------------------|
| 6 | 3 | 9 |
| 8 | 4 | 12 |
| 10 | 5 | 15 |
| 12 | 6 | 18 |

Signal is 5V push-pull, **under 5mA**. The 2.2k / 3.3k divider to GPIO 0 is
mandatory — the C3 pins are not 5V tolerant.

### Hall line sequence is NOT universal

Application guideline 2 in the controller datasheet, verbatim:

> "Applicable to hall brushless dc motor with Hall at 120°, **not all
> manufacturers' Hall line sequence are corresponding**, you can adjust the
> Hall line sequence or motor three-phase line sequence according to the actual
> situation, to achieve the best driving effect."

This is the manufacturer explicitly documenting that **swapping Hall or phase
lines is a normal, expected adjustment**, not a wiring mistake. If the motor
hunts, stalls, or refuses to accelerate, this is the first thing to try and the
procedure is below.

### The motor is a high-speed, low-torque design

From the 42BLF datasheet:

| Variant | Rated | Torque | Current | Power | Peak torque | Back EMF |
|---------|-------|--------|---------|-------|-------------|----------|
| 42BLF20 | 4000 RPM | 0.063 Nm | 1.65 A | 26 W | 0.185 Nm | 3.2 V/kRPM |
| 42BLF40 | 4000 RPM | 0.125 Nm | 3.3 A | 52 W | 0.38 Nm | 3.2 V/kRPM |
| 42BLF60 | 4000 RPM | 0.185 Nm | 5 A | 78 W | 0.55 Nm | 3.2 V/kRPM |
| 42BLF80 | 4000 RPM | 0.25 Nm | 6.6 A | 104 W | 0.75 Nm | 3.2 V/kRPM |

Torque constant 0.043 Nm/A across the family. Peak torque on the smallest variant
is under 0.2 Nm, so these have very little margin for a poor commutation angle —
which is exactly the condition that makes Hall ordering matter.

Hall sensor supply must be **+5 to +20 VDC**; the driver's 5V sits at the bottom
of that range. If the Hall rail measures outside it, readings will be unreliable.

### It spins up, then can't get past a low ceiling

Observed on a clean power cycle with the shaft completely free, using the boot
trace (`bt`). PWM was pegged at 255 throughout:

| time | PWM | period | true RPM (PPR 12) |
|------|-----|--------|-------------------|
| 0.0–3.0s | 0 → 183 | — | ESC arming, then ramp |
| 3.25–3.75s | 214 → 255 | 12–18 ms | ~250–420 |
| 4.0–6.25s | 255 | **29.7 ms steady** | **~126** |
| 7.75s+ | — | — | stall failsafe trips |

So it *does* break away from rest on its own, spins up, then settles at a very
consistent but low speed and gets cut. The period is stable at 29.7 ms for over
two seconds, which is genuine commutation, not noise.

Against a 4000 RPM rated motor, ~126 RPM is ~3% of rated speed. The motor has no
mechanical load. Leading suspect is the Hall line sequence, which the datasheet
explicitly warns varies between manufacturers — see above. Fix it by the swap
procedure in the next section.

### Stalled, the driver cuts out

The driver shuts down if it stalls for too long, and the firmware's own stall
failsafe (`STALL_TIMEOUT_MS`) cuts PWM when pulses stop for 150 ms. Either way a
motor that loses sync reads as *dead* rather than *slow*. Never interpret a dead
high-duty reading as "the commutation broke"; check the low end first, and read
the boot trace rather than commanding a duty live.

Hand-spinning the shaft during the jitter is still a useful cross-check: if it
accelerates freely under finger power, the limit is commutation; if it resists,
it is mechanical.

### VR tops out at 66% of range with a 3.3V driver

Datasheet: `0.1V - 5V` analog speed input, **20kΩ** input impedance. The driver
filters the incoming PWM into an analog average, so a 3.3V PWM signal can never
command more than `3.3 / 5 = 66%` of full speed, at any duty cycle including
100%.

Targets above 66% of the motor's maximum are unreachable with direct ESP32
drive. Use a level shifter — a single N-MOSFET with pull-up, or a TXS0102 — if
the operating point needs the top of the range.

PWM input frequency must be 1-20kHz; the firmware uses 5kHz, which is in range.

### The 5V control output is not a supply

The datasheet states the 5V port prohibits connecting external devices; it exists
only for the board's own pot and reverse switch. Power the ESP32 from USB and
share ground with the driver instead.

**Confirmed symptom of getting this wrong:** the motor runs cleanly with USB
attached and jitters when run standalone. The laptop's 5V rail is stiff enough to
hold the C3's 3.3V steady; the driver's 5V logic output cannot, so the rail sags
and the Hall ISR timing degrades, which corrupts the RPM measurement and makes
the PID hunt.

Never wire both the driver's 5V and USB into the ESP32 at the same time — that
ties two sources together and pushes current between them through the protection
diodes whenever their voltages differ, which is why the fault hides completely
while USB is plugged in.

Isolating it: run from a USB wall charger or power bank rather than a laptop. If
the jitter disappears, it was the supply, not the data connection.

## Fixing it

Swap **one Hall wire at a time**. Each transposition rotates the offset 60°, and
swapping two phase wires is commutation-equivalent to swapping the
corresponding two Hall wires, so rotating Hall wiring alone walks you through
every valid alignment. Leave the phases alone.

Retest after each swap with `m 150`. Three possible outcomes:

1. **It starts at low duty and stays alive at 255** → aligned, done
2. **It swaps to the opposite failure band** → better, try another swap
3. **No change across all three** → the Hall connector isn't reaching the
   driver at all; check the 5-wire plug and Hall VCC

Never leave a mismatched motor running against a load. It draws far more
current than a correctly aligned one and will damage the driver.

## Finding the Hall permutation

Swapping a Hall wire requires cutting power, which destroys any measurement
taken before the swap. So each power cycle **scores itself** into NVS
automatically, starting `TRIAL_START_MS` after boot and running for
`TRIAL_CAPTURE_MS`. Nothing needs to be read off a screen and remembered.

```
t ha-hb      tag the wiring that is currently soldered
<swap the wire, power cycle, wait ~16s>
r            ranked table of everything tried so far
```

Ranking is fastest-first with jitter as the tie-breaker, and anything that
produced no usable signal sinks to the bottom.

Measured on the 42BLF, transposing Ha and Hb:

| Wiring | pulses in window | peak RPM | jitter |
|--------|------------------|----------|--------|
| as shipped | 91 | 566 | 29.6% |
| **Ha/Hb transposed** | **2,374** | **1,855** | **10.8%** |

A 26× jump in pulse throughput and a 3× reduction in jitter is not a marginal
result — it is the difference between a motor that fights you and one that runs.

## Speed measurement, and why it dominated the tuning

The original estimator counted pulses in a 40ms window. At 1440 RPM with 12
pulses/rev that window holds ~11.5 pulses, so **one pulse of quantisation error
is ±8.7%, or ±125 RPM**. The PID was chasing its own sensor, and no gain set
could beat a noise floor that large — the best achievable spread was ~78 RPM.

Speed is now derived from the smoothed inter-pulse interval instead:

```
RPM = 60e6 / (period_us x PULSES_PER_REV)
```

which resolves to microseconds rather than whole pulses. Measured spread went
from ~89 RPM to ~7 RPM at the same operating point — a 13× improvement, entirely
from the sensor, with the motor unchanged.

One trap worth recording: the EMA update must use a **signed** difference. As the
motor accelerates the interval shrinks, and an unsigned subtraction underflows,
wrapping the accumulator and destroying the estimate.

## Tuning notes

Gains were re-derived empirically after both upstream faults were fixed; the
previous values (0.150 / 0.120 / 0.004) were not merely mistuned, they were
calibrated against a wrong pulse count and a quantised sensor.

```
Kp 0.040   Ki 0.080   Kd 0.001
```

Result at 1440 RPM, free shaft, 24V, verified over a 60s soak and again from a
cold boot with no manual intervention:

| metric | value |
|--------|-------|
| mean | 1439.4 RPM |
| sd | 6.7 RPM |
| ripple | 1417–1454 RPM (~±1.4%) |
| duty | 129/255 (50%), ample headroom |

Tune live with `k`, score with `t 25` and read the spread, then commit to
`config_common.h` only once it holds over a soak. Watch the duty: if it pegs at
255 the loop has no authority left and the gains are not the problem.

## Timing

`ctrl.ctrlLoopMaxPeriodUs` records the worst observed control-loop period. The
nominal period is 5000us. Large excursions mean something is preempting the
control task — usually serial printing moved into the control path, which this
build deliberately avoids by publishing state and printing from the idle task.

## Building and flashing

```sh
arduino-cli compile -b esp32:esp32:nologo_esp32c3_super_mini esp32-c3/control
arduino-cli upload -p /dev/ttyACM0 -b esp32:esp32:nologo_esp32c3_super_mini esp32-c3/control
arduino-cli monitor -p /dev/ttyACM0 -c baudrate=115200
```
