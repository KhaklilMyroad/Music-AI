# -*- coding: utf-8 -*-
"""Sunset Frames — Nokdim: CAD plot set generator.
One geometry model -> 11 PDF sheets (A3) + DXF for AutoCAD.
Coordinates: X across front (S- / N+), Y depth (cliff -8, frames Y=0, stage 2..10), Z up. Meters.
"""
import math
from matplotlib.backends.backend_pdf import PdfPages
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ---------------- Master data ----------------
FX = [-12.84, -8.56, -4.28, 0.0, 4.28, 8.56, 12.84]
FH = [5.5, 7.0, 8.5, 10.0, 8.5, 7.0, 5.5]
FN = ['F1', 'F2', 'F3', 'F4', 'F5', 'F6', 'F7']
CH = 0.29            # truss chord width
SPAN = 2.5           # clear span
LEG_IN = SPAN / 2    # 1.25
LEG_C = LEG_IN + CH / 2
LEG_OUT = LEG_IN + CH
BASE_Z = 0.21        # steel base + spacer
PIPES = {0: [3.2], 1: [3.0, 5.0], 2: [3.5, 6.0], 3: [4.0, 7.0], 4: [3.5, 6.0], 5: [3.0, 5.0], 6: [3.2]}
MP_H = {0: [4.0], 1: [5.5], 2: [6.5], 3: [3.5, 7.5], 4: [6.5], 5: [5.5], 6: [4.0]}
LB_OFF = {2: [-0.8, 0.0, 0.8], 1: [-0.5, 0.5]}
LEG_SEGS = {0: [3, 2], 1: [3, 2, 1, .5], 2: [3, 3, 2], 3: [3, 3, 2, 1, .5], 4: [3, 3, 2], 5: [3, 2, 1, .5], 6: [3, 2]}
PA_FRAMES = [2, 4]   # F3, F5
STAGE = (-6, 6, 2, 10, 0, 1)        # x0,x1,y0,y1,z0,z1
RISER = (-1.5, 1.5, 2.5, 4.5, 1.0, 1.4)
SUB_X = [-3.75, -2.25, -0.75, 0.75, 2.25, 3.75]
SUB = (1.35, 0.75, 0.75)            # w,d,h
SUB_Y = 10.4
FOH = (-2, 2, 34, 37)
CLIFF_Y = -8.0

LCOL = {  # layer -> (matplotlib color, ACI color)
    'TRUSS': ('0.45', 8), 'STAGE': ('0.15', 250), 'STAGEFILL': ('0.25', 251),
    'PIPE': ('0.55', 9), 'MP': ('#1f4fd8', 5), 'JDC': ('#e619c3', 6),
    'LB': ('#9b6fe0', 200), 'MOLE': ('#e6d800', 2), 'TYP': ('#7ac943', 3),
    'PA': ('0.1', 250), 'DIM': ('0.2', 1), 'TXT': ('0.1', 7), 'SITE': ('0.35', 4),
}

# ---------------- primitive emitters ----------------
class P:
    def __init__(self): self.items = []
    def line(self, x1, y1, x2, y2, layer='TRUSS', lw=0.7):
        self.items.append(dict(k='l', p=(x1, y1, x2, y2), layer=layer, lw=lw))
    def rect(self, x, y, w, h, layer='TRUSS', fill=False, lw=0.7):
        self.items.append(dict(k='r', p=(x, y, w, h), layer=layer, fill=fill, lw=lw))
    def circle(self, x, y, r, layer='TXT', fill=True, lw=0.7):
        self.items.append(dict(k='c', p=(x, y, r), layer=layer, fill=fill, lw=lw))
    def poly(self, pts, layer='TRUSS', fill=False, lw=0.7):
        self.items.append(dict(k='p', p=pts, layer=layer, fill=fill, lw=lw))
    def text(self, x, y, s, size=7, layer='TXT', ha='center', rot=0):
        self.items.append(dict(k='t', p=(x, y), s=s, size=size, layer=layer, ha=ha, rot=rot))
    def dim(self, x1, y1, x2, y2, label, off=0.6, size=6.5):
        # simple linear dimension with ticks
        if abs(y1 - y2) < 1e-9:  # horizontal
            yd = y1 - off
            self.line(x1, y1, x1, yd - 0.1, 'DIM', 0.5); self.line(x2, y2, x2, yd - 0.1, 'DIM', 0.5)
            self.line(x1, yd, x2, yd, 'DIM', 0.5)
            self.text((x1 + x2) / 2, yd - 0.45, label, size, 'DIM')
        else:  # vertical
            xd = x1 + off
            self.line(x1, y1, xd + 0.1, y1, 'DIM', 0.5); self.line(x2, y2, xd + 0.1, y2, 'DIM', 0.5)
            self.line(xd, y1, xd, y2, 'DIM', 0.5)
            self.text(xd + 0.35, (y1 + y2) / 2, label, size, 'DIM', rot=90)

