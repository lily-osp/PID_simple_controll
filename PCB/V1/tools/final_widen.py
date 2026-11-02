#!/usr/bin/env python3
"""Widen current-carrying traces as far as the layout allows, using the DRC as
the oracle: try descending width targets, keep what passes, back off the traces
that violate. Keeps the approved routing topology untouched.
"""
import re
import subprocess
import sys

sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "bldc_esp32_driver.kicad_pcb"
RPT = "/tmp/opencode/drc-widen.rpt"
MM = 1_000_000

TARGETS = {
    "PH_A": 0.80, "PH_B": 0.80, "PH_C": 0.80,
    "V_IN": 0.80, "PNEG": 0.80,
    "+12V": 0.60, "+5V": 0.60, "+3.3V": 0.40,
    "GND": 0.50,
}
STAGES = [0.80, 0.70, 0.60, 0.50, 0.45, 0.40, 0.35, 0.30]
COPPER_VIOLATIONS = ("clearance", "shorting", "hole", "copper_edge", "track", "via")


def run_drc():
    subprocess.run(
        ["kicad-cli", "pcb", "drc", "--output", RPT, "--severity-all", BOARD],
        check=True, capture_output=True,
    )
    return parse(RPT)


def parse(path):
    """Return (copper_violation_points, counts) from a DRC report."""
    text = open(path).read()
    points, counts = [], {}
    current = None
    for line in text.splitlines():
        m = re.match(r"\[(\w+)\]:", line.strip())
        if m:
            current = m.group(1)
            counts[current] = counts.get(current, 0) + 1
            continue
        if current and any(k in current for k in COPPER_VIOLATIONS):
            c = re.search(r"@\(([-\d.,]+) mm, ([-\d.,]+) mm\)", line)
            if c:
                # DRC reports use the system locale decimal separator
                px = float(c.group(1).replace(",", "."))
                py = float(c.group(2).replace(",", "."))
                points.append((px, py))
    return points, counts


def refill(board):
    pcbnew.ZONE_FILLER(board).Fill(board.Zones())


board = pcbnew.LoadBoard(BOARD)
cands = [t for t in board.GetTracks()
         if t.Type() == pcbnew.PCB_TRACE_T and t.GetNetname() in TARGETS]
print(f"{len(cands)} candidate traces across {len(TARGETS)} nets")

held = {id(t): t.GetWidth() / MM for t in cands}

for stage in STAGES:
    changed = 0
    for t in cands:
        want = min(stage, TARGETS[t.GetNetname()])
        if t.GetWidth() / MM < want - 1e-9:
            t.SetWidth(int(round(want * MM)))
            changed += 1
    if not changed:
        continue
    refill(board)
    board.Save(BOARD)

    points, counts = run_drc()
    copper = {k: v for k, v in counts.items() if any(x in k for x in COPPER_VIOLATIONS)}
    print(f"stage {stage:.2f}mm: {changed} raised, copper violations {copper or 'none'}")

    if not points:
        for t in cands:
            held[id(t)] = t.GetWidth() / MM
        continue

    # back off every candidate near a reported copper violation
    reverted = 0
    for t in cands:
        s, e = t.GetStart(), t.GetEnd()
        for px, py in points:
            P = pcbnew.VECTOR2I(int(px * MM), int(py * MM))
            seg = pcbnew.SEG(s, e)
            if seg.Distance(P) < 1.2 * MM:
                t.SetWidth(int(round(held[id(t)] * MM)))
                reverted += 1
                break
    print(f"   backed off {reverted} traces")
    refill(board)
    board.Save(BOARD)

board.Save(BOARD)
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
