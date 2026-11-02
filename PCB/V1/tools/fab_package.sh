#!/usr/bin/env bash
# Fab package for JLCPCB: gerbers + drill + position + zipped bundle.
# Usage: ./tools/fab_package.sh [--2oz]
set -euo pipefail

cd "$(dirname "$0")/.."
PCB=bldc_esp32_driver.kicad_pcb
OUT=fab
SIZE=$(python3 -c "
import sys; sys.path.insert(0,'/usr/lib/python3/dist-packages')
import pcbnew
b=pcbnew.LoadBoard('bldc_esp32_driver.kicad_pcb')
bb=b.GetBoardEdgesBoundingBox()
print(f'{bb.GetWidth()/1e6:.0f} x {bb.GetHeight()/1e6:.0f} mm')" 2>/dev/null)
COPPER_NOTE="1oz"
[ "${1:-}" = "--2oz" ] && COPPER_NOTE="2oz"

rm -rf "$OUT"
mkdir -p "$OUT/gerbers"

kicad-cli pcb export gerbers \
  --output "$OUT/gerbers/" \
  --layers "F.Cu,In1.Cu,In2.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,F.Paste,B.Paste,Edge.Cuts" \
  "$PCB" >/dev/null

kicad-cli pcb export drill \
  --output "$OUT/gerbers/" \
  --format excellon --excellon-units mm --excellon-zeros-format decimal \
  --excellon-oval-format alternate \
  "$PCB" >/dev/null

kicad-cli pcb export pos \
  --output "$OUT/positions.csv" --format csv --units mm --side both \
  --use-drill-file-origin "$PCB" >/dev/null

# --- PCBA files in JLCPCB's upload format -----------------------------------
kicad-cli sch export bom --output "$OUT/bom_raw.csv" \
  --fields "Reference,Value,Footprint,LCSC Part" \
  --labels "Refs,Value,Footprint,LCSC" \
  --group-by "Value,Footprint,LCSC" --exclude-dnp \
  bldc_esp32_driver.kicad_sch >/dev/null

kicad-cli pcb export pos --output "$OUT/cpl_raw.csv" --format csv --units mm \
  --side front --use-drill-file-origin "$PCB" >/dev/null

python3 tools/make_jlcpcb_assembly.py "$OUT" "$PCB"

# KiCad writes the inner copper layers with their internal layer IDs (L5/L7)
# in the job file while the gerbers themselves carry the correct L2/L3. Make the
# job file agree with the gerbers so CAM cannot read a 4-layer stack as 8-layer.
sed -i 's/Copper,L5,Inr/Copper,L2,Inr/; s/Copper,L7,Inr/Copper,L3,Inr/' \
  "$OUT/gerbers/bldc_esp32_driver-job.gbrjob"

( cd "$OUT/gerbers" && zip -q -r "../bldc_esp32_driver_gerbers.zip" . )

cat > "$OUT/ORDER.md" <<EOF
# Fabrication order — bldc_esp32_driver

| Parameter | Value |
|---|---|
| Size | $SIZE |
| Layers | **4** (F.Cu / In1.Cu / In2.Cu / B.Cu) |
| Thickness | 1.6 mm |
| Copper | **$COPPER_NOTE outer / 1oz inner** |
| Surface finish | HASL lead-free |
| Soldermask | green (any) |
| Silkscreen | white |
| Min track / clearance | 0.2 mm / 0.2 mm |
| Min drill | 0.3 mm |
| Mounting holes | 4 x 3.2 mm NPTH (M3), non-plated |
| Edge clearance | 0.5 mm |

Gerbers: \`bldc_esp32_driver_gerbers.zip\` (drill files included).
Assembly positions: \`positions.csv\` (mm, drill origin).

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
| \`bom_jlcpcb.csv\` | 27 lines, columns Comment / Designator / Footprint / LCSC Part # |
| \`cpl_jlcpcb.csv\` | 65 placements, origin at the board's bottom-left corner, Y up |

The **LCSC Part # column is empty** - the schematic carries no LCSC numbers, so
they must be assigned before the BOM can be uploaded.
EOF

# --- refresh the 3D renders so they can never go stale -----------------------
mkdir -p render
kicad-cli pcb render --side top    --quality high --width 2400 --height 1800 \
  -o render/routed_top.png "$PCB" >/dev/null 2>&1 && echo "  render/routed_top.png"
kicad-cli pcb render --side bottom --quality high --width 2400 --height 1800 \
  -o render/routed_bottom.png "$PCB" >/dev/null 2>&1 && echo "  render/routed_bottom.png"
kicad-cli pcb render --side top --quality high --width 2400 --height 1800 \
  --zoom 2.4 --pivot "0,-1,0" -o render/routed_top_zoom.png "$PCB" >/dev/null 2>&1 \
  && echo "  render/routed_top_zoom.png"

echo "package ready in $OUT/"
ls -la "$OUT" "$OUT/gerbers"
