"""
visuals.py - cozy cyberpunk visuals for the HUD.

  * Honeycomb  - a tk.Canvas that draws the PC live feeds as hexagon tiles, each
                 with a circular ring-gauge and centered value (CPU / GPU / RAM /
                 NET / DISK around a live clock in the middle) - the honeycomb
                 arrangement from the reference, but hexagons instead of circles.
  * make_ambient - a soft, glassy, theme-tinted background image (two radial
                 glows + vignette) that gives the window its cozy, see-through
                 ambience. Returns a PIL image, or None if PIL is unavailable.
"""

from __future__ import annotations

import math
import tkinter as tk
from typing import Dict, Optional, Tuple

try:
    from PIL import Image, ImageOps, ImageDraw, ImageFilter
    _HAS_PIL = True
except Exception:  # noqa: BLE001
    _HAS_PIL = False

import random


def _hex2rgb(h: str) -> Tuple[int, int, int]:
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore


# ════════════════════════════════════════════════════════════════════════
#  HONEYCOMB  (hex ring-gauge tiles)
# ════════════════════════════════════════════════════════════════════════
class Honeycomb(tk.Canvas):
    # cell -> angle on the flower (deg, 90 = top). center handled separately.
    PETALS = {
        "cpu": 90, "ram": 30, "gpu": 330, "disk": 270, "net": 210, "weather": 150,
    }

    def __init__(self, parent, theme: dict, r: int = 52):
        self.r = r
        self.d = math.sqrt(3) * r                 # center-to-center spacing
        pad = r + 10
        self.W = int(2 * (self.d * math.cos(math.radians(30))) + 2 * r + pad)
        self.H = int(2 * self.d + 2 * r + pad)
        super().__init__(parent, width=self.W, height=self.H,
                         bg=theme["glass"], highlightthickness=0, bd=0)
        self.theme = theme
        self.cx, self.cy = self.W / 2, self.H / 2
        self._centers: Dict[str, Tuple[float, float]] = {}
        self._last: Dict[str, Tuple[float, str, str, str]] = {}  # name->(pct,big,sub,colorkey)
        self._layout()

    # ── geometry ────────────────────────────────────────────────────────
    def _hex_points(self, cx, cy, r):
        pts = []
        for a in (90, 150, 210, 270, 330, 30):   # pointy-top
            rad = math.radians(a)
            pts += [cx + r * math.cos(rad), cy - r * math.sin(rad)]
        return pts

    def _layout(self):
        self.delete("all")
        self._centers = {"clock": (self.cx, self.cy)}
        for name, ang in self.PETALS.items():
            rad = math.radians(ang)
            self._centers[name] = (self.cx + self.d * math.cos(rad),
                                   self.cy - self.d * math.sin(rad))
        for name, (cx, cy) in self._centers.items():
            self.create_polygon(self._hex_points(cx, cy, self.r),
                                 fill=self.theme["glass2"], outline=self.theme["border"],
                                 width=2, joinstyle="round", tags=("hex", f"hex_{name}"))

    # ── drawing a gauge ─────────────────────────────────────────────────
    def set(self, name: str, pct: Optional[float], big: str, sub: str,
            color_key: str = "accent"):
        if name not in self._centers:
            return
        self._last[name] = (pct if pct is not None else -1, big, sub, color_key)
        cx, cy = self._centers[name]
        rr = self.r * 0.56
        self.delete(f"dyn_{name}")
        color = self.theme.get(color_key, self.theme["accent"])
        bbox = (cx - rr, cy - rr, cx + rr, cy + rr)
        # track
        self.create_arc(*bbox, start=0, extent=359.9, style=tk.ARC,
                        outline=self.theme["grid"], width=6, tags=(f"dyn_{name}",))
        # value arc
        if pct is not None and pct > 0:
            self.create_arc(*bbox, start=90, extent=-3.599 * max(0, min(100, pct)),
                            style=tk.ARC, outline=color, width=6, tags=(f"dyn_{name}",))
        # texts
        self.create_text(cx, cy - 7, text=big, fill=self.theme["text"],
                         font=("TkDefaultFont", 13, "bold"), tags=(f"dyn_{name}",))
        self.create_text(cx, cy + 13, text=sub, fill=self.theme["dim"],
                         font=("TkDefaultFont", 8), tags=(f"dyn_{name}",))

    def set_clock(self, hhmm: str, date: str, seconds: int):
        self.set("clock", seconds / 60 * 100, hhmm, date, "accent2")

    # ── re-theme ────────────────────────────────────────────────────────
    def retheme(self, theme: dict):
        self.theme = theme
        self.configure(bg=theme["glass"])
        self._layout()
        for name, (pct, big, sub, ck) in list(self._last.items()):
            self.set(name, pct if pct >= 0 else None, big, sub, ck)


