#!/usr/bin/env python3
"""Add SMD probe pads on the nets that matter for bring-up.

Test points already on the board are kept and never renumbered; the script only
fills in the nets that still lack one. A pad is placed *centred on existing
copper of its own net* where possible, so it connects by overlap. When no such
spot exists, a short stub track (0.25 mm, F.Cu) is routed from the net's copper
to the nearest clear spot.

A candidate is only accepted if the pad clears every other net by PAD_CLEARANCE,
clears the silkscreen, sits at least EDGE_MARGIN from the board edge, and stays
out of component courtyards. Stubs must clear other nets by the same rule.

The pads are marked board-only and excluded from BOM/position files, so they do
not show up in the PCBA order.
"""
import math
import re
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = sys.argv[1] if len(sys.argv) > 1 else "bldc_esp32_driver.kicad_pcb"

# reference to reuse when a pad is being re-placed after a layout change, so the
# numbers already printed in TESTPLAN.md stay valid
PREFER = {"+3.3V": "TP5", "RPM_IN": "TP8", "GPIO5": "TP13"}
MM = 1_000_000
PAD_D = 1.5
PAD_CLEARANCE = 0.30   # pad edge to any other net
EDGE_MARGIN = 1.2      # pad centre to board edge
TRACK_W = 0.25
TRACK_CLEARANCE = 0.28

# nets worth probing during bring-up
TARGETS = ["V_IN", "PNEG", "+12V", "+5V", "+3.3V", "VR", "EL", "ZF",
           "PWM_OUT", "RPM_IN", "ISENSE_F", "GPIO5",
           "HALL_OUT_A", "HALL_OUT_B", "HALL_OUT_C", "GND",
           # second pass: enable chain, analogue front end, power stage
           "GPIO4", "POT_ADC",
           "VB_A", "VB_B", "VB_C",
           "GQ_GH1", "GQ_GH2", "GQ_GH3", "GQ_GL1", "GQ_GL2", "GQ_GL3"]

b = pcbnew.LoadBoard(BOARD)
b.BuildConnectivity()
bb = b.GetBoardEdgesBoundingBox()
X0, X1 = bb.GetX() / MM, bb.GetRight() / MM
Y0, Y1 = bb.GetY() / MM, bb.GetBottom() / MM

probed = {}          # net -> (ref, x, y)
next_ref = 1
for fp in b.GetFootprints():
    ref = fp.GetReference()
    if not ref.startswith("TP"):
        continue
    next_ref = max(next_ref, int(re.sub(r"\D", "", ref) or 0) + 1)
    pad = next(iter(fp.Pads()))
    probed[pad.GetNetname()] = (ref, pad.GetPosition().x / MM, pad.GetPosition().y / MM)

bodies = []      # component courtyards to stay outside of
obstacles = []   # (x1,y1,x2,y2,radius,net)
for t in b.GetTracks():
    s, e = t.GetStart(), t.GetEnd()
    r = max(t.GetWidth() / 2 / MM, 0.15)
    obstacles.append((s.x / MM, s.y / MM, e.x / MM, e.y / MM, r, t.GetNetname()))
for fp in b.GetFootprints():
    if not fp.GetReference().startswith("TP"):
        court = [it.GetBoundingBox() for it in fp.GraphicalItems()
                 if it.GetLayer() == pcbnew.F_CrtYd]
        if court:
            bodies.append((min(r.GetX() for r in court) / MM,
                           min(r.GetY() for r in court) / MM,
                           max(r.GetRight() for r in court) / MM,
                           max(r.GetBottom() for r in court) / MM))
    for p in fp.Pads():
        q = p.GetPosition()
        obstacles.append((q.x / MM, q.y / MM, q.x / MM, q.y / MM,
                          max(p.GetSize().x, p.GetSize().y) / 2 / MM,
                          p.GetNetname()))
    # the mask aperture clips any silk line it touches
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
    if not (X0 + EDGE_MARGIN < x < X1 - EDGE_MARGIN and
            Y0 + EDGE_MARGIN < y < Y1 - EDGE_MARGIN):
        return False
    m = PAD_D / 2 + PAD_CLEARANCE
    for bx0, by0, bx1, by1 in bodies:
        if bx0 - m < x < bx1 + m and by0 - m < y < by1 + m:
            return False
    for ox1, oy1, ox2, oy2, r, onet in obstacles:
        is_pad = (ox1 == ox2 and oy1 == oy2)
        if onet == net and not is_pad:
            continue
        if seg_dist(x, y, ox1, oy1, ox2, oy2) < (PAD_D / 2 + PAD_CLEARANCE + r):
            return False
    return True


