"""Hand-drawn 'adventure parchment' look for the installer, rendered with Pillow.

Everything here is drawn in code (no game art, logos or fonts): parchment, ink, forest
green and gold, curled corner flourishes, and an ocarina-style music staff for progress.
Text is rendered with bundled OFL fonts (Cinzel for headings, Selawik for body).
"""
import math
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from . import paint

HERE = os.path.join(os.path.dirname(__file__), "fonts")
CINZEL = os.path.join(HERE, "cinzel", "Cinzel.ttf")
BODY = os.path.join(HERE, "selawksb.ttf")
BODY_LIGHT = os.path.join(HERE, "selawksl.ttf")
BODY_BOLD = os.path.join(HERE, "selawkb.ttf")

PARCHMENT = (233, 216, 174)
INK = (58, 38, 20)
INK_SOFT = (104, 78, 48)
GREEN = (36, 72, 44)
GREEN_HI = (52, 98, 60)
GOLD = (204, 164, 76)
GOLD_HI = (240, 206, 120)
CREAM = (248, 240, 216)
RED = (150, 44, 32)

_font_cache = {}


def font(kind, size, weight=None):
    key = (kind, size, weight)
    if key not in _font_cache:
        path = {"title": CINZEL, "body": BODY, "light": BODY_LIGHT, "bold": BODY_BOLD}[kind]
        f = ImageFont.truetype(path, size)
        if kind == "title":
            try:
                f.set_variation_by_axes([weight or 700])
            except (OSError, AttributeError):
                pass
        _font_cache[key] = f
    return _font_cache[key]


# ---------------------------------------------------------------- backgrounds

