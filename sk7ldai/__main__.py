"""
Entry point for `python -m sk7ldai`.

  python -m sk7ldai          -> launch the GUI
  python -m sk7ldai --cli    -> launch the terminal (headless) mode
"""

import argparse
import sys


def main():
    parser = argparse.ArgumentParser(
        prog="sk7ldai",
        description="Sk7ld-AI - Digital Longship Intelligence System (GUI/CLI hybrid).")
    parser.add_argument("--cli", action="store_true",
                        help="run in terminal mode instead of the GUI")
    parser.add_argument("--version", action="store_true", help="print version and exit")
    args = parser.parse_args()

    if args.version:
        from . import __version__, __app_name__
        print(f"{__app_name__} v{__version__}")
        return

    if args.cli:
        from .cli import main as cli_main
        cli_main()
        return

    try:
        from .gui.app import main as gui_main
    except Exception as exc:  # customtkinter missing or no display
        print(f"[!] GUI unavailable ({exc}).")
        print("    Falling back to CLI mode. Install the GUI deps with:")
        print("      pip install customtkinter")
        print("    or run headless with:  python -m sk7ldai --cli\n")
        from .cli import main as cli_main
        cli_main()
        return
    gui_main()


if __name__ == "__main__":
    sys.exit(main() or 0)
