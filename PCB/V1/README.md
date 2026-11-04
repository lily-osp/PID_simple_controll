# BLDC Motor Driver — JYQD-V7.3E3 Architecture + ESP32-C3 Super Mini + Hall Amp

Custom **64 × 98 mm, 4-layer** PCB (full-integration) based on the **JYQD-V7.3E3** brushless driver
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
 ESP32-C3: FG (scaled) / PWM → VR / EL / trim pot
```

- **Power tree**: `V_IN` (J5 P+) → U8 L7812 → `+12V` (gate-driver VCC) → U7 L7805 →
  `+5V` (logic). Hall amp runs on **+5V**, so 74HC14 outputs drive JY01 directly.
- **Current sense**: P− passes through R1 shunt (R005, 2512) to GND; JY01 `Is` sees the
  filtered shunt node (`ISENSE_F` via R36 + C21). *Caveat:* verify scaling against the
  driver's internal sense topology before relying on current limit.

## Design notes

- **78xx regulators**: with 12–36 V input keep `V_IN ≤ 28 V` for dropout/power margin
  (12 V nominal recommended).
- **PWM → VR**: GPIO1 drives the JY01 `VR` node through **R7 (100 Ω)**, directly. The
  JYQD datasheet accepts PWM 1–20 kHz on `VR` and averages it internally, so no level
  shifter is needed. Max drive is 3.3 V of the 0.1–5 V range ≈ 66 % speed.
- **GPIO4 → EL level shift**: EL is pulled up to **+5V** (R33 10 kΩ); GPIO4 drives it
  open-drain through R34 (1 kΩ). Configure GPIO4 as open-drain in firmware. Per the
  JYQD datasheet, EL high/floating **allows** operation and GND forbids it, so the
  motor is enabled by default at power-up.
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
| Schematic parity | 0 genuine (266 cosmetic: root-sheet `/` prefix, footprint lib prefix) |
| Outline closure | closed Edge.Cuts loop, 0 open endpoints, 64.1 × 98.1 mm |
| Pads outside outline | 0 |
| Orphan nets (1 pad) | none |
| Fab files | 11 gerbers (4 copper) + 1 drill (Excellon, metric, decimal) + job file |
| Solder mask | 238 front / 33 rear openings (205 SMD + 29 THT + 4 NPTH); 0.05 mm expansion, 0.10 mm min web |
| Paste | 205 front apertures (1:1 with the SMD pads), none on the rear |

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

**Folder layout:** `PCB/V1/` is this board. When a smaller revision is attempted it goes
in `PCB/V2/` alongside it, so both stay buildable and comparable.

**The previous board is preserved at git tag `v1`** (commit 837cf5a): 70 × 120 mm,
2 layers. This folder is the current 64 × 98 mm 4-layer board.

| | old (tag `v1`) | this board |
|---|---|---|
| Size | 70 × 120 mm (8400 mm²) | **64 × 98 mm (6272 mm², −25 %)** |
| Layers | 2 | **4** (In1 = solid GND plane) |
| Signal layers | 2 | 3 (F.Cu, In2.Cu, B.Cu) |
| Phase copper (avg) | 0.33–0.39 mm | **0.67–0.74 mm** |
| Traces / vias | 1277 / 142 | 849 / 121 |
| DRC | 0 / 0 | 0 / 0 |

- **Schematic**: complete & verified — netlist matches the design table **223/234 pins**
  (floating pins are the 3 unused 74HC14 gate outputs + 8 spare ESP32 GPIOs).
- **Board**: **fully routed, DRC-clean, fab package generated** — 64.1 mm × 98.1 mm
  (5 mm rounded corners), 85 footprints (67 components + 4 M3 holes + 14 test points).
  - 849 traces, 121 vias, 4 zones (solid GND plane on In1 + GND pours on
    F.Cu / B.Cu / In2.Cu)
  - **DRC: 0 violations, 0 unconnected items** (`kicad-cli pcb drc --severity-all`)
  - **Schematic parity: 0 genuine mismatches** — the 266 reported items are cosmetic only
    (schematic nets carry the root-sheet `/` prefix; footprints are reported without their
    library prefix). Verified programmatically: 0 net-name differences, 0 footprint
    differences after normalisation, 0 extra footprints.
  - **Outline**: closed Edge.Cuts loop, 0 open endpoints; **0 pads outside** the outline.
  - **Drills**: 0.3 mm ×110 and 0.4 mm ×15 (vias), 0.8/1.0/1.1/1.2/1.3 mm ×29
    (component holes), 3.2 mm ×4 (M3 mounting, NPTH).
  - Renders: `render/routed_top.png`, `render/routed_bottom.png`
  - **Bottom silkscreen**: OSP cloud logo (16 mm, vectorised from
    `OSP_1600.png` with potrace into 14 filled polygons) and the credit
    `designed by : github.com/1999azzar`, both on `B.SilkS`.

### Copper sizing (measured, not assumed)

The 4-layer stack gives the phases a dedicated corridor, so they are no longer starved by the 2-layer
clearance wall. Length-weighted averages:

| Net | 2-layer avg | **this board avg** | min | max |
|---|---|---|---|---|
| PH_A | 0.33 mm | **0.75 mm** | 0.25 mm | 0.80 mm |
| PH_B | 0.35 mm | **0.74 mm** | 0.25 mm | 0.80 mm |
| PH_C | 0.39 mm | **0.77 mm** | 0.25 mm | 0.80 mm |
| V_IN | 0.80 mm | **0.79 mm** | 0.65 mm | 0.80 mm |
| PNEG | 0.80 mm | **0.80 mm** | 0.80 mm | 0.80 mm |
| +12V / +5V | 0.57 mm | 0.40 mm | 0.40 mm | 0.40 mm |

> **Current capability.** The phases now run at 0.75 mm average with only short
> (sub-millimetre) necks at the driver's 0.65 mm-pitch pads. On **2 oz outer copper** that
> is roughly **4 A per phase**, up from ~2.6 A on the 2-layer board. The `+12V`/`+5V` rails are thinner
> than v1 (0.40 mm) because they are logic/gate-drive supplies: 0.40 mm on 2 oz carries
> ~1.5 A, and the actual load is a few hundred mA.

## Component placement (64 × 98 mm)

| Zone | Components |
|---|---|
| Top edge | J5 (power in), J6 (motor out), M3 holes in the corners |
| Bottom edge | J3 (Hall port) |
| Left column | C1/C2/C5 bulk → U8 (7812) → C3 → U7 (7805) → C4, i.e. the whole power chain |
| Under J6 | Q2/Q3/Q4 (JY2605M) with R1 shunt |
| Right of the FETs | U3 (JY213L), bootstrap C13–C15 + D1–D3, gate resistors R14–R19 |
| Middle | U1 (JY01) + R8–R13, then the Hall amp (U4 LM324, U5 74HC14, R21–R31) |
| Bottom | U6 (ESP32-C3), RV1, LEDs |

`U3` sits clear of the FET row on purpose: its 0.65 mm-pitch phase-sense pins need a
fanout corridor, and placing it in line with the FETs makes them unreachable.

## Routing pipeline (reproducible)

1. `gen_sch_full.py` — regenerate schematic (netlist-verified).
2. `compact_4l.py` — the placement + 64 × 98 mm rounded outline, with a courtyard
   clash report (`--check` reports without saving).
3. `route_prep_4l.py` — export the DSN and inject width classes. **In1.Cu is set to
   `power`**, so FreeRouting will not put signal traces on it and it stays a solid plane.
4. FreeRouting **2.1.0** on Java 21:
   `java -jar freerouting.jar -de board.dsn -do board.ses -mp 40 -mt 1`
   (single-threaded; the multi-threaded optimizer creates clearance violations).
5. `import_4l.py` — import the session, (re)create the GND plane + pours, refill.
6. `fix_open_nets_4l.py NET...` — rip a few nets and re-route them with everything else
   frozen, when the router leaves a handful open.
7. `silk_4l.py` — hide passive reference designators and clear silkscreen warnings.
8. `fab_package.sh [--2oz]` — gerbers + drill + positions + `fab/ORDER.md`.

**Five things that cost hours, documented so they don't again:**

- KiCad exports a GND pour as a full-board Specctra `(plane ...)` on **every** copper
  layer. If the pours are present during export, FreeRouting sees an occupied board and
  plateaus at ~90+ unrouted. Remove the zones before export, refill afterwards.
- `board.Remove(item)` silently does nothing in this pcbnew build. Use `board.Delete(item)`
  — the failure mode is invisible (the board keeps its old tracks) and costs a full
  routing run to notice.
- FreeRouting can finish routing and then hang before writing the `.ses`. The cause is
  stale `java` processes from earlier runs; `kill -9` every `java` before starting.
- A `0.65 mm`-pitch TSSOP cannot fan out three sense pins into a via between adjacent
  pads. It needs ~3 mm of clear corridor above the pin row; that is what drove the
  power-stage placement.
- On a 4-layer board the zones can end up as several filled islands. Stitch them to the
  In1 plane with GND vias, otherwise DRC reports the pour as unconnected.
- KiCad writes the inner copper layers with their internal layer IDs (`Copper,L5,Inr`,
  `L7`) into the `.gbrjob` even though the gerbers themselves carry the correct `L2`/`L3`.
  `fab_package.sh` rewrites the job file so CAM cannot read a 4-layer stack as 8-layer.
- A 3D render with no model library looks like a bare board with random pads, which reads
  as "the placement is broken". This machine has no `kicad-packages3d` installed; the
  models are fetched with `nix build nixpkgs#kicad.libraries.packages3d` and are shipped
  as **zip files named `.stpZ`**, not zstd. Unzip the ones the board references and point
  `KICAD9_3DMODEL_DIR` at the result:
  `KICAD9_3DMODEL_DIR=<dir> kicad-cli pcb render ...`
  This project's models are installed at `~/.local/share/kicad/3dmodels` and the path is
  registered in `~/.config/kicad/9.0/kicad_common.json`, so a plain render works.
