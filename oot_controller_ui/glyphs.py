"""Rebuild the game's button-glyph font (Font2/Scalable/External) with Xbox glyphs.

The font is OpenType/CFF, 1000 units per em. Private-use glyphs:
  E040 A  E041 B  E042 X  E043 Y  E044 L  E045 R  E046 ZL  E047 ZR
  E048 power  E049 d-pad  E04A home  E04B +  E04C -   E05E/E05F sticks
Mapping (emulator with A/B swapped, i.e. buttons matched by label):
  X<->Y swapped, L/R -> LB/RB, ZL/ZR -> LT/RT, + -> Menu, - -> View.
"""
import io

import pathops
from fontTools.misc.transform import Transform
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont


class Letters:
    def __init__(self, path):
        self.font = TTFont(path)
        self.gs = self.font.getGlyphSet()
        self.cmap = self.font.getBestCmap()

    def text(self, s, cx, cy, cap, tracking=0.0):
        scale = cap / self.font["OS/2"].sCapHeight
        raw = pathops.Path()
        x = 0.0
        for ch in s:
            g = self.cmap[ord(ch)]
            self.gs[g].draw(TransformPen(raw.getPen(), Transform(scale, 0, 0, scale, x, 0)))
            x += self.font["hmtx"][g][0] * scale + tracking * cap
        bp = BoundsPen(None)
        raw.draw(bp)
        x0, y0, x1, y1 = bp.bounds
        out = pathops.Path()
        raw.draw(TransformPen(out.getPen(), Transform(1, 0, 0, 1, cx - (x0 + x1) / 2, cy - (y0 + y1) / 2)))
        return out


def rrect(x0, y0, x1, y1, r_tl, r_tr, r_br, r_bl):
    k = 0.5523
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo((x0 + r_bl, y0))
    pen.lineTo((x1 - r_br, y0))
    if r_br:
        pen.curveTo((x1 - r_br + r_br * k, y0), (x1, y0 + r_br - r_br * k), (x1, y0 + r_br))
    pen.lineTo((x1, y1 - r_tr))
    if r_tr:
        pen.curveTo((x1, y1 - r_tr + r_tr * k), (x1 - r_tr + r_tr * k, y1), (x1 - r_tr, y1))
    pen.lineTo((x0 + r_tl, y1))
    if r_tl:
        pen.curveTo((x0 + r_tl - r_tl * k, y1), (x0, y1 - r_tl + r_tl * k), (x0, y1 - r_tl))
    pen.lineTo((x0, y0 + r_bl))
    if r_bl:
        pen.curveTo((x0, y0 + r_bl - r_bl * k), (x0 + r_bl - r_bl * k, y0), (x0 + r_bl, y0))
    pen.closePath()
    return p


def circle(cx, cy, r):
    return rrect(cx - r, cy - r, cx + r, cy + r, r, r, r, r)


def sub(a, b):
    return pathops.op(a, b, pathops.PathOp.DIFFERENCE)


def union(a, b):
    return pathops.op(a, b, pathops.PathOp.UNION)


def bumper(L, left):
    big, small = 170, 70
    shape = rrect(45, 95, 675, 505, big if left else small, small if left else big, small, small)
    return sub(shape, L.text("LB" if left else "RB", 360, 300, 215, 0.06))


def trigger(L, left):
    shape = rrect(100, 40, 620, 585, 200, 200, 70, 70)
    return sub(shape, L.text("LT" if left else "RT", 360, 285, 215, 0.06))


def menu_button():
    bars = pathops.Path()
    for y in (215, 300, 385):
        bars = union(bars, rrect(185, y - 22, 415, y + 22, 22, 22, 22, 22))
    return sub(circle(300, 300, 244), bars)


def view_button():
    t = 34
    back = sub(rrect(250, 250, 430, 430, 30, 30, 30, 30), rrect(250 + t, 250 + t, 430 - t, 430 - t, 10, 10, 10, 10))
    front_full = rrect(170, 170, 350, 350, 30, 30, 30, 30)
    front = sub(front_full, rrect(170 + t, 170 + t, 350 - t, 350 - t, 10, 10, 10, 10))
    return sub(circle(300, 300, 244), union(front, sub(back, front_full)))


# ---------------------------------------------------------------- PlayStation shapes

def polygon(points):
    p = pathops.Path()
    pen = p.getPen()
    pen.moveTo(points[0])
    for pt in points[1:]:
        pen.lineTo(pt)
    pen.closePath()
    return p


def bar(x0, y0, x1, y1, w):
    """A straight stroke of width w from (x0,y0) to (x1,y1), square ends."""
    import math
    dx, dy = x1 - x0, y1 - y0
    n = math.hypot(dx, dy)
    ox, oy = -dy / n * w / 2, dx / n * w / 2
    return polygon([(x0 + ox, y0 + oy), (x1 + ox, y1 + oy), (x1 - ox, y1 - oy), (x0 - ox, y0 - oy)])


FACE_C, FACE_R = (320, 301), 282     # the A/B/X/Y glyph circle in the original font
PS_SIZE, PS_W = 370, 50              # symbol size and stroke, font units


