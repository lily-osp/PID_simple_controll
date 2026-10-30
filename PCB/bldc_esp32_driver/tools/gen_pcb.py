#!/usr/bin/env python3
"""Generate the placement-only PCB for bldc_esp32_driver from the verified schematic
netlist + JYQD-V7.3E3-mirrored layout.  Board 70 x 120 mm.
"""
import sys, re, os
sys.path.insert(0, '/usr/lib/python3/dist-packages')
import pcbnew

import importlib.util
spec = importlib.util.spec_from_file_location("gen", "/tmp/opencode/gen_sch_full.py")
gen = importlib.util.module_from_spec(spec); sys.modules["gen"] = gen
try:
    spec.loader.exec_module(gen)
except SystemExit:
    pass

BOARD_P = "/home/azzar/project/microcontrollers/03_projects/pids/pid-simple-controll/PCB/bldc_esp32_driver/bldc_esp32_driver.kicad_pcb"
NET_P = "/tmp/opencode/net_full.net"
FOOTPRINT_LIBS = "/usr/share/kicad/footprints"
LOCAL_LIB = "/home/azzar/project/microcontrollers/03_projects/pids/pid-simple-controll/PCB/bldc_esp32_driver/footprints"

# ---- ref -> (footprint, value) from schematic tables ----
ref_fp = {}
ref_val = {}
for (ref, libid, unit, value, fp, x, y) in gen.COMPS:
    ref_fp[ref] = fp
    ref_val[ref] = value

# ---- parse netlist: ref -> {pin -> netname}, and net name set ----
net = open(NET_P).read()
blocks = net.split('(net (code ')[1:]
ref_pins = {}
netnames = set()
for b in blocks:
    nm = re.search(r'\(name "([^"]+)"', b)
    if not nm:
        continue
    nname = nm.group(1).lstrip("/")
    netnames.add(nname)
    for r, p in re.findall(r'\(node \(ref "([^"]+)"\) \(pin "([^"]+)"', b):
        ref_pins.setdefault(r, {})[p] = nname

# ---- placement table: ref -> (x_mm, y_mm, rot_deg)  [board 70 x 120, origin top-left] ----
POS = {
    # LEFT edge ports
    "J3":  (4.0, 12.0, 0),
    "J4":  (4.0, 34.0, 0),
    # power entry (far right) + bulk caps + shunt
    "J5":  (53.0, 7.0, 0),
    "R1":  (44.0, 14.0, 0),
    "R36": (38.0, 14.0, 0),
    "C21": (38.0, 18.0, 0),
    "C1":  (61.0, 22.0, 0),
    "C2":  (61.0, 40.0, 0),
    "C5":  (48.0, 22.0, 0),
    # regulators
    "U8":  (44.0, 34.0, 0),
    "C3":  (32.0, 34.0, 0),
    "C11": (24.0, 28.0, 0),
    "C12": (24.0, 32.0, 0),
    "U7":  (44.0, 52.0, 0),
    "C4":  (32.0, 52.0, 0),
    # signal chain: controller -> gate R -> driver -> gate R -> bridges
    "U1":  (22.0, 74.0, 0),
    "R8":  (30.0, 68.0, 0),
    "R9":  (30.0, 72.0, 0),
    "R10": (30.0, 76.0, 0),
    "R11": (30.0, 80.0, 0),
    "R12": (30.0, 84.0, 0),
    "R13": (30.0, 88.0, 0),
    "U3":  (38.0, 78.0, 0),
    "R14": (46.0, 68.0, 0),
    "R15": (46.0, 72.0, 0),
    "R16": (46.0, 76.0, 0),
    "R17": (46.0, 80.0, 0),
    "R18": (46.0, 84.0, 0),
    "R19": (46.0, 88.0, 0),
    "Q2":  (56.0, 68.0, 0),
    "Q3":  (56.0, 78.0, 0),
    "Q4":  (56.0, 88.0, 0),
    # bootstrap diodes + caps (between driver and bridges)
    "D1":  (36.0, 60.0, 0),
    "D2":  (41.0, 60.0, 0),
    "D3":  (46.0, 60.0, 0),
    "C13": (36.0, 66.0, 0),
    "C14": (41.0, 66.0, 0),
    "C15": (46.0, 66.0, 0),
    # LEFT amp section
    "R21": (4.0, 50.0, 0),
    "R22": (4.0, 54.0, 0),
    "R23": (4.0, 58.0, 0),
    "C16": (8.0, 50.0, 0),
    "C17": (8.0, 54.0, 0),
    "C18": (8.0, 58.0, 0),
    "U4":  (14.0, 64.0, 0),
    "R25": (4.0, 70.0, 0),
    "R26": (4.0, 74.0, 0),
    "R27": (4.0, 78.0, 0),
    "R29": (8.0, 70.0, 0),
    "R30": (8.0, 74.0, 0),
    "R31": (8.0, 78.0, 0),
    "U5":  (14.0, 86.0, 0),
    "C19": (21.0, 88.0, 0),
    "C20": (20.0, 92.0, 0),
    # BOTTOM: ESP32 + control
    "U6":  (46.0, 105.0, 0),
    "U2":  (30.0, 92.0, 0),
    "R7":  (26.0, 88.0, 0),
    "R6":  (24.0, 92.0, 0),
    "R4":  (16.0, 92.0, 0),
    "R5":  (16.0, 96.0, 0),
    "C6":  (16.0, 100.0, 0),
    "RV1": (8.0, 100.0, 0),
    "R20": (28.0, 106.0, 0),
    "LED1": (32.0, 106.0, 0),
    "R32": (28.0, 110.0, 0),
    "LED2": (32.0, 110.0, 0),
    "R33": (12.0, 106.0, 0),
    "R34": (16.0, 106.0, 0),
    "R35": (12.0, 110.0, 0),
    "J1":  (62.0, 96.0, 0),
    "J2":  (67.0, 96.0, 0),
}

