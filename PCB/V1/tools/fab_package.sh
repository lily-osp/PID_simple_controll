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
EOF

echo "package ready in $OUT/"
ls -la "$OUT" "$OUT/gerbers"
