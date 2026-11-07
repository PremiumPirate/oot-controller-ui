"""Build the standalone installer for the current platform with PyInstaller.

  python packaging/build_installer.py

Output (in dist/):
  Windows   OoT-Controller-UI-Installer.exe          (one file)
  Linux     OoT-Controller-UI-Installer               (one file; runs on Steam Deck desktop mode)
  macOS     OoT Controller UI Installer.app           (zip it for distribution)
PyInstaller can't cross-compile: build each platform on that platform (see .github/workflows).
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from oot_controller_ui import theme  # noqa: E402

build_dir = os.path.join(ROOT, "build", "installer")
os.makedirs(build_dir, exist_ok=True)
icon = theme.app_icon(256)
ico = os.path.join(build_dir, "icon.ico")
icns = os.path.join(build_dir, "icon.icns")
png = os.path.join(build_dir, "icon.png")
icon.save(ico, sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
icon.save(png)
try:
    theme.app_icon(512).save(icns)
except Exception:  # noqa: BLE001 - icns writing isn't available everywhere
    icns = None

sep = ";" if sys.platform == "win32" else ":"
name = "OoT Controller UI Installer" if sys.platform == "darwin" else "OoT-Controller-UI-Installer"
args = [
    sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--windowed",
    "--name", name,
    "--distpath", os.path.join(ROOT, "dist"), "--workpath", build_dir, "--specpath", build_dir,
    "--add-data", "%s%soot_controller_ui/fonts" % (os.path.join(ROOT, "oot_controller_ui", "fonts"), sep),
    "--collect-submodules", "fontTools",
    "--collect-all", "astc_encoder",
    "--collect-all", "archspec",          # astc_encoder picks its CPU build via archspec's JSON data
    "--collect-all", "pathops",
    "--hidden-import", "PIL._tkinter_finder",
    "--exclude-module", "cv2", "--exclude-module", "scipy", "--exclude-module", "matplotlib",
]
if sys.platform == "darwin":
    args += ["--onedir", "--osx-bundle-identifier", "io.github.premiumpirate.oot-controller-ui"]
    if icns:
        args += ["--icon", icns]
else:
    args += ["--onefile", "--icon", ico if sys.platform == "win32" else png]
args.append(os.path.join(ROOT, "installer.py"))
print(" ".join(args))
subprocess.check_call(args, cwd=ROOT)
