# BLDC Motor Driver — JYQD-V7.3E3 Architecture + ESP32-C3 Super Mini + Hall Amp

Custom 70 × 120 mm PCB (full-integration rebuild) based on the **JYQD-V7.3E3**
brushless driver architecture, with an **ESP32-C3 Super Mini** controller and a Hall
sensor signal conditioner (RC filter → LM324 gain ×11 → 74HC14 Schmitt trigger).

> `JYQD-V7.3E3-English.pdf` is a product datasheet (specs + wiring), not a schematic.
> The circuit is implemented with the JY IC family — **JY01** (SOP-16 controller),
> **JY213L** (TSSOP-20 3-phase gate driver), **JY2605M** (DFN-8 dual-NMOS half-bridge)
> — the same silicon used in the reference board.

## Architecture

```
 V_IN ── 7812 ── +12V ── 7805 ── +5V
   │                │          │
 JY01 ──gate R── JY213L ──gate R── JY2605M ×3 ── phases A/B/C
   │                │
 Hall amp (5V): RC → LM324(×11) → 74HC14 → JY01 Hall inputs
 ESP32-C3: FG (scaled) / PWM / VR (via open-drain FET) / EL / trim pot
```

- **Power tree**: `V_IN` (J5 P+) → U8 L7812 → `+12V` (gate-driver VCC) → U7 L7805 →
  `+5V` (logic). Hall amp runs on **+5V**, so 74HC14 outputs drive JY01 directly.
- **Current sense**: P− passes through R1 shunt (R005, 2512) to GND; JY01 `Is` sees the
  filtered shunt node (`ISENSE_F` via R36 + C21). *Caveat:* JY01's `Is` input expects the
  driver's internal sense topology — verify scaling before enabling current limit.

## Port pinouts

| Port | Pins | Pitch |
|---|---|---|
| J5 power (right edge) | `P+  P−  MC  MB  MA` | 5.00 mm (MaiXu MX126) |
| J3 Hall (left edge) | `GND  Hc  Hb  Ha  5V` | 2.54 mm |
| J4 control (left edge) | `GND  VR  Z/F  Signal  EL  5V` | 2.54 mm |
| J1 breakout | GPIO5,6,7,8,9,10,20,21 + GND | 2.54 mm |
| J2 breakout | GPIO0,1,2,3,4 + 3V3,GND,5V (+nc) | 2.54 mm |

## Design notes

- **78xx regulators**: with 12 V–36 V input and 7805, keep `V_IN ≤ 28 V` for a safe
  dropout/power margin (12 V nominal recommended).
- **GPIO4 → EL level shift**: EL is pulled up to **+5V** (R33 10 kΩ); GPIO4 drives it
  open-drain through R34 (1 kΩ). Configure GPIO4 as open-drain in firmware.
- **FG scaling**: JY01 FG (5 V) → R4 2.2 k / R5 3.3 k divider → GPIO9 (RPM in, 3.3 V).
- **ERR LED** driven from GPIO5 via R32 (560 Ω); **PWR LED** from +5V via R20 (560 Ω).

## Status

- **Schematic**: complete & verified. `kicad-cli sch export netlist` matches the design
  table **254/258 pins** (the 4 floating pins are intentional: U5.8/10/12 unused 74HC14
  gate outputs, J2.9 nc). ERC clean of errors — only benign embedded-symbol / power-flag
  notices.
- **Board**: **placement only, no routing** — for review.
  - Form factor 70 mm × 120 mm
  - 0 courtyard/bbox overlaps, 0 board-edge clearance violations
  - pad-net assignment verified 0 mismatches vs schematic netlist
  - Tracks 0, Vias 0, Zones 0

## Component placement (left → right signal flow)

| Zone | Components |
|---|---|
| Left edge | J3 (Hall), J4 (control) ports |
| Left-mid | Hall amp: R21–R31, C16–C20, U4 (LM324), U5 (74HC14) |
| Center | U1 (JY01) → R8–R13 → U3 (JY213L) → R14–R19 → Q2/Q3/Q4 (JY2605M) |
| Center-right | bootstrap D1–D3 + C13–C15 |
| Right | J5 power terminal, C1/C2/C5 bulk, R1 shunt, U8/U7 regulators, C3/C4/C11/C12 |
| Bottom | U6 (ESP32-C3), U2 (CSD13380F3), RV1 trim, LEDs, J1/J2 breakouts |

## Files

```
bldc_esp32_driver/
├── bldc_esp32_driver.kicad_sch    # schematic (rebuilt from scratch)
├── bldc_esp32_driver.kicad_pcb    # board (placement only, unrouted)
├── bldc_esp32_driver.kicad_pro
├── bldc_esp32_driver.kicad_prl
├── bldc_esp32_driver-erc.rpt
├── README.md
├── footprints/ESP32-C3-SuperMini.kicad_mod
├── footprints/JY2605M_DFN8_5x6.kicad_mod   # DFN-8 5×6 half-bridge (no exact lib match)
├── fp-lib-table
└── fp-info-cache
```

## Next steps

1. Review placement in KiCad (`bldc_esp32_driver.kicad_pcb`).
2. Approve placement → route (FreeRouting + GND pour) → DRC → export fab package.

No routing done yet. No order placed.
