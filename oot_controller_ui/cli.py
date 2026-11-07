"""oot-controller-ui command line.

  python -m oot_controller_ui check     --nup GAME.nup | --romfs DIR
  python -m oot_controller_ui build     --nup GAME.nup | --romfs DIR  --out MOD_FOLDER
  python -m oot_controller_ui patch-nup --nup GAME.nup
  python -m oot_controller_ui undo      --nup GAME.nup
"""
import argparse
import os
import sys

from . import __version__, build, known, nup
from .fonts import FONT_SETS, font_set


def _source(a):
    if bool(a.nup) == bool(a.romfs):
        raise SystemExit("give exactly one of --nup or --romfs")
    return build.NupSource(a.nup) if a.nup else build.DirSource(a.romfs)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="oot_controller_ui", description="Xbox, PS5 or Steam Deck button UI for Ocarina of Time (Switch 2).")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, hlp in [("gui", "open the installer window"),
                      ("check", "check that your game version is supported"),
                      ("build", "write a mod folder (Lichii build 95+ loads it for .nup games)"),
                      ("patch-nup", "legacy: write the changes into a Lichii .nup, for Lichii build 93 and older"),
                      ("undo", "restore a .nup patched with patch-nup to the original")]:
        p = sub.add_parser(name, help=hlp)
        p.add_argument("--nup", help="your Lichii .nup game file")
        if name in ("check", "build"):
            p.add_argument("--romfs", help="an extracted romfs folder instead of a .nup")
        if name == "build":
            p.add_argument("--out", required=True, help="mod folder to create (romfs/ goes inside)")
        if name in ("build", "patch-nup"):
            p.add_argument("--style", choices=["xbox", "ps5", "steam"], default="xbox",
                           help="button style: xbox (default), ps5 or steam (Steam Deck)")
            p.add_argument("--fonts", choices=sorted(FONT_SETS), default="selawik",
                           help="letter fonts: bundled Selawik (default) or Windows Segoe UI")
        if name == "patch-nup":
            p.add_argument("--yes", action="store_true", help="don't ask for confirmation")
    a = ap.parse_args(argv)

    if a.cmd == "gui":
        from . import gui
        gui.main()
        return

    if a.cmd == "undo":
        if not a.nup:
            raise SystemExit("--nup is required")
        nup.undo(a.nup)
        return

    patched = bool(a.nup) and os.path.exists(a.nup + ".undo")
    if a.cmd == "patch-nup":
        if not a.nup:
            raise SystemExit("--nup is required")
        a.romfs = None
        print("This edits your .nup in place (about +70 MB). Undo data is saved next to it,")
        print("but keep your own backup. Close Lichii before continuing.")
        if not a.yes and input("Patch %s? [y/N] " % os.path.basename(a.nup)).strip().lower() != "y":
            print("cancelled")
            return
        if patched:
            nup.undo(a.nup)          # rebuild from the original files, not an earlier patch
    elif patched:
        raise SystemExit("%s is already patched by this tool; run 'undo' first (or use patch-nup, "
                         "which re-patches from the original)." % a.nup)

    src = _source(a)
    if a.cmd == "check":
        files = {rel: src.read(rel) for rel in build.INPUTS}
        print("supported: " + build.identify(files))
        return

    out = build.build(src, font_set(a.fonts), a.style)
    if isinstance(src, build.NupSource):
        src.nup.close()

    if a.cmd == "build":
        build.write_mod(out, a.out)
        print("\nmod written to %s" % os.path.abspath(a.out))
        print("Lichii/Eden: put it at  <user dir>/load/%016X/<mod name>/  (it must contain romfs/)" % known.TITLE_ID)
        print("Enable only one UI mod (Xbox, PS5 or Steam Deck) at a time.")
        return

    nup.apply(a.nup, out)


if __name__ == "__main__":
    main(sys.argv[1:])
