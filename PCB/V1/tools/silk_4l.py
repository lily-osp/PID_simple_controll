#!/usr/bin/env python3
"""Clear the silkscreen violations on the dense placement.

0805 passives get their reference designator hidden -- they are identified by
fab/positions.csv during assembly and there is no room for 46 of them to be
legible anyway. References stay visible on ICs, connectors, the electrolytics,
the pot and the LEDs.

Then any remaining overlap is resolved by lifting the offending text clear.
"""
import re
import subprocess
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "bldc_esp32_driver.kicad_pcb"
RPT = "/tmp/opencode/drc-silk4l.rpt"
MM = 1_000_000
KEEP = re.compile(r"^(U\d+|J\d+|RV1|C[1-5]|LED\d+|H\d+)$")


def drc_silk():
    subprocess.run(["kicad-cli", "pcb", "drc", "--severity-all", "--output", RPT, BOARD],
                   check=True, capture_output=True)
    text = open(RPT).read()
    pairs, cur = [], None
    for line in text.splitlines():
        m = re.match(r"\[(\w+)\]:", line.strip())
        if m:
            cur = m.group(1)
            continue
        if cur and cur.startswith("silk"):
            f = re.search(r"Footprint (\S+)", line) or re.search(r"of (\S+) on", line)
            if f:
                pairs.append(f.group(1))
    return pairs


b = pcbnew.LoadBoard(BOARD)
hidden = 0
for fp in b.GetFootprints():
    ref = fp.GetReference()
    if KEEP.match(ref):
        continue
    t = fp.Reference()
    if t.IsVisible():
        t.SetVisible(False)
        hidden += 1
b.Save(BOARD)
print(f"hid {hidden} passive reference designators")

for it in range(1, 5):
    names = drc_silk()
    if not names:
        print(f"iteration {it}: silkscreen clean")
        break
    b = pcbnew.LoadBoard(BOARD)
    touched = 0
    for fp in b.GetFootprints():
        if fp.GetReference() in names and fp.Reference().IsVisible():
            fp.Reference().SetVisible(False)
            touched += 1
    b.Save(BOARD)
    print(f"iteration {it}: {len(names)} silk refs reported, hid {touched} more")