- **U6 (ESP32-C3 SuperMini) has no official 3D model.** It is a third-party board, so it
  is not in the Espressif library (which covers ESP32-C3-MINI-1/WROOM-02 only), and the
  GrabCAD/Printables/SnapEDA models need an account. A dimensionally correct
  representative body (22.5 x 18 x 1.6 mm + USB-C + antenna area) is used instead,
  from `Custom.3dshapes/ESP32-C3-SuperMini.wrl`. It is for visualisation, not mechanical
  clearance work.
- The mask gerbers are emitted as **G36/G37 region fills**, not aperture flashes. Counting
  `%ADD`/`D03` in them reports zero and looks catastrophic; count `G36` instead.

## Ordering

```bash
./tools/fab_package.sh --2oz     # 2 oz outer copper; drop the flag for 1 oz
```

Output in `fab/`:

| File | Contents |
|---|---|
| `bldc_esp32_driver_gerbers.zip` | 11 gerbers (4 copper, 2 mask, 2 silk, 2 paste, Edge.Cuts) + `.drl` |
| `positions.csv` | assembly centroids, mm, drill origin |
| `ORDER.md` | board spec sheet to hand to the fab |

Verification already passed on this exact board: 0 DRC violations, 0 unconnected items,
closed outline, 0 pads outside the outline, 0 genuine schematic-parity mismatches.

