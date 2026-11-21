#!/usr/bin/env python3
"""V2 rework of the power stage, gate fan-out and current-sense reference.

What this does to bldc_esp32_driver.kicad_pcb (see README "V2 rework"):

1. Q2-Q4 get the REAL JY2605M land (PowerPAK SO-8 dual, pins 1=S1 2=G1 3=S2
   4=G2 5,6=D2 7,8=D1) instead of the invented DFN8 footprint, rotated 90 deg
   so each dual sits as a half-bridge: D1 (left pad) = V_IN, D2 (right pad) =
   phase, S1 (bottom-left lead) = phase, S2 = GND, G1/G2 = gates.
2. The whole power stage around them is re-routed: V_IN rail, phase wraps
   (F.Cu -> In1.Cu -> F.Cu), low-side source vias, gate fan-out on B.Cu.
3. U1 (JY01) pins 9-12 keep the schematic's corrected order (9=BT 10=BB
   11=CT 12=CB) - the four gate-drive tracks are redrawn accordingly.
4. The current-sense reference moves to the connector side of R1 so that the
   JY01 Is pin sees a POSITIVE shunt voltage (U1 Vss and C21 -> PNEG,
   R36 cold end -> GND).

Run from PCB/V1:  python3 tools/v2_power_stage_rework.py [in.kicad_pcb] [out.kicad_pcb]
"""
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

SRC = sys.argv[1] if len(sys.argv) > 1 else "bldc_esp32_driver.kicad_pcb"
DST = sys.argv[2] if len(sys.argv) > 2 else SRC

