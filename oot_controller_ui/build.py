"""Build the Xbox UI files from the user's own game files."""
import hashlib
import os

from . import bntx, glyphs, known, paint, ring
from .formats import (bfttf_decode, bfttf_encode, load_dictionaries, restbl_get, restbl_set,
                      unzs, zs)
from .nup import Nup

INPUTS = [known.FONT + ".zs", known.BNTX + ".zs", known.BLARC + ".zs", known.RSTB + ".zs", known.ZSDIC]
TEXTURE_SWAPS = [("KeyTexFontX_00", "KeyTexFontY_00"), ("OcarinaButtonX_00", "OcarinaButtonY_00")]


class NupSource:
    def __init__(self, path):
        self.nup = Nup(path)
        if not any(p["title_id"] == known.TITLE_ID for p in self.nup.packages):
            raise SystemExit("this .nup is not Ocarina of Time (Switch 2, %016X)" % known.TITLE_ID)
        self.idx = self.nup.romfs_index()

    def read(self, rel):
        if rel not in self.idx:
            raise SystemExit("missing from the .nup: " + rel)
        return self.nup.read(self.idx[rel])


class DirSource:
    """An extracted romfs folder (e.g. from Lichii's 'Extract NUP' or an NSP dump)."""

    def __init__(self, path):
        self.path = path

    def read(self, rel):
        p = os.path.join(self.path, *rel.split("/"))
        if not os.path.exists(p):
            raise SystemExit("missing from the romfs folder: " + rel)
        return open(p, "rb").read()


def identify(files):
    """Return the supported version name, or raise with what didn't match."""
    sums = {rel: hashlib.sha256(data).hexdigest() for rel, data in files.items()}
    for name, want in known.VERSIONS.items():
        if all(sums[rel] == h for rel, h in want.items()):
            return name
    bad = [rel for rel in INPUTS if all(v[rel] != sums[rel] for v in known.VERSIONS.values())]
    raise SystemExit("unsupported game version: these files differ from every supported version:\n  "
                     + "\n  ".join(bad) + "\nSee CLAUDE.md ('Supporting another version').")


STYLES = {
    "xbox": dict(label="Xbox", bumpers=("LB", "RB"), font_note="X/Y swapped, LB/RB, LT/RT, Menu, View"),
    "ps5": dict(label="PS5", bumpers=("L1", "R1"), font_note="Cross/Circle/Triangle/Square, L1/R1, L2/R2, Options, Create"),
    "steam": dict(label="Steam Deck", bumpers=("L1", "R1"), font_note="X/Y swapped, L1/R1, L2/R2, Menu, View"),
}
# Switch button -> PlayStation symbol (buttons matched by position: Cross = Switch A, etc.)
PS_SYMBOL = {"A": "cross", "B": "circle", "X": "triangle", "Y": "square"}


STEPS = ["Reading your game files", "Writing the button font", "Painting the textures",
         "Moving the action ring", "Saving"]


def build(source, font_set, style="xbox", log=print, progress=lambda i, label: None):
    """progress(i, label) is called as each of STEPS[0..3] starts (the caller does step 4)."""
    if style not in STYLES:
        raise SystemExit("unknown style %r (choose: %s)" % (style, ", ".join(STYLES)))
    st = STYLES[style]
    progress(0, STEPS[0])
    files = {rel: source.read(rel) for rel in INPUTS}
    log("game version: " + identify(files))
    log("style: " + st["label"])
    dicts = load_dictionaries(files[known.ZSDIC])
    out = {}

    # 1. button-glyph font
    progress(1, STEPS[1])
    font_orig = unzs(files[known.FONT + ".zs"], dicts)
    font_new = bfttf_encode(glyphs.build(bfttf_decode(font_orig), font_set["bold"], style))
    out[known.FONT + ".zs"] = zs(font_new)
    log("font: " + st["font_note"])

    # 2. UI texture bank
    progress(2, STEPS[2])
    b = bytearray(unzs(files[known.BNTX + ".zs"], dicts))
    if style in ("xbox", "steam"):
        for x, y in TEXTURE_SWAPS:
            bntx.swap(b, x, y)
    else:
        for btn, kind in PS_SYMBOL.items():
            bntx.encode_into(b, "KeyTexFont%s_00" % btn, paint.keytex(kind))
            bntx.encode_into(b, "OcarinaButton%s_00" % btn, paint.ocarina_face(kind))
    for name in ("Controller_Pro1", "Controller_Pro"):
        bntx.encode_into(b, name, paint.controller(bntx.decode(b, name), font_set["semilight"], style))
    lb, rb = st["bumpers"]
    bntx.encode_into(b, "OcarinaButtonL_00", paint.ocarina_lr(lb, True, font_set["semibold"]))
    bntx.encode_into(b, "OcarinaButtonR_00", paint.ocarina_lr(rb, False, font_set["semibold"]))
    bntx.encode_into(b, "OcarinaButtonLRSh_00", paint.ocarina_lr_shadow())
    out[known.BNTX + ".zs"] = zs(bytes(b))
    log("textures: ring letters, controller picture, ocarina icons")

    # 3. action-ring layout
    progress(3, STEPS[3])
    out[known.BLARC + ".zs"] = zs(ring.patch(unzs(files[known.BLARC + ".zs"], dicts)))
    log("layout: action ring rearranged (bottom = Switch A, right = Switch B)")

    # 4. resource size table: keep the original headroom over the (bigger) font
    rstb = bytearray(unzs(files[known.RSTB + ".zs"], dicts))
    entry = restbl_get(rstb, known.FONT)
    restbl_set(rstb, known.FONT, max(entry, len(font_new) + entry - len(font_orig)))
    out[known.RSTB + ".zs"] = zs(bytes(rstb))
    return out


def write_mod(out, mod_dir):
    for rel, data in out.items():
        p = os.path.join(mod_dir, "romfs", *rel.split("/"))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)