def stub_ok(x1, y1, x2, y2, net):
    need = TRACK_W / 2 + TRACK_CLEARANCE
    for ox1, oy1, ox2, oy2, r, onet in obstacles:
        if onet == net or onet == "__silk__":
            continue   # same net, or silkscreen: a covered track may pass under silk
        # sample the stub densely enough that a crossing cannot slip through
        steps = max(1, int(math.hypot(x2 - x1, y2 - y1) / 0.2))
        for i in range(steps + 1):
            f = i / steps
            if seg_dist(x1 + (x2 - x1) * f, y1 + (y2 - y1) * f,
                        ox1, oy1, ox2, oy2) < need + r:
                return False
    return True


def edge_dist(p):
    return min(p[0] - X0, X1 - p[0], p[1] - Y0, Y1 - p[1])


def fcu_samples(net):
    """Points on the net's F.Cu copper: pads, track endpoints, then interiors."""
    ends, mids = [], []
    for fp in b.GetFootprints():
        for p in fp.Pads():
            if p.GetNetname() == net and p.IsOnLayer(pcbnew.F_Cu):
                q = p.GetPosition()
                ends.append((q.x / MM, q.y / MM))
    for t in b.GetTracks():
        if t.GetNetname() != net or t.GetLayer() != pcbnew.F_Cu:
            continue
        if t.Type() == pcbnew.PCB_VIA_T:
            continue
        s, e = t.GetStart(), t.GetEnd()
        a = (s.x / MM, s.y / MM)
        c = (e.x / MM, e.y / MM)
        ends += [a, c]
        steps = max(1, int(math.hypot(c[0] - a[0], c[1] - a[1]) / 0.5))
        for i in range(1, steps):
            f = i / steps
            mids.append((a[0] + (c[0] - a[0]) * f, a[1] + (c[1] - a[1]) * f))
    return ends + mids


def add_pad(net, x, y, ref=None):
    global next_ref
    n = next(v for v in b.GetNetsByName().values() if v.GetNetname() == net)
    fp = pcbnew.FOOTPRINT(b)
    fp.SetPosition(pcbnew.VECTOR2I(int(round(x * MM)), int(round(y * MM))))
    fp.SetReference(ref or f"TP{next_ref}")
    if ref is None:
        next_ref += 1
    fp.Reference().SetVisible(False)
    pad = pcbnew.PAD(fp)
    pad.SetShape(pcbnew.PAD_SHAPE_CIRCLE)
    pad.SetAttribute(pcbnew.PAD_ATTRIB_SMD)
    pad.SetSize(pcbnew.VECTOR2I(int(PAD_D * MM), int(PAD_D * MM)))
    ls = pcbnew.LSET()
    ls.AddLayer(pcbnew.F_Cu)
    ls.AddLayer(pcbnew.F_Mask)
    pad.SetLayerSet(ls)
    pad.SetPosition(fp.GetPosition())   # absolute; zero local offset
    pad.SetNet(n)
    fp.Add(pad)
    fp.SetAttributes(pcbnew.FP_BOARD_ONLY | pcbnew.FP_EXCLUDE_FROM_BOM
                     | pcbnew.FP_EXCLUDE_FROM_POS_FILES)
    b.Add(fp)
    obstacles.append((x, y, x, y, PAD_D / 2, net))
    return fp.GetReference()


