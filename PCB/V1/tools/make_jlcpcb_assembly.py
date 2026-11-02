#!/usr/bin/env python3
"""Convert KiCad's BOM/position exports into JLCPCB's PCBA upload format.

JLCPCB BOM : Comment, Designator, Footprint, LCSC Part #
JLCPCB CPL : Designator, Mid X, Mid Y, Layer, Rotation
             (mm, origin at the board's bottom-left corner, Y increasing upward)

Usage: make_jlcpcb_assembly.py <fab_dir> <board.kicad_pcb>
"""
import csv
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

FAB = sys.argv[1] if len(sys.argv) > 1 else "fab"
BOARD = sys.argv[2] if len(sys.argv) > 2 else "bldc_esp32_driver.kicad_pcb"

bb = pcbnew.LoadBoard(BOARD).GetBoardEdgesBoundingBox()
X0, Y1 = bb.GetX() / 1e6, bb.GetBottom() / 1e6

# LCSC numbers verified against lcsc.com, keyed by (Value, Footprint)
lcsc = {}
try:
    for row in csv.DictReader(open("tools/lcsc_map.csv")):
        lcsc[(row["Value"], row["Footprint"])] = row["LCSC"]
except FileNotFoundError:
    pass

bom = list(csv.DictReader(open(f"{FAB}/bom_raw.csv")))
missing = []
with open(f"{FAB}/bom_jlcpcb.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Comment", "Designator", "Footprint", "LCSC Part #"])
    for r in bom:
        part = r["LCSC"] or lcsc.get((r["Value"], r["Footprint"]), "")
        if not part:
            missing.append(r["Value"])
        w.writerow([r["Value"], r["Refs"], r["Footprint"], part])
print(f"  LCSC numbers filled : {len(bom) - len(missing)} of {len(bom)}")
if missing:
    print(f"  still to assign     : {', '.join(missing)}")

cpl = list(csv.DictReader(open(f"{FAB}/cpl_raw.csv")))
with open(f"{FAB}/cpl_jlcpcb.csv", "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
    for r in cpl:
        w.writerow([
            r["Ref"],
            f"{float(r['PosX']) - X0:.4f}",
            f"{float(r['PosY']) + Y1:.4f}",
            "Top" if r["Side"] == "top" else "Bottom",
            f"{float(r['Rot']):.1f}",
        ])

print(f"  bom_jlcpcb.csv : {len(bom)} lines")
print(f"  cpl_jlcpcb.csv : {len(cpl)} placements")