def truss_front(p, xc, z0, z1, w=CH, joints=None):
    """vertical truss member, front/side view: chords + zigzag + joint ticks"""
    xl, xr = xc - w / 2, xc + w / 2
    p.line(xl, z0, xl, z1); p.line(xr, z0, xr, z1)
    z, i = z0, 0
    step = 0.5
    while z + step <= z1 + 1e-6:
        if i % 2 == 0: p.line(xl, z, xr, z + step, lw=0.4)
        else: p.line(xr, z, xl, z + step, lw=0.4)
        z += step; i += 1
    if joints:
        zj = z0
        for s in joints[:-1]:
            zj += s
            p.line(xl - 0.05, zj, xr + 0.05, zj, lw=1.0)

def truss_horiz(p, x0, x1, zt, w=CH):
    zb = zt - w
    p.line(x0, zb, x1, zb); p.line(x0, zt, x1, zt)
    x, i = x0, 0
    while x + 0.5 <= x1 + 1e-6:
        if i % 2 == 0: p.line(x, zb, x + 0.5, zt, lw=0.4)
        else: p.line(x, zt, x + 0.5, zb, lw=0.4)
        x += 0.5; i += 1

def frame_front(p, i, fixtures=True, pa=True, seg_labels=False):
    fx, H = FX[i], FH[i]
    for s in (-1, 1):
        xc = fx + s * LEG_C
        p.rect(xc - 0.4, 0, 0.8, 0.05, 'TRUSS')                       # base plate
        p.rect(xc - CH / 2, 0.05, CH, BASE_Z - 0.05, 'TRUSS')         # stub+spacer
        truss_front(p, xc, BASE_Z, H - CH, joints=LEG_SEGS[i])
        p.rect(xc - CH / 2, H - CH, CH, CH, 'TRUSS', lw=1.0)          # box corner
        if seg_labels:
            zj, segs = BASE_Z, LEG_SEGS[i]
            for sgl in segs:
                p.text(xc + s * 0.55, zj + sgl / 2, f'{sgl:.1f}', 5.5, 'DIM', rot=90)
                zj += sgl
    truss_horiz(p, fx - LEG_IN, fx + LEG_IN, H)                        # span
    for zp in PIPES[i]:                                                # internal pipes
        p.line(fx - LEG_IN, zp, fx + LEG_IN, zp, 'PIPE', 1.3)
    p.text(fx, H + 0.45, FN[i], 8, 'TXT')
    if pa and i in PA_FRAMES:
        for k in range(8):
            zk = 7.5 - k * 0.26
            wk = 0.55 + k * 0.012
            p.rect(fx - wk, zk - 0.24, 2 * wk, 0.22, 'PA', fill=True, lw=0.3)
        p.line(fx, H - CH, fx, 7.5, 'PA', 0.8)
    if fixtures:
        for s in (-1, 1):
            for zm in MP_H[i]:                                         # MegaPointe on legs (outside)
                x = fx + s * (LEG_OUT + 0.28)
                p.circle(x, zm, 0.24, 'MP'); p.rect(x - 0.13, zm - 0.4, 0.26, 0.18, 'MP', fill=True, lw=0.3)
            p.rect(fx + s * LEG_C - 0.16, 2.5 - 0.16, 0.32, 0.32, 'MOLE', fill=True)   # Molefay
            for dx in (0.95, 1.6):                                     # Typhoon uplights at base
                p.circle(fx + s * dx, 0.14, 0.13, 'TYP')
        njdc = 2 if i == 3 else 1
        for xo in ([-0.6, 0.6] if njdc == 2 else [0]):                 # JDC1 on span
            p.rect(fx + xo - 0.28, FH[i] - CH + 0.02, 0.56, 0.25, 'JDC', fill=True)
        pipes, offs = PIPES[i], None
        for zp in pipes:
            n3 = (i == 3) or (zp == pipes[0] and i in (0, 2, 4, 6))
            offs = LB_OFF[2] if n3 else LB_OFF[1]
            if i in (0, 6): offs = LB_OFF[2]
            for xo in offs:
                p.circle(fx + xo, zp, 0.14, 'LB')

