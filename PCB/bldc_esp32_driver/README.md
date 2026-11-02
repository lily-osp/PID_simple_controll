# BLDC Motor Driver — JYQD-V7.3E3 Architecture + ESP32-C3 Super Mini + Hall Amp

Custom 70 × 120 mm PCB (full-integration) based on the **JYQD-V7.3E3** brushless driver
architecture, with an **ESP32-C3 Super Mini** controller and a Hall sensor signal
conditioner (RC filter → LM324 gain ×11 → 74HC14 Schmitt trigger).

> `JYQD-V7.3E3-English.pdf` is a product datasheet (specs + wiring), not a schematic.
> The circuit uses the JY IC family — **JY01** (SOP-16 controller), **JY213L** (TSSOP-20
> 3-phase gate driver), **JY2605M** (DFN-8 dual-NMOS half-bridge) — the same silicon as
> the reference board.

## External interface (fully integrated — 3 connectors only)

Everything else is handled on-board by the ESP32 (speed/direction/enable are driven
internally to the JY01). No control port, no GPIO breakouts.

| Connector | Pins | Function | Pitch |
|---|---|---|---|
| **J5** power | `P+  P−` | +12 V (V_IN) and ground | 5.00 mm (MaiXu MX126) |
| **J6** motor | `MA  MB  MC` | phase A / B / C to BLDC | 5.00 mm (MaiXu MX126) |
| **J3** Hall | `GND  Hc  Hb  Ha  5V` | Hall sensors (powered from 5 V) | 2.54 mm |

## Architecture

```
 V_IN ── 7812 ── +12V ── 7805 ── +5V
   │                │          │
 JY01 ──gate R── JY213L ──gate R── JY2605M ×3 ── phases A/B/C (J6)
   │                │
 Hall amp (5V): RC → LM324(×11) → 74HC14 → JY01 Hall inputs
 ESP32-C3: FG (scaled) / PWM / VR (open-drain) / EL / trim pot
```

- **Power tree**: `V_IN` (J5 P+) → U8 L7812 → `+12V` (gate-driver VCC) → U7 L7805 →
  `+5V` (logic). Hall amp runs on **+5V**, so 74HC14 outputs drive JY01 directly.
- **Current sense**: P− passes through R1 shunt (R005, 2512) to GND; JY01 `Is` sees the
  filtered shunt node (`ISENSE_F` via R36 + C21). *Caveat:* verify scaling against the
  driver's internal sense topology before relying on current limit.

## Design notes

- **78xx regulators**: with 12–36 V input keep `V_IN ≤ 28 V` for dropout/power margin
  (12 V nominal recommended).
- **GPIO4 → EL level shift**: EL is pulled up to **+5V** (R33 10 kΩ); GPIO4 drives it
  open-drain through R34 (1 kΩ). Configure GPIO4 as open-drain in firmware.
- **FG scaling**: JY01 FG (5 V) → R4 2.2 k / R5 3.3 k divider → GPIO0 (RPM in, 3.3 V).
- **ESP32 pin usage**: GPIO0=RPM (FG), GPIO1=PWM→VR, GPIO2=**unconnected** (boot
  strapping pin, internal pull-up holds it high), GPIO3=trim ADC (ADC1_CH3),
  GPIO4=EL (open-drain), GPIO5=ERR LED. GPIO6–10/20/21 are spare/unconnected.
- **ERR LED** driven from GPIO5 via R32 (560 Ω); **PWR LED** from +5V via R20 (560 Ω).

## Pre-order audit

Checks performed on the exact fabrication data (`fab/`), all passing:

| Check | Result |
|---|---|
| DRC (`--severity-all`) | 0 violations, 0 unconnected items |
| Schematic parity | 0 genuine (268 cosmetic: root-sheet `/` prefix, footprint lib prefix) |
| Outline closure | 8 Edge.Cuts segments, 0 open endpoints, 70.0 × 120.0 mm |
| Pads outside outline | 0 |
| Orphan nets (1 pad) | none |
| Fab files | 9 gerbers + 1 drill (Excellon, metric, decimal) + job file |

### Electrical fixes applied at audit

- **Bootstrap caps C13–C15 were 10 µF/25 V.** The `VB_x` rail floats on the phase and
  peaks at `V_IN + (V_+12V − V_f)` ≈ **V_IN + 11.3 V**. At the intended 12 V input that
  is 23.3 V (93 % of the rating); at 24 V input it is 35.3 V and the part fails short,
  taking the JY213L with it. Changed to **1 µF/50 V**, which is also the correct
  bootstrap value for this gate charge (droop ≈ Q_g/C ≈ 50 mV/cycle). Footprint
  unchanged (0805).
