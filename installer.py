"""Entry point for the packaged installer (PyInstaller).

Double-click: opens the installer window.
`<installer> --cli <command> ...` runs the command-line tool instead (same as `python -m oot_controller_ui`).
"""
import multiprocessing
import sys


def run():
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        from oot_controller_ui.cli import main as cli_main
        cli_main(sys.argv[2:])
    else:
        from oot_controller_ui.gui import main as gui_main
        gui_main()


if __name__ == "__main__":
    multiprocessing.freeze_support()
    run()