placed, skipped = [], []
for net in TARGETS:
    if net in probed:
        continue
    if next((v for v in b.GetNetsByName().values() if v.GetNetname() == net), None) is None:
        skipped.append((net, "net not found"))
        continue

    # 1. a spot already sitting on this net's copper
    spot = next((c for c in sorted(fcu_samples(net), key=edge_dist)
                 if spot_ok(c[0], c[1], net)), None)
    if spot:
        placed.append((add_pad(net, spot[0], spot[1], PREFER.get(net)), net, spot, None))
        continue

    # 2. otherwise a short stub to the nearest clear spot
    best = None
    for anchor in sorted(fcu_samples(net), key=edge_dist):
        for radius in (0.9, 1.2, 1.5, 1.8, 2.2, 2.6, 3.0, 3.6, 4.2, 5.0, 6.0,
                       7.0, 8.0, 9.0, 10.0, 11.0):
            for deg in range(0, 360, 8):
                a = math.radians(deg)
                x = anchor[0] + radius * math.cos(a)
                y = anchor[1] + radius * math.sin(a)
                if not spot_ok(x, y, net):
                    continue
                if not stub_ok(anchor[0], anchor[1], x, y, net):
                    continue
                if best is None or radius < best[0]:
                    best = (radius, anchor, (x, y), None)
            if best and best[0] <= radius:
                break
        if best:
            break
    if not best:
        # 3. an L-shaped stub, when a straight one is blocked
        for anchor in sorted(fcu_samples(net), key=edge_dist):
            for radius in (0.9, 1.2, 1.5, 1.8, 2.2, 2.6, 3.0, 3.6, 4.2, 5.0, 6.0,
                           7.0, 8.0, 9.0, 10.0, 11.0):
                for deg in range(0, 360, 8):
                    a = math.radians(deg)
                    x = anchor[0] + radius * math.cos(a)
                    y = anchor[1] + radius * math.sin(a)
                    if not spot_ok(x, y, net):
                        continue
                    for corner in ((x, anchor[1]), (anchor[0], y)):
                        if stub_ok(anchor[0], anchor[1], corner[0], corner[1], net) and \
                           stub_ok(corner[0], corner[1], x, y, net):
                            if best is None or radius < best[0]:
                                best = (radius, anchor, (x, y), corner)
                            break
                if best and best[0] <= radius:
                    break
            if best:
                break
    if not best:
        skipped.append((net, "no clear spot"))
        continue

    radius, anchor, spot, corner = best
    ref = add_pad(net, spot[0], spot[1], PREFER.get(net))
    n = next(v for v in b.GetNetsByName().values() if v.GetNetname() == net)
    pts = [anchor] if corner is None else [anchor, corner]
    pts.append(spot)
    for p1, p2 in zip(pts, pts[1:]):
        t = pcbnew.PCB_TRACK(b)
        t.SetNet(n)
        t.SetLayer(pcbnew.F_Cu)
        t.SetWidth(int(TRACK_W * MM))
        t.SetStart(pcbnew.VECTOR2I(int(round(p1[0] * MM)), int(round(p1[1] * MM))))
        t.SetEnd(pcbnew.VECTOR2I(int(round(p2[0] * MM)), int(round(p2[1] * MM))))
        b.Add(t)
    placed.append((ref, net, spot, anchor))

b.Save(BOARD)
print(f"new test points: {len(placed)}  (board total: {len(probed) + len(placed)})")
for ref, net, (x, y), anchor in placed:
    how = "on copper" if anchor is None else f"stub from ({anchor[0]:.2f},{anchor[1]:.2f})"
    print(f"  {ref:<5} {net:<12} ({x:6.2f},{y:6.2f})  {how}")
if skipped:
    print("skipped:")
    for net, why in skipped:
        print(f"  {net:<12} {why}")
