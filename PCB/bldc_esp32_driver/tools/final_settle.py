#!/usr/bin/env python3
"""Iterate DRC -> revert offending widened traces -> refill until the copper is
DRC-clean. Operates on the already-widened board; only ever narrows traces back
to the width the approved routing used.
"""
import re
import subprocess
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "bldc_esp32_driver.kicad_pcb"
RPT = "/tmp/opencode/drc-settle.rpt"
MM = 1_000_000
TARGETS = {
    "PH_A": 0.80, "PH_B": 0.80, "PH_C": 0.80,
    "V_IN": 0.80, "PNEG": 0.80,
    "+12V": 0.60, "+5V": 0.60, "+3.3V": 0.40,
    "GND": 0.50,
}
COPPER = ("clearance", "shorting", "hole", "copper_edge")


def drc():
    subprocess.run(["kicad-cli", "pcb", "drc", "--output", RPT, "--severity-all", BOARD],
                   check=True, capture_output=True)
    text = open(RPT).read()
    points, other = [], {}
    cur = None
    for line in text.splitlines():
        m = re.match(r"\[(\w+)\]:", line.strip())
        if m:
            cur = m.group(1)
            if not any(k in cur for k in COPPER):
                other[cur] = other.get(cur, 0) + 1
            continue
        if cur and any(k in cur for k in COPPER):
            c = re.search(r"@\(([-\d.,]+) mm, ([-\d.,]+) mm\)", line)
            if c:
                points.append((float(c.group(1).replace(",", ".")),
                               float(c.group(2).replace(",", "."))))
    return points, other


board = pcbnew.LoadBoard(BOARD)
cands = [t for t in board.GetTracks()
         if t.Type() == pcbnew.PCB_TRACE_T and t.GetNetname() in TARGETS]

for it in range(1, 9):
    points, other = drc()
    if not points:
        print(f"iteration {it}: copper DRC clean  (other: {other or 'none'})")
        break
    reverted = 0
    for t in cands:
        seg = pcbnew.SEG(t.GetStart(), t.GetEnd())
        for px, py in points:
            if seg.Distance(pcbnew.VECTOR2I(int(px * MM), int(py * MM))) < 1.2 * MM:
                # step down to the next lower standard width
                w = round(t.GetWidth() / MM, 2)
                nxt = 0.25 if w <= 0.30 else (0.50 if w <= 0.55 else 0.60 if w <= 0.65 else 0.80)
                t.SetWidth(int(round(nxt * MM)))
                reverted += 1
                break
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    print(f"iteration {it}: {len(points)} copper points, narrowed {reverted} traces")

print("\nfinal widths:")
totals = {}
for t in board.GetTracks():
    if t.Type() != pcbnew.PCB_TRACE_T:
        continue
    n = t.GetNetname()
    totals.setdefault(n, {}).setdefault(round(t.GetWidth() / MM, 2), 0)
    totals[n][round(t.GetWidth() / MM, 2)] += 1
for n in ("PH_A", "PH_B", "PH_C", "V_IN", "PNEG", "+12V", "+5V", "GND"):
    if n in totals:
        print(f"  {n:<6} {dict(sorted(totals[n].items()))}")
