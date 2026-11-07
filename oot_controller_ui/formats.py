"""Small Nintendo container formats used by the Switch 2 Ocarina of Time romfs.

- .zs        zstd, sometimes with a dictionary from Pack/ZsDic.pack.zs
- SARC       archives (.pack, .blarc, .bfarc)
- BFTTF      the XOR wrapper around .bfotf/.bfttf fonts (Switch 2 key)
- RESTBL     the resource size table (System/Resource/ResourceSizeTable...)
"""
import struct
import zlib

import zstandard

# ---------------------------------------------------------------- zstd / .zs

def load_dictionaries(zsdic_pack_zs: bytes):
    raw = zstandard.ZstdDecompressor().decompress(zsdic_pack_zs, max_output_size=1 << 26)
    return [zstandard.ZstdCompressionDict(v) for _, v in sarc_files(raw)]


def unzs(blob: bytes, dicts=()) -> bytes:
    try:
        return zstandard.ZstdDecompressor().decompressobj().decompress(blob)
    except zstandard.ZstdError:
        pass
    for d in dicts:
        try:
            return zstandard.ZstdDecompressor(dict_data=d).decompressobj().decompress(blob)
        except zstandard.ZstdError:
            continue
    raise ValueError("could not decompress .zs data")


def zs(data: bytes, level=12) -> bytes:
    """Plain zstd (the game accepts frames without a dictionary)."""
    return zstandard.ZstdCompressor(level=level, threads=-1).compress(data)


# ---------------------------------------------------------------- SARC

def _sarc_index(data: bytes):
    assert data[:4] == b"SARC", "not a SARC"
    assert data[6:8] == b"\xff\xfe", "only little-endian SARC is supported"
    hdr_len, = struct.unpack_from("<H", data, 4)
    data_off, = struct.unpack_from("<I", data, 0x0C)
    pos = hdr_len
    assert data[pos:pos + 4] == b"SFAT"
    sfat_len, count = struct.unpack_from("<HH", data, pos + 4)
    ents = [struct.unpack_from("<IIII", data, pos + sfat_len + i * 16) for i in range(count)]
    names = pos + sfat_len + count * 16
    assert data[names:names + 4] == b"SFNT"
    names += struct.unpack_from("<H", data, names + 4)[0]
    out = []
    for i, (_, attr, start, end) in enumerate(ents):
        if attr & 0x01000000:
            no = names + (attr & 0xFFFF) * 4
            name = data[no:data.index(b"\0", no)].decode()
        else:
            name = "file_%d" % i
        out.append((name, data_off + start, end - start))
    return out


def sarc_files(data: bytes):
    """[(name, bytes)] in archive order (names can repeat: the UI blarc stores copies)."""
    return [(n, data[o:o + s]) for n, o, s in _sarc_index(data)]


def sarc_entries(data: bytes, wanted: str):
    """[(absolute offset, size)] of every entry called `wanted`."""
    out = [(o, s) for n, o, s in _sarc_index(data) if n == wanted]
    if not out:
        raise KeyError(wanted)
    return out


# ---------------------------------------------------------------- BFTTF fonts

BFTTF_KEY = 0xA6018502          # Switch 2 ("Ounce") font XOR key
BFTTF_MAGIC = 0x7F9A0218        # first word once XORed


def _xor_words(b: bytes) -> bytes:
    b = b + b"\0" * (-len(b) % 4)
    n = len(b) // 4
    return struct.pack(">%dI" % n, *(w ^ BFTTF_KEY for w in struct.unpack(">%dI" % n, b)))


def bfttf_decode(blob: bytes) -> bytes:
    magic, size = struct.unpack(">II", _xor_words(blob[:8]))
    if magic != BFTTF_MAGIC:
        raise ValueError("not a Switch 2 BFTTF font (magic %#x)" % magic)
    return _xor_words(blob[8:])[:size]


def bfttf_encode(font: bytes) -> bytes:
    hdr = struct.pack(">II", BFTTF_MAGIC, len(font))
    return _xor_words(hdr + font)[:8 + len(font) + (-len(font) % 4)]


# ---------------------------------------------------------------- RESTBL

def restbl_get(rstb: bytes, path: str):
    """Size entry for a romfs path (without .zs), or None."""
    return _restbl_find(rstb, path)[1]


def restbl_set(rstb: bytearray, path: str, size: int):
    pos, _ = _restbl_find(rstb, path)
    if pos is None:
        raise KeyError(path)
    struct.pack_into("<I", rstb, pos, size)


def _restbl_find(rstb, path):
    assert bytes(rstb[:6]) == b"RESTBL", "not a RESTBL"
    _, strsz, ncrc, nname = struct.unpack_from("<IIII", rstb, 6)
    target = zlib.crc32(path.encode())
    pos = 0x16
    for _ in range(ncrc):
        crc, size = struct.unpack_from("<II", rstb, pos)
        if crc == target:
            return pos + 4, size
        pos += 8
    for _ in range(nname):
        name = bytes(rstb[pos:pos + strsz]).split(b"\0")[0].decode()
        if name == path:
            return pos + strsz, struct.unpack_from("<I", rstb, pos + strsz)[0]
        pos += strsz + 4
    return None, None
