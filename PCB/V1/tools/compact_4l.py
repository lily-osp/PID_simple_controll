#!/usr/bin/env python3
"""Compact 4-layer placement: 60 x 95 mm, power chain down the left edge,
motor stage under J6, logic across the middle and bottom.

Translations only -- every footprint keeps the rotation it was verified with.
Run with --check to report courtyard clashes without saving.
"""
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "bldc_esp32_driver.kicad_pcb"
MM = 1_000_000

# new outline, 5 mm corner radius
X0, Y0, W, H = 100.0, 40.0, 64.0, 98.0
R = 5.0

# ref -> (x, y, rotation)
PLACE = {
    # --- top edge: power in, motor out, M3 holes in the corners
    "H1": (105.0, 45.0, 0), "H2": (159.0, 45.0, 0),
    "H3": (105.0, 133.0, 0), "H4": (159.0, 133.0, 0),
    "J5": (116.0, 45.5, 0), "J6": (140.0, 45.5, 0),
    "J3": (120.0, 134.0, 90),  # hall cable out the bottom edge

    # --- band B: input bulk caps + shunt
    "C1": (108.0, 57.0, 0), "C2": (122.0, 57.0, 0), "C5": (136.0, 57.0, 0),
    "R1": (150.0, 57.0, 90),

    # --- band C: half-bridges, gate driver, bootstrap (driver clear of the FET row)
    "Q2": (108.0, 68.0, 0), "Q3": (118.0, 68.0, 0), "Q4": (128.0, 68.0, 0),
    "U3": (140.0, 68.0, 90),
    "C13": (150.0, 64.0, 0), "C14": (154.0, 64.0, 0), "C15": (158.0, 64.0, 0),
    "D1": (150.0, 69.0, 90), "D2": (154.0, 69.0, 90), "D3": (158.0, 69.0, 90),
    "R14": (150.0, 73.0, 0), "R15": (150.0, 76.0, 0), "R16": (150.0, 79.0, 0),
    "R17": (158.0, 73.0, 0), "R18": (158.0, 76.0, 0), "R19": (158.0, 79.0, 0),

    # --- band D: 7812 -> 7805 chain lying flat, plus the JY01
    "U8": (105.0, 88.0, 0), "C3": (117.0, 88.0, 0),
    "U7": (130.0, 88.0, 0), "C4": (142.0, 88.0, 0),
    "U1": (156.0, 86.0, 0),
    "C11": (106.0, 95.0, 0), "C12": (110.0, 95.0, 0),
    "R8": (153.0, 94.0, 0), "R9": (153.0, 97.0, 0), "R10": (153.0, 100.0, 0),
    "R11": (159.0, 94.0, 0), "R12": (159.0, 97.0, 0), "R13": (159.0, 100.0, 0),

    # --- band E: hall conditioning
    "U4": (106.0, 102.0, 0), "U5": (117.0, 102.0, 0),
    "R21": (126.0, 98.0, 0), "R22": (130.0, 98.0, 0), "R23": (134.0, 98.0, 0),
    "R25": (126.0, 102.0, 0), "R26": (130.0, 102.0, 0), "R27": (134.0, 102.0, 0),
    "R29": (126.0, 106.0, 0), "R30": (130.0, 106.0, 0), "R31": (134.0, 106.0, 0),
    "C16": (140.0, 98.0, 0), "C17": (144.0, 98.0, 0), "C18": (148.0, 98.0, 0),

    # --- band F: ESP32 and its support
    "U6": (112.0, 120.0, 90),
    "R4": (126.0, 115.0, 0), "R5": (126.0, 119.0, 0),
    "R6": (131.0, 113.0, 90), "R7": (135.0, 113.0, 90),
    "R32": (139.0, 113.0, 90), "R33": (143.0, 113.0, 90), "R34": (147.0, 113.0, 90),
    "R35": (151.0, 113.0, 90), "R36": (155.0, 113.0, 90),
    "C6": (131.0, 119.0, 0), "C19": (135.0, 119.0, 0),
    "C20": (139.0, 119.0, 0), "C21": (143.0, 119.0, 0),
    "U2": (148.0, 121.0, 0), "R20": (152.0, 121.0, 0),
    "LED1": (148.0, 125.0, 0), "LED2": (152.0, 125.0, 0),
    "RV1": (145.0, 131.0, 0),
}


def rounded_outline(b, x0, y0, w, h, r):
    """Replace Edge.Cuts with a rounded rectangle."""
    for d in list(b.GetDrawings()):
        if d.GetLayer() == pcbnew.Edge_Cuts:
            b.Remove(d)
    pts = []
    for cx, cy, a0 in ((x0 + r, y0 + r, 180), (x0 + w - r, y0 + r, 270),
                       (x0 + w - r, y0 + h - r, 0), (x0 + r, y0 + h - r, 90)):
        for i in range(9):
            import math
            a = math.radians(a0 + i * 90 / 8)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    for i, (px, py) in enumerate(pts):
        qx, qy = pts[(i + 1) % len(pts)]
        seg = pcbnew.PCB_SHAPE(b)
        seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
        seg.SetLayer(pcbnew.Edge_Cuts)
        seg.SetWidth(int(0.1 * MM))
        seg.SetStart(pcbnew.VECTOR2I(int(px * MM), int(py * MM)))
        seg.SetEnd(pcbnew.VECTOR2I(int(qx * MM), int(qy * MM)))
        b.Add(seg)


b = pcbnew.LoadBoard(BOARD)

missing = [r for r in PLACE if r not in {f.GetReference() for f in b.GetFootprints()}]
extra = [f.GetReference() for f in b.GetFootprints() if f.GetReference() not in PLACE]
assert not missing, f"unknown refs in PLACE: {missing}"
assert not extra, f"footprints with no target position: {extra}"

for fp in b.GetFootprints():
    x, y, rot = PLACE[fp.GetReference()]
    fp.SetOrientationDegrees(rot)
    fp.SetPosition(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))

# ---- courtyard clash report --------------------------------------------------
boxes = []
for fp in b.GetFootprints():
    bb = fp.GetBoundingBox(False, False)
    boxes.append((fp.GetReference(), bb.GetX() / MM, bb.GetY() / MM,
                  bb.GetRight() / MM, bb.GetBottom() / MM))
clash = []
for i in range(len(boxes)):
    for j in range(i + 1, len(boxes)):
        a, c = boxes[i], boxes[j]
        if not (a[3] <= c[1] or a[1] >= c[3] or a[4] <= c[2] or a[2] >= c[4]):
            overlap = min(a[3], c[3]) - max(a[1], c[1]), min(a[4], c[4]) - max(a[2], c[2])
            clash.append((a[0], c[0], overlap))

outside = [r for r, x0, y0, x1, y1 in boxes
           if x0 < X0 + 0.4 or x1 > X0 + W - 0.4 or y0 < Y0 + 0.4 or y1 > Y0 + H - 0.4]

print(f"{len(boxes)} footprints placed on {W:.0f} x {H:.0f} mm")
print(f"clashes: {len(clash)}")
for a, c, o in clash:
    print(f"   {a} <-> {c}   overlap {o[0]:.1f} x {o[1]:.1f} mm")
print(f"outside the outline: {len(outside)} {outside}")

if "--check" not in sys.argv:
    b.SetCopperLayerCount(4)
    rounded_outline(b, X0, Y0, W, H, R)
    b.Save(BOARD)
    print("saved")
