#!/usr/bin/env python3
"""
sk7ld_ai.py - top-level launcher for the Sk7ld-AI repo.

Run the GUI:      python3 sk7ld_ai.py
Run headless:     python3 sk7ld_ai.py --cli

This is a thin wrapper around `python -m sk7ldai` so the repo has an obvious
entry script for new users and desktop launchers.
"""

import os
import sys

# Ensure the package next to this file is importable when run directly.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sk7ldai.__main__ import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main() or 0)