b = pcbnew.LoadBoard(SRC)
N = {n.GetNetname(): n for n in b.GetNetInfo().NetsByNetcode().values()}
LAY = {n: b.GetLayerID(n) for n in ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")}


def mm(v):
    return pcbnew.FromMM(v)


def V(x, y):
    return pcbnew.VECTOR2I(mm(x), mm(y))


def track(net, layer, a, c, w):
    t = pcbnew.PCB_TRACK(b)
    t.SetStart(V(*a))
    t.SetEnd(V(*c))
    t.SetWidth(mm(w))
    t.SetLayer(LAY[layer])
    t.SetNet(N[net])
    b.Add(t)
    return t


def via(net, at, drill=0.3, dia=0.6):
    v = pcbnew.PCB_VIA(b)
    v.SetPosition(V(*at))
    v.SetDrill(mm(drill))
    v.SetWidth(mm(dia))
    v.SetViaType(pcbnew.VIATYPE_THROUGH)
    v.SetLayerPair(LAY["F.Cu"], LAY["B.Cu"])
    v.SetNet(N[net])
    b.Add(v)
    return v


# ---------------------------------------------------------------- 1. footprints
FETS = {  # ref: (centre x, phase net, high-side gate, low-side gate)
    "Q2": (107.0, "PH_A", "GQ_GH1", "GQ_GL1"),
    "Q3": (117.0, "PH_B", "GQ_GH2", "GQ_GL2"),
    "Q4": (127.0, "PH_C", "GQ_GH3", "GQ_GL3"),
}
CY = 74.5

for ref, (cx, ph, gh, gl) in FETS.items():
    old = b.FindFootprintByReference(ref)
    if old and str(old.GetFPID().GetLibItemName()) == "JY2605M_PowerPAK_SO8_Dual":
        continue                      # already reworked
    if old:
        b.Delete(old)
    fp = pcbnew.FootprintLoad("footprints", "JY2605M_PowerPAK_SO8_Dual")
    fp.SetFPID(pcbnew.LIB_ID("local", "JY2605M_PowerPAK_SO8_Dual"))
    fp.SetReference(ref)
    fp.SetValue("JY2605M")
    fp.SetPosition(V(cx, CY))
    fp.SetOrientationDegrees(90)
    b.Add(fp)
    netmap = {"1": ph, "2": gh, "3": "GND", "4": gl,
              "5": ph, "6": ph, "7": "V_IN", "8": "V_IN"}
    for pad in fp.Pads():
        pad.SetNet(N[netmap[pad.GetNumber()]])

# ---------------------------------------------------------------- 2. rip up
WIN = (100.5, 64.0, 136.5, 86.5)          # x0, y0, x1, y1
RIP = {"V_IN", "PH_A", "PH_B", "PH_C", "GND",
       "GQ_GH1", "GQ_GL1", "GQ_GH2", "GQ_GL2", "GQ_GH3", "GQ_GL3"}
# GND tracks inside the window are the old source stubs; the four GND pours
# carry the return current, so they are ripped with the rest.


def in_win(x, y, pad=0.0):
    x0, y0, x1, y1 = WIN
    return x0 - pad <= x <= x1 + pad and y0 - pad <= y <= y1 + pad


def seg_hits_win(ax, ay, cx_, cy_):
    """crude but sufficient: sample the segment"""
    steps = max(2, int(max(abs(cx_ - ax), abs(cy_ - ay)) * 4))
    for i in range(steps + 1):
        t = i / steps
        if in_win(ax + (cx_ - ax) * t, ay + (cy_ - ay) * t):
            return True
    return False


doomed = []
for t in b.GetTracks():
    if t.GetNetname() not in RIP:
        continue
    if t.GetClass() == "PCB_VIA":
        p = t.GetPosition()
        if in_win(p.x / 1e6, p.y / 1e6):
            doomed.append(t)
    else:
        s, e = t.GetStart(), t.GetEnd()
        if seg_hits_win(s.x / 1e6, s.y / 1e6, e.x / 1e6, e.y / 1e6):
            doomed.append(t)
for t in doomed:
    b.Remove(t)
print(f"ripped {len(doomed)} tracks/vias in the power-stage window")

# ---------------------------------------------------------------- 3. test points
# the four western gate test pads move onto the new gate vias
TP_MOVE = {"TP19": (106.365, 78.6), "TP21": (108.905, 78.6),
           "TP22": (118.905, 78.6), "TP27": (126.365, 78.6)}
for ref, pos in TP_MOVE.items():
    fp = b.FindFootprintByReference(ref)
    fp.SetPosition(V(*pos))
    for pad in fp.Pads():
        pad.SetSize(pcbnew.VECTOR2I(mm(1.0), mm(1.0)))

# the silkscreen numbers follow their pads
SILK_MOVE = {"19": (106.365, 80.3), "21": (108.905, 80.3),
             "22": (118.905, 80.3), "27": (126.365, 80.3)}
for d in b.GetDrawings():
    if d.GetClass() == "PCB_TEXT" and d.GetText() in SILK_MOVE:
        x, y = SILK_MOVE[d.GetText()]
        if abs(d.GetPosition().y / 1e6 - y) > 0.5:      # not moved yet
            d.SetPosition(V(x, y))

# ---------------------------------------------------------------- 4. new copper
RAIL_Y = 69.3          # V_IN rail above the FET row
WRAP_Y = 80.6          # In1.Cu phase wrap
VIA_ROW = 78.6         # gate / source via row under each package
W_PWR, W_SIG = 1.5, 0.4

for ref, (cx, ph, gh, gl) in FETS.items():
    # --- V_IN: rail stub down into the left (D1) pad
    track("V_IN", "F.Cu", (cx - 1.27, RAIL_Y), (cx - 1.27, 72.6), W_PWR)
    # --- phase wrap: S1 lead -> F.Cu stub -> vias -> In1.Cu -> vias -> D2 pad
    track(ph, "F.Cu", (cx - 1.905, 77.3), (cx - 1.905, 78.9), 0.8)
    track(ph, "F.Cu", (cx - 1.905, 78.9), (cx - 2.6, 78.9), 0.8)
    via(ph, (cx - 1.905, 78.9))
    via(ph, (cx - 2.6, 78.9))
    track(ph, "In1.Cu", (cx - 2.6, 78.9), (cx - 2.6, WRAP_Y), 2.0)
    track(ph, "In1.Cu", (cx - 2.6, WRAP_Y), (cx + 3.5, WRAP_Y), 2.0)
    track(ph, "In1.Cu", (cx + 3.5, WRAP_Y), (cx + 3.5, 75.5), 2.0)
    via(ph, (cx + 3.5, 75.0))
    via(ph, (cx + 3.5, 76.0))
    track(ph, "F.Cu", (cx + 3.5, 76.0), (cx + 3.5, 75.0), W_PWR)
    track(ph, "F.Cu", (cx + 3.5, 75.0), (cx + 1.0, 75.0), W_PWR)
    # --- low-side source: short stub into a via down to the ground planes
    track("GND", "F.Cu", (cx + 0.635, 77.3), (cx + 0.635, VIA_ROW), 0.8)
    via("GND", (cx + 0.635, VIA_ROW))
    # --- gates: stub down to the via row
    track(gh, "F.Cu", (cx - 0.635, 77.3), (cx - 0.635, VIA_ROW), W_SIG)
    via(gh, (cx - 0.635, VIA_ROW))
    track(gl, "F.Cu", (cx + 1.905, 77.3), (cx + 1.905, VIA_ROW), W_SIG)
    via(gl, (cx + 1.905, VIA_ROW))

# --- V_IN rails and feeds
track("V_IN", "F.Cu", (107.18, 61.5), (107.18, RAIL_Y), W_PWR)      # C1 column
track("V_IN", "F.Cu", (121.18, 61.5), (121.18, RAIL_Y), W_PWR)      # C2 column
track("V_IN", "F.Cu", (102.8, RAIL_Y), (115.73, RAIL_Y), W_PWR)     # rail A
track("V_IN", "F.Cu", (121.18, RAIL_Y), (125.73, RAIL_Y), W_PWR)    # rail B
track("V_IN", "F.Cu", (102.8, RAIL_Y), (102.8, 80.0), W_PWR)        # down the west edge
track("V_IN", "F.Cu", (102.8, 80.0), (105.0, 83.36), W_PWR)         # to TP1
track("V_IN", "F.Cu", (105.0, 83.36), (105.0, 88.0), W_PWR)         # to U8 pin 1

# --- phase escapes to U3 / J6 / bootstrap caps
track("PH_A", "F.Cu", (110.5, 75.0), (110.5, 71.2), 1.0)
via("PH_A", (110.5, 71.2))
track("PH_A", "In2.Cu", (110.5, 71.2), (109.69, 68.39), 0.8)
track("PH_A", "In2.Cu", (109.69, 68.39), (138.15, 68.39), 0.8)

track("PH_B", "F.Cu", (120.5, 75.0), (120.5, 72.59), 1.0)
track("PH_B", "F.Cu", (120.5, 72.59), (119.07, 72.59), 1.0)
track("PH_B", "F.Cu", (119.07, 72.59), (119.07, 51.52), 0.8)
via("PH_B", (119.07, 69.5))
track("PH_B", "B.Cu", (119.07, 69.5), (139.82, 69.5), 0.4)

track("PH_C", "F.Cu", (130.5, 75.0), (130.5, 72.59), 1.0)
track("PH_C", "F.Cu", (130.5, 72.59), (131.09, 72.59), 1.0)
track("PH_C", "F.Cu", (131.09, 72.59), (131.09, 52.69), 0.8)

# --- gate fan-out: In2 lane (kept, from the resistors) -> via -> B.Cu -> gate via
#     lane depth rises from east to west so nothing crosses
GATE_FAN = [  # net, In2 hand-off via, B.Cu lane y, gate x
    ("GQ_GL3", (132.3, 71.65), 79.6, 128.905),
    ("GQ_GH3", (133.0, 76.31), 80.2, 126.365),
    ("GQ_GL2", (133.7, 72.71), 80.8, 118.905),
    ("GQ_GH2", (134.4, 80.63), 81.4, 116.365),
    ("GQ_GL1", (135.1, 73.99), 82.0, 108.905),
    ("GQ_GH1", (136.4, 75.40), 82.6, 106.365),
]
IN2_TAIL = {  # the kept In2 lane is redrawn from its eastern anchor to the via
    "GQ_GL3": [((155.92, 71.65), (132.3, 71.65))],
    "GQ_GH3": [((158.37, 76.31), (133.0, 76.31))],
    "GQ_GL2": [((137.72, 72.71), (133.7, 72.71))],
    "GQ_GH2": [((150.97, 80.63), (134.4, 80.63))],
    "GQ_GL1": [((138.63, 73.99), (135.1, 73.99))],
    "GQ_GH1": [((138.82, 74.44), (137.2, 74.44)), ((137.2, 74.44), (136.4, 75.40))],
}
for net, (vx, vy), lane, gx in GATE_FAN:
    for a, c in IN2_TAIL[net]:
        track(net, "In2.Cu", a, c, 0.25)
    via(net, (vx, vy))
    track(net, "B.Cu", (vx, vy), (vx, lane), 0.25)
    track(net, "B.Cu", (vx, lane), (gx, lane), 0.25)
    track(net, "B.Cu", (gx, lane), (gx, VIA_ROW), 0.25)

# ------------------------------------------------- 4b. JY01 pins 9-12 un-swap
# The JY01 datasheet order is 9 BT, 10 BB, 11 CT, 12 CB.  V1 wired 9<->10 and
# 11<->12, so on the B and C legs the chip's top-arm output drove the bottom
# FET and vice versa - the motor cannot commutate.  The whole chain
# (U1 pin -> 100R -> FD6288T input) is otherwise correct, so the crossing is
# undone once, at the gate driver's inputs, where there is room: the four
# approach tracks under U3 are re-routed (two hops on In1.Cu, one on B.Cu, one
# extended on In2.Cu) and the nets/designators follow.
def cut_at(net, pt, r=0.08):
    n = 0
    for t in list(b.GetTracks()):
        if t.GetClass() == "PCB_VIA" or t.GetNetname() != net:
            continue
        for q in (t.GetStart(), t.GetEnd()):
            if abs(q.x / 1e6 - pt[0]) <= r and abs(q.y / 1e6 - pt[1]) <= r:
                b.Remove(t)
                n += 1
                break
    return n


def kill_via(net, pt, r=0.08):
    for t in list(b.GetTracks()):
        if t.GetClass() != "PCB_VIA" or t.GetNetname() != net:
            continue
        q = t.GetPosition()
        if abs(q.x / 1e6 - pt[0]) <= r and abs(q.y / 1e6 - pt[1]) <= r:
            b.Remove(t)


u1 = b.FindFootprintByReference("U1")
if u1.FindPadByNumber("9").GetNetname() == "GO_BB":       # not yet reworked
    # --- rip the four approaches to U3 pins 2/3/5/6
    cut_at("GI_HIN2", (137.22, 76.86)); cut_at("GI_HIN2", (137.22, 91.94))
    cut_at("GI_LIN2", (139.07, 76.96)); cut_at("GI_LIN2", (139.18, 76.86))
    cut_at("GI_LIN2", (139.07, 90.82))   # vertical + stub to the via
    cut_at("GI_HIN3", (137.88, 76.86)); cut_at("GI_HIN3", (137.88, 92.81))
    cut_at("GI_LIN3", (139.82, 76.86)); cut_at("GI_LIN3", (139.82, 78.41))
    cut_at("GI_LIN3", (139.79, 78.44)); kill_via("GI_LIN3", (139.79, 78.44))

    # --- swap the net names along both crossed chains (U3's own pads keep
    #     theirs - that is what the swap is for) and the two resistor pairs
    SWAPS = {"GO_BT": "GO_BB", "GO_BB": "GO_BT", "GI_HIN2": "GI_LIN2",
             "GI_LIN2": "GI_HIN2", "GO_CT": "GO_CB", "GO_CB": "GO_CT",
             "GI_HIN3": "GI_LIN3", "GI_LIN3": "GI_HIN3"}
    for t in b.GetTracks():
        if t.GetNetname() in SWAPS:
            t.SetNet(N[SWAPS[t.GetNetname()]])
    for ref in ("U1", "R10", "R11", "R12", "R13", "TP19", "TP20", "TP21",
                "TP22", "TP23", "TP27"):
        fp = b.FindFootprintByReference(ref)
        for pad in fp.Pads():
            if pad.GetNetname() in SWAPS:
                pad.SetNet(N[SWAPS[pad.GetNetname()]])
    # the two 100R pairs are identical parts, so the designators move with the
    # function they now serve
    for a, c in (("R10", "R11"), ("R12", "R13")):
        fa, fc = b.FindFootprintByReference(a), b.FindFootprintByReference(c)
        fa.SetReference("_tmp"); fc.SetReference(a); fa.SetReference(c)

    # --- U3 pin 2 (HIN2) <- the chain that used to land on pin 5.
    #     It already has a via at (139.70,91.45), so the hop starts there.
    track("GI_HIN2", "B.Cu", (139.70, 91.45), (137.225, 84.8), 0.25)
    via("GI_HIN2", (137.225, 84.8))
    track("GI_HIN2", "F.Cu", (137.225, 84.8), (137.225, 77.4), 0.2)
    # --- U3 pin 5 (LIN2) <- the chain that used to land on pin 2
    track("GI_LIN2", "F.Cu", (136.85, 92.31), (137.22, 91.94), 0.25)   # re-link
    track("GI_LIN2", "F.Cu", (137.22, 91.94), (137.22, 89.0), 0.25)
    via("GI_LIN2", (137.22, 89.0))
    track("GI_LIN2", "In1.Cu", (137.22, 89.0), (139.175, 84.8), 0.25)
    via("GI_LIN2", (139.175, 84.8))
    track("GI_LIN2", "F.Cu", (139.175, 84.8), (139.175, 77.4), 0.2)
    # --- U3 pin 3 (HIN3) <- the chain that used to land on pin 6 (In2 run west)
    track("GI_HIN3", "In2.Cu", (140.0, 78.23), (137.875, 78.9), 0.25)
    via("GI_HIN3", (137.875, 78.9))
    track("GI_HIN3", "F.Cu", (137.875, 78.9), (137.875, 77.4), 0.2)
    # --- U3 pin 6 (LIN3) <- the chain that used to land on pin 3
    track("GI_LIN3", "F.Cu", (137.48, 93.21), (137.88, 92.81), 0.25)   # re-link
    track("GI_LIN3", "F.Cu", (137.88, 92.81), (137.88, 90.8), 0.25)
    via("GI_LIN3", (137.88, 90.8))
    track("GI_LIN3", "In1.Cu", (137.88, 90.8), (139.825, 87.3), 0.25)
    via("GI_LIN3", (139.825, 87.3))
    track("GI_LIN3", "F.Cu", (139.825, 87.3), (139.825, 77.4), 0.2)

# ---------------------------------------------------------------- 5. Is reference
# U1 pin 3 (Vss) and C21 pin 2 move from GND to PNEG; R36 pin 2 moves to GND.
u1, r36, c21 = (b.FindFootprintByReference(r) for r in ("U1", "R36", "C21"))
u1.FindPadByNumber("3").SetNet(N["PNEG"])
c21.FindPadByNumber("2").SetNet(N["PNEG"])
r36.FindPadByNumber("2").SetNet(N["GND"])

# the old PNEG tail fed R36; R36's cold end is GND now, so drop those segments
for t in list(b.GetTracks()):
    if t.GetNetname() != "PNEG" or t.GetClass() == "PCB_VIA":
        continue
    s_, e_ = t.GetStart(), t.GetEnd()
    if min(s_.y / 1e6, e_.y / 1e6) >= 109.0:
        b.Remove(t)
        continue
    # the diagonal that used to run down to R36 now ends nowhere
    if {(round(s_.x / 1e6, 2), round(s_.y / 1e6, 2)),
        (round(e_.x / 1e6, 2), round(e_.y / 1e6, 2))} == {(155.0, 109.26), (161.21, 103.05)}:
        b.Remove(t)
        continue
    # and the trunk now ends at the branch via, not 1 mm past it
    if abs(s_.y / 1e6 - 103.05) < 0.02 and abs(s_.x / 1e6 - 161.21) < 0.02:
        t.SetStart(V(161.21, 102.0))
    elif abs(e_.y / 1e6 - 103.05) < 0.02 and abs(e_.x / 1e6 - 161.21) < 0.02:
        t.SetEnd(V(161.21, 102.0))
# U1 pin 3 and C21 pin 2 leave the pour: drop the GND stubs that fed them
for t in list(b.GetTracks()):
    if t.GetNetname() != "GND" or t.GetClass() == "PCB_VIA":
        continue
    for p_ in (t.GetStart(), t.GetEnd()):
        x_, y_ = p_.x / 1e6, p_.y / 1e6
        if (abs(x_ - 153.5) < 0.2 and abs(y_ - 84.09) < 0.2) or \
           (abs(x_ - 143.95) < 0.7 and abs(y_ - 119.0) < 0.7):
            b.Remove(t)
            break

# PNEG branches run on In1.Cu, the one layer with no routing on it
via("PNEG", (161.21, 87.0))                          # off the existing trunk
track("PNEG", "In1.Cu", (161.21, 87.0), (152.0, 87.0), 0.4)
track("PNEG", "In1.Cu", (152.0, 87.0), (152.0, 84.09), 0.4)
track("PNEG", "In1.Cu", (152.0, 84.09), (151.9, 84.09), 0.4)
via("PNEG", (151.9, 84.09))
track("PNEG", "F.Cu", (151.9, 84.09), (152.8, 84.09), 0.4)      # into U1 pin 3

via("PNEG", (161.21, 102.0))                         # on the trunk -> C21 pin 2
track("PNEG", "In1.Cu", (161.21, 102.0), (162.6, 103.4), 0.4)
track("PNEG", "In1.Cu", (162.6, 103.4), (162.6, 119.3), 0.4)
track("PNEG", "In1.Cu", (162.6, 119.3), (146.5, 119.3), 0.4)
track("PNEG", "In1.Cu", (146.5, 119.3), (145.6, 119.0), 0.4)
via("PNEG", (145.6, 119.0))
track("PNEG", "F.Cu", (145.6, 119.0), (144.3, 119.0), 0.4)      # into C21 pin 2

# R36's cold end is GND now: stub + stitching via so its pour island is tied
# to the ground planes (an SMD pad alone would leave that island floating)
track("GND", "F.Cu", (155.0, 112.09), (155.0, 111.0), 0.4)
via("GND", (155.0, 111.0))

# ---------------------------------------------------------------- 6. refill
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
b.BuildConnectivity()
b.Save(DST)
print(f"saved {DST}")
