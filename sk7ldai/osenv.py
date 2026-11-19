"""
osenv.py - OS awareness for Sk7ld-AI.

The same codebase runs on Kali/Linux and on Windows. This module centralises the
platform check so the installer (paths, package managers, sudo), the runner
(which terminal to open) and the arsenal (which tools to expose) all adapt.

Set SK7LD_AI_OS=windows|linux to force a target (used by the Windows build and
for testing the Windows path on Linux).
"""

from __future__ import annotations

import os
import sys


def forced() -> str:
    v = os.environ.get("SK7LD_AI_OS", "").strip().lower()
    return v if v in ("windows", "linux") else ""


def is_windows() -> bool:
    f = forced()
    if f:
        return f == "windows"
    return sys.platform.startswith("win")


def os_name() -> str:
    return "windows" if is_windows() else "linux"
