#!/usr/bin/env python3
"""Incremental routing prep: rip only the nets touched by the placement change,
export the DSN, add the wide PHASE class, and freeze all remaining copper so the
router may not disturb the approved routing.

Usage: final_incremental.py [--rip] [--dsn PATH] [--width UM]
"""
import argparse
import re
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "bldc_esp32_driver.kicad_pcb"

RIP_NETS = (
    ["PH_A", "PH_B", "PH_C"]
    + [f"GP_HO{i}" for i in (1, 2, 3)] + [f"GP_LO{i}" for i in (1, 2, 3)]
    + [f"GQ_GH{i}" for i in (1, 2, 3)] + [f"GQ_GL{i}" for i in (1, 2, 3)]
)

ap = argparse.ArgumentParser()
ap.add_argument("--rip", action="store_true", help="rip the affected nets from the board first")
ap.add_argument("--dsn", default="/tmp/opencode/inc.dsn")
ap.add_argument("--width", type=int, default=600, help="phase trace width in um")
args = ap.parse_args()

board = pcbnew.LoadBoard(BOARD)

if args.rip:
    dead = [t for t in board.GetTracks() if t.GetNetname() in RIP_NETS]
    for t in dead:
        board.Remove(t)
    board.Save(BOARD)
    print(f"ripped {len(dead)} items on {len(RIP_NETS)} nets")

# Pours are exported as full-board Specctra planes on both layers, which leaves the
# router no space; drop them here and refill after the session is imported.
zones = list(board.Zones())
for z in zones:
    board.Remove(z)
if zones:
    board.Save(BOARD)
    print(f"removed {len(zones)} pours for routing")

assert pcbnew.ExportSpecctraDSN(board, args.dsn), "DSN export failed"
src = open(args.dsn).read()

special = ["PH_A", "PH_B", "PH_C"]
all_nets = [n.GetNetname() for n in board.GetNetsByName().values()
            if n.GetNetname() and n.GetNetname() not in special]


def q(name):
    return f'"{name}"' if re.search(r"[^A-Za-z0-9_+\-.]", name) else name


# extra via padstack for the phase class
if "Via[0-1]_1000:500_um" not in src:
    src = src.replace('    (via "Via[0-1]_600:300_um")\n',
                      '    (via "Via[0-1]_600:300_um")\n    (via "Via[0-1]_1000:500_um")\n')
    m = re.search(r'    \(padstack "Via\[0-1\]_600:300_um"\n.*?\n    \)\n', src, re.S)
    block = m.group(0).replace('"Via[0-1]_600:300_um"', '"Via[0-1]_1000:500_um"')
    block = block.replace("(circle F.Cu 600)", "(circle F.Cu 1000)")
    block = block.replace("(circle B.Cu 600)", "(circle B.Cu 1000)")
    src = src[:m.end()] + block + src[m.end():]

m = re.search(r"    \(class kicad_default .*?\n    \)\n", src, re.S)
default_block = (
    f"    (class kicad_default {' '.join(q(n) for n in all_nets)}\n"
    '      (circuit\n        (use_via "Via[0-1]_600:300_um")\n      )\n'
    "      (rule\n        (width 200)\n        (clearance 200)\n      )\n    )\n"
)
phase_block = (
    "    (class pwr_phase PH_A PH_B PH_C\n"
    '      (circuit\n        (use_via "Via[0-1]_1000:500_um")\n      )\n'
    f"      (rule\n        (width {args.width})\n        (clearance 250)\n      )\n    )\n"
)
src = src[:m.start()] + default_block + phase_block + src[m.end():]

# freeze every wire/via that is already routed
before = src.count("(type route)")
src = src.replace("(type route)", "(type protect)")
print(f"protected {before} existing wire/via segments")

open(args.dsn, "w").write(src)
print(f"DSN ready: {args.dsn}  phase width {args.width/1000:.2f}mm")
