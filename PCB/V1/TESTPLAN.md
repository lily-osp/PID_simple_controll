# Bring-up test plan — bldc_esp32_driver V1

Written to be followed in order. Do not skip a stage because the previous one
"looked fine" — most failures on a board like this show up as a rail that is
slightly wrong, not as a dead board.

## Test points

Twenty-one probe pads are on the board, 1.5 mm bare copper on the top side, each
with its **number printed on the silkscreen** beside it (the "TP" prefix is
dropped — pad `16` is `TP16`). There is no TP6 and no TP13: both were dropped
when the area around them turned out to be occupied, and the numbers were not
reused so the references stay stable.

Five nets have no pad and are probed on a component pad instead:

| Net | Probe at | Why no pad |
|---|---|---|
| `EL` | R33 pin 1 | boxed in by +5V / FG |
| `HALL_OUT_A` | U5 pin 2 | blocked by the hall filter tracks |
| `VB_B`, `VB_C` | C14 / C15 pin 1 | no free spot near the power stage |
| `GQ_GH3` | Q4 pin 1 | same |
| `GPIO5` | R32 pin 1 | module, mounting hole and board edge leave no room |

| TP | Net | Position (mm) | Expected |
|---|---|---|---|
| TP1 | V_IN | 105.00, 83.36 | supply in, 12 V nominal |
| TP2 | PNEG | 161.21, 61.98 | ≈0 V (shunt return) |
| TP3 | +12V | 109.05, 92.79 | 11.3 V at 12 V in, 12.0 V at ≥15 V in |
| TP4 | +5V | 102.12, 109.56 | 5.0 V ±0.25 |
| TP5 | +3.3V | 138.68, 131.00 | 3.3 V ±0.15 (module LDO, feeds the trim pot) |
| TP7 | PWM_OUT | 133.50, 110.83 | 0–3.3 V PWM from the ESP32 |
| TP8 | RPM_IN | 130.59, 124.20 | 0–3.3 V pulses when the motor turns |
| TP9 | ISENSE_F | 154.88, 104.34 | mV-range, rises with load |
| TP10 | GND | 158.60, 117.24 | 0 V reference |
| TP11 | VR | 149.35, 119.26 | 0–3.3 V, follows PWM duty 1:1 |
| TP12 | ZF | 149.97, 109.86 | static, ≈5 V forward / 0 V reverse |
| TP14 | HALL_OUT_B | 113.02, 93.87 | 0–5 V square wave, shaft turning |
| TP15 | HALL_OUT_C | 116.32, 94.36 | 0–5 V square wave, shaft turning |
| TP16 | GPIO4 | 109.32, 109.60 | 3.3 V = enabled, 0 V = forbidden |
| TP17 | POT_ADC | 112.40, 109.88 | 0–3.3 V, midpoint at pot centre |
| TP18 | VB_A | 147.11, 65.03 | V_IN + ~11 V when the high side switches |
| TP19 | GQ_GH1 | 102.26, 77.44 | 0–12 V gate drive, phase A high side |
| TP20 | GQ_GH2 | 149.75, 81.51 | 0–12 V gate drive, phase B high side |
| TP21 | GQ_GL1 | 102.01, 72.44 | 0–12 V gate drive, phase A low side |
| TP22 | GQ_GL2 | 112.10, 71.07 | 0–12 V gate drive, phase B low side |
| TP23 | GQ_GL3 | 155.19, 74.28 | 0–12 V gate drive, phase C low side |

## Stage 0 — unpowered

1. **Visual**: no solder bridges on the 0.65 mm-pitch TSSOP (U3) or the DFN
   half-bridges (Q2–Q4). Check the electrolytic polarity (C1/C2/C5 stripe to
   `PNEG`, C3 to `+12V`, C4 to `+5V`).
2. **Rail shorts** — continuity, power off, all supplies disconnected:
   - `V_IN` ↔ `PNEG` : open
   - `+12V` ↔ `GND` : open
   - `+5V` ↔ `GND` : open
   - `+3.3V` ↔ `GND` : open
   A few hundred ohms is normal on `+5V`/`+3.3V` (the ICs load them); a few ohms
   or less is a short.
3. **Shunt**: `PNEG` ↔ `GND` should read ≈5 mΩ (R1). Much higher means R1 is
   not seated.

## Stage 1 — power only, no motor, current-limited

Bench supply on `V_IN`/`PNEG`, **current limit 150 mA**, 12 V. Nothing should
get warm.

| Check | Pass |
|---|---|
| Input current, idle | < 60 mA |
| TP3 `+12V` | 10.5–11.5 V (the 7812 drops out at 12 V in — this is expected) |
| TP4 `+5V` | 4.85–5.15 V |
| TP5 `+3.3V` | 3.15–3.45 V |
| PWR LED | lit |

