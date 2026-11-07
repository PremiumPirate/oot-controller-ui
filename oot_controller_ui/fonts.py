"""Which letter fonts to draw with.

Default: Selawik (Microsoft's open-source, SIL OFL 1.1 stand-in for Segoe UI), bundled.
'segoe' uses the Segoe UI files from a Windows install instead (what the original build used).
"""
import os

HERE = os.path.join(os.path.dirname(__file__), "fonts")
WIN = os.path.join(os.environ.get("WINDIR", "C:/Windows"), "Fonts")

FONT_SETS = {
    "selawik": {"bold": os.path.join(HERE, "selawkb.ttf"),
                "semibold": os.path.join(HERE, "selawksb.ttf"),
                "semilight": os.path.join(HERE, "selawksl.ttf")},
    "segoe": {"bold": os.path.join(WIN, "segoeuib.ttf"),
              "semibold": os.path.join(WIN, "seguisb.ttf"),
              "semilight": os.path.join(WIN, "segoeuisl.ttf")},
}


def font_set(name):
    fs = FONT_SETS[name]
    missing = [p for p in fs.values() if not os.path.exists(p)]
    if missing:
        raise SystemExit("font set '%s' is missing: %s" % (name, ", ".join(missing)))
    return fs