### Assembly (PCBA)

The board is set up to be ordered **assembled**, with these deliberately left
unpopulated (marked DNP in both the schematic and the board, so the BOM and CPL
exclude them automatically):

| Ref | Part | Why |
|---|---|---|
| U6 | ESP32-C3 SuperMini | third-party module, fitted by hand |
| J3 | 1x05 2.54 mm header | no headers wanted — wires go straight to the pads |
| J5 | MX126 2-pin terminal | power wires soldered directly |
| J6 | MX126 3-pin terminal | motor wires soldered directly |

**Five parts cannot be bought from LCSC**, so no assembly house that sources
from that catalogue can fit them: **U1 (JY01)**, **U3 (JY213L)** and
**Q2–Q4 (JY2605M)**. They are only sold through Alibaba/AliExpress/specialist
vendors. Either hand-solder them or supply them as consigned parts.

**Test points.** Fourteen 1.5 mm probe pads are on the top side for bring-up
(`V_IN`, `PNEG`, `+12V`, `+5V`, `+3.3V`, `VR`, `ZF`, `PWM_OUT`, `RPM_IN`,
`ISENSE_F`, `GPIO5`, `HALL_OUT_B`, `HALL_OUT_C`, `GND`). `EL` and `HALL_OUT_A`
have no pad — the area around them is fully occupied, so probe them on R33 pin 1
and U5 pin 2 (both 0805 / 1.27 mm pitch, easy to touch). The pads are board-only
and excluded from the BOM/CPL, so they cost nothing. Positions, expected voltages
and a staged bring-up procedure are in [`TESTPLAN.md`](TESTPLAN.md).

