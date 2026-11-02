#!/usr/bin/env python3
"""Clear the remaining cosmetic silkscreen DRC warnings:
 - pull the DFN-8 pin-1 marker off pad 4's mask aperture (Q2/Q3/Q4)
 - lift any reference text that overlaps its own silkscreen
"""
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "bldc_esp32_driver.kicad_pcb"
MM = 1_000_000

b = pcbnew.LoadBoard(BOARD)

# ---- 1. DFN-8 pin-1 marker: move it clear of the pad mask apertures ----
# footprint child shapes are stored in BOARD coordinates, so the local target
# must be rotated by the footprint orientation and offset by its position
PIN1_START = (-2.6, -3.0)
PIN1_END = (-2.6, -2.6)


def to_board(fp, local):
    import math
    ang = math.radians(fp.GetOrientationDegrees())
    cos_a, sin_a = math.cos(ang), math.sin(ang)
    ox, oy = local
    pos = fp.GetPosition()
    # KiCad rotates footprint children clockwise for a positive orientation
    dx = ox * cos_a + oy * sin_a
    dy = -ox * sin_a + oy * cos_a
    return pcbnew.VECTOR2I(int(round(pos.x + dx * MM)), int(round(pos.y + dy * MM)))


moved = 0
for fp in b.GetFootprints():
    if str(fp.GetFPID().GetLibItemName()) != "JY2605M_DFN8_5x6":
        continue
    for item in fp.GraphicalItems():
        if item.GetLayer() != pcbnew.F_SilkS or item.Type() != pcbnew.PCB_SHAPE_T:
            continue
        if abs(item.GetStart().x - item.GetEnd().x) < 1000:  # vertical marker
            item.SetStart(to_board(fp, PIN1_START))
            item.SetEnd(to_board(fp, PIN1_END))
            moved += 1
print(f"pin-1 markers repositioned: {moved}")

# ---- 2. reference text vs own silk ----
lifted = 0
for fp in b.GetFootprints():
    field = fp.Reference()
    if field.GetLayer() not in (pcbnew.F_SilkS,):
        continue
    fr = field.GetBoundingBox()
    body = fp.GetBoundingBox(False, False)
    clash = False
    for item in fp.GraphicalItems():
        if item.GetLayer() == pcbnew.F_SilkS and fr.Intersects(item.GetBoundingBox()):
            clash = True
            break
    if not clash:
        continue
    pos = field.GetPosition()
    field.SetPosition(pcbnew.VECTOR2I(pos.x, int(body.GetY() - 1.1 * MM)))
    lifted += 1
print(f"reference texts lifted clear of silk: {lifted}")

b.Save(BOARD)
print("saved")