def view_front(fixtures=True, pa=True, seg_labels=False, dims=True):
    p = P()
    p.line(-16.5, 0, 16.5, 0, 'SITE', 1.2)                             # ground
    for i in range(7): frame_front(p, i, fixtures, pa, seg_labels)
    # stage front silhouette behind frames (dashed feel: thin)
    p.rect(STAGE[0], 0, 12, 1, 'STAGE', lw=0.9)
    p.rect(RISER[0], 1, 3, 0.4, 'STAGE', lw=0.9)
    p.rect(-1.2, 1.4, 2.4, 0.5, 'STAGE', fill=True, lw=0.4)            # DJ console
    for xs in SUB_X: p.rect(xs - SUB[0] / 2, 0, SUB[0], SUB[2], 'PA', lw=0.8)
    if dims:
        p.dim(FX[0] - LEG_OUT, 0, FX[6] + LEG_OUT, 0, '28.76', off=1.8)
        for i in (0, 1, 2, 3): p.dim(FX[i] + LEG_OUT + 0.55, 0, FX[i] + LEG_OUT + 0.55, FH[i], f'{FH[i]:.2f}', off=0.05)
        p.dim(FX[3] + LEG_OUT, 9.0, FX[4] - LEG_OUT, 9.0, '1.20', off=-0.3)
    return p, (-17.5, 17.5, -3.4, 11.6)

def view_top(scope='macro'):
    p = P()
    x0s, x1s, y0s, y1s = STAGE[0], STAGE[1], STAGE[2], STAGE[3]
    if scope in ('macro', 'rigging'):
        p.line(-17, CLIFF_Y, 17, CLIFF_Y, 'SITE', 1.4)
        p.text(0, CLIFF_Y - 0.6, 'CLIFF EDGE — KEEP OUT STRIP 2.0 m', 6.5, 'SITE')
        p.line(-17, CLIFF_Y + 2, 17, CLIFF_Y + 2, 'SITE', 0.5)
    for i, fx in enumerate(FX):                                        # frames row at Y=0
        p.rect(fx - LEG_IN - CH, -CH / 2, SPAN + 2 * CH, CH, 'TRUSS', lw=1.0)
        for s in (-1, 1):
            p.rect(fx + s * LEG_C - CH / 2, -CH / 2, CH, CH, 'TRUSS', fill=True, lw=0.4)
        p.text(fx, -0.95, FN[i], 7.5, 'TXT')
        if scope == 'rigging':
            for s in (-1, 1):                                          # ballast cradles
                p.rect(fx + s * LEG_C - 0.6, -0.6, 1.2, 1.2, 'DIM', lw=0.9)
            if i in (2, 3, 4):                                         # guys
                anch = [(-2.6, -2.6), (2.6, -2.6)] if i != 3 else [(-2.8, -2.8), (2.8, -2.8), (-4.5, -2.0), (4.5, -2.0)]
                for ax_, ay_ in anch:
                    p.line(fx, 0, fx + ax_, ay_, 'DIM', 0.6)
                    p.circle(fx + ax_, ay_, 0.15, 'DIM', fill=False)
    p.rect(x0s, y0s, 12, 8, 'STAGE', lw=1.4)                           # stage
    if scope == 'stage':
        for gx in range(-6, 7, 2): p.line(gx, y0s, gx, y1s, 'STAGE', 0.3)
        for gy in range(3, 10): p.line(x0s, gy, x1s, gy, 'STAGE', 0.3)
    p.rect(RISER[0], RISER[2], 3, 2, 'STAGE', lw=1.1); p.text(0, 5.1, 'DJ RISER 3.0 x 2.0  +0.40', 6.5, 'TXT')
    p.rect(-1.2, 3.6, 2.4, 0.6, 'STAGE', fill=(scope == 'stage'), lw=0.5)  # console
    if scope == 'stage':
        p.rect(-6, 0.8, 1.75, 1.2, 'STAGE', lw=0.8); p.text(-5.1, 1.4, 'STAIRS', 5.5, 'TXT')
        p.rect(2.8, 0.8, 3.2, 1.2, 'STAGE', lw=0.8); p.text(4.4, 1.4, 'RAMP 1:8', 5.5, 'TXT')
        p.rect(6.6, 8, 1.3, 2, 'STAGE', lw=0.8); p.text(7.25, 9, 'AMPS', 5.5, 'TXT', rot=90)
        for xw in (-2.2, 2.2): p.poly([(xw - 0.3, 4.9), (xw + 0.3, 4.9), (xw, 5.35)], 'STAGE', lw=0.6)
    for xs in SUB_X:                                                   # subs row
        p.rect(xs - SUB[0] / 2, SUB_Y, SUB[0], SUB[1], 'PA', lw=0.9)
    p.text(0, SUB_Y + 1.35, '6 x DUAL-18" SUB — CARDIOID (4+2), 1.5 m c-c', 6, 'TXT')
    if scope == 'macro':
        p.rect(FOH[0], FOH[2], 4, 3, 'SITE', lw=1.0); p.text(0, FOH[2] + 1.5, 'FOH 4x3', 6.5, 'SITE')
        p.line(-16, 22, 16, 22, 'SITE', 0.7); p.text(0, 22.6, 'AUDIENCE LINE — 12.0 m MIN FROM FRAMES', 6.5, 'SITE')
        p.dim(x0s, y1s, x1s, y1s, '12.00', off=-2.9)
        p.dim(x1s + 0.4, y0s, x1s + 0.4, y1s, '8.00', off=1.2)
        p.dim(FX[6] + 2.2, 0, FX[6] + 2.2, y0s, '2.00', off=1.2)
        p.dim(15.2, y1s, 15.2, FOH[2], '24.00', off=1.2)
        return p, (-18.5, 19.5, -10.5, 38.5)
    if scope == 'rigging':
        return p, (-18.5, 18.5, -10.5, 13.5)
    p.dim(x0s, y1s, x1s, y1s, '12.00', off=-2.9)
    p.dim(x1s + 0.4, y0s, x1s + 0.4, y1s, '8.00', off=1.7)
    return p, (-9.5, 9.5, -0.5, 13.0)

