"""Read Lichii .nup packages, and reversibly replace files inside one.

Format (from Lichii's src/core/file_sys/nup_container.cpp): a 0x80-byte superblock
("NUP\\x01"), a SHA-256-checked table of contents (packages, directories, files, a
children array and a string pool), then a blob region of raw or zstd file extents.

Patching appends new data to the end of the file and repoints the file records; the
original superblock, TOC and size are saved to <file>.undo first, so `undo` restores the
file byte for byte. `apply` always undoes an earlier patch first.
"""
import hashlib
import os
import struct

import zstandard

NO_DIR = 0xFFFFFFFF
UNDO_MAGIC = b"NUPUNDO1"


class Nup:
    def __init__(self, path):
        self.path = path
        self.f = open(path, "rb")
        sb = self.f.read(0x80)
        if sb[:4] != b"NUP\x01":
            raise ValueError("%s is not a Lichii .nup file" % path)
        self.toc_off, self.toc_size = struct.unpack_from("<QQ", sb, 8)
        self.f.seek(self.toc_off)
        toc = self.f.read(self.toc_size)
        if hashlib.sha256(toc).digest() != sb[0x18:0x38]:
            raise ValueError("the .nup table of contents fails its checksum")
        magic, pkg_count, dir_count, file_count, pool_off, pool_size = struct.unpack_from("<IIQQQQ", toc, 0)
        assert magic == 0x01434F54
        pos = 0x30
        self.packages = []
        for _ in range(pkg_count):
            tid, root, exefs, romfs, ver, kind = struct.unpack_from("<QIIIIB", toc, pos)
            self.packages.append(dict(title_id=tid, exefs=exefs, romfs=romfs, version=ver, kind=kind))
            pos += 0x40
        pool = toc[pool_off:pool_off + pool_size]
        self.dirs = []
        for _ in range(dir_count):
            no, nl, fc, cc = struct.unpack_from("<IIII", toc, pos)
            self.dirs.append((pool[no:no + nl].decode("utf-8", "replace"), fc, cc))
            pos += 0x18
        self.file_rec_base = pos
        self.files = []
        for _ in range(file_count):
            no, nl, size, eoff, esize = struct.unpack_from("<IIQQQ", toc, pos)
            self.files.append((pool[no:no + nl].decode("utf-8", "replace"), size, eoff, esize, toc[pos + 0x40]))
            pos += 0x50
        self.children = struct.unpack_from("<%dI" % ((pool_off - pos) // 4), toc, pos)

    def close(self):
        self.f.close()

    def _walk(self, d, prefix=""):
        _, first, count = self.dirs[d]
        for slot in range(first, first + count):
            c = self.children[slot]
            if c >= len(self.dirs):
                yield prefix + self.files[c - len(self.dirs)][0], c - len(self.dirs)
            else:
                yield from self._walk(c, prefix + self.dirs[c][0] + "/")

    def romfs_index(self):
        """romfs-relative path -> file index (update packages override the base)."""
        idx = {}
        for p in sorted(self.packages, key=lambda p: p["kind"] == 1):
            if p["kind"] in (0, 1) and p["romfs"] != NO_DIR:
                idx.update(dict(self._walk(p["romfs"])))
        return idx

    def read(self, fi):
        _, size, eoff, esize, codec = self.files[fi]
        if size == 0:
            return b""
        self.f.seek(eoff)
        data = self.f.read(esize)
        return data[:size] if codec == 0 else zstandard.ZstdDecompressor().decompress(data, max_output_size=size)


def undo(path, quiet=False):
    up = path + ".undo"
    if not os.path.exists(up):
        if not quiet:
            print("nothing to undo")
        return False
    blob = open(up, "rb").read()
    assert blob[:8] == UNDO_MAGIC, "bad undo file"
    orig_size, toc_off, toc_len = struct.unpack_from("<QQQ", blob, 8)
    with open(path, "r+b") as f:
        f.seek(0)
        f.write(blob[32:32 + 0x80])
        f.seek(toc_off)
        f.write(blob[32 + 0x80:32 + 0x80 + toc_len])
        f.truncate(orig_size)
    os.remove(up)
    print("restored the original .nup (%d bytes)" % orig_size)
    return True


def apply(path, replacements):
    """replacements: {romfs-relative path: bytes}. Every path must already exist."""
    undo(path, quiet=True)
    size = os.path.getsize(path)
    with open(path, "rb") as f:
        sb = bytearray(f.read(0x80))
        toc_off, toc_size = struct.unpack_from("<QQ", sb, 8)
        f.seek(toc_off)
        toc = bytearray(f.read(toc_size))
    nup = Nup(path)
    idx = nup.romfs_index()
    rec_base = nup.file_rec_base
    nup.close()
    missing = [p for p in replacements if p not in idx]
    if missing:
        raise SystemExit("not in this .nup, refusing to patch: %s" % ", ".join(missing))

    with open(path + ".undo", "wb") as u:
        u.write(UNDO_MAGIC + struct.pack("<QQQ", size, toc_off, toc_size) + bytes(sb) + bytes(toc))

    with open(path, "r+b") as f:
        end = size
        for rel, data in replacements.items():
            off = (end + 15) & ~15
            f.seek(end)
            f.write(b"\0" * (off - end) + data)
            end = off + len(data)
            r = rec_base + idx[rel] * 0x50
            struct.pack_into("<QQQ", toc, r + 0x08, len(data), off, len(data))
            toc[r + 0x20:r + 0x40] = hashlib.sha256(data).digest()
            toc[r + 0x40] = 0
            print("  replaced", rel)
        f.truncate(end)
        sb[0x18:0x38] = hashlib.sha256(toc).digest()
        struct.pack_into("<Q", sb, 0x40, end)
        f.seek(toc_off)
        f.write(toc)
        f.seek(0)
        f.write(sb)
    verify(path, replacements)
    print("patched %s (+%d bytes). Undo data: %s.undo" % (os.path.basename(path), end - size, path))


def verify(path, replacements):
    """Re-open the file and check what Lichii checks, plus that our files read back."""
    nup = Nup(path)
    with open(path, "rb") as f:
        sb = f.read(0x80)
    blob_off, fsize = struct.unpack_from("<QQ", sb, 0x38)
    assert fsize == os.path.getsize(path), "file size field mismatch"
    for _, s, o, e, c in nup.files:
        if s:
            assert e and o >= blob_off and o % 16 == 0 and o <= fsize and e <= fsize - o and c <= 1, "bad extent"
    idx = nup.romfs_index()
    for rel, data in replacements.items():
        assert nup.read(idx[rel]) == data, "read-back mismatch: " + rel
    nup.close()
