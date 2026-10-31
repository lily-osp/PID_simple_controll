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
    # ============ LEFT: Hall port + amp ============
    "J3":  (5.0, 6.0, 0),
    "R21": (4.0, 24.0, 0), "R22": (4.0, 28.0, 0), "R23": (4.0, 32.0, 0),
    "C16": (7.5, 24.0, 0), "C17": (7.5, 28.0, 0), "C18": (7.5, 32.0, 0),
    "U4":  (12.5, 42.0, 0),
    "R25": (4.0, 54.0, 0), "R26": (4.0, 58.0, 0), "R27": (4.0, 62.0, 0),
    "R29": (7.5, 54.0, 0), "R30": (7.5, 58.0, 0), "R31": (7.5, 62.0, 0),
    "U5":  (14.0, 74.0, 0),
    "C19": (4.0, 84.0, 0), "C20": (7.5, 84.0, 0),

    # ============ CENTER (signal chain flow, common axis) ============
    "D1":  (34.0, 30.0, 0), "D2":  (39.0, 30.0, 0), "D3":  (44.0, 30.0, 0),
    "C13": (34.0, 36.0, 0), "C14": (39.0, 36.0, 0), "C15": (44.0, 36.0, 0),
    "U1":  (22.0, 54.0, 0),      # JY01
    "R8":  (30.0, 38.0, 0), "R9":  (30.0, 42.0, 0), "R10": (30.0, 46.0, 0),
    "R11": (30.0, 50.0, 0), "R12": (30.0, 54.0, 0), "R13": (30.0, 58.0, 0),
    "U3":  (40.0, 48.0, 0),      # JY213L
    "R14": (46.0, 38.0, 0), "R15": (46.0, 42.0, 0), "R16": (46.0, 46.0, 0),
    "R17": (46.0, 50.0, 0), "R18": (46.0, 54.0, 0), "R19": (46.0, 58.0, 0),
    "Q2":  (53.0, 40.0, 0), "Q3":  (53.0, 50.0, 0), "Q4":  (53.0, 60.0, 0),

    # ============ RIGHT: power + regulators ============
    "J5":  (60.0, 10.0, 0),       # P+ P-
    "J6":  (58.0, 22.0, 0),      # MA MB MC
    "C1":  (63.0, 42.0, 0),      # bulk 480uF
    "C2":  (63.0, 60.0, 0),      # bulk 480uF
    "C5":  (63.0, 78.0, 0),      # bulk 220uF
    "R1":  (48.0, 12.0, 0),       # shunt
    "R36": (16.0, 14.0, 0), "C21": (16.0, 18.0, 0),
    "U8":  (60.0, 98.0, 0),     # 7812
    "C3":  (48.0, 98.0, 0),
    "C11": (41.0, 96.0, 0), "C12": (41.0, 100.0, 0),
    "U7":  (60.0, 114.0, 0),     # 7805
    "C4":  (48.0, 114.0, 0),

    # ============ CENTER-BOTTOM: ESP32 + control (fills pocket) ============
    "U6":  (30.0, 78.0, 0),      # ESP32-C3 Super Mini
    "R7":  (44.0, 70.0, 0),      # PWM gate R
    "U2":  (44.0, 76.0, 0),      # CSD13380F3
    "R6":  (44.0, 82.0, 0),      # VR pull-up
    "R4":  (14.5, 56.0, 0), "R5": (14.5, 62.0, 0), "C6": (14.5, 68.0, 0),  # FG divider
    "RV1": (8.0, 98.0, 0),
    "R20": (48.0, 88.0, 0), "LED1": (52.0, 88.0, 0),
    "R32": (56.0, 86.0, 0), "LED2": (56.0, 90.0, 0),
    "R33": (18.0, 106.0, 0), "R34": (23.0, 106.0, 0), "R35": (20.0, 110.0, 0),
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

# ---- board outline 70 x 120, 5mm rounded corners (Edge.Cuts) ----
R = 5.0
W, H = 70.0, 120.0

def add_edge(x1, y1, x2, y2):
    seg = pcbnew.PCB_SHAPE(board)
    seg.SetShape(pcbnew.SHAPE_T_SEGMENT)
    seg.SetStart(pcbnew.VECTOR2I(int(x1 * 1e6), int(y1 * 1e6)))
    seg.SetEnd(pcbnew.VECTOR2I(int(x2 * 1e6), int(y2 * 1e6)))
    seg.SetLayer(pcbnew.Edge_Cuts)
    seg.SetWidth(int(0.1 * 1e6))
    board.Add(seg)

def add_arc(cx, cy, x1, y1, x2, y2):
    arc = pcbnew.PCB_SHAPE(board)
    arc.SetShape(pcbnew.SHAPE_T_ARC)
    arc.SetStart(pcbnew.VECTOR2I(int(x1 * 1e6), int(y1 * 1e6)))
    arc.SetEnd(pcbnew.VECTOR2I(int(x2 * 1e6), int(y2 * 1e6)))
    arc.SetCenter(pcbnew.VECTOR2I(int(cx * 1e6), int(cy * 1e6)))
    arc.SetLayer(pcbnew.Edge_Cuts)
    arc.SetWidth(int(0.1 * 1e6))
    board.Add(arc)

# straight edges (inset by R at the corners)
add_edge(R, 0, W - R, 0)            # top
add_edge(W, R, W, H - R)            # right
add_edge(W - R, H, R, H)            # bottom
add_edge(0, H - R, 0, R)            # left
# corner arcs (90 deg, bulging toward the board corner)
add_arc(W - R, R, W - R, 0, W, R)           # top-right
add_arc(W - R, H - R, W, H - R, W - R, H)   # bottom-right
add_arc(R, H - R, R, H, 0, H - R)           # bottom-left
add_arc(R, R, 0, R, R, 0)                   # top-left

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
