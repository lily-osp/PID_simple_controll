#!/usr/bin/env python3
"""Export the 4-layer DSN and inject width classes for FreeRouting.

In1.Cu is already declared (type power) on the board, so the router treats it as
a plane and will not drop signal traces on it -- that keeps the GND plane solid.
"""
import re
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "bldc_esp32_driver.kicad_pcb"
DSN = "/tmp/opencode/c4.dsn"

CLASSES = [
    ("pwr_phase", ["PH_A", "PH_B", "PH_C"], 800, 250, "Via[0-3]_800:400_um"),
    ("pwr_in",    ["V_IN", "PNEG"], 800, 250, "Via[0-3]_800:400_um"),
    ("pwr_supply", ["+12V", "+5V"], 400, 200, "Via[0-3]_800:400_um"),
]
BASE_VIA = "Via[0-3]_600:300_um"
BIG_VIA = "Via[0-3]_800:400_um"


def q(name):
    return f'"{name}"' if re.search(r"[^A-Za-z0-9_+\-.]", name) else name


b = pcbnew.LoadBoard(BOARD)
assert pcbnew.ExportSpecctraDSN(b, DSN), "DSN export failed"
src = open(DSN).read()

# ---- extra via padstack for the wide classes ---------------------------------
if BIG_VIA not in src:
    m = re.search(r'    \(padstack "' + re.escape(BASE_VIA) + r'"\n.*?\n    \)\n', src, re.S)
    assert m, "base padstack not found"
    block = m.group(0).replace(BASE_VIA, BIG_VIA)
    block = re.sub(r"\(circle (\w+\.Cu) 600\)", r"(circle \1 800)", block)
    src = src[:m.end()] + block + src[m.end():]
    src = src.replace(f'    (via "{BASE_VIA}")\n',
                      f'    (via "{BASE_VIA}")\n    (via "{BIG_VIA}")\n')

special = [n for _, nets, *_ in CLASSES for n in nets]
all_nets = [n.GetNetname() for n in b.GetNetsByName().values()
            if n.GetNetname() and n.GetNetname() not in special]

m = re.search(r"    \(class kicad_default .*?\n    \)\n", src, re.S)
assert m, "default class not found"
default_block = (
    f"    (class kicad_default {' '.join(q(n) for n in all_nets)}\n"
    "      (circuit\n"
    f'        (use_via "{BASE_VIA}")\n'
    "      )\n"
    "      (rule\n"
    "        (width 250)\n"
    "        (clearance 200)\n"
    "      )\n"
    "    )\n"
)
extra = ""
for name, nets, width, clr, via in CLASSES:
    extra += (
        f"    (class {name} {' '.join(q(n) for n in nets)}\n"
        "      (circuit\n"
        f'        (use_via "{via}")\n'
        "      )\n"
        "      (rule\n"
        f"        (width {width})\n"
        f"        (clearance {clr})\n"
        "      )\n"
        "    )\n"
    )
src = src[:m.start()] + default_block + extra + src[m.end():]

open(DSN, "w").write(src)
print(f"DSN ready: {DSN}")
print(f"  {len(all_nets)} default nets @0.25mm, {len(CLASSES)} width classes")
for name, nets, width, clr, _ in CLASSES:
    print(f"  {name:<11} {width/1000:.2f}mm / clr {clr/1000:.2f}  {' '.join(nets)}")
layers = re.findall(r"\(layer (\S+)\n      \(type (\w+)\)", src)
print("  layers:", ", ".join(f"{n}({t})" for n, t in layers))