The through-hole parts (C1–C5, U7, U8, RV1) are in the CPL, but JLCPCB's
economical PCBA is SMD-only — use their through-hole option or solder those by
hand as well.

`fab/bom_jlcpcb.csv` (27 lines) and `fab/cpl_jlcpcb.csv` (65 placements) are in
JLCPCB's upload format.

**LCSC part numbers: 23 of 26 lines are filled**, each verified against live
LCSC/JLCPCB stock (see `tools/lcsc_map.csv` for the mapping and manufacturer
part). Only these remain blank, and only because LCSC does not carry them:

| Line | Why |
|---|---|
| U1 (JY01), U3 (JY213L), Q2–Q4 (JY2605M) | not in the LCSC catalogue at all |

Values that changed so the parts are actually orderable:

- `C1/C2` are **470 µF/63 V** — 480 µF is not a real capacitor value.
- `C3–C5` are 220 µF/50 V, D10 × 12.5 mm, **5 mm pitch** (matches the D10/P5 land).
- `R1` is a 5 mΩ ±1 % **3 W** 2512 shunt.
- **U2 and R6 are gone.** The old VR interface was an open-drain N-MOSFET with a
  5 V pull-up, which **inverted** the speed control — idle became full speed and the
  PID ran as positive feedback. It was also built around `CSD13380F3`, a 0.73 × 0.64 mm
  TI FemtoFET that cannot sit on the SOT-23-3 land. Both parts were removed and R7 now
  feeds `VR` directly.

> **ERC note**: the schematic reports 28 ERC items, all accounted for — 11 unconnected
> pins are the intentionally-unused 74HC14 gates and spare ESP32 GPIOs; 3 are library
> version/resolution warnings; the rest are power-flag bookkeeping (`V_IN` and the JY01
> `Vss` are fed from external connectors, which ERC wants a `PWR_FLAG` for). None affect
> the manufactured board.

## Files

```
bldc_esp32_driver/
├── bldc_esp32_driver.kicad_sch    # schematic
├── bldc_esp32_driver.kicad_pcb    # board (64 x 98 mm, 4 layers, DRC-clean)
├── bldc_esp32_driver.kicad_pro
├── README.md                      # this file
├── TESTPLAN.md                    # staged bring-up procedure
├── footprints/ESP32-C3-SuperMini.kicad_mod
├── footprints/JY2605M_DFN8_5x6.kicad_mod   # DFN-8 5x6 half-bridge (no exact lib match)
├── render/routed_{top,bottom,top_zoom}.png # refreshed by fab_package.sh
├── fab/                           # gerbers, drill, ORDER.md, BOM + CPL (JLCPCB)
├── tools/gen_sch_full.py, gen_pcb.py, verify_net.py
├── tools/compact_4l.py, route_prep_4l.py, import_4l.py, fix_open_nets_4l.py
├── tools/add_testpoints.py, make_jlcpcb_assembly.py, lcsc_map.csv
├── tools/silk_4l.py, set_values.py, fix_pot_pin_and_holes.py
├── tools/final_{incremental,import_ses,widen,settle,minwidth,silk_cleanup}.py
├── tools/fab_package.sh           # gerbers + BOM/CPL + renders in one shot
├── fp-lib-table
└── fp-info-cache
```
