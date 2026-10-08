#!/usr/bin/env python3
"""Measure window glass in an elevation drawing (PDF, scale 1:50).

Glass in the project drawings is filled light grey, so every grey, mostly filled rectangle
is a pane. The script renders the page, finds those rectangles and prints them in metres.

Usage:
    python3 measure_elevations.py DRAWING.pdf --x0 PX --y0 PX [--rotate] [--flip-x] [--scale 50] [--dpi 200]

    --x0   pixel column of the reference wall edge (x = 0 m) in the rendered page
    --y0   pixel row of the 0,000 level in the rendered page
    --rotate   rotate the page 90° counter-clockwise first (gable views and sections are drawn sideways)
    --flip-x   measure x leftwards from --x0 (for views seen from the opposite side)

How the values in the model were calibrated (200 dpi, 1:50 → 157.48 px per metre):
    D11B110 pohled JZ:  --x0 533  --y0 1526            (west wall, 0,000)
    D11B110 pohled SV:  --x0 1806 --y0 3065 --flip-x   (east wall seen from the north; x_world = 14,9 − x)
    D11B111 pohled SZ:  --rotate --x0 721  --y0 1490   (x is z from the north wall)
    D11B112 pohled JV:  --rotate --x0 2232 --y0 1477 --flip-x
Requires: poppler-utils (pdftoppm), Pillow, numpy, scipy.
"""
import argparse, subprocess, tempfile, os
import numpy as np
from PIL import Image
from scipy import ndimage

ap = argparse.ArgumentParser()
ap.add_argument('pdf')
ap.add_argument('--x0', type=float, required=True)
ap.add_argument('--y0', type=float, required=True)
ap.add_argument('--rotate', action='store_true')
ap.add_argument('--flip-x', action='store_true')
ap.add_argument('--scale', type=float, default=50)
ap.add_argument('--dpi', type=int, default=200)
a = ap.parse_args()

Image.MAX_IMAGE_PIXELS = None
with tempfile.TemporaryDirectory() as t:
    subprocess.run(['pdftoppm', '-r', str(a.dpi), '-png', '-singlefile', a.pdf, os.path.join(t, 'p')], check=True,
                   stderr=subprocess.DEVNULL)
    im = Image.open(os.path.join(t, 'p.png')).convert('L')
if a.rotate:
    im = im.rotate(90, expand=True)
g = np.array(im)
ppm = a.dpi / 25.4 * 1000 / a.scale          # pixels per metre on the drawing
lab, _ = ndimage.label((g > 185) & (g < 240))
rows = []
for i, s in enumerate(ndimage.find_objects(lab)):
    h, w = s[0].stop - s[0].start, s[1].stop - s[1].start
    if w > 25 and h > 25 and (lab[s] == i + 1).mean() > 0.6:
        x1, x2 = (s[1].start - a.x0) / ppm, (s[1].stop - a.x0) / ppm
        if a.flip_x:
            x1, x2 = -x2, -x1
        y1, y2 = (a.y0 - s[0].stop) / ppm, (a.y0 - s[0].start) / ppm
        rows.append((x1, x2, y1, y2))
print(f'{ppm:.2f} px/m, {len(rows)} panes (x from reference edge, y from 0,000), metres:')
for x1, x2, y1, y2 in sorted(rows):
    print(f'  x {x1:6.2f} – {x2:6.2f}   y {y1:5.2f} – {y2:5.2f}   ({x2 - x1:.2f} × {y2 - y1:.2f})')
