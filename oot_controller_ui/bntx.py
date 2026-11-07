"""BNTX textures for Switch 2 games: lookup, block-linear (de)swizzle, BC4 and ASTC 4x4.

Switch 2 uses the Tegra block-linear layout with one difference: inside each 512-byte GOB,
address bits 5 and 6 are swapped (see Lichii's astc_decoder.comp).
"""
import re
import struct

import numpy as np
from PIL import Image

BC4 = 0x1D01
ASTC4x4_SRGB = 0x2D06


def textures(b):
    """name -> dict(fmt, w, h, bh, size, data). Texture headers live near the start."""
    head = bytes(b[:8_000_000])
    out = {}
    for m in re.finditer(b"BRTI", head):
        t = m.start()
        fmt, = struct.unpack_from("<I", head, t + 0x1C)
        w, h = struct.unpack_from("<II", head, t + 0x24)
        bh_log2, = struct.unpack_from("<I", head, t + 0x34)
        size, = struct.unpack_from("<I", head, t + 0x50)
        nameoff, _, ptrs = struct.unpack_from("<QQQ", head, t + 0x60)
        n, = struct.unpack_from("<H", head, nameoff)
        name = head[nameoff + 2:nameoff + 2 + n].decode("utf-8", "replace")
        data, = struct.unpack_from("<Q", head, ptrs)
        out[name] = dict(fmt=fmt, w=w, h=h, bh=1 << bh_log2, size=size, data=data)
    return out


def _addr(width_bytes, rows, bh):
    gobs_x = (width_bytes + 63) // 64
    y = np.arange(rows)[:, None]
    x = np.arange(width_bytes)[None, :]
    gob_y = y // 8
    gob = ((gob_y // bh) * gobs_x + x // 64) * bh + (gob_y % bh)
    xi, yi = x % 64, y % 8
    w = (xi // 32) * 256 + (yi // 2) * 64 + ((xi % 32) // 16) * 32 + (yi % 2) * 16 + (xi % 16)
    w = (w & ~0x60) | (((w >> 5) & 1) << 6) | (((w >> 6) & 1) << 5)   # Switch 2 bit swap
    return gob * 512 + w


def _bpb(fmt):
    return {BC4: 8, ASTC4x4_SRGB: 16}[fmt]


def read_linear(b, t):
    bx, by = (t["w"] + 3) // 4, (t["h"] + 3) // 4
    raw = np.frombuffer(bytes(b[t["data"]:t["data"] + t["size"]]), np.uint8)
    return raw[_addr(bx * _bpb(t["fmt"]), by, t["bh"])].tobytes()


def write_linear(b, t, lin):
    bx, by = (t["w"] + 3) // 4, (t["h"] + 3) // 4
    out = np.zeros(t["size"], np.uint8)
    out[_addr(bx * _bpb(t["fmt"]), by, t["bh"]).ravel()] = np.frombuffer(lin, np.uint8)
    b[t["data"]:t["data"] + t["size"]] = out.tobytes()


def decode(b, name):
    t = textures(b)[name]
    lin = read_linear(b, t)
    if t["fmt"] == BC4:
        return Image.frombytes("L", (t["w"], t["h"]), lin, "bcn", 4)
    if t["fmt"] == ASTC4x4_SRGB:
        return astc_decode(lin, t["w"], t["h"])
    raise ValueError("unsupported format %#x" % t["fmt"])


def encode_into(b, name, im):
    t = textures(b)[name]
    if im.size != (t["w"], t["h"]):
        raise ValueError("%s must be %dx%d" % (name, t["w"], t["h"]))
    if t["fmt"] == BC4:
        lin = bc4_encode(im)
    elif t["fmt"] == ASTC4x4_SRGB:
        lin = astc_encode(im)
    else:
        raise ValueError("unsupported format %#x" % t["fmt"])
    write_linear(b, t, lin)


def swap(b, name_a, name_b):
    """Exchange two textures' image data (they must match in size and format)."""
    T = textures(b)
    a, c = T[name_a], T[name_b]
    assert (a["fmt"], a["w"], a["h"], a["bh"], a["size"]) == (c["fmt"], c["w"], c["h"], c["bh"], c["size"])
    da, dc, s = a["data"], c["data"], a["size"]
    b[da:da + s], b[dc:dc + s] = bytes(b[dc:dc + s]), bytes(b[da:da + s])


def bc4_encode(img):
    a = np.asarray(img.convert("L"), np.float32)
    h, w = a.shape
    H, W = (h + 3) // 4 * 4, (w + 3) // 4 * 4
    p = np.pad(a, ((0, H - h), (0, W - w)), mode="edge")
    blocks = p.reshape(H // 4, 4, W // 4, 4).transpose(0, 2, 1, 3).reshape(-1, 16)
    e0 = np.round(blocks.max(1)).astype(np.uint8)
    e1 = np.round(blocks.min(1)).astype(np.uint8)
    flat = e0 == e1
    e0 = np.where(flat & (e0 < 255), e0 + 1, e0).astype(np.uint8)
    e1 = np.where(flat & (e0 == e1), e1 - 1, e1).astype(np.uint8)
    f0, f1 = e0.astype(np.float32)[:, None], e1.astype(np.float32)[:, None]
    pal = np.concatenate([f0, f1] + [((8 - i) * f0 + (i - 1) * f1) / 7 for i in range(2, 8)], 1)
    idx = np.abs(blocks[:, :, None] - pal[:, None, :]).argmin(2).astype(np.uint64)
    bits = np.zeros(len(blocks), np.uint64)
    for i in range(16):
        bits |= idx[:, i] << np.uint64(3 * i)
    out = np.zeros((len(blocks), 8), np.uint8)
    out[:, 0], out[:, 1] = e0, e1
    for k in range(6):
        out[:, 2 + k] = ((bits >> np.uint64(8 * k)) & np.uint64(0xFF)).astype(np.uint8)
    return out.tobytes()


def astc_decode(lin, w, h):
    from astc_encoder import ASTCConfig, ASTCContext, ASTCImage, ASTCProfile, ASTCSwizzle, ASTCType
    ctx = ASTCContext(ASTCConfig(ASTCProfile.LDR_SRGB, 4, 4, 1, 60))
    img = ASTCImage(ASTCType.U8, w, h, 1)
    ctx.decompress(lin, img, ASTCSwizzle())
    return Image.frombytes("RGBA", (w, h), img.data)


def astc_encode(im):
    from astc_encoder import (ASTCConfig, ASTCContext, ASTCImage, ASTCProfile,
                              ASTCQualityPreset, ASTCSwizzle, ASTCType)
    im = im.convert("RGBA")
    ctx = ASTCContext(ASTCConfig(ASTCProfile.LDR_SRGB, 4, 4, 1, ASTCQualityPreset.THOROUGH))
    return ctx.compress(ASTCImage(ASTCType.U8, im.width, im.height, 1, im.tobytes()), ASTCSwizzle())
