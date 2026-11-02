#!/usr/bin/env python3
"""Import the autorouter session back into the board, restore the GND pours,
refill them, and report connectivity + width stats.
"""
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "bldc_esp32_driver.kicad_pcb"
SES = sys.argv[1] if len(sys.argv) > 1 else "/tmp/opencode/inc.ses"
MM = 1_000_000

b = pcbnew.LoadBoard(BOARD)

if not pcbnew.ImportSpecctraSES(b, SES):
    sys.exit("SES import failed")

print(f"imported: {len(b.GetTracks())} tracks/vias")

# ---- restore GND pours only if they were removed earlier ----
if len(list(b.Zones())) == 0:
    gnd = next(n for n in b.GetNetsByName().values() if n.GetNetname() == "GND")
    outline = [(91.205, 44.705), (160.795, 44.705), (160.795, 164.295), (91.205, 164.295)]
    for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
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
        for x, y in outline:
            poly.Append(int(x * MM), int(y * MM))
        b.Add(z)
print(f"pours: {len(list(b.Zones()))}")

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(BOARD)

# ---- report ----
widths = {}
segs = {}
for t in b.GetTracks():
    if t.Type() != pcbnew.PCB_TRACE_T:
        continue
    n = t.GetNetname()
    w = round(t.GetWidth() / MM, 3)
    widths.setdefault(n, {}).setdefault(w, 0)
    widths[n][w] += 1
    segs[n] = segs.get(n, 0) + t.GetLength() / MM

for n in ("PH_A", "PH_B", "PH_C", "V_IN", "PNEG", "+12V", "+5V", "GND"):
    if n in widths:
        print(f"{n:<7} widths={dict(sorted(widths[n].items()))} total={segs[n]:.1f}mm")
    else:
        print(f"{n:<7} no tracks (pour-only)")
