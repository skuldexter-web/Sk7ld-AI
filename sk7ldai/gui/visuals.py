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
import time
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




def _mix(c1, c2, t: float) -> str:
    """Blend two #rrggbb colours, t in 0..1."""
    a, b = _hex2rgb(c1), _hex2rgb(c2)
    return "#%02x%02x%02x" % tuple(
        max(0, min(255, int(a[i] + (b[i] - a[i]) * t))) for i in range(3))


# ════════════════════════════════════════════════════════════════════════
#  VOICE ORB  (smooth plexus wireframe globe for listen / talk)
# ════════════════════════════════════════════════════════════════════════
class VoiceOrb(tk.Canvas):
    """
    A glowing plexus globe - dots joined by faint lines on a rotating sphere,
    with depth fading, a soft halo and a floor shadow (like the reference art).

    Two motions, same globe:
      * listening - calm: slow spin, gentle breathing.
      * talking   - lively: faster spin, speech-like pulse that swells the mesh.

    Smoothness: every canvas item (halo, lines, dots) is created ONCE and then
    moved with `coords`/`itemconfigure` each frame - no per-frame delete/recreate,
    so there's no flicker and far less CPU churn. Time-based so the motion speed
    is independent of frame rate.
    """

    def __init__(self, parent, theme: dict, size: int = 230, n: int = 60):
        super().__init__(parent, width=size, height=size, bg=theme["glass2"],
                         highlightthickness=0, bd=0)
        self.theme = theme
        self.size = size
        self.cx = size / 2
        self.cy = size * 0.46
        self.R = size * 0.37
        self.n = n
        self.mode = None
        self._running = False
        self._job = None
        self._t = 0.0
        self._last = None
        self._energy = 0.0
        self._pts = self._fib_sphere(n)
        self._phase = [(i * 0.7) % (2 * math.pi) for i in range(n)]
        self._edges = self._build_edges(self._pts, k=3)
        self._built = False
        self._halo = None
        self._floor = None
        self._line_ids = []
        self._dot_ids = []

    # ── geometry ────────────────────────────────────────────────────────
    @staticmethod
    def _fib_sphere(n):
        pts = []
        ga = math.pi * (3 - math.sqrt(5))
        for i in range(n):
            y = 1 - (i / (n - 1)) * 2
            r = math.sqrt(max(0.0, 1 - y * y))
            th = ga * i
            pts.append((math.cos(th) * r, y, math.sin(th) * r))
        return pts

    @staticmethod
    def _build_edges(pts, k=3):
        edges = set()
        for i, a in enumerate(pts):
            d = []
            for j, b in enumerate(pts):
                if i == j:
                    continue
                dx, dy, dz = a[0] - b[0], a[1] - b[1], a[2] - b[2]
                d.append((dx * dx + dy * dy + dz * dz, j))
            d.sort()
            for _, j in d[:k]:
                edges.add((min(i, j), max(i, j)))
        return list(edges)

    def set_theme(self, theme: dict):
        self.theme = theme
        self.configure(bg=theme["glass2"])
        self._built = False          # colours rebuilt on next frame
        self.delete("all")
        self._halo = self._floor = None
        self._line_ids = []
        self._dot_ids = []

    # ── control ─────────────────────────────────────────────────────────
    def start(self, mode: str):
        self.mode = mode
        self._last = None
        if not self._running:
            self._running = True
            self._animate()

    def stop(self):
        self._running = False
        if self._job is not None:
            try:
                self.after_cancel(self._job)
            except Exception:
                pass
            self._job = None

    # ── one-time item creation ──────────────────────────────────────────
    def _build_items(self):
        self.delete("all")
        glass2 = self.theme["glass2"]
        # soft halo discs behind the globe (concentric, dim -> transparent-ish)
        self._halo = []
        for k, f in enumerate((1.55, 1.3, 1.08)):
            r = self.R * f
            col = _mix(glass2, self.theme["glow"], 0.10 + 0.07 * (2 - k))
            self._halo.append(self.create_oval(self.cx - r, self.cy - r,
                                               self.cx + r, self.cy + r,
                                               outline="", fill=col))
        # floor shadow ellipse
        fr = self.R * 1.05
        fy = self.cy + self.R * 1.28
        self._floor = self.create_oval(self.cx - fr, fy - self.R * 0.12,
                                       self.cx + fr, fy + self.R * 0.12,
                                       outline="", fill=_mix(glass2, self.theme["accent"], 0.12))
        # edges, then dots (drawn last = on top)
        self._line_ids = [self.create_line(0, 0, 0, 0, fill=glass2, width=1)
                          for _ in self._edges]
        self._dot_ids = [self.create_oval(0, 0, 0, 0, outline="", fill=glass2)
                         for _ in self._pts]
        self._built = True

    # ── animation ───────────────────────────────────────────────────────
    def _animate(self):
        if not self._running:
            return
        now = time.monotonic()
        dt = 0.033 if self._last is None else min(0.05, now - self._last)
        self._last = now
        self._t += dt
        if not self._built:
            self._build_items()

        talking = (self.mode == "talking")
        if talking:
            spin = 0.9
            amp = 0.16
            freq = 2.3
            burst = max(0.0, math.sin(self._t * 4.4)) ** 2
            pulse = 0.45 * burst + 0.12
            tgt = 0.45 + 0.55 * burst
            line_col = _mix(self.theme["glass2"], self.theme["accent2"], 0.85)
            dot_hi = self.theme["glow"]
        else:
            spin = 0.42
            amp = 0.06
            freq = 1.2
            pulse = 0.0
            tgt = 0.16
            line_col = _mix(self.theme["glass2"], self.theme["accent"], 0.7)
            dot_hi = self.theme["accent"]
        # ease energy toward its target for buttery transitions
        self._energy += (tgt - self._energy) * min(1.0, dt * 6)

        yaw = self._t * spin
        pitch = 0.32 * math.sin(self._t * 0.35)
        cy_, sy_ = math.cos(yaw), math.sin(yaw)
        cp_, sp_ = math.cos(pitch), math.sin(pitch)
        R = self.R
        dim = self.theme["grid"]
        glass2 = self.theme["glass2"]

        scr = []
        for i, (x, y, z) in enumerate(self._pts):
            disp = amp * math.sin(self._t * freq + self._phase[i]) + amp * pulse
            r = 1.0 + disp
            x, y, z = x * r, y * r, z * r
            x, z = x * cy_ + z * sy_, -x * sy_ + z * cy_
            y, z = y * cp_ - z * sp_, y * sp_ + z * cp_
            persp = 0.72 + 0.28 * ((z + 1.4) / 2.8)
            scr.append((self.cx + x * R * persp, self.cy + y * R * persp, z))

        # lines: colour fades with average depth (back = dim, front = bright)
        for idx, (i, j) in enumerate(self._edges):
            x1, y1, z1 = scr[i]
            x2, y2, z2 = scr[j]
            depth = (((z1 + z2) * 0.5) + 1.4) / 2.8      # 0 back .. 1 front
            col = _mix(dim, line_col, max(0.0, min(1.0, depth)) ** 1.3)
            self.coords(self._line_ids[idx], x1, y1, x2, y2)
            self.itemconfigure(self._line_ids[idx], fill=col,
                               width=2 if depth > 0.6 else 1)

        # dots: size + colour by depth, with an energy-driven glow on front nodes
        for idx, (sx, sy, z) in enumerate(scr):
            depth = (z + 1.4) / 2.8
            rad = 1.4 + 2.6 * depth + 1.3 * self._energy * depth
            col = _mix(_mix(dim, dot_hi, depth), self.theme["glow"],
                       self._energy * depth * 0.8)
            self.coords(self._dot_ids[idx], sx - rad, sy - rad, sx + rad, sy + rad)
            self.itemconfigure(self._dot_ids[idx], fill=col)

        # halo + floor breathe a touch with energy
        glowf = 0.10 + 0.22 * self._energy
        for k, hid in enumerate(self._halo):
            self.itemconfigure(hid, fill=_mix(glass2, self.theme["glow"],
                                              glowf * (0.5 + 0.25 * (2 - k))))
        self.itemconfigure(self._floor, fill=_mix(glass2, self.theme["accent"],
                                                  0.10 + 0.10 * self._energy))

        self._job = self.after(16, self._animate)       # ~60 fps target
