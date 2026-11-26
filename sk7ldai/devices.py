"""
devices.py - local hardware discovery for Sk7ld-AI.

Finds the gear an operator actually plugs in, with zero hard dependencies:

  * USB dongles  - RTL-SDR, GPS/GNSS, Wi-Fi adapters, Bluetooth (categorised by
                   known VID:PID and by name keywords).
  * Audio I/O    - microphones (inputs) and speakers (outputs) for Voice Mode.
  * Cameras      - webcams for Object-Detection Mode.

Everything is best-effort and defensive: importing never fails, and each probe
is wrapped so a missing tool just yields an empty list. Cross-platform:
  Linux   -> lsusb / /sys, sounddevice or arecord/aplay, /dev/video* or OpenCV
  Windows -> PowerShell Get-PnpDevice, sounddevice, OpenCV (DirectShow)
  macOS   -> system_profiler, sounddevice, OpenCV
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from typing import Dict, List, Optional

# ── known USB IDs (lowercase hex, no 0x) ────────────────────────────────
# RTL-SDR (Realtek RTL2832U based dongles)
RTLSDR_IDS = {("0bda", "2832"), ("0bda", "2838")}
# GPS / GNSS receivers
GPS_VENDORS = {"1546"}  # u-blox
# Wi-Fi adapter vendors commonly used for war-driving / monitor mode
WIFI_VENDORS = {"148f", "0cf3", "0bda", "2357", "0e8d", "7392", "2001"}  # Ralink/Atheros/Realtek/TP-Link/MediaTek/D-Link
# Bluetooth radios
BT_VENDORS = {"0a12", "8087", "0a5c"}  # CSR / Intel / Broadcom

_NAME_HINTS = [
    ("rtl-sdr", ("rtl2832", "rtl2838", "rtl-sdr", "rtlsdr", "dvb-t", "realtek.*dvb")),
    ("gps", ("u-blox", "ublox", "gnss", "gps", "glonass", "nmea")),
    ("wifi", ("802.11", "wlan", "wireless", "wi-fi", "wifi", "ralink", "mediatek",
              "atheros", "ath9k", "rtl88", "awus", "alfa")),
    ("bluetooth", ("bluetooth", "bt ", "csr8510", "csr ")),
    ("serial", ("ftdi", "cp210", "ch340", "ch341", "pl2303", "prolific", "uart")),
]


def _categorise(vid: str, pid: str, name: str) -> str:
    vid, pid, low = vid.lower(), pid.lower(), (name or "").lower()
    if (vid, pid) in RTLSDR_IDS:
        return "rtl-sdr"
    # name keywords win first (most specific / reliable)
    for cat, hints in _NAME_HINTS:
        for h in hints:
            if re.search(h, low):
                return cat
    if vid in GPS_VENDORS:
        return "gps"
    if vid in BT_VENDORS:
        return "bluetooth"
    if vid in WIFI_VENDORS:
        return "wifi"
    return "other"


# ════════════════════════════════════════════════════════════════════════
#  USB devices
# ════════════════════════════════════════════════════════════════════════
def list_usb() -> List[Dict[str, str]]:
    """Return [{vid, pid, name, category}]; empty list if nothing can be read."""
    try:
        if os.name == "nt":
            return _usb_windows()
        if sys.platform == "darwin":
            return _usb_macos()
        return _usb_linux()
    except Exception:
        return []


def _usb_linux() -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    exe = shutil.which("lsusb")
    if exe:
        res = subprocess.run([exe], capture_output=True, text=True, timeout=5)
        for line in res.stdout.splitlines():
            m = re.search(r"ID\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\s*(.*)", line)
            if not m:
                continue
            vid, pid, name = m.group(1), m.group(2), m.group(3).strip() or "USB device"
            out.append({"vid": vid, "pid": pid, "name": name,
                        "category": _categorise(vid, pid, name)})
        return out
    # fallback: walk /sys/bus/usb/devices
    base = "/sys/bus/usb/devices"
    if os.path.isdir(base):
        for entry in sorted(os.listdir(base)):
            d = os.path.join(base, entry)
            try:
                vid = open(os.path.join(d, "idVendor")).read().strip()
                pid = open(os.path.join(d, "idProduct")).read().strip()
            except Exception:
                continue
            name = "USB device"
            for f in ("product", "manufacturer"):
                try:
                    name = open(os.path.join(d, f)).read().strip() or name
                    break
                except Exception:
                    pass
            out.append({"vid": vid, "pid": pid, "name": name,
                        "category": _categorise(vid, pid, name)})
    return out


def _usb_windows() -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    ps = ("Get-PnpDevice -PresentOnly | Where-Object {$_.InstanceId -like 'USB*'} | "
          "Select-Object FriendlyName,InstanceId | ConvertTo-Csv -NoTypeInformation")
    res = subprocess.run(["powershell", "-NoProfile", "-Command", ps],
                         capture_output=True, text=True, timeout=15)
    seen = set()
    for line in res.stdout.splitlines():
        m = re.search(r"VID_([0-9A-Fa-f]{4})&PID_([0-9A-Fa-f]{4})", line)
        if not m:
            continue
        vid, pid = m.group(1).lower(), m.group(2).lower()
        name = line.split('","')[0].strip('" ') or "USB device"
        key = (vid, pid, name)
        if key in seen:
            continue
        seen.add(key)
        out.append({"vid": vid, "pid": pid, "name": name,
                    "category": _categorise(vid, pid, name)})
    return out


def _usb_macos() -> List[Dict[str, str]]:
    out: List[Dict[str, str]] = []
    res = subprocess.run(["system_profiler", "SPUSBDataType"],
                         capture_output=True, text=True, timeout=15)
    name = vid = pid = None
    for raw in res.stdout.splitlines():
        line = raw.strip()
        if line.endswith(":") and "Product ID" not in line and "Vendor ID" not in line:
            name = line[:-1].strip()
        elif line.startswith("Product ID:"):
            pid = (re.search(r"0x([0-9a-fA-F]{1,4})", line) or [None, ""])[1].rjust(4, "0")
        elif line.startswith("Vendor ID:"):
            vid = (re.search(r"0x([0-9a-fA-F]{1,4})", line) or [None, ""])[1].rjust(4, "0")
            if name and vid and pid:
                out.append({"vid": vid, "pid": pid, "name": name,
                            "category": _categorise(vid, pid, name)})
                name = vid = pid = None
    return out


def rf_devices() -> List[Dict[str, str]]:
    """Just the radios an operator cares about: SDR, GPS, Wi-Fi, Bluetooth."""
    keep = {"rtl-sdr", "gps", "wifi", "bluetooth"}
    return [d for d in list_usb() if d["category"] in keep]


# ════════════════════════════════════════════════════════════════════════
#  Audio devices (mics + speakers)
# ════════════════════════════════════════════════════════════════════════
def list_audio() -> Dict[str, List[Dict]]:
    """Return {'inputs': [...], 'outputs': [...]} of audio devices."""
    inputs: List[Dict] = []
    outputs: List[Dict] = []
    try:
        import sounddevice as sd
        for i, dev in enumerate(sd.query_devices()):
            entry = {"index": i, "name": dev.get("name", f"device {i}")}
            if dev.get("max_input_channels", 0) > 0:
                inputs.append(entry)
            if dev.get("max_output_channels", 0) > 0:
                outputs.append(entry)
        return {"inputs": inputs, "outputs": outputs}
    except Exception:
        pass
    # Linux fallback: arecord/aplay
    try:
        if shutil.which("arecord"):
            r = subprocess.run(["arecord", "-l"], capture_output=True, text=True, timeout=5)
            for m in re.finditer(r"card \d+: (.+?) \[", r.stdout):
                inputs.append({"index": len(inputs), "name": m.group(1)})
        if shutil.which("aplay"):
            r = subprocess.run(["aplay", "-l"], capture_output=True, text=True, timeout=5)
            for m in re.finditer(r"card \d+: (.+?) \[", r.stdout):
                outputs.append({"index": len(outputs), "name": m.group(1)})
    except Exception:
        pass
    return {"inputs": inputs, "outputs": outputs}


# ════════════════════════════════════════════════════════════════════════
#  Cameras (webcams)
# ════════════════════════════════════════════════════════════════════════
def list_cameras(max_index: int = 5) -> List[Dict]:
    """Return [{index, name}] of working cameras (best-effort)."""
    cams: List[Dict] = []
    # Try OpenCV probing first (works on all platforms)
    try:
        import cv2
        backend = cv2.CAP_DSHOW if os.name == "nt" else 0
        for i in range(max_index):
            cap = cv2.VideoCapture(i, backend) if backend else cv2.VideoCapture(i)
            try:
                if cap.isOpened():
                    ok, _ = cap.read()
                    if ok:
                        cams.append({"index": i, "name": f"camera {i}"})
            finally:
                cap.release()
        if cams:
            return cams
    except Exception:
        pass
    # Linux fallback: /dev/video*
    try:
        import glob
        for path in sorted(glob.glob("/dev/video*")):
            m = re.search(r"(\d+)$", path)
            cams.append({"index": int(m.group(1)) if m else len(cams), "name": path})
    except Exception:
        pass
    return cams


# ════════════════════════════════════════════════════════════════════════
#  One-shot summary for the console
# ════════════════════════════════════════════════════════════════════════
def scan() -> Dict:
    return {"usb": list_usb(), "audio": list_audio(), "cameras": list_cameras()}


def scan_lines() -> List[str]:
    """Human-readable scan report lines for the GUI console."""
    out: List[str] = []
    usb = list_usb()
    radios = [d for d in usb if d["category"] in ("rtl-sdr", "gps", "wifi", "bluetooth")]
    out.append("[~] Scanning local hardware...")
    if radios:
        out.append(f"[OK] Radios / dongles ({len(radios)}):")
        icon = {"rtl-sdr": "📡 SDR", "gps": "🛰 GPS", "wifi": "📶 WiFi",
                "bluetooth": "🔵 BT "}
        for d in radios:
            out.append(f"     {icon.get(d['category'], d['category'])}"
                       f"  {d['vid']}:{d['pid']}  {d['name']}")
    else:
        out.append("[!] No SDR / GPS / Wi-Fi / Bluetooth dongles detected "
                   "(or lsusb/PnP unavailable).")
    audio = list_audio()
    out.append(f"[OK] Microphones: {len(audio['inputs'])} | "
               f"Speakers: {len(audio['outputs'])}")
    for d in audio["inputs"][:6]:
        out.append(f"     🎤 [{d['index']}] {d['name']}")
    for d in audio["outputs"][:6]:
        out.append(f"     🔈 [{d['index']}] {d['name']}")
    cams = list_cameras()
    if cams:
        out.append(f"[OK] Cameras: {len(cams)}")
        for c in cams:
            out.append(f"     🎥 [{c['index']}] {c['name']}")
    else:
        out.append("[!] No cameras detected.")
    return out
