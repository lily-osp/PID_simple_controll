#!/usr/bin/env python3
"""Set up net classes (wide traces for power) + export DSN for FreeRouting."""
import sys
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "/home/azzar/project/microcontrollers/03_projects/pids/pid-simple-controll/PCB/bldc_esp32_driver/bldc_esp32_driver.kicad_pcb"
board = pcbnew.LoadBoard(BOARD)
ncs = board.GetNetClasses()

def ensure(name, width, clearance, via_d, via_drill):
    if name in ncs:
        c = ncs[name]
    else:
        c = pcbnew.NETCLASS(name)
        ncs[name] = c
    c.SetTrackWidth(int(width * 1e6))
    c.SetClearance(int(clearance * 1e6))
    c.SetViaDiameter(int(via_d * 1e6))
    c.SetViaDrill(int(via_drill * 1e6))
    return c

ensure("Default", 0.25, 0.2, 0.6, 0.3)
power = ensure("POWER", 1.5, 0.35, 1.0, 0.5)
supply = ensure("SUPPLY", 0.6, 0.3, 0.8, 0.4)

POWER_NETS = {"V_IN", "GND", "PNEG", "PH_A", "PH_B", "PH_C"}
SUPPLY_NETS = {"+12V", "+5V", "+3.3V"}

counts = {}
for net in board.GetNetsByName().values():
    name = net.GetNetname()
    if name in POWER_NETS:
        net.SetNetClass(power); counts["POWER"] = counts.get("POWER", 0) + 1
    elif name in SUPPLY_NETS:
        net.SetNetClass(supply); counts["SUPPLY"] = counts.get("SUPPLY", 0) + 1
    else:
        counts["Default"] = counts.get("Default", 0) + 1
print("net class assignment:", counts)

board.Save(BOARD)
print("saved")

ok = pcbnew.ExportSpecctraDSN(board, "/tmp/opencode/board.dsn")
print("DSN export:", ok)
