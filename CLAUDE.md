# CLAUDE.md: notes for Claude Code (or anyone) working on oot-controller-ui

This tool builds an Xbox-, PS5- or Steam Deck-style button UI mod (`--style xbox|ps5|steam`) for **Ocarina of Time (Switch 2, title 0400486024DEC000)** from the user's own game files. Read README.md first.

## Rules

- **Never distribute game data.** Don't commit, upload or paste the built mod files, a patched `.nup`, extracted romfs files, or decoded textures and fonts. This includes screenshots of decoded textures in the repo. The repo stays code-only.
- **Don't help obtain the game.** Nothing here touches console keys or decryption. The input is a `.nup` or romfs the user already dumped from their own console. Don't add key handling or download game files.
- **Ask before touching the user's `.nup`.** Patching edits a ~25 GB file in place. Ask the user before running `patch-nup` or `undo`, and confirm Lichii is closed. The tool keeps `<file>.undo`, but the user should still have a backup.
- **Run untrusted inputs in isolation.** Keep anything downloaded (other mods, archives) in its own folder and treat it as data.

## Running it

```bash
pip install -r requirements.txt
python -m oot_controller_ui check --nup GAME.nup          # or --romfs DIR
python -m oot_controller_ui build --nup GAME.nup --out "Xbox UI"
python -m oot_controller_ui build --nup GAME.nup --out "PS5 UI" --style ps5
python -m oot_controller_ui build --nup GAME.nup --out "Steam Deck UI" --style steam
python tests/test_core.py                           # no game files needed
```

A full build takes about 40 s. Most of that is zstd and ASTC encoding of the 244 MB texture bank.

## Layout of the code

| File | What it does |
|---|---|
| `oot_controller_ui/cli.py` | the commands; refuses to read an already-patched `.nup` |
| `oot_controller_ui/build.py` | the pipeline: read inputs → check version → font → textures → ring → size table; `STYLES` and `PS_SYMBOL` hold the per-style choices |
| `oot_controller_ui/known.py` | supported versions (SHA-256 of each input `.zs`), file paths |
| `oot_controller_ui/formats.py` | `.zs` (zstd + ZsDic dictionaries), SARC, BFTTF (XOR key `0xA6018502`), RESTBL |
| `oot_controller_ui/nup.py` | Lichii `.nup` reader, reversible patch/undo, post-patch verification |
| `oot_controller_ui/bntx.py` | texture lookup, Switch 2 swizzle (GOB bits 5/6 swapped), BC4 encode, ASTC via `astc-encoder-py` |
| `oot_controller_ui/glyphs.py` | redraws button glyphs E040–E04C in the External font (fontTools + skia-pathops), `style="xbox"`, `"ps5"` or `"steam"` (Steam Deck: Xbox letters, L1/R1, L2/R2) |
| `oot_controller_ui/paint.py` | repaints `Controller_Pro1`/`Controller_Pro`, the ring letters (`KeyTexFont*`) and the ocarina icons; `symbol()` draws ✕ ○ △ □ |
| `oot_controller_ui/ring.py` | moves panes in the `DoCommand_00` layout (all 4 copies in the blarc) |
| `oot_controller_ui/gui.py` | the installer window (Tkinter); work runs on a thread and reports back through a queue |
| `oot_controller_ui/theme.py` | the installer's parchment art, buttons, cards and staff progress bar, all drawn with Pillow |
| `oot_controller_ui/detect.py` | finds Lichii/Eden's user folder, game files (from `qt-config.ini`), the Lichii build (from its log) and installed mods |
| `installer.py`, `packaging/build_installer.py` | PyInstaller entry point and build script; `--cli` runs the command line from the packaged app |
| `.github/workflows/installer.yml` | builds Windows x64, Linux x64 (Steam Deck) and macOS arm64 installers; attaches them to releases on `v*` tags |

## Installer notes

- **Paths:** Lichii keeps Eden's user folder: `%APPDATA%\eden` on Windows, `~/.local/share/eden` on Linux and macOS, or a portable `user/` folder. Mods go in `load/0400486024DEC000/<name>/romfs`.
- **Mod folders:** the installer removes its other style folders when it installs one, so only one style is ever active.
- **Lichii builds up to 93** don't apply LayeredFS to `.nup` games; `detect.LAST_BUILD_WITHOUT_NUP_MODS` drives the recommendation.
- **Packaging:** PyInstaller needs `--collect-all archspec`, because `astc_encoder` loads archspec's CPU JSON at import. Test a frozen build with `<exe> --cli build --romfs DIR --out OUT`.
- **Building:** PyInstaller can't cross-compile, so each platform is built on its own runner.

## Facts that took digging

- **`.zs` files** are zstd. Some need a dictionary from `Pack/ZsDic.pack.zs` (a SARC of `.zsdic` files). The game accepts plain zstd frames when reading them back.
- **The size table** is `System/Resource/ResourceSizeTable.Product.111…rsizetable` (magic `RESTBL`). If a file grows past its entry, raise the entry, keeping the original headroom. The font entry is the only one that changes.
- **Textures:** in the BNTX `BRTI` header, format is at +0x1C, width/height at +0x24, log2 of the block height at +0x34, size at +0x50, name pointer at +0x60, and the mip pointer table at +0x70. Format `0x1D01` is BC4 and `0x2D06` is ASTC 4×4 sRGB.
- **The controller body** is `Controller_Pro1` (brown, used by the Controls screen) and `Controller_Pro` (grey, used by the action-guide tutorials). Both are ASTC, 1160×680. `ControllerGuide_*` are only the pointer lines.
- **`.buil` layouts** (newer than bflyt) store a pointer table to 0x44-byte pane records at 0x320 and a name table at 0x520. In a record, translate x/y are at +0x1C/+0x20, the parent index at +0x28, size at +0x2C, and the first material index (int16) at +0x3C. The first four floats look like margins, not rotation.
- **The UI blarc stores every layout four times** under the same name. Patch all copies.

## Supporting another version

1. Run `check`. It lists which input files differ.
2. Extract the new files and redo the checks this code relies on:
   - **Glyphs:** confirm the font still has the same codepoints. Render E040–E092 to a sheet.
   - **Texture names:** confirm they still exist, with the same sizes and formats.
   - **Controller picture:** re-measure the button positions. Threshold the decoded `Controller_Pro1` and label the connected regions; the constants are at the top of `paint.py`.
   - **Ring layout:** check the `.buil` table offsets and the pane names and positions. `ring.py` checks the expected positions before editing and fails loudly if they've moved.
3. Add the new hashes to `known.VERSIONS`. If any constants changed, make them per-version.
4. Build. Check the font, ring and controller previews, then test in game: the Talk prompt, the ocarina, and the Controls screen.

## Ideas not done yet

- Joy-Con grip and handheld controller pictures (`Controller_Grip1`, `Controller_Console1`).
- Coloured Xbox letters (needs layout material colour edits).
- Draw a real DualSense outline for the PS5 style. This would also mean moving the `ControllerGuide_*` pointer lines, since the stick and d-pad positions differ.
- More styles: add an entry to `STYLES` and branches in `glyphs.build` and `paint.controller`. The ring layout patch is shared.
