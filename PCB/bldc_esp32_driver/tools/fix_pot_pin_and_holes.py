#!/usr/bin/env python3
"""Pre-order mechanical/electrical fixes, all in one reproducible pass.

1. POT_ADC moves from U6 pin 11 (GPIO2, a strapping pin) to pin 12 (GPIO3).
   Only the final 1.3 mm stub is rerouted; the 20 mm trunk is untouched.
   GPIO2 is left floating, which is the state its internal boot pull-up wants.
2. C4 (10 mm electrolytic) shifts 2.4 mm left so an M3 screw head clears its can
   at the bottom-right corner; its three track endpoints are snapped along.
3. Four M3 mounting holes go in at the corner-arc centres (5 mm from each edge),
   marked board-only so they do not show up as schematic-parity extras, with a
   1.2 mm copper-free ring so a screw head cannot short the GND pour.

Schematic side: gen_sch_full.py maps POT_ADC to ("U6","12").
"""
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "bldc_esp32_driver.kicad_pcb"
MM = 1_000_000
LIB = "/usr/share/kicad/footprints/MountingHole.pretty"
HOLES = {"H1": (96.0, 49.5), "H2": (156.0, 49.5), "H3": (96.0, 159.5), "H4": (156.0, 159.5)}
HOLE_CLR = 1.2      # copper-free ring around each hole, mm
C4_SHIFT = -2.4     # mm in X
PAD_SNAP = 0.25     # a track endpoint this close to an old pad centre follows it


def net(b, name):
    return next(n for n in b.GetNetsByName().values() if n.GetNetname() == name)


def near(p, q, tol=PAD_SNAP):
    return abs(p.x - q.x) / MM < tol and abs(p.y - q.y) / MM < tol


b = pcbnew.LoadBoard(BOARD)

# ---- 1. POT_ADC: U6 pin 11 -> pin 12 ----------------------------------------
u6 = next(f for f in b.GetFootprints() if f.GetReference() == "U6")
pads = {p.GetPadName(): p for p in u6.Pads()}
pot = net(b, "POT_ADC")
orphan = pcbnew.NETINFO_ITEM(b, "unconnected-(U6-GPIO2-Pad11)")
b.Add(orphan)
pads["12"].SetNet(pot)
pads["11"].SetNet(orphan)

stub = [t for t in b.GetTracks()
        if t.Type() == pcbnew.PCB_TRACE_T and t.GetNetname() == "POT_ADC"
        and abs(t.GetStart().y - t.GetEnd().y) < 1000
        and abs(t.GetStart().y / MM - pads["11"].GetPosition().y / MM) < 0.01]
assert len(stub) == 1, f"expected 1 stub, got {len(stub)}"
seg = stub[0]
trunk_end = min((seg.GetStart(), seg.GetEnd()), key=lambda p: p.x)
b.Remove(seg)
new = pcbnew.PCB_TRACK(b)
new.SetStart(trunk_end)
new.SetEnd(pcbnew.VECTOR2I(int(pads["12"].GetPosition().x), int(trunk_end.y)))
new.SetWidth(seg.GetWidth())
new.SetLayer(pcbnew.F_Cu)
new.SetNet(pot)
b.Add(new)
print(f"POT_ADC: U6 pin 11 (GPIO2) freed, pin 12 (GPIO3) connected "
      f"via {new.GetLength()/MM:.2f} mm stub")

# ---- 2. C4 clearance from the bottom-right hole ------------------------------
c4 = next(f for f in b.GetFootprints() if f.GetReference() == "C4")
before = {p.GetPadName(): pcbnew.VECTOR2I(p.GetPosition()) for p in c4.Pads()}
c4.SetPosition(pcbnew.VECTOR2I(int(c4.GetPosition().x + C4_SHIFT * MM), c4.GetPosition().y))
after = {p.GetPadName(): p.GetPosition() for p in c4.Pads()}
moved = 0
for t in b.GetTracks():
    if t.Type() != pcbnew.PCB_TRACE_T:
        continue
    for get, set_ in ((t.GetStart, t.SetStart), (t.GetEnd, t.SetEnd)):
        pt = get()
        for name, old in before.items():
            if near(pt, old):
                set_(after[name])
                moved += 1
                break
b.BuildConnectivity()
print(f"C4 moved {C4_SHIFT:+.1f} mm in X, {moved} track endpoints snapped")

# ---- 3. four M3 mounting holes ----------------------------------------------
board_only = getattr(pcbnew, "FP_BOARD_ONLY", 0)
for ref, (x, y) in HOLES.items():
    fp = pcbnew.FootprintLoad(LIB, "MountingHole_3.2mm_M3")
    assert fp, "MountingHole footprint missing"
    fp.SetReference(ref)
    fp.SetPosition(pcbnew.VECTOR2I(int(x * MM), int(y * MM)))
    fp.Reference().SetVisible(False)
    if board_only:
        fp.SetAttributes(fp.GetAttributes() | board_only)
    for p in fp.Pads():
        p.SetLocalClearance(int(HOLE_CLR * MM))
    b.Add(fp)
print(f"mounting holes: {', '.join(HOLES)} ({'board-only' if board_only else 'ATTR MISSING'})")

pcbnew.ZONE_FILLER(b).Fill(b.Zones())
b.Save(BOARD)

# ---- 4. report ---------------------------------------------------------------
for p in u6.Pads():
    if p.GetPadName() in ("11", "12"):
        print(f"  U6 pin {p.GetPadName()}: {p.GetNetname()}")
for p in c4.Pads():
    print(f"  C4 pad {p.GetPadName()}: {p.GetNetname()} at "
          f"({p.GetPosition().x/MM:.2f},{p.GetPosition().y/MM:.2f})")