# ════════════════════════════════════════════════════════════════════════
#  AMBIENT BACKGROUND
# ════════════════════════════════════════════════════════════════════════
def _glow(size: Tuple[int, int], color, strength: float):
    g = Image.radial_gradient("L").resize(size)   # 0 center .. 255 edge
    g = ImageOps.invert(g)                         # bright center
    layer = Image.new("RGBA", size, color + (0,))
    layer.putalpha(g.point(lambda v: int(v * strength)))
    return layer


def make_ambient(w: int, h: int, theme: dict):
    """
    Cozy, theme-tinted blurred-bokeh backdrop (like a rainy glass window), so the
    floating glass cards read as frosted panels over a soft desktop. Returns a PIL
    RGB image, or None if PIL is unavailable.
    """
    if not _HAS_PIL or w < 10 or h < 10:
        return None
    rw, rh = min(w, 1100), min(h, 720)
    base = Image.new("RGB", (rw, rh), _hex2rgb(theme["bg"]))
    draw = ImageDraw.Draw(base, "RGBA")

    palette = [theme["accent"], theme["accent2"], theme["glow"], theme["sub_col"]]
    warm = (255, 180, 90)                       # a few warm "city light" bokeh
    rnd = random.Random(hash(theme.get("title", "")) & 0xFFFFFFFF)

    # scattered soft bokeh discs
    for _ in range(46):
        cx = rnd.uniform(-0.05, 1.05) * rw
        cy = rnd.uniform(-0.05, 1.05) * rh
        rad = rnd.uniform(0.04, 0.14) * min(rw, rh)
        col = _hex2rgb(rnd.choice(palette)) if rnd.random() > 0.18 else warm
        a = rnd.randint(26, 74)
        draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=col + (a,))

    # two broad glows anchor the composition
    base = base.convert("RGBA")
    for fx, fy, col, rad, strg in [(0.22, 0.24, theme["accent"], 0.9, 0.16),
                                   (0.85, 0.85, theme["accent2"], 1.0, 0.13)]:
        gs = int(min(rw, rh) * rad)
        layer = Image.new("RGBA", (rw, rh), (0, 0, 0, 0))
        glow = _glow((gs, gs), _hex2rgb(col), strg)
        layer.paste(glow, (int(fx * rw - gs / 2), int(fy * rh - gs / 2)), glow)
        base = Image.alpha_composite(base, layer)

    base = base.convert("RGB").filter(ImageFilter.GaussianBlur(radius=max(6, rw // 70)))

    # darken + vignette so bright cards sit comfortably on top (cozy)
    dark = Image.new("RGB", (rw, rh), _hex2rgb(theme["bg"]))
    base = Image.blend(base, dark, 0.34)
    vg = Image.radial_gradient("L").resize((rw, rh))
    vlayer = Image.new("RGBA", (rw, rh), (0, 0, 0, 255))
    vlayer.putalpha(vg.point(lambda v: int(v * 0.36)))
    base = Image.alpha_composite(base.convert("RGBA"), vlayer).convert("RGB")
    return base
