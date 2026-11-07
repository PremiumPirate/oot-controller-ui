"""Self-contained tests (no game files needed):  python -m pytest tests   or   python tests/test_core.py"""
import hashlib
import os
import struct
import sys
import tempfile

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from oot_controller_ui import bntx, formats, nup  # noqa: E402


def make_nup(path, files):
    """Write a minimal valid .nup: one update package whose romfs holds `files` {name: bytes}."""
    names = list(files)
    pool = b""
    def add(s):
        nonlocal pool
        off = len(pool)
        pool += s.encode()
        return off, len(s.encode())
    dirs = [add(""), add("romfs")]
    fnames = [add(n) for n in names]
    dir_count, file_count = 2, len(names)
    children = [1] + [dir_count + i for i in range(file_count)]
    needed = 0x30 + 0x40 + dir_count * 0x18 + file_count * 0x50
    pool_off = needed + len(children) * 4
    blob_off = 0x80 + ((pool_off + len(pool) + 15) & ~15)
    blob, recs, cur = b"", [], blob_off
    for (no, nl), n in zip(fnames, names):
        data = files[n]
        recs.append(struct.pack("<IIQQQ32sBBH12s", no, nl, len(data), cur, len(data),
                                hashlib.sha256(data).digest(), 0, 0, 0, b""))
        pad = (-len(data)) % 16
        blob += data + b"\0" * pad
        cur += len(data) + pad
    toc = struct.pack("<IIQQQQQ", 0x01434F54, 1, dir_count, file_count, pool_off, len(pool), 0)
    toc += struct.pack("<QIIIIBBHIQI20s", 0x0400486024DEC000, 0, 0xFFFFFFFF, 1, 131072, 1, 0, 0, 0, 0, 0, b"")
    toc += struct.pack("<IIIIQ", *dirs[0], 0, 1, 0) + struct.pack("<IIIIQ", *dirs[1], 1, file_count, 0)
    toc += b"".join(recs) + struct.pack("<%dI" % len(children), *children) + pool
    toc += b"\0" * (blob_off - 0x80 - len(toc))
    size = blob_off + len(blob)
    sb = b"NUP\x01" + struct.pack("<HHQQ32sQQII16s32s", 0x80, 1, 0x80, len(toc), hashlib.sha256(toc).digest(),
                                   blob_off, size, 1, 0, b"", b"")
    with open(path, "wb") as f:
        f.write(sb + toc + blob)


def test_nup_patch_and_undo():
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "game.nup")
        make_nup(p, {"a.bin": b"original A" * 10, "b.bin": b"original B"})
        before = open(p, "rb").read()
        n = nup.Nup(p)
        assert {k: n.read(v) for k, v in n.romfs_index().items()} == {"a.bin": b"original A" * 10, "b.bin": b"original B"}
        n.close()
        nup.apply(p, {"b.bin": b"patched B, longer than before"})
        n = nup.Nup(p)
        idx = n.romfs_index()
        assert n.read(idx["b.bin"]) == b"patched B, longer than before"
        assert n.read(idx["a.bin"]) == b"original A" * 10
        n.close()
        nup.apply(p, {"b.bin": b"again"})          # re-apply undoes first: file doesn't keep growing
        assert os.path.getsize(p) < len(before) + 64
        assert nup.undo(p)
        assert open(p, "rb").read() == before
        assert not os.path.exists(p + ".undo")


def test_bfttf_roundtrip():
    font = os.urandom(1001)
    assert formats.bfttf_decode(formats.bfttf_encode(font)) == font


def test_swizzle_roundtrip():
    t = dict(fmt=bntx.BC4, w=93, h=93, bh=2, size=0, data=0)
    bx, by = 24, 24
    t["size"] = ((bx * 8 + 63) // 64) * 64 * ((by + 15) // 16) * 16
    buf = bytearray(t["size"])
    lin = os.urandom(bx * by * 8)
    bntx.write_linear(buf, t, lin)
    assert bntx.read_linear(buf, t) == lin


def test_bc4_encode_quality():
    g = np.tile(np.linspace(0, 255, 64, dtype=np.float32), (64, 1))
    lin = bntx.bc4_encode(Image.fromarray(g.astype(np.uint8)))
    back = np.asarray(Image.frombytes("L", (64, 64), lin, "bcn", 4), np.float32)
    assert np.abs(back - g).max() <= 4


def test_ps_symbols_draw():
    from oot_controller_ui import paint
    for kind in ("cross", "circle", "triangle", "square"):
        k = np.asarray(paint.keytex(kind))
        assert k.max() > 200 and (k > 128).mean() > 0.03, kind      # visible white strokes
        o = np.asarray(paint.ocarina_face(kind))
        assert o[46, 8, 3] < 10 and o[46, 46, 3] > 245, kind       # outside transparent, disc opaque


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
