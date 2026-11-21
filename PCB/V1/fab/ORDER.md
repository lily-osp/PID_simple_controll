# Fabrication order — bldc_esp32_driver

| Parameter | Value |
|---|---|
| Size | 64 x 98 mm |
| Layers | **4** (F.Cu / In1.Cu / In2.Cu / B.Cu) |
| Thickness | 1.6 mm |
| Copper | **1oz outer / 1oz inner** |
| Surface finish | HASL lead-free |
| Soldermask | green (any) |
| Silkscreen | white |
| Min track / clearance | 0.2 mm / 0.2 mm |
| Min drill | 0.3 mm |
| Mounting holes | 4 x 3.2 mm NPTH (M3), non-plated |
| Edge clearance | 0.5 mm |

Gerbers: `bldc_esp32_driver_gerbers.zip` (drill files included).
Assembly positions: `positions.csv` (mm, drill origin).

## Assembly (PCBA)

**Left unpopulated on purpose:**

| Ref | Part | Why |
|---|---|---|
| U6 | ESP32-C3 SuperMini | third-party module, fitted by the user |
| J3 | 1x05 2.54 mm header | no header wanted - wires soldered to the pads |
| J5 | MX126 2-pin terminal | no header wanted - power wires soldered directly |
| J6 | MX126 3-pin terminal | no header wanted - motor wires soldered directly |

**Not available from LCSC - JLCPCB cannot assemble these:**

| Ref | Part | Where it comes from |
|---|---|---|
| U1 | JY01 (SOP-16) | Shanghai Juyi (juyitech.com) / Taobao shop 301588897, ~CNY 5.4 |
| Q2-Q4 | JY2605M (DFN5x6 dual N-MOS, 60 V 50 A 14 mOhm) | same vendor, ~CNY 2.5 each |

Both are hand-soldered or supplied to JLCPCB as consigned parts; everything
else in the BOM, **including U3 (FD6288T, C97683)**, is in the LCSC catalogue
and can be assembled.

**Through-hole parts** (C1-C5, U7, U8, RV1) appear in the CPL, but JLCPCB's
economical PCBA covers SMD only - either use their through-hole option or
solder these by hand.

Assembly files:

| File | Contents |
|---|---|
| `bom_jlcpcb.csv` | 26 part lines, columns Comment / Designator / Footprint / LCSC Part # |
| `cpl_jlcpcb.csv` | 63 placements, origin at the board's bottom-left corner, Y up |

LCSC numbers come from `tools/lcsc_map.csv`; 2 of the 26 lines are
blank (Q2-Q4, U1), because LCSC does not carry those parts.
