"""The installer window (Tkinter + Pillow-drawn art). Works with mouse, keyboard, or a
controller mapped to arrows/Enter/Escape (the Steam Deck's desktop controls do this).

  python -m oot_controller_ui gui
"""
import os
import queue
import shutil
import sys
import threading
import traceback
import tkinter as tk
from tkinter import filedialog

from PIL import ImageTk

from . import __version__, build, detect, known, nup, theme
from .fonts import font_set

W, H = 960, 620
STYLE_INFO = {
    "xbox": ("Xbox", ["LB", "RB", "LT", "RT"], "Xbox controllers"),
    "ps5": ("PlayStation 5", ["L1", "R1", "L2", "R2"], "DualSense / DualShock"),
    "steam": ("Steam Deck", ["L1", "R1", "L2", "R2"], "Steam Deck & Steam Controller"),
}


class Widget:
    def __init__(self, app, x, y, render, action, enabled=True, selected=False):
        self.app, self.x, self.y, self.render, self.action = app, x, y, render, action
        self.enabled, self.selected, self.hot = enabled, selected, False
        self.tag = "w%d" % id(self)
        self.item = None
        self.draw()
        c = app.canvas
        c.tag_bind(self.tag, "<Enter>", lambda e: app.set_focus(self))
        c.tag_bind(self.tag, "<Button-1>", lambda e: self.activate())

    def draw(self):
        img = ImageTk.PhotoImage(self.render(self.hot, self.selected, self.enabled))
        self.photo = img
        if self.item is None:
            self.item = self.app.canvas.create_image(self.x, self.y, image=img, anchor="nw", tags=(self.tag, "screen"))
        else:
            self.app.canvas.itemconfigure(self.item, image=img)

    def activate(self):
        if self.enabled:
            self.action()


