"""Repaint UI textures from the game's own images.

controller(): the Pro Controller picture (Controller_Pro1 brown / Controller_Pro grey,
1160x680). Every button stays where it is, so the Controls screen's pointer lines still land.
ocarina_lr() / ocarina_lr_shadow(): the 93x93 note icons for L/R, redrawn as LB/RB.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

SS = 4
FACE = {"top": ((801.0, 168.5), "Y"), "left": ((732.0, 227.5), "X"),
        "right": ((869.5, 227.5), "B"), "bottom": ((801.0, 287.0), "A")}
FACE_R = 30.5
MINUS, PLUS, SMALL_R = (477.5, 162.0), (682.5, 162.0), 17.0
HOME, HOME_R = (632.0, 227.5), 19.5
CAPTURE = (528.0, 228.0)


def _gauss1d(a, sigma, axis=0):
    r = int(sigma * 4)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    pad = [(0, 0)] * a.ndim
    pad[axis] = (r, r)
    p = np.pad(a, pad, mode="edge")
    return np.apply_along_axis(lambda v: np.convolve(v, k, mode="valid"), axis, p)


def _remove_c_button(im):
    """Fill the C button and its glow from the plain body just left of it, plus grain."""
    rgb = np.asarray(im)[..., :3].astype(np.float32)
    m = Image.new("L", im.size, 0)
    ImageDraw.Draw(m).ellipse([536, 380, 624, 442], fill=255)
    soft = np.asarray(m.filter(ImageFilter.GaussianBlur(3)), np.float32)[..., None] / 255
    xl, xr, ya, yb = 528, 632, 370, 443
    rows = np.array([np.median(rgb[y, 526:536], axis=0) for y in range(ya, yb)])
    rows = _gauss1d(rows, 4, axis=0)
    filled = rgb.copy()
    filled[ya:yb, xl:xr] = rows[:, None, :]
    body = rgb[290:330, 560:600]
    sd = body.std(axis=(0, 1)).mean()
    grain = np.random.default_rng(1).normal(0, sd if sd > 1.5 else 0.0, rgb.shape[:2])
    filled += grain[..., None] * soft
    out = rgb * (1 - soft) + filled * soft
    return Image.fromarray(np.dstack([np.clip(out, 0, 255).astype(np.uint8), np.asarray(im)[..., 3]]), "RGBA")


def symbol(d, kind, cx, cy, size, width, fill):
    """Draw a PlayStation face symbol (outline strokes) centred on (cx, cy), all in pixels."""
    h = size / 2
    if kind == "cross":
        r = h * 0.78
        for a, b in (((cx - r, cy - r), (cx + r, cy + r)), ((cx - r, cy + r), (cx + r, cy - r))):
            d.line([a, b], fill=fill, width=int(width))
            for x, y in (a, b):
                d.ellipse([x - width / 2, y - width / 2, x + width / 2, y + width / 2], fill=fill)
    elif kind == "circle":
        r = h * 0.86
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=fill, width=int(width))
    elif kind == "square":
        r = h * 0.74
        d.rectangle([cx - r, cy - r, cx + r, cy + r], outline=fill, width=int(width))
    elif kind == "triangle":
        r = h * 1.08 - width * 0.75              # centred stroke; a touch larger so it matches visually
        cy2 = cy + r * 0.08                      # image y grows downward
        pts = [(cx, cy2 - r), (cx + r * 0.866, cy2 + r * 0.5), (cx - r * 0.866, cy2 + r * 0.5)]
        d.line(pts + pts[:2], fill=fill, width=int(width), joint="curve")
    else:
        raise ValueError(kind)


PS_FACE = {"top": "triangle", "left": "square", "right": "circle", "bottom": "cross"}


def keytex(kind, size=64):
    """The ring's faded letter textures (64x64, white on black, BC4): a PS symbol instead."""
    ss = 8
    im = Image.new("L", (size * ss, size * ss), 0)
    symbol(ImageDraw.Draw(im), kind, size * ss / 2, size * ss / 2, 30 * ss, 5 * ss, 255)
    return im.resize((size, size), Image.LANCZOS)


