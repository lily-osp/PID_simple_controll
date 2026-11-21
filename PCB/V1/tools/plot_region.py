#!/usr/bin/env python3
"""Quick PNG plot of a board window (tracks, vias, pads, refs) for visual review.

Usage: plot_region.py <board.kicad_pcb> <out.png> x0 y0 x1 y1 [scale_px_per_mm]
"""
import sys
sys.path.insert(0, "/usr/lib/python3/dist-packages")
import pcbnew
from PIL import Image, ImageDraw

BOARD, OUT = sys.argv[1], sys.argv[2]
X0, Y0, X1, Y1 = (float(v) for v in sys.argv[3:7])
S = float(sys.argv[7]) if len(sys.argv) > 7 else 40.0

LAYER_COLOR = {
    "F.Cu": (200, 40, 40), "In1.Cu": (190, 140, 40), "In2.Cu": (40, 150, 60),
    "B.Cu": (60, 90, 220),
}
b = pcbnew.LoadBoard(BOARD)
W, H = int((X1 - X0) * S), int((Y1 - Y0) * S)
img = Image.new("RGB", (W, H), (18, 18, 18))
d = ImageDraw.Draw(img, "RGBA")


def px(x, y):
    return ((x - X0) * S, (y - Y0) * S)


for t in b.GetTracks():
    if t.GetClass() == "PCB_VIA":
        p = t.GetPosition()
        x, y = px(p.x / 1e6, p.y / 1e6)
        r = t.GetWidth(pcbnew.F_Cu) / 2e6 * S
        d.ellipse([x - r, y - r, x + r, y + r], fill=(230, 230, 230))
        continue
    col = LAYER_COLOR.get(b.GetLayerName(t.GetLayer()), (120, 120, 120))
    s, e = t.GetStart(), t.GetEnd()
    d.line([px(s.x / 1e6, s.y / 1e6), px(e.x / 1e6, e.y / 1e6)],
           fill=col + (200,), width=max(1, int(t.GetWidth() / 1e6 * S)))

for fp in b.GetFootprints():
    for p in fp.Pads():
        c = p.GetPosition()
        w, h = p.GetSizeX() / 2e6 * S, p.GetSizeY() / 2e6 * S
        x, y = px(c.x / 1e6, c.y / 1e6)
        d.rectangle([x - w, y - h, x + w, y + h], outline=(255, 215, 0), width=1,
                    fill=(255, 215, 0, 70))
    fc = fp.GetPosition()
    fx, fy = px(fc.x / 1e6, fc.y / 1e6)
    if -20 < fx < W + 20 and -20 < fy < H + 20:
        d.text((fx + 2, fy + 2), fp.GetReference(), fill=(255, 255, 255))

for x in range(int(X0), int(X1) + 1, 5):
    d.line([px(x, Y0), px(x, Y1)], fill=(60, 60, 60), width=1)
    d.text(px(x, Y0 + 0.3), str(x), fill=(140, 140, 140))
for y in range(int(Y0), int(Y1) + 1, 5):
    d.line([px(X0, y), px(X1, y)], fill=(60, 60, 60), width=1)
    d.text(px(X0 + 0.2, y), str(y), fill=(140, 140, 140))

img.save(OUT)
print(f"{OUT}  {W}x{H}px  window ({X0},{Y0})-({X1},{Y1}) mm")
