#!/usr/bin/env python3
"""Add GND copper pour on F.Cu + B.Cu, refill zones."""
import sys
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "/home/azzar/project/microcontrollers/03_projects/pids/pid-simple-controll/PCB/bldc_esp32_driver/bldc_esp32_driver.kicad_pcb"
b = pcbnew.LoadBoard(BOARD)

gnd = None
for net in b.GetNetsByName().values():
    if net.GetNetname() == "GND":
        gnd = net
        break
assert gnd is not None, "GND net not found"

# board outline 70 x 120, inset 0.5 mm for zone (edge clearance handled by DRC anyway)
INSET = 0.25e6
W, H = 70e6, 120e6
pts = [
    pcbnew.VECTOR2I(int(INSET), int(INSET)),
    pcbnew.VECTOR2I(int(W - INSET), int(INSET)),
    pcbnew.VECTOR2I(int(W - INSET), int(H - INSET)),
    pcbnew.VECTOR2I(int(INSET), int(H - INSET)),
]

for layer in (pcbnew.F_Cu, pcbnew.B_Cu):
    z = pcbnew.ZONE(b)
    z.SetLayer(layer)
    z.SetNetCode(gnd.GetNetCode())
    z.SetLocalClearance(int(0.3e6))          # pour clearance
    z.SetMinThickness(int(0.25e6))           # min copper width
    z.SetThermalReliefGap(int(0.3e6))
    z.SetThermalReliefSpokeWidth(int(0.4e6))
    z.SetPadConnection(pcbnew.ZONE_CONNECTION_THERMAL)
    # outline
    poly = z.Outline()
    poly.NewOutline()
    for p in pts:
        poly.Append(int(p.x), int(p.y))
    z.SetOutline(poly)
    b.Add(z)

b.Save(BOARD)

# refill
filler = pcbnew.ZONE_FILLER(b)
filler.Fill(b.Zones())
b.Save(BOARD)
print("zones:", len(list(b.Zones())))