# ---- board ----
board = pcbnew.CreateEmptyBoard()

# nets
netcodes = {}
for name in sorted(netnames):
    ni = pcbnew.NETINFO_ITEM(board, name)
    board.Add(ni)
    netcodes[name] = ni.GetNetCode()
print("nets:", len(netcodes))

# footprints
def load_fp(fpstr):
    if fpstr.startswith("local:"):
        name = fpstr.split(":", 1)[1]
        return pcbnew.FootprintLoad(LOCAL_LIB, name)
    lib, name = fpstr.split(":", 1)
    return pcbnew.FootprintLoad(os.path.join(FOOTPRINT_LIBS, lib + ".pretty"), name)

missing = []
for ref in sorted(ref_fp):
    fpstr = ref_fp[ref]
    fp = load_fp(fpstr)
    if fp is None:
        missing.append((ref, fpstr))
        continue
    fp.SetReference(ref)
    fp.SetValue(ref_val[ref])
    x, y, rot = POS[ref]
    fp.SetPosition(pcbnew.VECTOR2I(int(x * 1e6), int(y * 1e6)))
    if rot:
        fp.SetOrientation(pcbnew.EDA_ANGLE(rot, pcbnew.DEGREES_T))
    board.Add(fp)
    pins = ref_pins.get(ref, {})
    for pad in fp.Pads():
        pnum = str(pad.GetNumber())
        if pnum in pins:
            pad.SetNetCode(netcodes[pins[pnum]])
print("missing footprints:", missing)

# ---- board outline 70 x 120 (Edge.Cuts) ----
def add_edge(x1, y1, x2, y2):
    seg = pcbnew.PCB_SHAPE(board)
    seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
    seg.SetStart(pcbnew.VECTOR2I(int(x1 * 1e6), int(y1 * 1e6)))
    seg.SetEnd(pcbnew.VECTOR2I(int(x2 * 1e6), int(y2 * 1e6)))
    seg.SetLayer(pcbnew.Edge_Cuts)
    seg.SetWidth(int(0.1 * 1e6))
    board.Add(seg)

add_edge(0, 0, 70, 0)
add_edge(70, 0, 70, 120)
add_edge(70, 120, 0, 120)
add_edge(0, 120, 0, 0)

# ---- save ----
pcbnew.SaveBoard(BOARD_P, board)
print("saved", BOARD_P, "footprints:", board.GetFootprints().size() if hasattr(board.GetFootprints(), "size") else len(list(board.GetFootprints())))

# ---- axis-aligned overlap report (rot-0 accurate) ----
print("--- overlap check (bounding boxes, mm) ---")
fps = list(board.GetFootprints())
boxes = []
for fp in fps:
    bb = fp.GetBoundingBox(False, False)  # pads, no text
    boxes.append((fp.GetReference(), bb.GetX()/1e6, bb.GetY()/1e6,
                  bb.GetX()/1e6 + bb.GetWidth()/1e6, bb.GetY()/1e6 + bb.GetHeight()/1e6))
ov = 0
for i in range(len(boxes)):
    for j in range(i+1, len(boxes)):
        r1, x1, y1, X1, Y1 = boxes[i]
        r2, x2, y2, X2, Y2 = boxes[j]
        if x1 < X2 and x2 < X1 and y1 < Y2 and y2 < Y1:
            ov += 1
            if ov <= 40:
                print(f"OVERLAP {r1} <-> {r2}")
print("total overlaps:", ov)