- **Unrated 0805 caps on rails** were given explicit ratings: `C12 → 10 µF/25 V` (it sits
  on +12 V), `C11/C19/C20 → 100 nF/50 V`.

### Layout changes applied at audit

1. **Trim pot moved off the strapping pin.** `RV1`'s wiper was on `GPIO2`, one of the
   three ESP32-C3 strapping pins (GPIO2/8/9), which must be high or floating at boot. The
   pot pulls it to 0 V at the low end of travel, so a power cycle with the pot turned
   down could enter joint-download boot instead of running firmware. The net now goes to
   `GPIO3` (`ADC1_CH3`, not a strapping pin); only the final 1.31 mm stub was rerouted,
   the 20 mm trunk is untouched. `GPIO2` is left floating, which is exactly the state its
   internal boot pull-up wants.
2. **Firmware followed the pin move.** `POT_SENSITIVITY_PIN` is now 3 and the
   `POT_ENABLE_PIN` gate is gone — the trim is always active and the pot midpoint is
   1.0×. Previously the firmware expected the enable on `GPIO3` while the board left it
   unconnected, so the pot did nothing at all. Both sketches compile (`pio run`,
   espressif32 7.0.1): control 17.9 % flash / 4.3 % RAM, embedded likewise.
3. **Four M3 mounting holes added** at the corner-arc centres (5 mm from each edge),
   NPTH 3.2 mm, marked board-only so they do not appear as schematic-parity extras, with
   a 1.2 mm copper-free ring so a screw head cannot short the GND pour.
4. **`C4` shifted 2.4 mm left** because its 10 mm can sat 0.4 mm from the bottom-right
   hole — an M3 head would have fouled it. Its three track endpoints were snapped to the
   new pad positions; nothing else moved.

### Remaining note

- **`EL` (GPIO4) and the ERR LED (GPIO5) are wired but unused by firmware.** `EL` is
  pulled to +5 V through R33 and driven open-drain through R34, so the JY01 enable state
  at power-up depends on the EL polarity of the JY01 itself — confirm before relying on
  the motor being disabled at boot. Wiring either up is a firmware change only.

## Status

- **Schematic**: complete & verified — netlist matches the design table **223/234 pins**
  (floating pins are the 3 unused 74HC14 gate outputs + 8 spare ESP32 GPIOs).
- **Board**: **fully routed, DRC-clean, fab package generated** — 70.0 mm × 120.0 mm
  (5 mm rounded corners), 73 footprints (69 components + 4 M3 mounting holes).
  - 1277 traces (4507 mm), 142 vias, 2 zones (GND pour on F.Cu + B.Cu, solid-connected)
  - **DRC: 0 violations, 0 unconnected items** (`kicad-cli pcb drc --severity-all`)
  - **Schematic parity: 0 genuine mismatches** — the 268 reported items are cosmetic only
    (schematic nets carry the root-sheet `/` prefix; footprints are reported without their
    library prefix). Verified programmatically: 0 net-name differences, 0 footprint
    differences after normalisation, 0 extra footprints.
  - **Outline**: closed Edge.Cuts loop, 8 segments, 0 open endpoints; **0 pads outside**
    the outline.
  - **Drills**: 0.3 mm ×142 (vias), 0.8/1.0/1.1/1.2/1.3 mm ×29 (component holes),
    3.2 mm ×4 (M3 mounting, NPTH).
  - Renders: `render/routed_top.png`, `render/routed_bottom.png`, `render/routed_top_zoom.png`

### Copper sizing (measured, not assumed)

Power copper is widened to the largest width the layout allows, validated by DRC rather
than by eye. Length-weighted width distribution of the motor phases:

| Net | < 0.25 mm | 0.25–0.39 mm | 0.40–0.59 mm | ≥ 0.60 mm | avg | max |
|---|---|---|---|---|---|---|
| PH_A | 1 % | 84 % | 1 % | 15 % | 0.33 mm | 0.80 mm |
| PH_B | 1 % | 80 % | 0 % | 19 % | 0.35 mm | 0.80 mm |
| PH_C | 2 % | 56 % | 2 % | 40 % | 0.39 mm | 0.60 mm |

`V_IN` and `PNEG` are **uniform 0.80 mm**; `+12V`/`+5V` average 0.57 mm.

> **Current capability — read this before choosing copper weight.** Capacity is set by
> the narrowest section, and ~80 % of each phase runs at 0.25–0.39 mm. That is about
> **1.3 A per phase on 1 oz** and **2.6 A on 2 oz**. The corridors are geometrically
> saturated: a fine-grained widening pass (0.30 mm → 0.80 mm in 0.05 mm steps, DRC
> re-validated at every step) can only raise ~1 % of the phase length further, because
> adjacent 0.2 mm-clearance copper leaves no room. Order **2 oz copper** if the motor
> draws more than ~1 A per phase. Going beyond ~2.6 A needs a layout change (wider
> corridors for the phases, or 4 layers), not different traces in this placement.


