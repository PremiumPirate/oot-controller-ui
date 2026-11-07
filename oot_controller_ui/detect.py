"""Find Lichii/Eden's user folder, the user's game files and the Lichii build, on each OS.

Lichii keeps Eden's data layout (src/common/fs/path_util.cpp):
  Windows        <exe dir>/user  if it exists, else %APPDATA%/eden
  Linux, macOS,  ./user (portable) if it exists, else $XDG_DATA_HOME/eden (~/.local/share/eden);
  Steam Deck     config in $XDG_CONFIG_HOME/eden (~/.config/eden)
Mods live in <user dir>/load/<TITLE ID>/<mod name>/romfs/...
"""
import os
import re
import sys

from . import known

UI_FOLDERS = {"xbox": "Xbox UI", "ps5": "PS5 UI", "steam": "Steam Deck UI"}


def _env_dir(var, fallback):
    v = os.environ.get(var)
    return v if v else os.path.join(os.path.expanduser("~"), fallback)


_override = None


def set_user_dir(path):
    """Use a folder the user picked: Lichii's user folder itself, or the folder that holds a
    portable 'user' folder (next to lichii.exe)."""
    global _override
    path = os.path.normpath(path)
    if os.path.isdir(os.path.join(path, "user")):
        path = os.path.join(path, "user")
    _override = path
    return path


def user_dirs():
    """Candidate Eden/Lichii user folders that exist, most likely first."""
    if _override:
        return [_override]
    c = []
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            c.append(os.path.join(appdata, "eden"))
    else:
        c.append(os.path.join(_env_dir("XDG_DATA_HOME", ".local/share"), "eden"))
        if sys.platform == "darwin":
            c.append(os.path.expanduser("~/Library/Application Support/eden"))
    return [d for d in c if os.path.isdir(d)]


def config_files():
    c = []
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            c.append(os.path.join(appdata, "eden", "config", "qt-config.ini"))
    else:
        c.append(os.path.join(_env_dir("XDG_CONFIG_HOME", ".config"), "eden", "qt-config.ini"))
    for d in user_dirs():
        c.append(os.path.join(d, "config", "qt-config.ini"))
    return [f for f in dict.fromkeys(c) if os.path.isfile(f)]


def _is_oot_nup(path):
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"NUP\x01"
    except OSError:
        return False


def find_games():
    """.nup files from Lichii's game folders and recent files (quick header check only)."""
    found, dirs = [], []
    for cfg in config_files():
        try:
            text = open(cfg, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        for m in re.finditer(r"^Paths\\recentFiles=(.*)$", text, re.M):
            for p in re.split(r",\s*", m.group(1)):
                p = p.strip().strip('"')
                if p.lower().endswith(".nup"):
                    found.append(os.path.normpath(p))
        for m in re.finditer(r"^Paths\\gamedirs\\\d+\\path=(.*)$", text, re.M):
            p = m.group(1).strip().strip('"')
            if p and p not in ("SDMC", "UserNAND", "SysNAND"):
                dirs.append(p)
    for d in dirs:
        try:
            for n in os.listdir(d):
                if n.lower().endswith(".nup"):
                    found.append(os.path.normpath(os.path.join(d, n)))
        except OSError:
            pass
    out = []
    for p in dict.fromkeys(found):
        if os.path.isfile(p) and _is_oot_nup(p):
            out.append(p)
    # Ocarina of Time first (file name hint), then the rest
    out = sorted(out, key=lambda p: ("ocarina" not in p.lower(), p.lower()))
    return out + find_dumps()


def find_dumps():
    """RomFS dumps made with Lichii's 'Dump RomFS' (<user>/dump/<TITLE ID>/romfs), which is how
    NSP/XCI players give the builder their game files."""
    tid = "%016X" % known.TITLE_ID
    out = []
    for d in user_dirs():
        for name in (tid, tid.lower()):
            p = os.path.normpath(os.path.join(d, "dump", name, "romfs"))
            if os.path.isfile(os.path.join(p, *known.FONT.split("/")) + ".zs") and \
                    os.path.normcase(p) not in [os.path.normcase(o) for o in out]:
                out.append(p)
    return out


def lichii_build():
    """Build number from Lichii's newest log ('... nx2-build-93'), or None."""
    for d in user_dirs():
        log = os.path.join(d, "log", "eden_log.txt")
        try:
            head = open(log, encoding="utf-8", errors="replace").read(4000)
        except OSError:
            continue
        m = re.search(r"build-(\d+)", head)
        if m:
            return int(m.group(1))
    return None


# Lichii builds up to this one don't apply LayeredFS mods to .nup games. Build 95 (tagged
# build-94) added it: "LayeredFS mods now apply to NUP titles" (Lichii PR #203).
LAST_BUILD_WITHOUT_NUP_MODS = 93
FIRST_BUILD_WITH_NUP_MODS = 95


def mod_root():
    d = user_dirs()
    if not d:
        return None
    return os.path.join(d[0], "load", "%016X" % known.TITLE_ID)


def installed_mods():
    root = mod_root()
    if not root or not os.path.isdir(root):
        return []
    return [os.path.join(root, n) for n in UI_FOLDERS.values() if os.path.isdir(os.path.join(root, n))]


def open_folder(path):
    import subprocess
    if sys.platform == "win32":
        os.startfile(path)  # noqa: S606
    elif sys.platform == "darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
