# Fabrication order — bldc_esp32_driver

| Parameter | Value |
|---|---|
| Size | 64 x 98 mm |
| Layers | **4** (F.Cu / In1.Cu / In2.Cu / B.Cu) |
| Thickness | 1.6 mm |
| Copper | **2oz outer / 1oz inner** |
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

| Ref | Part | Note |
|---|---|---|
| U1 | JY01 (SOP-16) | JYQD family IC, not in the LCSC catalogue |
| U3 | JY213L (TSSOP-20) | ditto |
| Q2-Q4 | JY2605M (DFN-8) | ditto |

Those five parts must be hand-soldered, or supplied to JLCPCB as consigned
parts. Everything else is standard and can be assembled.

**Through-hole parts** (C1-C5, U7, U8, RV1) appear in the CPL, but JLCPCB's
economical PCBA covers SMD only - either use their through-hole option or
solder these by hand.

Assembly files:

| File | Contents |
|---|---|
| `bom_jlcpcb.csv` | 27 lines, columns Comment / Designator / Footprint / LCSC Part # |
| `cpl_jlcpcb.csv` | 65 placements, origin at the board's bottom-left corner, Y up |

The **LCSC Part # column is empty** - the schematic carries no LCSC numbers, so
they must be assigned before the BOM can be uploaded.
