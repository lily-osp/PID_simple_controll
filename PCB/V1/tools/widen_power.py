#!/usr/bin/env python3
"""Widen V_IN / PNEG / phase traces to 0.8mm where clearance allows."""
import sys, math
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew

BOARD = "/home/azzar/project/microcontrollers/03_projects/pids/pid-simple-controll/PCB/bldc_esp32_driver/bldc_esp32_driver.kicad_pcb"
b = pcbnew.LoadBoard(BOARD)
TARGET = {"V_IN", "PNEG", "PH_A", "PH_B", "PH_C"}
WIDE = 0.8

def pdist(x1,y1,x2,y2,px,py):
    dx,dy=x2-x1,y2-y1; L2=dx*dx+dy*dy
    if L2<1e-12: return math.hypot(px-x1,py-y1)
    t=max(0.0,min(1.0,((px-x1)*dx+(py-y1)*dy)/L2))
    return math.hypot(px-(x1+t*dx),py-(y1+t*dy))

obs = []
for t in b.GetTracks():
    s,e=t.GetStart(),t.GetEnd()
    if t.Type() == pcbnew.PCB_VIA_T:
        hw = 0.3  # via half-width (0.6mm dia)
    else:
        hw = t.GetWidth()/2e6
    obs.append((t.GetNetCode(),s.x/1e6,s.y/1e6,e.x/1e6,e.y/1e6,hw))
for fp in b.GetFootprints():
    for p in fp.Pads():
        pos=p.GetPosition(); sz=p.GetSize()
        obs.append((p.GetNetCode(),pos.x/1e6,pos.y/1e6,pos.x/1e6,pos.y/1e6,min(sz.x,sz.y)/2e6))

CLEAR=0.2
def ok_widen(n, x1,y1,x2,y2, half):
    for (oc,ox1,oy1,ox2,oy2,ohw) in obs:
        if oc==n: continue
        req=half+ohw+CLEAR
        for t in (0.0,0.25,0.5,0.75,1.0):
            px,py=x1+(x2-x1)*t,y1+(y2-y1)*t
            if pdist(ox1,oy1,ox2,oy2,px,py)<req: return False
    return True

# widen traces (skip segments touching a TSSOP/DFN pad: those must stay thin)
widened = 0
for t in list(b.GetTracks()):
    if t.Type() != pcbnew.PCB_TRACE_T: continue
    if t.GetNetname() not in TARGET: continue
    s,e=t.GetStart(),t.GetEnd()
    x1,y1,x2,y2=s.x/1e6,s.y/1e6,e.x/1e6,e.y/1e6
    if t.GetWidth()/1e6 >= WIDE - 0.05: continue
    if ok_widen(t.GetNetCode(), x1,y1,x2,y2, WIDE/2):
        t.SetWidth(int(WIDE*1e6)); widened += 1
print("widened traces:", widened)
b.Save(BOARD)
