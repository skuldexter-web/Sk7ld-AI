"""
feeds.py - live data feeds for the Sk7ld-AI HUD.

  * SystemStats - CPU %, RAM used/total/%, GPU % (best-effort), and ethernet/Wi-Fi
                  up+down throughput. Uses psutil when available, otherwise parses
                  /proc and /sys directly, so it works on a bare Kali box.
  * Weather     - current conditions + 3-day forecast from wttr.in (no API key,
                  IP-based location). Degrades gracefully to "offline".

Everything here is read-only and defensive: a missing tool, sensor, or network
never raises - it returns None / zeros so the GUI keeps ticking.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import urllib.request
import urllib.parse
from typing import Dict, List, Optional

try:
    import psutil  # type: ignore
    _HAS_PSUTIL = True
except Exception:  # noqa: BLE001
    psutil = None  # type: ignore
    _HAS_PSUTIL = False


def human_rate(bytes_per_sec: float) -> str:
    """Format a byte/s rate compactly (e.g. 6.2 kB/s, 112 B/s, 1.3 MB/s)."""
    b = max(0.0, bytes_per_sec)
    for unit in ("B", "kB", "MB", "GB"):
        if b < 1024 or unit == "GB":
            return f"{b:.0f} {unit}/s" if unit == "B" else f"{b:.1f} {unit}/s"
        b /= 1024
    return f"{b:.1f} GB/s"


def human_bytes(n: float) -> str:
    b = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if b < 1024 or unit == "TB":
            return f"{b:.1f} {unit}"
        b /= 1024
    return f"{b:.1f} TB"


# ════════════════════════════════════════════════════════════════════════
#  SYSTEM STATS
# ════════════════════════════════════════════════════════════════════════
class SystemStats:
    def __init__(self):
        self._last_net = None          # (bytes_sent, bytes_recv, monotonic)
        self._last_cpu = None          # (idle, total) for /proc fallback
        self._gpu_mode: Optional[str] = None   # "nvidia" | "amd" | "none" | None(unknown)
        if _HAS_PSUTIL:
            try:
                psutil.cpu_percent(interval=None)  # prime the baseline
            except Exception:
                pass

    # ── CPU ─────────────────────────────────────────────────────────────
    def _cpu(self) -> float:
        if _HAS_PSUTIL:
            try:
                return float(psutil.cpu_percent(interval=None))
            except Exception:
                return 0.0
        try:
            with open("/proc/stat") as fh:
                parts = fh.readline().split()[1:]
            vals = [int(x) for x in parts]
            idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
            total = sum(vals)
            if self._last_cpu is not None:
                di = idle - self._last_cpu[0]
                dt = total - self._last_cpu[1]
                self._last_cpu = (idle, total)
                return max(0.0, min(100.0, (1 - di / dt) * 100)) if dt > 0 else 0.0
            self._last_cpu = (idle, total)
        except Exception:
            pass
        return 0.0

    # ── RAM ─────────────────────────────────────────────────────────────
    def _ram(self):
        if _HAS_PSUTIL:
            try:
                vm = psutil.virtual_memory()
                return vm.used, vm.total, vm.percent
            except Exception:
                pass
        try:
            info = {}
            with open("/proc/meminfo") as fh:
                for line in fh:
                    k, _, v = line.partition(":")
                    info[k] = int(v.strip().split()[0]) * 1024
            total = info.get("MemTotal", 0)
            avail = info.get("MemAvailable", info.get("MemFree", 0))
            used = total - avail
            pct = (used / total * 100) if total else 0.0
            return used, total, pct
        except Exception:
            return 0, 0, 0.0

    # ── NET ─────────────────────────────────────────────────────────────
    def _net(self):
        now = time.monotonic()
        sent = recv = 0
        if _HAS_PSUTIL:
            try:
                io = psutil.net_io_counters()
                sent, recv = io.bytes_sent, io.bytes_recv
            except Exception:
                pass
        else:
            try:
                with open("/proc/net/dev") as fh:
                    for line in fh.readlines()[2:]:
                        iface, _, data = line.partition(":")
                        if iface.strip() == "lo":
                            continue
                        cols = data.split()
                        recv += int(cols[0]); sent += int(cols[8])
            except Exception:
                pass
        up = down = 0.0
        if self._last_net is not None:
            dt = now - self._last_net[2]
            if dt > 0:
                up = max(0.0, (sent - self._last_net[0]) / dt)
                down = max(0.0, (recv - self._last_net[1]) / dt)
        self._last_net = (sent, recv, now)
        return up, down

    # ── GPU (best-effort) ───────────────────────────────────────────────
    def _gpu(self) -> Optional[float]:
        if self._gpu_mode == "none":
            return None
        # NVIDIA
        if self._gpu_mode in (None, "nvidia") and shutil.which("nvidia-smi"):
            try:
                out = subprocess.run(
                    ["nvidia-smi", "--query-gpu=utilization.gpu",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=2)
                val = out.stdout.strip().splitlines()[0].strip()
                self._gpu_mode = "nvidia"
                return float(val)
            except Exception:
                if self._gpu_mode == "nvidia":
                    return None
        # AMD / Intel via sysfs
        if self._gpu_mode in (None, "amd"):
            for card in ("card0", "card1"):
                path = f"/sys/class/drm/{card}/device/gpu_busy_percent"
                if os.path.exists(path):
                    try:
                        with open(path) as fh:
                            self._gpu_mode = "amd"
                            return float(fh.read().strip())
                    except Exception:
                        pass
        self._gpu_mode = "none"
        return None

    # ── DISK ────────────────────────────────────────────────────────────
    def _disk(self):
        try:
            import shutil as _sh
            du = _sh.disk_usage(os.environ.get("SK7LD_AI_DISK", "/"))
            pct = (du.used / du.total * 100) if du.total else 0.0
            return du.used, du.total, pct
        except Exception:
            return 0, 0, 0.0

    # ── sample ──────────────────────────────────────────────────────────
    def sample(self) -> Dict:
        used, total, ram_pct = self._ram()
        up, down = self._net()
        gpu = self._gpu()
        d_used, d_total, d_pct = self._disk()
        return {
            "cpu": self._cpu(),
            "ram_used": used, "ram_total": total, "ram_pct": ram_pct,
            "gpu": gpu,                      # None => n/a
            "net_up": up, "net_down": down,  # bytes/sec
            "disk_used": d_used, "disk_total": d_total, "disk_pct": d_pct,
            "backend": "psutil" if _HAS_PSUTIL else "/proc",
        }


# ════════════════════════════════════════════════════════════════════════
#  WEATHER  (wttr.in - no API key, IP-based location)
# ════════════════════════════════════════════════════════════════════════
class Weather:
    URL = "https://wttr.in/{loc}?format=j1"

    def __init__(self, location: str = ""):
        self.location = location  # "" => wttr auto-detects by IP

    def fetch(self, timeout: float = 8.0) -> Optional[Dict]:
        url = self.URL.format(loc=urllib.parse.quote(self.location))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "curl/8"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            return None
        try:
            cur = data["current_condition"][0]
            area = data.get("nearest_area", [{}])[0]
            name = ""
            if area:
                name = (area.get("areaName", [{}])[0].get("value", "")
                        or area.get("country", [{}])[0].get("value", ""))
            days: List[Dict] = []
            for d in data.get("weather", [])[:3]:
                hourly = d.get("hourly", [])
                mid = hourly[len(hourly) // 2] if hourly else {}
                days.append({
                    "date": d.get("date", ""),
                    "hi": d.get("maxtempC", "?"),
                    "lo": d.get("mintempC", "?"),
                    "desc": (mid.get("weatherDesc", [{}])[0].get("value", "").strip()),
                })
            return {
                "location": name or (self.location or "Local"),
                "temp": cur.get("temp_C", "?"),
                "feels": cur.get("FeelsLikeC", "?"),
                "desc": cur.get("weatherDesc", [{}])[0].get("value", "").strip(),
                "humidity": cur.get("humidity", "?"),
                "wind": cur.get("windspeedKmph", "?"),
                "days": days,
            }
        except Exception:
            return None
