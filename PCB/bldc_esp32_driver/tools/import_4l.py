#!/usr/bin/env python3
"""Import the 4-layer route, add the GND plane on In1 and GND pours on the
signal layers, refill, and report per-net widths.

Usage: import_4l.py [session.ses]
"""
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "bldc_esp32_driver.kicad_pcb"
SES = sys.argv[1] if len(sys.argv) > 1 else "/tmp/opencode/c4.ses"
MM = 1_000_000
X0, Y0, W, H, R = 100.0, 40.0, 60.0, 95.0, 5.0
INSET = 0.25


def outline_points(inset):
    x0, y0, w, h, r = X0 + inset, Y0 + inset, W - 2 * inset, H - 2 * inset, R - inset
    pts = []
    for cx, cy, a0 in ((x0 + r, y0 + r, 180), (x0 + w - r, y0 + r, 270),
                       (x0 + w - r, y0 + h - r, 0), (x0 + r, y0 + h - r, 90)):
        for i in range(9):
            a = math.radians(a0 + i * 90 / 8)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


b = pcbnew.LoadBoard(BOARD)
if not pcbnew.ImportSpecctraSES(b, SES):
    sys.exit("SES import failed")
print(f"imported: {len(b.GetTracks())} tracks/vias")

gnd = next(n for n in b.GetNetsByName().values() if n.GetNetname() == "GND")
pts = outline_points(INSET)

# keep one GND zone per copper layer, drop duplicates, add any that are missing
keep, seen = [], set()
for z in b.Zones():
    if z.GetNetname() == "GND" and z.GetLayer() not in seen:
        seen.add(z.GetLayer())
        keep.append(z)
for z in list(b.Zones()):
    if z not in keep:
        b.Delete(z)
b.BuildConnectivity()

for layer in (pcbnew.In1_Cu, pcbnew.F_Cu, pcbnew.B_Cu, pcbnew.In2_Cu):
    if layer in seen:
        continue
    z = pcbnew.ZONE(b)
    z.SetLayer(layer)
    z.SetNetCode(gnd.GetNetCode())
    z.SetLocalClearance(int(0.3 * MM))
    z.SetMinThickness(int(0.25 * MM))
    z.SetThermalReliefGap(int(0.3 * MM))
    z.SetThermalReliefSpokeWidth(int(0.4 * MM))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_FULL)
    poly = z.Outline()
    poly.NewOutline()
    for x, y in pts:
        poly.Append(int(x * MM), int(y * MM))
    b.Add(z)
print(f"zones: {len(list(b.Zones()))}")

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(BOARD)

# ---- width report ------------------------------------------------------------
widths, lengths = {}, {}
for t in b.GetTracks():
    if t.Type() != pcbnew.PCB_TRACE_T:
        continue
    n = t.GetNetname()
    widths.setdefault(n, {}).setdefault(round(t.GetWidth() / MM, 2), 0)
    widths[n][round(t.GetWidth() / MM, 2)] += 1
    lengths[n] = lengths.get(n, 0) + t.GetLength() / MM

print("\npower nets:")
for n in ("PH_A", "PH_B", "PH_C", "V_IN", "PNEG", "+12V", "+5V"):
    if n in widths:
        print(f"  {n:<6} {lengths[n]:6.1f} mm  {dict(sorted(widths[n].items()))}")
    else:
        print(f"  {n:<6} no tracks (pour only)")
tr = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_TRACE_T]
vi = [t for t in b.GetTracks() if t.Type() == pcbnew.PCB_VIA_T]
print(f"\ntotals: {len(tr)} traces, {sum(t.GetLength() for t in tr)/MM:.0f} mm, {len(vi)} vias")
