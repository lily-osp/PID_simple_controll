#!/usr/bin/env bash
# Fab package for JLCPCB: gerbers + drill + position + zipped bundle.
# Usage: ./tools/fab_package.sh [--2oz]
set -euo pipefail

cd "$(dirname "$0")/.."
PCB=bldc_esp32_driver.kicad_pcb
OUT=fab
COPPER_NOTE="1oz"
[ "${1:-}" = "--2oz" ] && COPPER_NOTE="2oz"

rm -rf "$OUT"
mkdir -p "$OUT/gerbers"

kicad-cli pcb export gerbers \
  --output "$OUT/gerbers/" \
  --layers "F.Cu,B.Cu,F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,F.Paste,B.Paste,Edge.Cuts" \
  "$PCB" >/dev/null

kicad-cli pcb export drill \
  --output "$OUT/gerbers/" \
  --format excellon --excellon-units mm --excellon-zeros-format decimal \
  --excellon-oval-format alternate \
  "$PCB" >/dev/null

kicad-cli pcb export pos \
  --output "$OUT/positions.csv" --format csv --units mm --side both \
  --use-drill-file-origin "$PCB" >/dev/null

( cd "$OUT/gerbers" && zip -q -r "../bldc_esp32_driver_gerbers.zip" . )

cat > "$OUT/ORDER.md" <<EOF
# Fabrication order — bldc_esp32_driver

| Parameter | Value |
|---|---|
| Size | 70 x 120 mm |
| Layers | 2 (F.Cu / B.Cu) |
| Thickness | 1.6 mm |
| Copper | **$COPPER_NOTE** |
| Surface finish | HASL lead-free |
| Soldermask | green (any) |
| Silkscreen | white |
| Min track / clearance | 0.2 mm / 0.2 mm |
| Min drill | 0.3 mm |
| Edge clearance | 0.5 mm |

Gerbers: \`bldc_esp32_driver_gerbers.zip\` (drill files included).
Assembly positions: \`positions.csv\` (mm, drill origin).
EOF

echo "package ready in $OUT/"
ls -la "$OUT" "$OUT/gerbers"
