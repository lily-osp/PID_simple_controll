#!/usr/bin/env python3
"""Put a small number next to every test point, on the front silkscreen.

The probe pads themselves are bare copper with no legend, which is fine for one
or two of them but unusable at twenty. This writes the TP number (without the
"TP" prefix, to keep it narrow) beside each pad.

Idempotent: labels created by a previous run are removed first. A position is
only accepted when the text box clears exposed copper (pads, so the mask
aperture), every existing silkscreen item, every other label, and the board
edge. If nothing fits, the pad is left unlabelled and reported.
"""
import math
import re
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else "bldc_esp32_driver.kicad_pcb"
MM = 1_000_000
TEXT_H = 0.80          # glyph height (DRC minimum)
TEXT_W = 0.80          # glyph width
THICK = 0.13
COPPER_GAP = 0.15      # text box to exposed copper
SILK_GAP = 0.12        # text box to other silk
EDGE_GAP = 0.30

b = pcbnew.LoadBoard(BOARD)
b.BuildConnectivity()
bb = b.GetBoardEdgesBoundingBox()
X0, X1 = bb.GetX() / MM, bb.GetRight() / MM
Y0, Y1 = bb.GetY() / MM, bb.GetBottom() / MM


def rect_of(item):
    r = item.GetBoundingBox()
    return (r.GetX() / MM, r.GetY() / MM, r.GetRight() / MM, r.GetBottom() / MM)


def overlap(a, c, gap):
    return not (a[2] + gap < c[0] or c[2] + gap < a[0] or
                a[3] + gap < c[1] or c[3] + gap < a[1])


# existing labels from an earlier run
removed = 0
for d in list(b.GetDrawings()):
    if d.Type() == pcbnew.PCB_TEXT_T and d.GetLayer() == pcbnew.F_SilkS \
            and d.GetText().isdigit() and len(d.GetText()) <= 2:
        b.Delete(d)
        removed += 1

copper = []      # pad mask apertures, all nets
silk = []        # everything already on the silkscreen
bodies = []      # component courtyards: a label hidden under a part is useless
for fp in b.GetFootprints():
    court = [it.GetBoundingBox() for it in fp.GraphicalItems()
             if it.GetLayer() == pcbnew.F_CrtYd]
    if court:
        bodies.append((min(r.GetX() for r in court) / MM,
                       min(r.GetY() for r in court) / MM,
                       max(r.GetRight() for r in court) / MM,
                       max(r.GetBottom() for r in court) / MM))
for fp in b.GetFootprints():
    for p in fp.Pads():
        r = rect_of(p)
        copper.append((r[0] - 0.05, r[1] - 0.05, r[2] + 0.05, r[3] + 0.05))
    for it in fp.GraphicalItems():
        if it.GetLayer() == pcbnew.F_SilkS:
            silk.append(rect_of(it))
    # reference / value fields are not GraphicalItems and are easy to forget
    for field in (fp.Reference(), fp.Value()):
        if field.GetLayer() == pcbnew.F_SilkS and field.IsVisible():
            silk.append(rect_of(field))
for d in b.GetDrawings():
    if d.GetLayer() == pcbnew.F_SilkS:
        silk.append(rect_of(d))

tps = []
for fp in b.GetFootprints():
    if fp.GetReference().startswith("TP"):
        pad = next(iter(fp.Pads()))
        tps.append((int(re.sub(r"\D", "", fp.GetReference())), fp.GetReference(),
                    pad.GetPosition().x / MM, pad.GetPosition().y / MM))
tps.sort()

labels = []      # placed label boxes
placed, skipped = [], []


def fits(box, own):
    if box[0] < X0 + EDGE_GAP or box[2] > X1 - EDGE_GAP:
        return False
    if box[1] < Y0 + EDGE_GAP or box[3] > Y1 - EDGE_GAP:
        return False
    for c in copper:
        if overlap(box, c, COPPER_GAP):
            return False
    for s in silk:
        if overlap(box, s, SILK_GAP):
            return False
    for l in labels:
        if overlap(box, l, SILK_GAP):
            return False
    for bd in bodies:
        if overlap(box, bd, 0.05):
            return False
    return True


for num, ref, px, py in tps:
    text = str(num)
    best = None
    for radius in (1.15, 1.45, 1.75, 2.10, 2.50, 3.00, 3.50, 4.00):
        for deg in range(0, 360, 5):
            a = math.radians(deg)
            cx = px + radius * math.cos(a)
            cy = py + radius * math.sin(a)
            t = pcbnew.PCB_TEXT(b)
            t.SetText(text)
            t.SetLayer(pcbnew.F_SilkS)
            t.SetTextSize(pcbnew.VECTOR2I(int(TEXT_W * MM), int(TEXT_H * MM)))
            t.SetTextThickness(int(THICK * MM))
            t.SetHorizJustify(pcbnew.GR_TEXT_H_ALIGN_CENTER)
            t.SetVertJustify(pcbnew.GR_TEXT_V_ALIGN_CENTER)
            t.SetPosition(pcbnew.VECTOR2I(int(round(cx * MM)), int(round(cy * MM))))
            box = rect_of(t)
            if fits(box, (px, py)):
                best = (t, box, cx, cy)
                break
        if best:
            break
    if not best:
        skipped.append(ref)
        continue
    t, box, cx, cy = best
    b.Add(t)
    labels.append(box)
    silk.append(box)
    placed.append((ref, text, cx, cy))

b.Save(BOARD)
print(f"labels written: {len(placed)}  (previous removed: {removed})")
for ref, text, x, y in placed:
    print(f"  {ref:<5} '{text}' at ({x:6.2f},{y:6.2f})")
if skipped:
    print("unlabelled (no room):", " ".join(skipped))