def view_side(fixtures=True):
    p = P()
    p.line(CLIFF_Y, 0, 15, 0, 'SITE', 1.2)
    p.line(CLIFF_Y, 0, CLIFF_Y - 0.01, -2.5, 'SITE', 1.2)              # cliff drop
    p.line(CLIFF_Y, -2.5, CLIFF_Y + 1.2, -3.2, 'SITE', 0.8)
    order = [3, 2, 1, 0]                                               # tallest first
    for i in order:                                                    # frames at y=0 (profiles overlap)
        H = FH[i]
        truss_front(p, 0, BASE_Z, H - CH, joints=LEG_SEGS[i])
        p.rect(-CH / 2, H - CH, CH, CH, 'TRUSS', lw=1.0)
        p.text(1.0, H - 0.05, f'{FN[i]}/{FN[6-i]} {H:.1f}' if i != 3 else f'F4 {H:.1f}', 6, 'TXT', ha='left')
    p.rect(-0.4, 0, 0.8, 0.05, 'TRUSS')
    if fixtures:
        p.rect(0.35, 7.5 - 2.1, 0.45, 2.1, 'PA', fill=True, lw=0.4)    # PA profile (east face)
        p.text(1.5, 6.4, 'KARA II x8\nTRIM 7.50', 5.5, 'TXT', ha='left')
        for zm in [3.5, 7.5]: p.circle(-0.55, zm, 0.2, 'MP')
        p.rect(-0.5, FH[3] - CH + 0.02, 0.45, 0.25, 'JDC', fill=True)
    p.rect(STAGE[2], 0, 8, 1, 'STAGE', lw=1.2)                         # stage section (y->x axis)
    for yl in range(2, 11, 2): p.line(yl, 0, yl, 1, 'STAGE', 0.4)
    p.rect(RISER[2], 1, 2, 0.4, 'STAGE', lw=0.9)
    p.rect(3.0, 1.4, 0.7, 0.5, 'STAGE', fill=True, lw=0.4)             # console
    p.line(2, 1, 2, 2.1, 'STAGE', 1.0); p.line(1.85, 2.1, 2.15, 2.1, 'STAGE', 1.0)   # rear handrail
    p.rect(SUB_Y, 0, SUB[1], SUB[2], 'PA', lw=0.9)                     # sub profile
    p.text(SUB_Y + 0.4, 1.15, 'SUBS', 5.5, 'TXT')
    p.dim(CLIFF_Y, 0, 0, 0, '8.00', off=1.2)
    p.dim(0, 0, 2, 0, '2.00', off=0.7)
    p.dim(12.6, 0, 12.6, 1, '1.00', off=0.4)
    p.dim(-1.9, 0, -1.9, FH[3], '10.00', off=0.1)
    p.text(13.8, 0.4, 'FOH @ +24.0 m →', 6, 'SITE', ha='left')
    return p, (-10.5, 16.5, -4.2, 11.6)

def iso(x, y, z):
    return (x - y) * 0.866, (x + y) * 0.5 + z