## Component placement (left → right signal flow)

| Zone | Components |
|---|---|
| Left edge | J3 (Hall port) |
| Left-mid | Hall amp: R21–R31, C16–C20, U4 (LM324), U5 (74HC14) |
| Center | U1 (JY01) → R8–R13 → U3 (JY213L) → R14–R19 → Q2/Q3/Q4 (JY2605M) |
| Center-right | bootstrap D1–D3 + C13–C15 |
| Right | J5 (power), J6 (motor), C1/C2/C5 bulk, R1 shunt, U8/U7 regulators, C3/C4/C11/C12 |
| Bottom | U6 (ESP32-C3), U2 (CSD13380F3), RV1 trim, LEDs, level-shift |

## Routing pipeline (reproducible)

1. `gen_sch_full.py` — regenerate schematic (netlist-verified).
2. `gen_pcb.py` — regenerate placement-only board (**only when re-planning from scratch**;
   never run it over a user-arranged placement).
3. `setup_netclasses.py` — assign net classes + export `board.dsn`.
4. `final_incremental.py` — rip the nets affected by a placement change, drop the GND
   pours, export the DSN, add the wide `pwr_phase` class and mark all remaining copper
   `(type protect)` so the router cannot disturb the approved routing.
5. FreeRouting **2.1.0** on **Java 21**: `java -jar freerouting.jar -de board.dsn -do board.ses -mt 1`
   (single-threaded — v2.1.0's multi-threaded optimizer is known to create clearance violations).
6. `final_import_ses.py` — import the session, restore + refill the pours.
7. `final_widen.py` / `final_minwidth.py` — staged widening using the DRC as the oracle.
8. `final_silk_cleanup.py` — clear silkscreen warnings.
9. `fab_package.sh [--2oz]` — gerbers + drill + positions + `fab/ORDER.md`.

**Two things that cost hours, documented so they don't again:**

- KiCad exports a GND pour as a full-board Specctra `(plane ...)` on **both** layers. If
  the pour is present during export, FreeRouting sees an occupied board and fails whole
  nets. Remove pours before export and refill afterwards.
- A full re-route from scratch at 0.8 mm power widths **cannot converge** here (plateaus
  at 24–38 unrouted). Preserve the routed board and route only the nets a placement change
  actually touches; that lands at 0 unrouted.

The committed board reflects the **user's hand-arranged placement** (69 components moved
in KiCad); the gen_pcb generator layout is only a fallback.

## Ordering

```bash
./tools/fab_package.sh --2oz     # or without --2oz for 1 A/phase
```

Output in `fab/`:

| File | Contents |
|---|---|
| `bldc_esp32_driver_gerbers.zip` | 9 gerbers (F/B Cu, mask, silk, paste, Edge.Cuts) + `.drl` |
| `positions.csv` | assembly centroids, mm, drill origin |
| `ORDER.md` | board spec sheet to hand to the fab |

Verification already passed on this exact board: 0 DRC violations, 0 unconnected items,
closed outline, 0 pads outside the outline, 0 genuine schematic-parity mismatches.

> **ERC note**: the schematic reports 28 ERC items, all accounted for — 11 unconnected
> pins are the intentionally-unused 74HC14 gates and spare ESP32 GPIOs; 3 are library
> version/resolution warnings; the rest are power-flag bookkeeping (`V_IN` and the JY01
> `Vss` are fed from external connectors, which ERC wants a `PWR_FLAG` for). None affect
> the manufactured board.

## Files

```
bldc_esp32_driver/
├── bldc_esp32_driver.kicad_sch    # schematic (rebuilt from scratch)
├── bldc_esp32_driver.kicad_pcb    # board (routed, widened, DRC-clean)
├── bldc_esp32_driver.kicad_pro
├── bldc_esp32_driver.kicad_prl
├── bldc_esp32_driver-erc.rpt
├── README.md
├── footprints/ESP32-C3-SuperMini.kicad_mod
├── footprints/JY2605M_DFN8_5x6.kicad_mod   # DFN-8 5×6 half-bridge (no exact lib match)
├── render/routed_{top,bottom,top_zoom}.png # 3D renders of the routed board
├── fab/                                    # gerbers, drill, positions, ORDER.md
├── tools/gen_sch_full.py, gen_pcb.py, verify_net.py
├── tools/final_{incremental,import_ses,widen,settle,minwidth,silk_cleanup}.py
├── tools/fix_pot_pin_and_holes.py, set_values.py
├── tools/fab_package.sh
├── fp-lib-table
└── fp-info-cache
```
