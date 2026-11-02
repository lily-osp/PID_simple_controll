#!/usr/bin/env python3
"""Add SMD test points on the nets that matter for bring-up.

Each test point is a 1.5 mm pad placed *centred on existing copper of its own
net*, so it connects by overlap and needs no extra routing. A candidate point is
only accepted if the pad clears every other net by PAD_CLEARANCE, and if it is
at least EDGE_MARGIN from the board edge.

The pads are marked board-only and excluded from BOM/position files, so they do
not show up in the PCBA order.
"""
import math
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "bldc_esp32_driver.kicad_pcb"
LIB = "/usr/share/kicad/footprints/TestPoint.pretty"
FPNAME = "TestPoint_Pad_D1.5mm"
MM = 1_000_000
PAD_D = 1.5
PAD_CLEARANCE = 0.30   # pad edge to any other net
EDGE_MARGIN = 1.2      # pad centre to board edge

# nets worth probing during bring-up
TARGETS = ["V_IN", "PNEG", "+12V", "+5V", "+3.3V", "VR", "EL",
           "PWM_OUT", "RPM_IN", "ISENSE_F", "GND"]

b = pcbnew.LoadBoard(BOARD)
b.BuildConnectivity()
bb = b.GetBoardEdgesBoundingBox()
X0, X1 = bb.GetX() / MM, bb.GetRight() / MM
Y0, Y1 = bb.GetY() / MM, bb.GetBottom() / MM

# every bit of copper that is not on the net being probed
bodies = []      # component bounding boxes to stay outside of
obstacles = []   # (x1,y1,x2,y2,radius)
for t in b.GetTracks():
    s, e = t.GetStart(), t.GetEnd()
    r = max(t.GetWidth() / 2 / MM, 0.15)
    obstacles.append((s.x / MM, s.y / MM, e.x / MM, e.y / MM, r, t.GetNetname()))
for fp in b.GetFootprints():
    for p in fp.Pads():
        q = p.GetPosition()
        obstacles.append((q.x / MM, q.y / MM, q.x / MM, q.y / MM,
                          max(p.GetSize().x, p.GetSize().y) / 2 / MM,
                          p.GetNetname()))
    # keep the probe pad off the neighbours' actual silkscreen: the mask
    # aperture clips any silk line it touches
    for it in fp.GraphicalItems():
        if it.GetLayer() != pcbnew.F_SilkS:
            continue
        if it.Type() == pcbnew.PCB_SHAPE_T:
            a, c = it.GetStart(), it.GetEnd()
            obstacles.append((a.x / MM, a.y / MM, c.x / MM, c.y / MM, 0.10, "__silk__"))
        else:
            r = it.GetBoundingBox()
            x0, y0 = r.GetX() / MM, r.GetY() / MM
            x1, y1 = r.GetRight() / MM, r.GetBottom() / MM
            obstacles.append((x0, y0, x1, y0, 0.0, "__silk__"))
            obstacles.append((x1, y0, x1, y1, 0.0, "__silk__"))
            obstacles.append((x1, y1, x0, y1, 0.0, "__silk__"))
            obstacles.append((x0, y1, x0, y0, 0.0, "__silk__"))


def seg_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def spot_ok(x, y, net):
    if not (X0 + EDGE_MARGIN < x < X1 - EDGE_MARGIN and Y0 + EDGE_MARGIN < y < Y1 - EDGE_MARGIN):
        return False
    m = PAD_D / 2 + PAD_CLEARANCE
    for bx0, by0, bx1, by1 in bodies:
        if bx0 - m < x < bx1 + m and by0 - m < y < by1 + m:
            return False
    for ox1, oy1, ox2, oy2, r, onet in obstacles:
        # never sit on top of any pad (even same-net): the probe needs bare copper
        is_pad = (ox1 == ox2 and oy1 == oy2)
        if onet == net and not is_pad:
            continue
        if seg_dist(x, y, ox1, oy1, ox2, oy2) < (PAD_D / 2 + PAD_CLEARANCE + r):
            return False
    return True


placed, skipped = [], []
for net in TARGETS:
    n = next((v for v in b.GetNetsByName().values() if v.GetNetname() == net), None)
    if n is None:
        skipped.append((net, "net not found"))
        continue
    # candidate points: sample every track of this net
    cands = []
    for t in b.GetTracks():
        # the probe pad is on F.Cu only, so it must land on F.Cu copper
        if t.GetNetname() != net or t.GetLayer() != pcbnew.F_Cu:
            continue
        s, e = t.GetStart(), t.GetEnd()
        L = math.hypot(e.x - s.x, e.y - s.y) / MM
        steps = max(1, int(L / 0.5))
        for i in range(steps + 1):
            f = i / steps
            cands.append((s.x / MM + (e.x - s.x) / MM * f,
                          s.y / MM + (e.y - s.y) / MM * f))
    # prefer spots near the board edge so probes are easy to reach
    cands.sort(key=lambda p: min(p[0] - X0, X1 - p[0], p[1] - Y0, Y1 - p[1]))
    spot = next((c for c in cands if spot_ok(c[0], c[1], net)), None)
    if spot is None:
        skipped.append((net, "no clear spot"))
        continue
    # build a bare probe pad: no courtyard, no silk, nothing to clash
    fp = pcbnew.FOOTPRINT(b)
    fp.SetPosition(pcbnew.VECTOR2I(int(spot[0] * MM), int(spot[1] * MM)))
    fp.SetReference(f"TP{len(placed) + 1}")
    fp.Reference().SetVisible(False)   # labelled in TESTPLAN.md, not on silk
    pad = pcbnew.PAD(fp)
    pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    pad.SetSize(pcbnew.VECTOR2I(int(PAD_D * MM), int(PAD_D * MM)))
    ls = pcbnew.LSET()
    ls.AddLayer(pcbnew.F_Cu)
    ls.AddLayer(pcbnew.F_Mask)
    pad.SetLayerSet(ls)
    pad.SetPosition(fp.GetPosition())   # absolute; gives a zero local offset
    pad.SetNet(n)
    fp.Add(pad)
    fp.SetAttributes(pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM
                     | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    b.Add(fp)
    placed.append((fp.GetReference(), net, spot))
    # keep later nets from landing on this pad
    obstacles.append((spot[0], spot[1], spot[0], spot[1], PAD_D / 2, net))

b.Save(BOARD)
print(f"test points placed: {len(placed)}")
for ref, net, (x, y) in placed:
    print(f"  {ref:<4} {net:<10} ({x:6.2f},{y:6.2f})")
if skipped:
    print("skipped:")
    for net, why in skipped:
        print(f"  {net:<10} {why}")