If a rail is low, stop and check that regulator's input before going on.

> At 12 V input the 7812 cannot regulate. If you need a true 12 V gate-drive
> rail, feed **≥15 V** into `V_IN` and re-check TP3 (should be 12.0 V).

## Stage 2 — ESP32 and the control path

Plug in the ESP32-C3 SuperMini (USB or the 5 V pin — **never** power it from the
driver's 5 V rail while also on USB without checking, see the main README).

1. **Boot**: serial console at 115200 shows the banner and the pin report.
2. **PWM**: with the motor disconnected, set a non-zero target. TP7 should show
   a PWM waveform 0–3.3 V. Confirm the duty changes with the command.
3. **VR tracking**: probe **TP11**. VR should move *with* the duty — 0 % duty
   ≈ 0 V, 100 % duty ≈ 3.3 V. It is a direct connection through R7, so there is no
   inversion. If VR does not move, R7 or the GPIO1 trace is the suspect.
   (The pad sits on a short stub off the VR node, so it reads the same as R7 pin 2.)
4. **EL chain**: **TP16** `GPIO4` is the MCU side, **R33 pin 1** is the driver
   side. GPIO4 high → EL ≈5 V → driver *allowed* to run; GPIO4 low → EL ≈0 V →
   forbidden. Pulling GPIO4 high while the console reports "disabled" means the
   firmware and the schematic disagree; check `EL_ACTIVE_LOW` in `config.h`.
5. **Trim pot**: **TP17** `POT_ADC` should sit near 1.65 V at mid-travel and move
   smoothly to both ends. A stuck value means the wiper (RV1 pin 2) is open.

## Stage 3 — Hall sensors, motor disconnected

Connect the motor's Hall connector to J3. Rotate the shaft **by hand**.

| Check | Pass |
|---|---|
| TP8 `RPM_IN` | square pulses, 0–3.3 V, one per FG edge |
| TP14 / TP15 `HALL_OUT_B` / `_C` | 0–5 V square waves, 120° apart, 50 % duty |
| TP14/TP15 vs U5 pin 2 (`HALL_OUT_A`) | three evenly spaced phases |
| Pulse rate | consistent with `PULSES_PER_REV` in the firmware |
| U4/U5 outputs | clean logic levels, no chatter at rest |

Hand-turning should give a stable, jitter-free count. Chatter here means the
hall filter (R21–R23 / C16–C18) or the LM324 gain is wrong.

## Stage 4 — first spin, current-limited

Motor connected, shaft free, **current limit 500 mA**, target low.

1. Command a small target. The motor should start and hold RPM.
2. Watch TP9 `ISENSE_F` — it should rise smoothly with load, no spikes.
3. Check Q2–Q4 and U3 temperature after 30 s: warm is fine, hot is not.
4. Sweep the target 500 → 1500 RPM. RPM should track without oscillation. If it
   hunts, turn the trim pot down (it scales all three gains).
5. **Gate drive sanity** (scope, if available): probe **TP19/TP20/TP21/TP22/TP23**
   (the FET gates) one at a time, then a phase node. Expect 0–12 V square edges,
   no ringing above ~2× V_IN, and **never** high-side and low-side of the same
   phase high together (shoot-through). Q4 pin 1 is the missing `GQ_GH3`.
6. **Bootstrap**: **TP18** `VB_A` should sit at V_IN + ~11 V while phase A's high
   side switches, and recharge every cycle. If it sags, C13 is open. `VB_B` and
   `VB_C` have no pad — probe C14 / C15 pin 1.

## Stage 5 — load

Only after stage 4 passes. Raise the current limit in steps and load the motor.
Watch:
- TP3 `+12V` — should not sag more than ~0.5 V
- TP9 `ISENSE_F` — linear with load
- Phase copper temperature

The phases are 0.75 mm average on 2 oz, good for roughly 4 A per phase. The
0.65 mm-pitch necks at U3 are the narrowest point.

## What each failure usually means

| Symptom | Likely cause |
|---|---|
| No `+12V` | 7812 reversed or not seated; input below dropout |
| `+5V` low, `+12V` fine | 7805 or C4 |
| `+3.3V` low or unstable | ESP32 module not seated, or USB/5 V contention |
| VR does not move with PWM | R7, or PWM_OUT not reaching it |
| Motor buzzes, no rotation | Hall order (Ha/Hb/Hc) or phase order (MA/MB/MC) |
| RPM reads double/half | `PULSES_PER_REV` mismatch |
| Random resets under load | `+5V` sagging, or the ESP32 fed from the driver rail |