def parchment(w, h, seed=7):
    rng = np.random.default_rng(seed)
    base = np.ones((h, w, 3), np.float32) * np.array(PARCHMENT, np.float32)
    # large soft blotches + fine grain
    blot = Image.fromarray((rng.random((h // 24 + 2, w // 24 + 2)) * 255).astype(np.uint8)).resize((w, h), Image.BICUBIC)
    blot = np.asarray(blot.filter(ImageFilter.GaussianBlur(18)), np.float32)[..., None] / 255
    grain = rng.normal(0, 5, (h, w, 1)).astype(np.float32)
    img = base * (0.92 + 0.12 * blot) + grain
    # fibres
    fib = Image.new("L", (w, h), 0)
    d = ImageDraw.Draw(fib)
    for _ in range(int(w * h / 2500)):
        x, y = rng.integers(0, w), rng.integers(0, h)
        a = rng.uniform(-0.4, 0.4)
        L = rng.integers(8, 30)
        d.line([(x, y), (x + L * math.cos(a), y + L * math.sin(a))], fill=int(rng.integers(20, 60)), width=1)
    img -= np.asarray(fib.filter(ImageFilter.GaussianBlur(0.6)), np.float32)[..., None] * 0.25
    # burnt vignette
    yy, xx = np.mgrid[0:h, 0:w]
    dx, dy = (xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)
    r = np.sqrt(dx ** 2 * 0.9 + dy ** 2)
    vig = np.clip((r - 0.62) / 0.55, 0, 1) ** 1.7
    img = img * (1 - 0.55 * vig[..., None]) + np.array([60, 32, 10], np.float32) * 0.55 * vig[..., None]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB")


def flourish(d, x, y, sx, sy, color, width=3):
    """A curled corner ornament at (x, y); sx/sy = +1/-1 pick the corner's direction."""
    pts = []
    for i in range(90):
        t = i / 89 * 4.2 * math.pi
        r = 26 * (1 - i / 110)
        pts.append((x + sx * (34 + r * math.cos(t)), y + sy * (34 + r * math.sin(t))))
    d.line(pts, fill=color, width=width, joint="curve")
    d.line([(x + sx * 8, y + sy * 8), (x + sx * 120, y + sy * 8)], fill=color, width=width)
    d.line([(x + sx * 8, y + sy * 8), (x + sx * 8, y + sy * 90)], fill=color, width=width)
    for k in (130, 142):
        d.ellipse([x + sx * k - 3, y + sy * 8 - 3, x + sx * k + 3, y + sy * 8 + 3], fill=color)


def frame(img):
    w, h = img.size
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, w - 11, h - 11], outline=INK, width=3)
    d.rectangle([18, 18, w - 19, h - 19], outline=GOLD, width=2)
    for (x, y, sx, sy) in ((18, 18, 1, 1), (w - 19, 18, -1, 1), (18, h - 19, 1, -1), (w - 19, h - 19, -1, -1)):
        flourish(d, x, y, sx, sy, INK_SOFT, 3)
    return img


def background(w, h):
    return frame(parchment(w, h))


# ---------------------------------------------------------------- text

def text(s, kind="body", size=18, color=INK, weight=None, shadow=None):
    f = font(kind, size, weight)
    bx = f.getbbox(s)
    pad = 4
    im = Image.new("RGBA", (bx[2] - bx[0] + pad * 2 + 2, bx[3] - bx[1] + pad * 2 + 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if shadow:
        d.text((pad - bx[0] + 1, pad - bx[1] + 2), s, font=f, fill=shadow)
    d.text((pad - bx[0], pad - bx[1]), s, font=f, fill=color)
    return im


def paragraph(s, width, kind="body", size=17, color=INK, spacing=6):
    f = font(kind, size)
    lines = []
    for para in s.split("\n"):
        words, cur = para.split(" "), ""
        for wd in words:
            t = (cur + " " + wd).strip()
            if f.getlength(t) <= width or not cur:
                cur = t
            else:
                lines.append(cur)
                cur = wd
        lines.append(cur)
    lh = size + spacing
    im = Image.new("RGBA", (width + 4, lh * len(lines) + 6), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for i, ln in enumerate(lines):
        d.text((2, 2 + i * lh), ln, font=f, fill=color)
    return im


# ---------------------------------------------------------------- widgets

def button(label, w=220, h=52, state="normal", primary=True):
    """state: normal | hover | focus | disabled."""
    ss = 3
    im = Image.new("RGBA", (w * ss, h * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    fill = {True: GREEN, False: (120, 92, 56)}[primary]
    if state in ("hover", "focus"):
        fill = {True: GREEN_HI, False: (146, 112, 70)}[primary]
    if state == "disabled":
        fill = (150, 138, 112)
    border = GOLD_HI if state in ("hover", "focus") else GOLD
    d.rounded_rectangle([2 * ss, 4 * ss, (w - 2) * ss, (h - 1) * ss], 14 * ss, fill=(30, 18, 8, 110))   # shadow
    d.rounded_rectangle([2 * ss, 1 * ss, (w - 2) * ss, (h - 4) * ss], 14 * ss, fill=fill, outline=border, width=3 * ss)
    d.rounded_rectangle([7 * ss, 6 * ss, (w - 7) * ss, (h - 9) * ss], 10 * ss, outline=(*border, 90), width=ss)
    im = im.resize((w, h), Image.LANCZOS)
    t = text(label, "title", 19, CREAM if state != "disabled" else (230, 222, 200), 700, shadow=(20, 12, 4, 160))
    im.alpha_composite(t, ((w - t.width) // 2, (h - 3 - t.height) // 2))
    if state == "focus":
        _sparkle(im, 16, h // 2 - 2)
    return im


def _sparkle(im, x, y):
    glow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(glow)
    d.ellipse([x - 7, y - 7, x + 7, y + 7], fill=(255, 250, 220, 200))
    glow = glow.filter(ImageFilter.GaussianBlur(3))
    d = ImageDraw.Draw(glow)
    d.ellipse([x - 3, y - 3, x + 3, y + 3], fill=(255, 255, 255, 255))
    im.alpha_composite(glow)


def panel(w, h, selected=False, hover=False):
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([3, 5, w - 1, h - 1], 16, fill=(40, 24, 8, 70))
    fill = (246, 232, 196) if (selected or hover) else (226, 206, 160)
    d.rounded_rectangle([0, 0, w - 4, h - 6], 16, fill=fill, outline=GOLD if selected else INK_SOFT,
                        width=4 if selected else 2)
    if selected:
        d.rounded_rectangle([7, 7, w - 11, h - 13], 11, outline=(*GOLD_HI, 160), width=2)
    return im


# ---------------------------------------------------------------- controller icons for style cards

def face_icons(style, size=46):
    """A little diamond of face buttons in the chosen style (drawn by us)."""
    ss = 4
    S = size * ss
    im = Image.new("RGBA", (S * 3, S * 3), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    pos = {"top": (1.5, 0.55), "left": (0.55, 1.5), "right": (2.45, 1.5), "bottom": (1.5, 2.45)}
    labels = {"xbox": {"top": "Y", "left": "X", "right": "B", "bottom": "A"},
              "steam": {"top": "Y", "left": "X", "right": "B", "bottom": "A"}}
    colors = {"xbox": {"A": (64, 140, 60), "B": (178, 52, 40), "X": (44, 96, 170), "Y": (214, 168, 40)}}
    f = font("bold", int(S * 0.52))
    for slot, (px, py) in pos.items():
        cx, cy, r = px * S, py * S, S * 0.46
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(46, 32, 18), outline=GOLD, width=ss * 2)
        if style == "ps5":
            paint.symbol(d, paint.PS_FACE[slot], cx, cy, S * 0.52, ss * 4.5, CREAM)
        else:
            ch = labels[style][slot]
            col = colors.get(style, {}).get(ch, CREAM)
            bx = d.textbbox((0, 0), ch, font=f)
            d.text((cx - (bx[0] + bx[2]) / 2, cy - (bx[1] + bx[3]) / 2), ch, font=f, fill=col)
    return im.resize((size * 3, size * 3), Image.LANCZOS)


def shoulder_tags(labels, h=30):
    f = font("bold", 17)
    out = []
    for lb in labels:
        w = int(f.getlength(lb)) + 22
        im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([0, 0, w - 1, h - 1], 8, fill=(46, 32, 18))
        bx = d.textbbox((0, 0), lb, font=f)
        d.text(((w - bx[2] - bx[0]) / 2, (h - bx[3] - bx[1]) / 2), lb, font=f, fill=CREAM)
        out.append(im)
    W = sum(i.width for i in out) + 8 * (len(out) - 1)
    strip = Image.new("RGBA", (W, h), (0, 0, 0, 0))
    x = 0
    for i in out:
        strip.alpha_composite(i, (x, 0))
        x += i.width + 8
    return strip


# ---------------------------------------------------------------- progress staff

NOTE_HEIGHTS = [3, 1, 2, 0, 1.5]   # staff positions for 5 notes (a little melody)


def staff(w, done, current=None, pulse=0.0):
    """Music staff with one note per step; `done` notes are inked, `current` glows."""
    h = 150
    im = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    top, gap = 30, 20
    for i in range(5):
        y = top + i * gap
        d.line([(40, y), (w - 20, y)], fill=(*INK_SOFT, 200), width=2)
    # a simple clef-like curl (our own drawing)
    pts = [(58 + 14 * math.sin(t / 10), top + 88 - t * 1.05) for t in range(0, 95)]
    d.line(pts, fill=(*INK_SOFT, 220), width=4, joint="curve")
    d.ellipse([46, top + 70, 66, top + 90], outline=(*INK_SOFT, 220), width=4)
    xs = [140 + i * (w - 200) / 4 for i in range(5)]
    for i, (x, hpos) in enumerate(zip(xs, NOTE_HEIGHTS)):
        y = top + hpos * gap * 1.6 + 6
        if i < done:
            d.ellipse([x - 16, y - 12, x + 16, y + 12], fill=GREEN, outline=GOLD, width=3)
            d.line([(x + 13, y - 2), (x + 13, y - 52)], fill=GREEN, width=4)
        elif i == current:
            g = Image.new("RGBA", im.size, (0, 0, 0, 0))
            gd = ImageDraw.Draw(g)
            r = 24 + 6 * pulse
            gd.ellipse([x - r, y - r, x + r, y + r], fill=(255, 236, 160, int(120 + 80 * pulse)))
            im.alpha_composite(g.filter(ImageFilter.GaussianBlur(8)))
            d = ImageDraw.Draw(im)
            d.ellipse([x - 16, y - 12, x + 16, y + 12], fill=GOLD_HI, outline=INK, width=3)
            d.line([(x + 13, y - 2), (x + 13, y - 52)], fill=INK, width=4)
        else:
            d.ellipse([x - 16, y - 12, x + 16, y + 12], outline=(*INK_SOFT, 150), width=3)
    return im


def app_icon(size=256):
    """Window/app icon: a gold-rimmed green medallion with a game pad and a music note."""
    ss = 4
    S = size * ss
    im = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.ellipse([S * 0.04, S * 0.04, S * 0.96, S * 0.96], fill=GREEN, outline=GOLD, width=int(S * 0.05))
    d.ellipse([S * 0.13, S * 0.13, S * 0.87, S * 0.87], outline=(*GOLD_HI, 140), width=int(S * 0.012))
    # game pad
    pad = [S * 0.2, S * 0.42, S * 0.8, S * 0.72]
    d.rounded_rectangle(pad, int(S * 0.14), fill=CREAM)
    d.ellipse([S * 0.18, S * 0.52, S * 0.40, S * 0.80], fill=CREAM)
    d.ellipse([S * 0.60, S * 0.52, S * 0.82, S * 0.80], fill=CREAM)
    cx, cy, a = S * 0.34, S * 0.56, S * 0.035
    d.rectangle([cx - a * 2.6, cy - a, cx + a * 2.6, cy + a], fill=GREEN)
    d.rectangle([cx - a, cy - a * 2.6, cx + a, cy + a * 2.6], fill=GREEN)
    for dx, dy in ((0, -1), (-1, 0), (1, 0), (0, 1)):
        x, y = S * 0.66 + dx * S * 0.055, S * 0.56 + dy * S * 0.055
        d.ellipse([x - S * 0.028, y - S * 0.028, x + S * 0.028, y + S * 0.028], fill=GREEN)
    # music note
    d.ellipse([S * 0.47, S * 0.27, S * 0.58, S * 0.36], fill=GOLD_HI)
    d.rectangle([S * 0.555, S * 0.13, S * 0.58, S * 0.32], fill=GOLD_HI)
    d.polygon([(S * 0.58, S * 0.13), (S * 0.68, S * 0.19), (S * 0.58, S * 0.21)], fill=GOLD_HI)
    return im.resize((size, size), Image.LANCZOS)
