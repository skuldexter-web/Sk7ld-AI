"""
netinfo.py - public IP lookup, direct or through the Tor SOCKS tunnel.

Used by the HUD IP indicator. A direct lookup shows the operator's real public
IP (red / "visible"); when anonymous mode is on the same lookup is routed
through Tor (127.0.0.1:9050) and shows the exit-node IP (green / "safe").

Lookups are best-effort and never raise: they return None on any failure so the
UI just shows "--".
"""

from __future__ import annotations

import json
import shutil
import subprocess
import urllib.request
from typing import Optional

TOR_SOCKS = "127.0.0.1:9050"
# A few keyless endpoints; first that answers wins.
_IP_URLS = ["https://api.ipify.org", "https://ifconfig.me/ip", "https://icanhazip.com"]
_GEO_URL = "http://ip-api.com/json/{ip}?fields=country,city,query"


def _clean(s: str) -> Optional[str]:
    s = (s or "").strip()
    # crude sanity check: looks like an IPv4/IPv6
    if s and len(s) <= 45 and all(c in "0123456789abcdefABCDEF:." for c in s):
        return s
    return None


def public_ip(timeout: float = 6.0) -> Optional[str]:
    """Real public IP via a direct connection."""
    for url in _IP_URLS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ip = _clean(resp.read().decode("utf-8"))
                if ip:
                    return ip
        except Exception:
            continue
    return None


def tor_ip(timeout: float = 15.0) -> Optional[str]:
    """
    Exit-node IP as seen through the Tor SOCKS proxy. Uses curl --socks5-hostname
    (present on Kali) so no PySocks dependency is required; falls back to torsocks.
    """
    curl = shutil.which("curl")
    if curl:
        for url in _IP_URLS:
            try:
                out = subprocess.run(
                    [curl, "-s", "--max-time", str(int(timeout)),
                     "--socks5-hostname", TOR_SOCKS, url],
                    capture_output=True, text=True, timeout=timeout + 2)
                ip = _clean(out.stdout)
                if ip:
                    return ip
            except Exception:
                continue
    # Fallback: torsocks curl (if torsocks wrapper is installed)
    if shutil.which("torsocks") and curl:
        try:
            out = subprocess.run(["torsocks", curl, "-s", _IP_URLS[0]],
                                 capture_output=True, text=True, timeout=timeout + 2)
            return _clean(out.stdout)
        except Exception:
            pass
    return None


def geo(ip: str, timeout: float = 6.0) -> str:
    """Best-effort 'City, Country' for an IP; returns '' on failure."""
    if not ip:
        return ""
    try:
        req = urllib.request.Request(_GEO_URL.format(ip=ip),
                                     headers={"User-Agent": "curl/8"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            d = json.loads(resp.read().decode("utf-8"))
            parts = [d.get("city", ""), d.get("country", "")]
            return ", ".join(p for p in parts if p)
    except Exception:
        return ""
