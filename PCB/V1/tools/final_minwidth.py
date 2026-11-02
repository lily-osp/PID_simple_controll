#!/usr/bin/env python3
"""Raise the *minimum* copper width on the motor phase nets.

Current capacity is set by the narrowest section of a net, so this pass works in
fine 0.05 mm stages on the phase nets only, remembers the last width the DRC
accepted for each trace, and reverts offenders to it. Monotone: a trace never
goes back below a width it has already passed at.
"""
import re
import subprocess
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "bldc_esp32_driver.kicad_pcb"
RPT = "/tmp/opencode/drc-minw.rpt"
MM = 1_000_000
NETS = {"PH_A", "PH_B", "PH_C"}
STAGES = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.70, 0.80]
COPPER = ("clearance", "shorting", "hole", "copper_edge")


def drc():
    subprocess.run(["kicad-cli", "pcb", "drc", "--output", RPT, "--severity-all", BOARD],
                   check=True, capture_output=True)
    text = open(RPT).read()
    pts, cur = [], None
    for line in text.splitlines():
        m = re.match(r"\[(\w+)\]:", line.strip())
        if m:
            cur = m.group(1)
            continue
        if cur and any(k in cur for k in COPPER):
            c = re.search(r"@\(([-\d.,]+) mm, ([-\d.,]+) mm\)", line)
            if c:
                pts.append((float(c.group(1).replace(",", ".")),
                            float(c.group(2).replace(",", "."))))
    return pts


board = pcbnew.LoadBoard(BOARD)
cands = [t for t in board.GetTracks()
         if t.Type() == pcbnew.PCB_TRACE_T and t.GetNetname() in NETS]
held = {id(t): t.GetWidth() / MM for t in cands}
print(f"{len(cands)} phase traces, start min width "
      f"{min(t.GetWidth() for t in cands)/MM:.2f}mm")

for stage in STAGES:
    raised = 0
    for t in cands:
        if t.GetWidth() / MM < stage - 1e-9:
            t.SetWidth(int(round(stage * MM)))
            raised += 1
    if not raised:
        continue
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)

    pts = drc()
    if not pts:
        for t in cands:
            held[id(t)] = t.GetWidth() / MM
        print(f"stage {stage:.2f}: {raised} raised, DRC clean")
        continue

    reverted = 0
    for t in cands:
        seg = pcbnew.SEG(t.GetStart(), t.GetEnd())
        for px, py in pts:
            if seg.Distance(pcbnew.VECTOR2I(int(px * MM), int(py * MM))) < 1.2 * MM:
                t.SetWidth(int(round(held[id(t)] * MM)))
                reverted += 1
                break
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())
    board.Save(BOARD)
    print(f"stage {stage:.2f}: {raised} raised, {reverted} reverted to held width, {len(pts)} pts")

board.Save(BOARD)
print("\nphase width summary:")
for n in ("PH_A", "PH_B", "PH_C"):
    segs = [t for t in board.GetTracks() if t.GetNetname() == n and t.Type() == pcbnew.PCB_TRACE_T]
    L = [t.GetLength() / MM for t in segs]
    W = [t.GetWidth() / MM for t in segs]
    print(f"  {n}: min {min(W):.2f}  avg {sum(l*w for l, w in zip(L, W))/sum(L):.2f}  max {max(W):.2f}")