def ocarina_face(kind):
    """93x93 ocarina note icon: white disc with a black PS symbol (same disc as the originals)."""
    ss = 8
    im = Image.new("RGBA", (OC_SIZE * ss, OC_SIZE * ss), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    c, r = 46.5 * ss, 33.5 * ss
    d.ellipse([c - r, c - r, c + r, c + r], fill=(255, 255, 255, 255))
    symbol(d, kind, c, c, 32 * ss, 5.5 * ss, (0, 0, 0, 255))
    out = np.array(im.resize((OC_SIZE, OC_SIZE), Image.LANCZOS))
    out[out[..., 3] == 0] = 0
    return Image.fromarray(out, "RGBA")


def controller(im, semilight_font, style="xbox"):
    im = im.convert("RGBA")
    a = np.asarray(im).astype(int)
    fill = tuple(a[215, 860, :3]) + (255,)
    small_fill = tuple(a[160, 466, :3]) + (255,)
    face = a[195:260, 838:901, :3].reshape(-1, 3)
    letter_c = tuple(face[face.sum(1).argmax()]) + (255,)
    minus = a[146:178, 461:494, :3].reshape(-1, 3)
    dark = tuple(minus[minus.sum(1).argmin()]) + (255,)

    im = _remove_c_button(im)
    L = Image.new("RGBA", (im.width * SS, im.height * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(L)
    S = lambda v: v * SS  # noqa: E731
    circ = lambda c, r, **k: d.ellipse([S(c[0] - r), S(c[1] - r), S(c[0] + r), S(c[1] + r)], **k)  # noqa: E731
    font = ImageFont.truetype(semilight_font, S(36))

    for slot, (c, ch) in FACE.items():
        circ(c, FACE_R, fill=fill)
        if style == "ps5":
            symbol(d, PS_FACE[slot], S(c[0]), S(c[1]), S(27), S(2.6), letter_c)
            continue
        bx = d.textbbox((0, 0), ch, font=font, anchor="ls")
        d.text((S(c[0]) - (bx[2] - bx[0]) / 2 - bx[0], S(c[1]) + (bx[3] - bx[1]) / 2), ch,
               font=font, fill=letter_c, anchor="ls")

    w = int(S(2.2))
    circ(MINUS, SMALL_R, fill=small_fill)
    cx, cy = MINUS
    if style == "ps5":                                          # Create: rays over a pill
        d.rounded_rectangle([S(cx - 7), S(cy + 2.5), S(cx + 7), S(cy + 6.5)], S(2), fill=dark)
        for x0, y0, x1, y1 in ((0, 0, 0, -7.5), (-3.2, 0.5, -6.3, -5.5), (3.2, 0.5, 6.3, -5.5)):
            d.line([(S(cx + x0), S(cy + y0)), (S(cx + x1), S(cy + y1))], fill=dark, width=int(S(2.2)))
    else:                                                       # View
        d.rounded_rectangle([S(cx - 2), S(cy - 8), S(cx + 8), S(cy + 2)], S(2), outline=dark, width=w)
        d.rounded_rectangle([S(cx - 8), S(cy - 2), S(cx + 2), S(cy + 8)], S(2), fill=small_fill, outline=dark, width=w)
    circ(PLUS, SMALL_R, fill=small_fill)                        # Menu / Options: three lines
    cx, cy = PLUS
    for dy in (-5.5, 0, 5.5):
        d.rounded_rectangle([S(cx - 7.5), S(cy + dy - 1.2), S(cx + 7.5), S(cy + dy + 1.2)], S(1.2), fill=dark)
    circ(HOME, HOME_R, fill=fill)                               # guide / PS / Steam button: plain ring, no logo
    circ(HOME, 11.5, outline=dark, width=int(S(2.6)))
    cx, cy = CAPTURE
    d.rounded_rectangle([S(cx - 14.5), S(cy - 14.5), S(cx + 14.5), S(cy + 14.5)], S(4), fill=fill)
    if style == "ps5":                                          # mute button: small bar
        d.rounded_rectangle([S(cx - 7), S(cy - 1.4), S(cx + 7), S(cy + 1.4)], S(1.4), fill=dark)
    elif style == "steam":                                      # Quick Access: three dots
        # the game shows this picture at ~45% size, so the dots must be big and well spaced
        for dx in (-8.5, 0, 8.5):
            d.ellipse([S(cx + dx - 3.3), S(cy - 3.3), S(cx + dx + 3.3), S(cy + 3.3)], fill=dark)
    else:                                                       # Share: upload arrow
        d.polygon([(S(cx), S(cy - 8)), (S(cx - 6), S(cy - 2)), (S(cx + 6), S(cy - 2))], fill=dark)
        d.rectangle([S(cx - 1.3), S(cy - 3), S(cx + 1.3), S(cy + 4)], fill=dark)
        d.rectangle([S(cx - 7), S(cy + 5.5), S(cx + 7), S(cy + 8)], fill=dark)

    im.alpha_composite(L.resize(im.size, Image.LANCZOS))
    return im


# ---------------------------------------------------------------- ocarina LB/RB icons

OC_SIZE, OC_SS = 93, 8
OC_BOX = (9, 15, 84, 75)
OC_BIG, OC_SMALL, OC_CAP = 22, 7, 30


def _bumper_mask(left):
    m = Image.new("L", (OC_SIZE * OC_SS, OC_SIZE * OC_SS), 0)
    d = ImageDraw.Draw(m)
    x0, y0, x1, y1 = (v * OC_SS for v in OC_BOX)
    d.rounded_rectangle([x0, y0, x1, y1], OC_SMALL * OC_SS, fill=255)
    r = OC_BIG * OC_SS
    if left:
        d.rectangle([x0, y0, x0 + r, y0 + r], fill=0)
        d.pieslice([x0, y0, x0 + 2 * r, y0 + 2 * r], 180, 270, fill=255)
    else:
        d.rectangle([x1 - r, y0, x1, y0 + r], fill=0)
        d.pieslice([x1 - 2 * r, y0, x1, y0 + 2 * r], 270, 360, fill=255)
    return m


def ocarina_lr(text, left, semibold_font):
    m = _bumper_mask(left)
    im = Image.new("RGBA", m.size, (255, 255, 255, 0))
    im.putalpha(m)
    d = ImageDraw.Draw(im)
    probe = ImageFont.truetype(semibold_font, 10).getbbox("H")
    font = ImageFont.truetype(semibold_font, int(10 * OC_CAP / (probe[3] - probe[1]) * OC_SS))
    bx = d.textbbox((0, 0), text, font=font)
    cx, cy = (OC_BOX[0] + OC_BOX[2]) / 2 * OC_SS, (OC_BOX[1] + OC_BOX[3]) / 2 * OC_SS
    d.text((cx - (bx[0] + bx[2]) / 2, cy - (bx[1] + bx[3]) / 2), text, font=font, fill=(0, 0, 0, 255))
    out = np.array(im.resize((OC_SIZE, OC_SIZE), Image.LANCZOS))
    out[out[..., 3] == 0] = 0          # fully transparent pixels are black, like the originals
    return Image.fromarray(out, "RGBA")


def ocarina_lr_shadow():
    m = _bumper_mask(False).resize((OC_SIZE, OC_SIZE), Image.LANCZOS)
    return m.filter(ImageFilter.GaussianBlur(2.6)).point(lambda v: min(255, int(v * 1.15)))