class App:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Controller UI for Ocarina of Time")
        self.root.resizable(False, False)
        self.root.geometry("%dx%d" % (W, H))
        self._icon = ImageTk.PhotoImage(theme.app_icon(128))
        self.root.iconphoto(True, self._icon)
        self.canvas = tk.Canvas(self.root, width=W, height=H, highlightthickness=0, bd=0)
        self.canvas.pack()
        self._bg = ImageTk.PhotoImage(theme.background(W, H))
        self.canvas.create_image(0, 0, image=self._bg, anchor="nw")
        self.keep, self.widgets, self.focus = [], [], None
        self.q = queue.Queue()
        self.back_action = None
        for k in ("<Left>", "<Up>", "<Shift-Tab>"):
            self.root.bind(k, lambda e: self.move(-1))
        for k in ("<Right>", "<Down>", "<Tab>"):
            self.root.bind(k, lambda e: self.move(1))
        for k in ("<Return>", "<space>", "<KP_Enter>"):
            self.root.bind(k, lambda e: self.focus and self.focus.activate())
        self.root.bind("<Escape>", lambda e: self.back_action and self.back_action())
        self.root.after(100, self._poll)
        # state
        self.games, self.game, self.game_status, self.patched, self.supported = None, None, "", False, False
        self.style, self.method = "xbox", None
        self.title_screen()

    # ------------------------------------------------------------ plumbing
    def clear(self):
        self.canvas.delete("screen")
        self.keep, self.widgets, self.focus, self.back_action = [], [], None, None

    def img(self, pil, x, y, anchor="nw"):
        p = ImageTk.PhotoImage(pil)
        self.keep.append(p)
        return self.canvas.create_image(x, y, image=p, anchor=anchor, tags=("screen",))

    def heading(self, title, subtitle=None):
        self.img(theme.text(title, "title", 36, theme.INK, 800, shadow=(255, 245, 220, 150)), W // 2, 52, "n")
        if subtitle:
            self.img(theme.text(subtitle, "light", 18, theme.INK_SOFT), W // 2, 108, "n")

    def add(self, w):
        self.widgets.append(w)
        if self.focus is None and w.enabled:
            self.set_focus(w)
        return w

    def set_focus(self, w):
        if not w.enabled:
            return
        if self.focus and self.focus is not w:
            self.focus.hot = False
            self.focus.draw()
        self.focus = w
        w.hot = True
        w.draw()

    def move(self, step):
        live = [w for w in self.widgets if w.enabled]
        if not live:
            return
        i = live.index(self.focus) if self.focus in live else -1
        self.set_focus(live[(i + step) % len(live)])

    def btn(self, label, x, y, action, primary=True, enabled=True, w=220):
        def render(hot, sel, en):
            return theme.button(label, w, 52, "disabled" if not en else ("focus" if hot else "normal"), primary)
        return self.add(Widget(self, x, y, render, action, enabled))

    def nav(self, back=None, next_label=None, next_action=None, next_enabled=True):
        if back:
            self.back_action = back
            self.btn("Back", 48, H - 92, back, primary=False, w=160)
        if next_label:
            self.btn(next_label, W - 48 - 220, H - 92, next_action, enabled=next_enabled)

    def bg(self, fn, done, fail=None):
        def run():
            try:
                self.q.put((done, fn()))
            except BaseException as e:  # noqa: BLE001 - shown to the user
                msg = str(e) if isinstance(e, SystemExit) else "%s: %s" % (type(e).__name__, e)
                traceback.print_exc()
                self.q.put((fail or self.error_screen, msg))
        threading.Thread(target=run, daemon=True).start()

    def _poll(self):
        try:
            while True:
                cb, val = self.q.get_nowait()
                cb(val)
        except queue.Empty:
            pass
        self.root.after(80, self._poll)

    # ------------------------------------------------------------ screens
    def title_screen(self):
        self.clear()
        self.img(theme.app_icon(120), W // 2, 70, "n")
        self.img(theme.text("Controller UI", "title", 54, theme.INK, 900, shadow=(255, 245, 220, 160)), W // 2, 200, "n")
        self.img(theme.text("for The Legend of Zelda: Ocarina of Time  ·  Switch 2", "light", 20, theme.INK_SOFT), W // 2, 274, "n")
        self.img(theme.paragraph(
            "Replaces the Switch button prompts with Xbox, PlayStation 5 or Steam Deck ones, "
            "built from your own game files on this computer.", 560, "light", 18, theme.INK), W // 2, 318, "n")
        self.btn("Begin", W // 2 - 110, 410, self.game_screen)
        self.btn("Restore / Remove", W // 2 - 110, 474, self.restore_screen, primary=False)
        self.img(theme.text("v" + __version__ + "  ·  not affiliated with Nintendo, Microsoft, Sony or Valve",
                            "light", 13, theme.INK_SOFT), W // 2, H - 44, "n")

    def game_screen(self):
        self.clear()
        self.heading("Find your game", "Pick your Ocarina of Time .nup file (from Lichii's 'Convert to NUP').")
        self.back_action = self.title_screen
        if self.games is None:
            self.img(theme.text("Looking for your games…", "light", 18, theme.INK_SOFT), W // 2, 250, "n")
            self.nav(back=self.title_screen)
            self.bg(detect.find_games, self._games_found, lambda m: self._games_found([]))
            return
        y = 160
        for path in self.games[:3]:
            self._game_card(path, y)
            y += 92
        if not self.games:
            self.img(theme.paragraph("I couldn't find a .nup automatically. Choose it with Browse.", 560,
                                     "light", 18, theme.INK_SOFT), W // 2, 200, "n")
        self.btn("Browse…", W // 2 - 110, max(y, 280) + 8, self._browse, primary=False)
        if self.game_status:
            col = theme.GREEN if self.supported else (theme.RED if not self.patched else theme.INK_SOFT)
            self.img(theme.paragraph(self.game_status, 760, "body", 16, col), W // 2, H - 168, "n")
        self.nav(back=self.title_screen, next_label="Next", next_action=self.style_screen,
                 next_enabled=bool(self.game) and (self.supported or self.patched))

    def _games_found(self, games):
        self.games = games
        if games and not self.game:
            self._choose_game(games[0])
        else:
            self.game_screen()

    def _game_card(self, path, y):
        name, folder = os.path.basename(path), os.path.dirname(path)
        def render(hot, sel, en):
            p = theme.panel(760, 82, selected=sel, hover=hot)
            p.alpha_composite(theme.text(name if len(name) < 64 else name[:61] + "…", "body", 18, theme.INK), (22, 12))
            p.alpha_composite(theme.text(folder if len(folder) < 90 else "…" + folder[-88:], "light", 14, theme.INK_SOFT), (22, 44))
            return p
        self.add(Widget(self, (W - 760) // 2, y, render, lambda: self._choose_game(path), selected=(path == self.game)))

    def _browse(self):
        p = filedialog.askopenfilename(title="Choose your Ocarina of Time .nup",
                                       filetypes=[("Lichii game package", "*.nup"), ("All files", "*.*")])
        if p:
            p = os.path.normpath(p)
            if self.games is not None and p not in self.games:
                self.games.insert(0, p)
            self._choose_game(p)

    def _choose_game(self, path):
        self.game, self.supported, self.patched = path, False, False
        self.game_status = "Checking this file…"
        self.game_screen()

        def check():
            if os.path.exists(path + ".undo"):
                return ("patched", None)
            src = build.NupSource(path)
            try:
                files = {rel: src.read(rel) for rel in build.INPUTS}
            finally:
                src.nup.close()
            return ("ok", build.identify(files))

        def done(res):
            kind, ver = res
            if kind == "patched":
                self.patched = True
                self.game_status = ("This file already has a controller UI patch. It will be restored to the "
                                    "original first, then the new style is applied.")
            else:
                self.supported = True
                self.game_status = "Supported game version (%s). Ready to go." % ver
            self.game_screen()

        def fail(msg):
            self.game_status = "Can't use this file: " + msg.split("\n")[0]
            self.game_screen()

        self.bg(check, done, fail)

    def style_screen(self):
        self.clear()
        self.heading("Choose your controller", "Which buttons should the game show?")
        x = 54
        for key, (title, shoulders, sub) in STYLE_INFO.items():
            self._style_card(key, title, shoulders, sub, x, 150)
            x += 290
        self.img(theme.paragraph(
            "Tip: set the emulator so the bottom face button is Switch A. In Lichii, swap A and B "
            "in the controller settings (Emulation > Configure > Controls).", 780, "light", 16, theme.INK_SOFT),
            W // 2, 440, "n")
        self.nav(back=self.game_screen, next_label="Next", next_action=self.method_screen)
        for w in self.widgets:
            if w.selected:
                self.set_focus(w)

    def _style_card(self, key, title, shoulders, sub, x, y):
        def render(hot, sel, en):
            p = theme.panel(270, 270, selected=sel, hover=hot)
            t = theme.text(title, "title", 22, theme.INK, 800)
            p.alpha_composite(t, ((266 - t.width) // 2, 14))
            ic = theme.face_icons(key, 44)
            p.alpha_composite(ic, ((266 - ic.width) // 2, 56))
            tags = theme.shoulder_tags(shoulders)
            p.alpha_composite(tags, ((266 - tags.width) // 2, 196))
            s = theme.text(sub, "light", 14, theme.INK_SOFT)
            p.alpha_composite(s, ((266 - s.width) // 2, 234))
            return p

        def pick():
            self.style = key
            for w in self.widgets:
                if getattr(w, "style_key", None):
                    w.selected = w.style_key == key
                    w.draw()
        w = self.add(Widget(self, x, y, render, pick, selected=(key == self.style)))
        w.style_key = key

    def method_screen(self):
        self.clear()
        self.heading("How should it be installed?")
        root = detect.mod_root()
        bnum = detect.lichii_build()
        old = bnum is not None and bnum <= detect.LAST_BUILD_WITHOUT_NUP_MODS
        if self.method is None:
            self.method = "patch" if (old or not root) else "mod"
        folder = os.path.join(root, detect.UI_FOLDERS[self.style]) if root else None
        opts = [
            ("mod", "Install as a mod", "Lichii/Eden loads it from its mod folder; switch it off any time in the "
             "game's Properties > Add-Ons." + ("\n" + folder if folder else "\nLichii's user folder wasn't found."),
             bool(root)),
            ("patch", "Patch the game file", "Writes the changes into your .nup (about +70 MB). Needed for Lichii "
             "build 93 and earlier, which don't load mods for .nup games. Fully reversible.", True),
        ]
        y = 140
        best = "patch" if (old or not root) else "mod"
        for key, title, desc, en in opts:
            self._method_card(key, title, desc, en, y, key == best)
            y += 160
        note = ("Detected Lichii build %d." % bnum) if bnum else "Couldn't detect your Lichii build."
        self.img(theme.text(note, "light", 15, theme.INK_SOFT), W // 2, 470, "n")
        self.nav(back=self.style_screen, next_label="Install", next_action=self.install)
        for w in self.widgets:
            if w.selected:
                self.set_focus(w)

    def _method_card(self, key, title, desc, enabled, y, recommended):
        def render(hot, sel, en):
            p = theme.panel(780, 146, selected=sel and en, hover=hot)
            t = theme.text(title + ("   (recommended for you)" if recommended else ""), "title", 21,
                           theme.INK if en else theme.INK_SOFT, 800)
            p.alpha_composite(t, (24, 12))
            p.alpha_composite(theme.paragraph(desc, 730, "light", 15, theme.INK if en else theme.INK_SOFT), (24, 52))
            return p

        def pick():
            self.method = key
            for w in self.widgets:
                if getattr(w, "method_key", None):
                    w.selected = w.method_key == key
                    w.draw()
        w = self.add(Widget(self, (W - 780) // 2, y, render, pick, enabled=enabled,
                            selected=(key == self.method and enabled)))
        w.method_key = key

    # ------------------------------------------------------------ install
    def install(self):
        self.clear()
        self.heading("Installing", STYLE_INFO[self.style][0] + " style")
        self.step, self.pulse_t = 0, 0
        self.staff_item = self.img(theme.staff(820, 0, 0), W // 2, 180, "n")
        self.status_item = self.img(theme.text(build.STEPS[0] + "…", "body", 18, theme.INK), W // 2, 350, "n")
        self.img(theme.text("This takes about a minute. Please keep Lichii closed.", "light", 15, theme.INK_SOFT),
                 W // 2, 392, "n")
        self._animate()
        game, style, method = self.game, self.style, self.method

        def progress(i, label):
            self.q.put((self._set_step, (i, label)))

        def work():
            if os.path.exists(game + ".undo"):
                nup.undo(game)
            src = build.NupSource(game)
            try:
                out = build.build(src, font_set("selawik"), style, log=lambda *_: None, progress=progress)
            finally:
                src.nup.close()
            progress(4, build.STEPS[4])
            if method == "mod":
                root = detect.mod_root()
                for other in detect.installed_mods():
                    shutil.rmtree(other)
                target = os.path.join(root, detect.UI_FOLDERS[style])
                build.write_mod(out, target)
                return ("mod", target)
            nup.apply(game, out)
            return ("patch", game)

        self.bg(work, self.done_screen)

    def _set_step(self, v):
        self.step = v[0]
        if not self.canvas.find_withtag(self.status_item):
            return
        self._status_photo = ImageTk.PhotoImage(theme.text(v[1] + "…", "body", 18, theme.INK))
        self.canvas.itemconfigure(self.status_item, image=self._status_photo)

    def _animate(self):
        if not self.canvas.find_withtag(self.staff_item):
            return
        import math
        self.pulse_t += 1
        pulse = 0.5 + 0.5 * math.sin(self.pulse_t / 3)
        self._staff_photo = ImageTk.PhotoImage(theme.staff(820, self.step, self.step, pulse))
        self.canvas.itemconfigure(self.staff_item, image=self._staff_photo)
        self.root.after(90, self._animate)

    def done_screen(self, res):
        kind, path = res
        self.clear()
        self.heading("All set!", STYLE_INFO[self.style][0] + " buttons are ready")
        self.img(theme.staff(820, 5), W // 2, 150, "n")
        if kind == "mod":
            msg = ("Installed as a mod in:\n%s\n\nStart Lichii and play. You can switch it off in the game's "
                   "Properties > Add-Ons." % path)
        else:
            msg = ("Your game file was patched. Start Lichii and play.\nTo undo it, run this installer again "
                   "and choose Restore / Remove.")
        self.img(theme.paragraph(msg, 760, "body", 17, theme.INK), W // 2, 320, "n")
        if kind == "mod":
            self.btn("Open folder", 48, H - 92, lambda: detect.open_folder(path), primary=False, w=200)
        self.btn("Finish", W - 48 - 220, H - 92, self.root.destroy)

    # ------------------------------------------------------------ restore
    def restore_screen(self):
        self.clear()
        self.heading("Restore / Remove", "Undo what this installer did.")
        self.back_action = self.title_screen
        mods = detect.installed_mods()
        if not (self.game and os.path.exists(self.game + ".undo")):
            for g in detect.find_games():          # quick header check only
                if os.path.exists(g + ".undo"):
                    self.game = g
                    break
        y = 160
        lines = []
        if mods:
            lines.append("Installed mod folders:\n" + "\n".join(mods))
        if self.game and os.path.exists(self.game + ".undo"):
            lines.append("Patched game file:\n" + self.game)
        if not lines:
            lines.append("Nothing installed by this tool was found. If you patched a game file that isn't "
                         "listed, choose it with Browse.")
        self.img(theme.paragraph("\n\n".join(lines), 780, "light", 16, theme.INK), W // 2, y, "n")

        def remove_mods():
            for m in detect.installed_mods():
                shutil.rmtree(m)
            self.message("Removed", "The mod folders were removed.")

        def restore_game():
            g = self.game
            self.clear()
            self.heading("Restoring…")
            self.bg(lambda: nup.undo(g), lambda _: self.message("Restored", "Your game file is back to the original."))

        def browse():
            p = filedialog.askopenfilename(title="Choose the patched .nup",
                                           filetypes=[("Lichii game package", "*.nup"), ("All files", "*.*")])
            if p:
                self.game = os.path.normpath(p)
                self.restore_screen()

        self.btn("Remove mods", 110, 420, remove_mods, primary=False, enabled=bool(mods), w=230)
        self.btn("Restore game", W // 2 - 115, 420, restore_game, primary=False,
                 enabled=bool(self.game and os.path.exists(self.game + ".undo")), w=230)
        self.btn("Browse…", W - 110 - 230, 420, browse, primary=False, w=230)
        self.nav(back=self.title_screen)

    def message(self, title, text):
        self.clear()
        self.heading(title)
        self.img(theme.paragraph(text, 700, "body", 18, theme.INK), W // 2, 200, "n")
        self.btn("Back to start", W // 2 - 110, 400, self.title_screen)

    def error_screen(self, msg):
        self.clear()
        self.heading("Something went wrong")
        self.img(theme.paragraph(msg, 780, "body", 16, theme.RED), W // 2, 170, "n")
        self.btn("Back to start", W // 2 - 110, H - 140, self.title_screen)

    def run(self):
        self.root.mainloop()


def main():
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass
    App().run()


if __name__ == "__main__":
    main()
