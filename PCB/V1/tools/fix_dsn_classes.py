#!/usr/bin/env python3
"""Inject proper net-class width rules into the Specctra DSN before FreeRouting.
KiCad's ExportSpecctraDSN collapses every net into one kicad_default class;
this rewrites it into POWER / SUPPLY / signal classes with real widths.
"""
import re

DSN = "/tmp/opencode/board.dsn"
t = open(DSN).read()

POWER = []
SUPPLY = []
VIA = '"Via[0-1]_600:300_um"'

# extract the net list of the kicad_default class
m = re.search(r'\(class kicad_default (.*?)\n\s*\(circuit', t, re.S)
assert m, "kicad_default class not found"
nets = m.group(1).split()
power_nets = [n for n in nets if n in POWER]
supply_nets = [n for n in nets if n in SUPPLY]
signal_nets = [n for n in nets if n not in POWER and n not in SUPPLY]

def cls(name, netlist, width, clearance):
    return (f'    (class {name} ' + ' '.join(netlist) + "\n"
            f'      (circuit\n        (use_via {VIA})\n      )\n'
            f'      (rule\n        (width {width})\n        (clearance {clearance})\n      )\n    )')

blocks = []
if power_nets:
    blocks.append(cls("POWER", power_nets, 800, 300))
if supply_nets:
    blocks.append(cls("SUPPLY", supply_nets, 600, 300))
blocks.append(cls("kicad_default", signal_nets, 250, 200))

new_class_section = "\n".join(blocks)

# replace the original class block (from '(class kicad_default' up to its matching close)
start = t.index("(class kicad_default")
# find the matching close: the block ends with "\n    )\n  )" before "(wiring"
end = t.index("  (wiring", start)
t = t[:start] + new_class_section + "\n" + t[end:]

# also bump the global structure rule width to 250 (default signal)
t = t.replace("    (rule\n      (width 200)\n      (clearance 200)", "    (rule\n      (width 250)\n      (clearance 200)")

open(DSN, "w").write(t)
print(f"POWER {len(power_nets)} nets, SUPPLY {len(supply_nets)} nets, signal {len(signal_nets)} nets")
print("DSN rewritten")
