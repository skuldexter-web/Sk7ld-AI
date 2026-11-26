"""
anon.py - anonymous mode (route Sk7ld-AI's outbound traffic through Tor).

When enabled, Sk7ld-AI's own outbound internet requests (public-IP check,
weather, self-update git pull) are routed through the Tor SOCKS proxy at
127.0.0.1:9050, and the HUD shows the Tor exit IP. Ollama stays local and is
never torified.

This is a Linux feature (Kali ships Tor + torsocks). On Windows it reports that
Tor Browser / a local Tor SOCKS proxy is required.

Design notes:
- enable() makes sure a Tor SOCKS proxy is reachable, starting the tor service
  if needed (via sudo systemctl/service - may prompt). It does NOT transparently
  hijack every socket in the process; instead the modules that reach the
  internet (netinfo, updater) honour `is_enabled()` and route through Tor.
- `torify_argv(argv)` wraps a command with torsocks so child processes
  (e.g. git) also go through Tor.
"""

from __future__ import annotations

import shutil
import socket
import subprocess
from typing import Callable, Optional

from .osenv import is_windows

TOR_HOST, TOR_PORT = "127.0.0.1", 9050
LogFn = Callable[[str], None]

_enabled = False


def is_enabled() -> bool:
    return _enabled


def socks_reachable(timeout: float = 2.0) -> bool:
    """True if something is listening on the Tor SOCKS port."""
    try:
        with socket.create_connection((TOR_HOST, TOR_PORT), timeout=timeout):
            return True
    except Exception:
        return False


def tor_available() -> bool:
    """Tor usable: either the SOCKS port is open, or the tor binary is installed."""
    return socks_reachable() or bool(shutil.which("tor"))


def _noop(_: str) -> None:
    pass


def _start_tor(log: LogFn) -> bool:
    """Try to start the Tor service (Linux). Returns True if SOCKS becomes reachable."""
    if socks_reachable():
        return True
    if is_windows():
        log("[!] On Windows, start Tor Browser or a local Tor SOCKS proxy on "
            "127.0.0.1:9050, then enable anonymous mode again.")
        return False
    if not shutil.which("tor"):
        log("[X] Tor is not installed. Install it with: sudo apt install -y tor")
        return False
    sudo = ["sudo", "-n"] if shutil.which("sudo") else []
    for cmd in (sudo + ["systemctl", "start", "tor"],
                sudo + ["service", "tor", "start"]):
        try:
            log("$ " + " ".join(cmd))
            subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        except Exception as exc:  # noqa: BLE001
            log(f"[!] {exc}")
    # give Tor a moment to open the SOCKS port
    import time
    for _ in range(10):
        if socks_reachable():
            return True
        time.sleep(1)
    return socks_reachable()


def enable(log: Optional[LogFn] = None) -> bool:
    """Turn anonymous mode on. Returns True on success."""
    global _enabled
    log = log or _noop
    if not _start_tor(log):
        log("[X] Could not reach a Tor SOCKS proxy on 127.0.0.1:9050.")
        _enabled = False
        return False
    _enabled = True
    log("[OK] Anonymous mode ON - outbound traffic routed through Tor.")
    return True


def disable(log: Optional[LogFn] = None) -> None:
    global _enabled
    log = log or _noop
    _enabled = False
    log("[OK] Anonymous mode OFF - outbound traffic is direct again.")


def torify_argv(argv: list) -> list:
    """Wrap a command with torsocks when anonymous mode is on (for child procs)."""
    if _enabled and shutil.which("torsocks"):
        return ["torsocks"] + list(argv)
    return list(argv)
