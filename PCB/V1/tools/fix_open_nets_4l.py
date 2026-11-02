#!/usr/bin/env python3
"""Incrementally re-route only the nets FreeRouting left open.

Rips the given nets, exports the DSN, freezes every other wire/via as
(type protect), and keeps the same width classes. Then run FreeRouting on the
result and import it with import_4l.py.

Usage: fix_open_nets_4l.py NET [NET ...]
"""
import re
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "bldc_esp32_driver.kicad_pcb"
DSN = "/tmp/opencode/fix.dsn"

CLASSES = [
    ("pwr_phase", ["PH_A", "PH_B", "PH_C"], 800, 250, "Via[0-3]_800:400_um"),
    ("pwr_in", ["V_IN", "PNEG"], 800, 250, "Via[0-3]_800:400_um"),
    ("pwr_supply", ["+12V", "+5V"], 400, 200, "Via[0-3]_800:400_um"),
]
BASE_VIA, BIG_VIA = "Via[0-3]_600:300_um", "Via[0-3]_800:400_um"

rip = set(sys.argv[1:])
assert rip, __doc__


def q(n):
    return f'"{n}"' if re.search(r"[^A-Za-z0-9_+\-.]", n) else n


b = pcbnew.LoadBoard(BOARD)
dead = [t for t in b.GetTracks() if t.GetNetname() in rip]
for t in dead:
    b.Delete(t)
b.Save(BOARD)
print(f"ripped {len(dead)} items on {', '.join(sorted(rip))}")

assert pcbnew.ExportSpecctraDSN(b, DSN), "DSN export failed"
src = open(DSN).read()

if BIG_VIA not in src:
    m = re.search(r'    \(padstack "' + re.escape(BASE_VIA) + r'"\n.*?\n    \)\n', src, re.S)
    block = m.group(0).replace(BASE_VIA, BIG_VIA)
    block = re.sub(r"\(circle (\w+\.Cu) 600\)", r"(circle \1 800)", block)
    src = src[:m.end()] + block + src[m.end():]
    src = src.replace(f'    (via "{BASE_VIA}")\n',
                      f'    (via "{BASE_VIA}")\n    (via "{BIG_VIA}")\n')

special = [n for _, nets, *_ in CLASSES for n in nets]
all_nets = [n.GetNetname() for n in b.GetNetsByName().values()
            if n.GetNetname() and n.GetNetname() not in special]
m = re.search(r"    \(class kicad_default .*?\n    \)\n", src, re.S)
default_block = (
    f"    (class kicad_default {' '.join(q(n) for n in all_nets)}\n"
    "      (circuit\n" f'        (use_via "{BASE_VIA}")\n' "      )\n"
    "      (rule\n        (width 250)\n        (clearance 200)\n      )\n    )\n"
)
extra = ""
for name, nets, width, clr, via in CLASSES:
    extra += (f"    (class {name} {' '.join(q(n) for n in nets)}\n"
              "      (circuit\n" f'        (use_via "{via}")\n' "      )\n"
              "      (rule\n" f"        (width {width})\n" f"        (clearance {clr})\n"
              "      )\n    )\n")
src = src[:m.start()] + default_block + extra + src[m.end():]

n = src.count("(type route)")
src = src.replace("(type route)", "(type protect)")
open(DSN, "w").write(src)
print(f"protected {n} existing segments -> {DSN}")