def iso_box(p, x0, x1, y0, y1, z0, z1, layer='TRUSS', lw=0.6):
    c = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0),
         (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    e = [(0, 1), (1, 2), (2, 3), (3, 0), (4, 5), (5, 6), (6, 7), (7, 4), (0, 4), (1, 5), (2, 6), (3, 7)]
    pts = [iso(*ci) for ci in c]
    for a, b in e: p.line(pts[a][0], pts[a][1], pts[b][0], pts[b][1], layer, lw)

def view_iso(fixtures=True):
    p = P()
    for i, fx in enumerate(FX):
        H = FH[i]
        for s in (-1, 1):
            xc = fx + s * LEG_C
            iso_box(p, xc - CH / 2, xc + CH / 2, -CH / 2, CH / 2, 0, H - CH, 'TRUSS', 0.5)
        iso_box(p, fx - LEG_IN - CH, fx + LEG_IN + CH, -CH / 2, CH / 2, H - CH, H, 'TRUSS', 0.6)
        xt, yt = iso(fx, 0, H + 0.4); p.text(xt, yt, FN[i], 7, 'TXT')
        for zp in PIPES[i]:
            a, b = iso(fx - LEG_IN, 0, zp), iso(fx + LEG_IN, 0, zp)
            p.line(a[0], a[1], b[0], b[1], 'PIPE', 1.1)
        if i in PA_FRAMES:
            iso_box(p, fx - 0.55, fx + 0.55, 0.15, 0.5, 5.4, 7.5, 'PA', 0.8)
        if fixtures:
            for s in (-1, 1):
                for zm in MP_H[i]:
                    cx, cy = iso(fx + s * (LEG_OUT + 0.28), 0, zm); p.circle(cx, cy, 0.2, 'MP')
                cx, cy = iso(fx + s * LEG_C, -0.2, 2.5); p.rect(cx - 0.13, cy - 0.13, 0.26, 0.26, 'MOLE', fill=True)
                for dx in (0.95, 1.6):
                    cx, cy = iso(fx + s * dx, 0, 0.12); p.circle(cx, cy, 0.11, 'TYP')
            for xo in ([-0.6, 0.6] if i == 3 else [0]):
                cx, cy = iso(fx + xo, -0.15, H - 0.1); p.rect(cx - 0.22, cy - 0.1, 0.44, 0.2, 'JDC', fill=True)
            for zp in PIPES[i]:
                offs = LB_OFF[2] if (i in (0, 3, 6) or zp == PIPES[i][0]) else LB_OFF[1]
                for xo in offs:
                    cx, cy = iso(fx + xo, 0, zp); p.circle(cx, cy, 0.12, 'LB')
    iso_box(p, STAGE[0], STAGE[1], STAGE[2], STAGE[3], 0, 1, 'STAGE', 0.9)
    iso_box(p, RISER[0], RISER[1], RISER[2], RISER[3], 1, 1.4, 'STAGE', 0.7)
    for xs in SUB_X:
        iso_box(p, xs - SUB[0] / 2, xs + SUB[0] / 2, SUB_Y, SUB_Y + SUB[1], 0, SUB[2], 'PA', 0.5)
    return p, None

# ---------------- legend / report ----------------
FIXTURES = [
    ('MP', 'Robe MegaPointe', 'Mode 1 - Standard 16-bit', 16, 470),
    ('JDC', 'GLP JDC1 Strobe', 'DMX Mode 2 (Normal)', 8, 1200),
    ('LB', 'Robe Robin LEDBeam 150', 'Mode 1 - Standard 16-bit', 30, 190),
    ('MOLE', 'James Thomas 1-light Molefay', 'Dimmer 1ch', 14, 650),
    ('TYP', 'Varitec LED Typhoon Par Outdoor', 'Mode 3 - Extended 16bit', 28, 200),
]

def draw_legend(ax, x, y, w=0.30, title='Fixtures on Stage'):
    ax.text(x + w / 2, y + 0.012, title, ha='center', size=9, weight='bold', transform=ax.transAxes)
    ax.add_patch(mpatches.Rectangle((x, y - 0.155), w, 0.16, fill=False, lw=0.8, transform=ax.transAxes))
    for j, (lay, name, mode, qty, _) in enumerate(FIXTURES):
        yy = y - 0.02 - j * 0.028
        ax.add_patch(mpatches.Rectangle((x + 0.008, yy - 0.008), 0.014, 0.016, color=LCOL[lay][0], transform=ax.transAxes))
        ax.text(x + 0.028, yy, f'{name}   |   {mode}   |   Qty: {qty}', size=6.5, va='center', transform=ax.transAxes)

# ---------------- sheet rendering ----------------
TITLE_ROWS = [('Project Name', 'Sunset Frames - Nokdim'), ('Project Date', '08/2026'),
              ('Venue', 'Nokdim Farm'), ('Address', 'Nokdim Farm, nr. Arad, Israel'),
              ('Client', '-'), ('Design Firm', '-')]

def title_block(fig, sheet_title, num, total=11, scale='NTS'):
    ax = fig.add_axes([0.55, 0.02, 0.43, 0.16]); ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')
    ax.add_patch(mpatches.Rectangle((0, 0), 1, 1, fill=False, lw=1.2))
    for fr in (1 / 6, 2 / 6, 3 / 6, 4 / 6, 5 / 6): ax.plot([0, 1], [fr, fr], color='k', lw=0.5)
    ax.plot([0.42, 0.42], [0, 1], color='k', lw=0.8)
    ax.plot([0.72, 0.72], [2 / 3, 1], color='k', lw=0.8)
    ax.plot([0.88, 0.88], [2 / 3, 1], color='k', lw=0.8)
    for j, (k, v) in enumerate(TITLE_ROWS):
        yy = 1 - (j + 0.5) / 6
        ax.text(0.015, yy, k, size=6, weight='bold', va='center')
        ax.text(0.16, yy, v, size=6, va='center')
    ax.text(0.43, 0.94, 'Sheet Title', size=6, weight='bold', va='top')
    ax.text(0.57, 0.75, sheet_title, size=10, ha='center', va='center')
    ax.text(0.73, 0.94, 'Sheet #', size=6, weight='bold', va='top')
    ax.text(0.80, 0.75, f'{num}  OF  {total}', size=8, ha='center', va='center')
    ax.text(0.89, 0.94, 'Revision', size=6, weight='bold', va='top')
    ax.text(0.94, 0.75, 'A', size=8, ha='center', va='center')
    ax.text(0.43, 0.60, 'Designed By', size=6, weight='bold', va='center')
    ax.text(0.60, 0.60, '-', size=7, va='center')
    ax.text(0.43, 0.44, 'Drawn By', size=6, weight='bold', va='center')
    ax.text(0.60, 0.44, 'Claude Code', size=7, va='center')
    ax.text(0.43, 0.24, f'Scale: {scale} @ A3   |   Units: meters   |   Coordinates per Appendix A (GA-01)', size=5.5, va='center')

def render(prims, ax):
    for it in prims.items:
        col = LCOL[it['layer']][0]
        if it['k'] == 'l':
            x1, y1, x2, y2 = it['p']; ax.plot([x1, x2], [y1, y2], color=col, lw=it['lw'])
        elif it['k'] == 'r':
            x, y, w, h = it['p']
            ax.add_patch(mpatches.Rectangle((x, y), w, h, fill=it['fill'], facecolor=col if it['fill'] else 'none',
                                            edgecolor=col, lw=it['lw']))
        elif it['k'] == 'c':
            x, y, r = it['p']
            ax.add_patch(mpatches.Circle((x, y), r, fill=it['fill'], facecolor=col if it['fill'] else 'none',
                                         edgecolor=col, lw=it['lw']))
        elif it['k'] == 'p':
            ax.add_patch(mpatches.Polygon(it['p'], closed=True, fill=it['fill'],
                                          facecolor=col if it['fill'] else 'none', edgecolor=col, lw=it['lw']))
        elif it['k'] == 't':
            x, y = it['p']; ax.text(x, y, it['s'], size=it['size'], color=col, ha=it['ha'], va='center', rotation=it['rot'])

def sheet(pdf, prims, ext, title, num, scale, view_label, legend=False, extra=None):
    fig = plt.figure(figsize=(16.54, 11.69))
    axb = fig.add_axes([0.01, 0.01, 0.98, 0.98]); axb.axis('off')
    axb.add_patch(mpatches.Rectangle((0.0, 0.0), 1, 1, fill=False, lw=1.5))
    axb.add_patch(mpatches.Rectangle((0.015, 0.015), 0.97, 0.97, fill=False, lw=0.6))
    ax = fig.add_axes([0.05, 0.2, 0.9, 0.75])
    ax.set_aspect('equal'); ax.axis('off')
    render(prims, ax)
    if ext: ax.set_xlim(ext[0], ext[1]); ax.set_ylim(ext[2], ext[3])
    axv = fig.add_axes([0.04, 0.06, 0.4, 0.08]); axv.axis('off'); axv.set_xlim(0, 1); axv.set_ylim(0, 1)
    axv.add_patch(mpatches.Circle((0.05, 0.55), 0.045, fill=False, lw=1.2))
    axv.text(0.05, 0.55, '1', ha='center', va='center', size=9)
    axv.text(0.10, 0.62, view_label, size=13, va='bottom')
    axv.plot([0.10, 0.62], [0.52, 0.52], color='k', lw=1.2)
    axv.text(0.10, 0.40, f'Scale: {scale}', size=8, va='top')
    if legend: draw_legend(axb, 0.03, 0.945)
    if extra: extra(fig, axb)
    title_block(fig, title, num, scale=scale)
    pdf.savefig(fig); plt.close(fig)

def equipment_sheet(pdf, num):
    fig = plt.figure(figsize=(16.54, 11.69))
    axb = fig.add_axes([0.01, 0.01, 0.98, 0.98]); axb.axis('off')
    axb.add_patch(mpatches.Rectangle((0, 0), 1, 1, fill=False, lw=1.5))
    axb.add_patch(mpatches.Rectangle((0.015, 0.015), 0.97, 0.97, fill=False, lw=0.6))
    def table(x, y, w, title, rows, colw, header=None, rh=0.030):
        axb.add_patch(mpatches.Rectangle((x, y - 0.035), w, 0.035, fill=True, facecolor='0.85', edgecolor='k', lw=0.8))
        axb.text(x + w / 2, y - 0.017, title, ha='center', va='center', size=9, weight='bold')
        yy = y - 0.035
        allrows = ([header] if header else []) + rows
        for r_i, row in enumerate(allrows):
            yy -= rh
            axb.add_patch(mpatches.Rectangle((x, yy), w, rh, fill=False, edgecolor='k', lw=0.5))
            xx = x
            for c_i, cell in enumerate(row):
                axb.text(xx + 0.004, yy + rh / 2, str(cell), size=6.5,
                         weight='bold' if (header and r_i == 0) else 'normal', va='center')
                xx += colw[c_i]
        return yy
    # Fixture types
    rows = [[n, m, q] for _, n, m, q, _ in FIXTURES]
    table(0.03, 0.95, 0.36, 'Fixture Types', rows, [0.17, 0.13, 0.05], header=['Fixture', 'Mode', 'Qty'])
    for j in range(len(FIXTURES)):
        axb.add_patch(mpatches.Rectangle((0.032, 0.95 - 0.035 - 0.03 * (j + 2) + 0.024), 0.010, 0.012,
                                         color=LCOL[FIXTURES[j][0]][0]))
    # Truss summary
    trows = [['HD34 3.0 m', 20, '60.0'], ['HD34 2.0 m', 21, '42.0'], ['HD34 1.0 m', 6, '6.0'],
             ['HD34 0.5 m', 13, '6.5'], ['Total', 60, '114.5']]
    table(0.44, 0.95, 0.25, 'Truss System Summary (HD34)', trows, [0.11, 0.06, 0.07], header=['Segment', 'Qty', 'Meters'])
    # Pipe summary
    prow = [['Alu pipe D50 x 2.50 m', 12, '30.0']]
    table(0.73, 0.95, 0.24, 'Pipe Summary', prow, [0.13, 0.05, 0.05], header=['Item', 'Qty', 'Meters'])
    # Rigging hardware
    hrows = [['Box Corner 2-Way 90deg', 14], ['Steel Base 800x800x10', 14], ['Spacer 50 mm', 14],
             ['Half Coupler (pipes)', 48], ['Ballast 1000 kg block', 20], ['Ground Anchor + Ratchet', 8],
             ['Chain Hoist 1 t (PA)', 2], ['Fly-Bar KARA II', 2]]
    table(0.73, 0.80, 0.24, 'Rigging Hardware', hrows, [0.19, 0.04])
    # Lighting summary totals
    srows = [[n, q] for _, n, _, q, _ in FIXTURES] + [['Total', 96]]
    table(0.03, 0.68, 0.30, 'Lighting Summary Totals', srows, [0.25, 0.04])
    # Power summary
    prows2 = [[n, q, w, q * w] for _, n, _, q, w in FIXTURES]
    prows2.append(['Lighting total', '', '', 37520]); prows2.append(['Audio (design avg)', '', '', 12000])
    prows2.append(['Control / misc', '', '', 5000]); prows2.append(['TOTAL +25% reserve', '', '', 68150])
    table(0.38, 0.68, 0.33, 'Power Summary (W)', prows2, [0.17, 0.05, 0.05, 0.06], header=['Load', 'Qty', 'W/unit', 'Total W'])
    # DMX patch summary
    drows = [['U1', 'MP01-13', '1-507'], ['U2', 'MP14-16+JDC+MOLE+TY01-14', '1-503'],
             ['U3', 'LB01-18', '1-486'], ['U4', 'LB19-30+TY15-28', '1-464'], ['U5', 'Spare', '-']]
    table(0.73, 0.47, 0.24, 'DMX / sACN Patch (grandMA3)', drows, [0.033, 0.145, 0.06],
          header=['Univ', 'Fixtures', 'Addr'])
    axb.text(0.03, 0.16, 'NOTES: All quantities derive from the master data of the technical specification (docs/nokdim-stage-technical-spec.md).\n'
                         'Structure erection subject to structural engineer approval: ballast/wind calc (survival 25 m/s), deck bearing report, PA hang detail on F3/F5 (east-face offset, 0.5 m clearance).',
             size=7, va='top')
    title_block(fig, 'Equipment Report', num, scale='NTS')
    pdf.savefig(fig); plt.close(fig)

def build_pdf(path):
    with PdfPages(path) as pdf:
        p, e = view_iso(True);            sheet(pdf, p, None, 'Macro - Iso', 1, '1:150', 'Macro - Iso')
        p, e = view_top('macro');         sheet(pdf, p, e, 'Macro - Top', 2, '1:200', 'Macro - Top')
        p, e = view_front(True, True);    sheet(pdf, p, e, 'Macro - Front', 3, '1:125', 'Macro - Front')
        p, e = view_side(True);           sheet(pdf, p, e, 'Macro - Side', 4, '1:100', 'Macro - Side')
        p, e = view_top('rigging');       sheet(pdf, p, e, 'Rigging - Stage', 5, '1:150', 'Rigging - Stage (Ballast & Guys)')
        p, e = view_front(False, False, True); sheet(pdf, p, e, 'Rigging - Front', 6, '1:125', 'Rigging - Front (Truss Segments)')
        p, e = view_top('stage');         sheet(pdf, p, e, 'Stage - Top', 7, '1:80', 'Stage - Top')
        p, e = view_side(False);          sheet(pdf, p, e, 'Stage - Side', 8, '1:100', 'Stage - Side')
        p, e = view_front(True, True);    sheet(pdf, p, e, 'Lighting - Stage', 9, '1:125', 'Lighting - Stage', legend=True)
        p, e = view_iso(True);            sheet(pdf, p, None, 'Lighting - Iso', 10, '1:150', 'Lighting - Stage - Iso', legend=True)
        equipment_sheet(pdf, 11)
    print('PDF plot set:', path)

# ---------------- DXF export ----------------
def build_dxf(path):
    import ezdxf
    doc = ezdxf.new('R2010', setup=True)
    msp = doc.modelspace()
    for lay, (_, aci) in LCOL.items():
        if lay not in doc.layers: doc.layers.add(lay, color=aci)
    doc.layers.add('VIEWLABEL', color=7)
    def emit(prims, dx, dy, label):
        msp.add_text(label, dxfattribs={'layer': 'VIEWLABEL', 'height': 0.8}).set_placement((dx, dy - 2.2))
        for it in prims.items:
            lay = it['layer']
            if it['k'] == 'l':
                x1, y1, x2, y2 = it['p']
                msp.add_line((x1 + dx, y1 + dy), (x2 + dx, y2 + dy), dxfattribs={'layer': lay})
            elif it['k'] == 'r':
                x, y, w, h = it['p']
                pts = [(x + dx, y + dy), (x + w + dx, y + dy), (x + w + dx, y + h + dy), (x + dx, y + h + dy)]
                msp.add_lwpolyline(pts, close=True, dxfattribs={'layer': lay})
            elif it['k'] == 'c':
                x, y, r = it['p']
                msp.add_circle((x + dx, y + dy), r, dxfattribs={'layer': lay})
            elif it['k'] == 'p':
                pts = [(a + dx, b + dy) for a, b in it['p']]
                msp.add_lwpolyline(pts, close=True, dxfattribs={'layer': lay})
            elif it['k'] == 't':
                x, y = it['p']
                msp.add_text(it['s'].replace('\n', ' '), dxfattribs={'layer': lay, 'height': max(it['size'] * 0.045, 0.18)}
                             ).set_placement((x + dx, y + dy))
    p, _ = view_top('macro');   emit(p, 0, 0, 'MACRO - TOP  (1m = 1 unit)')
    p, _ = view_front(True, True); emit(p, 50, 0, 'MACRO/LIGHTING - FRONT')
    p, _ = view_side(True);     emit(p, 100, 0, 'MACRO - SIDE')
    p, _ = view_top('rigging'); emit(p, 0, -60, 'RIGGING - STAGE')
    p, _ = view_front(False, False, True); emit(p, 50, -60, 'RIGGING - FRONT (SEGMENTS)')
    p, _ = view_top('stage');   emit(p, 100, -60, 'STAGE - TOP')
    p, _ = view_iso(True);      emit(p, 150, 0, 'ISO (ISOMETRIC PROJECTION)')
    # legend text
    y = -40
    msp.add_text('FIXTURE LEGEND', dxfattribs={'layer': 'VIEWLABEL', 'height': 0.9}).set_placement((150, y + 3))
    for lay, name, mode, qty, w in FIXTURES:
        msp.add_circle((150, y), 0.4, dxfattribs={'layer': lay})
        msp.add_text(f'{name} | {mode} | Qty {qty} | {w}W', dxfattribs={'layer': lay, 'height': 0.55}).set_placement((151.2, y - 0.25))
        y -= 1.6
    doc.saveas(path)
    print('DXF:', path)

if __name__ == '__main__':
    build_pdf('nokdim-stage-plot-set.pdf')
    build_dxf('nokdim-stage-plot-set.dxf')
