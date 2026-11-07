"""Rearrange the action-button ring (DoCommand_00 layout, Switch 2 '.buil' format).

Switch ring: X top, Y left, A right, B bottom.  Xbox ring: Y top, X left, B right, A bottom.
X/Y letters are swapped by texture elsewhere; here the right and bottom slots trade places
in all four ring groups, and the A/B background shapes trade materials so the gap behind
the main button follows it.

.buil layout facts used (this game version): 64 panes; pointer table to 0x44-byte pane
records at 0x320, name table (absolute string offsets) at 0x520. In a pane record the
translation x/y floats are at +0x1C/+0x20 and the first material index (int16) at +0x3C.
"""
import struct

from .formats import sarc_entries

LAYOUT = "DoCommand_00.buil"
RIGHT, BOTTOM = (80.0, 0.0), (0.0, -80.0)
MOVES = {
    "N_BtnA_00": BOTTOM, "P_B_00": RIGHT,    # A ring: main A to bottom, faded B to right
    "N_BtnB_00": RIGHT, "P_A_00": BOTTOM,    # B ring: main B to right, faded A to bottom
    "P_A_02": BOTTOM, "P_B_03": RIGHT,       # X ring
    "P_A_01": BOTTOM, "P_B_02": RIGHT,       # Y ring
}
EXPECTED_BEFORE = {"N_BtnA_00": RIGHT, "P_B_00": BOTTOM, "N_BtnB_00": BOTTOM, "P_A_00": RIGHT,
                   "P_A_02": RIGHT, "P_B_03": BOTTOM, "P_A_01": RIGHT, "P_B_02": BOTTOM}
SWAP_MATERIAL = ("P_BaseA_00", "P_BaseB_00")
NAME_TABLE, PTR_TABLE, COUNT = 0x520, 0x320, 64


def _panes(buil):
    out = {}
    for i in range(COUNT):
        a, = struct.unpack_from("<Q", buil, NAME_TABLE + i * 8)
        out[bytes(buil[a:buil.index(b"\0", a)]).decode()] = struct.unpack_from("<Q", buil, PTR_TABLE + i * 8)[0]
    return out


def _patch_buil(buil):
    p = _panes(buil)
    for name, want in EXPECTED_BEFORE.items():
        x, y = struct.unpack_from("<ff", buil, p[name] + 0x1C)
        if (round(x, 3), round(y, 3)) != (round(want[0], 3), round(want[1], 3)):
            raise ValueError("%s is at (%g, %g), expected %s: different layout version?" % (name, x, y, want))
    for name, (x, y) in MOVES.items():
        struct.pack_into("<ff", buil, p[name] + 0x1C, x, y)
    a, b = (p[n] + 0x3C for n in SWAP_MATERIAL)
    buil[a:a + 2], buil[b:b + 2] = bytes(buil[b:b + 2]), bytes(buil[a:a + 2])


def patch(blarc: bytes) -> bytes:
    """Return the layout archive with every copy of DoCommand_00 rearranged (size unchanged)."""
    out = bytearray(blarc)
    for off, size in sarc_entries(blarc, LAYOUT):
        buil = bytearray(out[off:off + size])
        _patch_buil(buil)
        out[off:off + size] = buil
    return bytes(out)
