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
- **ESP32 pin usage**: GPIO0=RPM (FG), GPIO1=PWM→VR, GPIO2=trim ADC, GPIO3=spare,
  GPIO4=EL (open-drain), GPIO5=ERR LED. GPIO6–10/20/21 are spare/unconnected.
- **ERR LED** driven from GPIO5 via R32 (560 Ω); **PWR LED** from +5V via R20 (560 Ω).

## Status

- **Schematic**: complete & verified — netlist matches the design table **223/234 pins**
  (floating pins are the 3 unused 74HC14 gate outputs + 8 spare ESP32 GPIOs).
- **Board**: **fully routed on the user-approved placement** — 70 mm × 120 mm
  (5 mm rounded corners), 69 footprints.
  - 1277 traces, 142 vias, 2 zones (GND pour on F.Cu + B.Cu, solid-connected)
  - Fully routed — **0 unconnected ratsnest items**, 0 copper DRC violations
  - DRC: 0 errors — only 5 cosmetic silkscreen warnings remain
  - Placement audit: every pad corner ≥ 0.5 mm inside the rounded outline
    (programmatic check); 0 footprint overlaps
  - Renders: `render/routed_top.png`, `render/routed_bottom.png`, `render/routed_top_zoom.png`
  - 0 Ω jumper allowance was reserved for orphan nets but turned out unnecessary

> **Trace-width caveat**: this 2-layer board is routed at uniform **0.25 mm** signal
> width — 0.8 mm power traces don't fit the TSSOP/DFN pin pitch without unrouteable
> congestion. The solid double-sided GND pour carries most of the return current. For
> motor current > ~1 A, either widen the phase / `V_IN` / `PNEG` traces by hand in the
> areas that have room, or specify **2 oz copper**. The reference JYQD board achieves
> 15 A with heavy copper + pours, not thin traces.

## Component placement (left → right signal flow)

| Zone | Components |
|---|---|
| Left edge | J3 (Hall port) |
| Left-mid | Hall amp: R21–R31, C16–C20, U4 (LM324), U5 (74HC14) |
| Center | U1 (JY01) → R8–R13 → U3 (JY213L) → R14–R19 → Q2/Q3/Q4 (JY2605M) |
| Center-right | bootstrap D1–D3 + C13–C15 |
| Right | J5 (power), J6 (motor), C1/C2/C5 bulk, R1 shunt, U8/U7 regulators, C3/C4/C11/C12 |
| Bottom | U6 (ESP32-C3), U2 (CSD13380F3), RV1 trim, LEDs, level-shift |

## Files

```
bldc_esp32_driver/
├── bldc_esp32_driver.kicad_sch    # schematic (rebuilt from scratch)
├── bldc_esp32_driver.kicad_pcb    # board (routed, user-approved placement)
├── bldc_esp32_driver.kicad_pro
├── bldc_esp32_driver.kicad_prl
├── bldc_esp32_driver-erc.rpt
├── README.md
├── footprints/ESP32-C3-SuperMini.kicad_mod
├── footprints/JY2605M_DFN8_5x6.kicad_mod   # DFN-8 5×6 half-bridge (no exact lib match)
├── render/routed_{top,bottom,top_zoom}.png # 3D renders of the routed board
├── tools/{gen_sch_full,gen_pcb,verify_net,setup_netclasses,add_gnd_pour2,export_dsn,fix_dsn_classes,widen_power}.py
├── fp-lib-table
└── fp-info-cache
```

## Routing pipeline (reproducible)

1. `gen_sch_full.py` — regenerate schematic (netlist-verified).
2. `gen_pcb.py` — regenerate placement-only board (**only when re-planning from scratch**;
   never run it over a user-arranged placement).
3. `setup_netclasses.py` — assign net classes + export `board.dsn`.
4. `fix_dsn_classes.py` — inject width rules into the DSN (KiCad's Specctra export drops them).
5. FreeRouting **2.5.0** (Java ≥ 25): `java -jar freerouting-2.5.0.jar -de board.dsn -do board.ses -us Hybrid -mt 1`
   with optimizer `max_passes: 0` in `~/.config/freerouting/freerouting.json`.
   (v1.9 wedges in its optimizer on this board density; `-mt 4` creates clearance
   violations on v1.9 — keep single-threaded either way.)
6. Import `board.ses` (Specctra), then `add_gnd_pour2.py` — GND pour + refill.
7. `kicad-cli pcb drc`.

The committed board reflects the **user's hand-arranged placement** (69 components moved
in KiCad); the gen_pcb generator layout is only a fallback.

## Next steps

1. Review routing/placement in KiCad (`bldc_esp32_driver.kicad_pcb`).
2. Optionally tidy the 18 silkscreen warnings (reference-text over pads / near edge).
3. Export fab package (Gerbers + drill + position) when approved.

No order placed.