def ps_symbol(kind, cx, cy, size=PS_SIZE, w=PS_W):
    h = size / 2
    if kind == "cross":
        d = h * 0.78
        return union(bar(cx - d, cy - d, cx + d, cy + d, w), bar(cx - d, cy + d, cx + d, cy - d, w))
    if kind == "circle":
        return sub(circle(cx, cy, h * 0.86), circle(cx, cy, h * 0.86 - w))
    if kind == "square":
        d = h * 0.74
        return sub(rrect(cx - d, cy - d, cx + d, cy + d, 0, 0, 0, 0),
                   rrect(cx - d + w, cy - d + w, cx + d - w, cy + d - w, 0, 0, 0, 0))
    if kind == "triangle":
        r = h * 0.98                     # circumradius; centroid at (cx, cy - small offset)
        cy2 = cy - r * 0.08
        pts = [(cx, cy2 + r), (cx - r * 0.866, cy2 - r * 0.5), (cx + r * 0.866, cy2 - r * 0.5)]
        ri = r - 2 * w                   # inner triangle: inset by w (inradius = r/2)
        inner = [(cx, cy2 + ri), (cx - ri * 0.866, cy2 - ri * 0.5), (cx + ri * 0.866, cy2 - ri * 0.5)]
        return sub(polygon(pts), polygon(inner))
    raise ValueError(kind)


def ps_face(kind):
    return sub(circle(*FACE_C, FACE_R), ps_symbol(kind, *FACE_C))


def ps_bumper(L, left):
    shape = rrect(45, 95, 675, 505, 120, 120, 70, 70)
    return sub(shape, L.text("L1" if left else "R1", 360, 300, 215, 0.06))


def ps_trigger(L, left):
    shape = rrect(100, 40, 620, 585, 200, 200, 70, 70)
    return sub(shape, L.text("L2" if left else "R2", 360, 285, 215, 0.06))


def create_button():
    """DualSense Create: three short rays over a small pill, knocked out of a circle."""
    c = circle(300, 300, 244)
    pill = rrect(185, 180, 415, 244, 32, 32, 32, 32)
    rays = union(bar(300, 290, 300, 410, 42),                       # rays spread upward, apart
                 union(bar(248, 282, 196, 372, 42), bar(352, 282, 404, 372, 42)))
    return sub(c, union(pill, rays))


def _set_glyph(font, gname, path, advance):
    cff = font["CFF "].cff
    priv = cff.topDictIndex[0].Private
    width = None if advance == priv.defaultWidthX else advance - priv.nominalWidthX
    pen = T2CharStringPen(width, None)
    path.draw(pen)
    cff.topDictIndex[0].CharStrings[gname] = pen.getCharString(private=priv, globalSubrs=cff.GlobalSubrs)
    bp = BoundsPen(None)
    path.draw(bp)
    font["hmtx"][gname] = (advance, int(round(bp.bounds[0])))


def build(otf_bytes, bold_font_path, style="xbox"):
    """Original External OTF bytes -> restyled OTF bytes ('xbox', 'ps5' or 'steam')."""
    font = TTFont(io.BytesIO(otf_bytes), recalcTimestamp=False)   # reproducible output
    L = Letters(bold_font_path)
    cmap = font.getBestCmap()
    cs = font["CFF "].cff.topDictIndex[0].CharStrings
    hmtx = font["hmtx"]
    g = {cp: cmap[cp] for cp in range(0xE040, 0xE04D)}
    if style in ("xbox", "steam"):
        # Xbox-layout letters: the X and Y glyphs trade places
        cs[g[0xE042]], cs[g[0xE043]] = cs[g[0xE043]], cs[g[0xE042]]
        hmtx[g[0xE042]], hmtx[g[0xE043]] = hmtx[g[0xE043]], hmtx[g[0xE042]]
        if style == "xbox":
            _set_glyph(font, g[0xE044], bumper(L, True), 720)
            _set_glyph(font, g[0xE045], bumper(L, False), 720)
            _set_glyph(font, g[0xE046], trigger(L, True), 720)
            _set_glyph(font, g[0xE047], trigger(L, False), 720)
        else:                                             # Steam Deck: L1/R1, L2/R2
            _set_glyph(font, g[0xE044], ps_bumper(L, True), 720)
            _set_glyph(font, g[0xE045], ps_bumper(L, False), 720)
            _set_glyph(font, g[0xE046], ps_trigger(L, True), 720)
            _set_glyph(font, g[0xE047], ps_trigger(L, False), 720)
        _set_glyph(font, g[0xE04B], menu_button(), 600)
        _set_glyph(font, g[0xE04C], view_button(), 600)
    elif style == "ps5":
        for cp, kind in ((0xE040, "cross"), (0xE041, "circle"), (0xE042, "triangle"), (0xE043, "square")):
            _set_glyph(font, g[cp], ps_face(kind), 640)
        _set_glyph(font, g[0xE044], ps_bumper(L, True), 720)
        _set_glyph(font, g[0xE045], ps_bumper(L, False), 720)
        _set_glyph(font, g[0xE046], ps_trigger(L, True), 720)
        _set_glyph(font, g[0xE047], ps_trigger(L, False), 720)
        _set_glyph(font, g[0xE04B], menu_button(), 600)      # Options (three lines)
        _set_glyph(font, g[0xE04C], create_button(), 600)
    else:
        raise ValueError(style)
    out = io.BytesIO()
    font.save(out)
    return out.getvalue()
