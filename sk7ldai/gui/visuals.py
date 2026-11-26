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


# ════════════════════════════════════════════════════════════════════════
#  VOICE ORB  (animated plexus wireframe sphere for listen / talk)
# ════════════════════════════════════════════════════════════════════════
class VoiceOrb(tk.Canvas):
    """
    An animated "orb" shown while Sk7ld-AI is listening or talking. Every theme
    gets its OWN orb shape (``theme["orb"]``), but all share the same two-state
    motion and are drawn in the active theme's colours:

      * listening - calm: slow spin / gentle breathing.
      * talking   - energetic: faster spin, speech-like pulses + jitter.

    Styles:
      * ``plexus`` - rotating morphing wireframe globe (default / monochrome).
      * ``virus``  - a spiky capsid (🦠) for the V1RU5 theme.
      * ``sigil``  - a rotating occult circle (hexagram + inverted pentagram +
                     horned XX-eyed goat glyph) for Cvlt of Baph0mau5.
      * ``viking`` - a horned-helmet warrior face inside a spinning code-ring,
                     for the SK7LD theme.
    """

    def __init__(self, parent, theme: dict, size: int = 230, n: int = 54):
        super().__init__(parent, width=size, height=size, bg=theme["glass2"],
                         highlightthickness=0, bd=0)
        self.theme = theme
        self.style = theme.get("orb", "plexus")
        self.size = size
        self.cx = self.cy = size / 2
        self.R = size * 0.40
        self.mode = None
        self._running = False
        self._job = None
        self._t = 0.0
        self._yaw = 0.0
        self._pitch = 0.0
        self._pulse = 0.0
        self._energy = 0.0
        # plexus data
        self._pts = self._fib_sphere(n)
        self._phase = [(i * 0.7) % (2 * math.pi) for i in range(n)]
        self._edges = self._build_edges(self._pts, k=3)
        # per-style phase tables (deterministic)
        self._spk_phase = [(i * 1.37) % (2 * math.pi) for i in range(22)]
        self._tick_phase = [(i * 2.11) % (2 * math.pi) for i in range(28)]

    # ── geometry (plexus) ───────────────────────────────────────────────
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
        self.style = theme.get("orb", "plexus")
        self.configure(bg=theme["glass2"])

    # ── small helpers ───────────────────────────────────────────────────
    def _u(self, ux, uy, s=0.8, dx=0.0, dy=0.0):
        """unit coords (-1..1) -> canvas pixels."""
        return (self.cx + ux * self.R * s + dx, self.cy + uy * self.R * s + dy)

    @staticmethod
    def _rot(pts, a):
        ca, sa = math.cos(a), math.sin(a)
        return [(x * ca - y * sa, x * sa + y * ca) for (x, y) in pts]

    # ── control ─────────────────────────────────────────────────────────
    def start(self, mode: str):
        self.mode = mode
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
        self.delete("all")

    # ── animation driver ────────────────────────────────────────────────
    def _animate(self):
        if not self._running:
            return
        self._t += 0.05
        talking = (self.mode == "talking")
        if talking:
            self._yaw += 0.075
            burst = max(0.0, math.sin(self._t * 5.0)) ** 2
            self._pulse = 0.6 * burst + 0.2 * (math.sin(self._t * 11.0) * 0.5 + 0.5)
            self._energy = 0.45 + 0.55 * burst
        else:
            self._yaw += 0.032
            self._pulse = 0.0
            self._energy = 0.14 + 0.08 * (math.sin(self._t * 1.3) * 0.5 + 0.5)

        self.delete("all")
        style = self.style
        if style == "virus":
            self._draw_virus(talking)
        elif style == "sigil":
            self._draw_sigil(talking)
        elif style == "viking":
            self._draw_viking(talking)
        else:
            self._draw_plexus(talking)
        self._job = self.after(50, self._animate)

    # ── style: plexus globe ─────────────────────────────────────────────
    def _draw_plexus(self, talking):
        amp = 0.17 if talking else 0.07
        freq = 2.4 if talking else 1.3
        jitter = 0.05 if talking else 0.0
        line_col = self.theme["accent2"] if talking else self.theme["accent"]
        dot_col = self.theme["glow"] if talking else self.theme["accent"]
        dim = self.theme["grid"]
        self._pitch = 0.35 * math.sin(self._t * 0.4)
        cy_, sy_ = math.cos(self._yaw), math.sin(self._yaw)
        cp_, sp_ = math.cos(self._pitch), math.sin(self._pitch)
        scr = []
        for i, (x, y, z) in enumerate(self._pts):
            disp = amp * math.sin(self._t * freq + self._phase[i]) + amp * self._pulse
            if jitter:
                disp += jitter * math.sin(self._t * 9 + i)
            r = 1.0 + disp
            x, y, z = x * r, y * r, z * r
            x, z = x * cy_ + z * sy_, -x * sy_ + z * cy_
            y, z = y * cp_ - z * sp_, y * sp_ + z * cp_
            persp = 0.70 + 0.30 * ((z + 1.5) / 3.0)
            scr.append((self.cx + x * self.R * persp, self.cy + y * self.R * persp, z))
        for (i, j) in self._edges:
            x1, y1, z1 = scr[i]
            x2, y2, z2 = scr[j]
            front = (z1 + z2) * 0.5 > 0
            self.create_line(x1, y1, x2, y2, fill=line_col if front else dim,
                             width=2 if front else 1)
        for (sx, sy, z) in scr:
            rad = 3.2 if z > 0 else 1.8
            self.create_oval(sx - rad, sy - rad, sx + rad, sy + rad,
                             fill=dot_col if z > 0 else dim, outline="")

    # ── style: V1RU5 - menacing virus (spiky capsid + fanged face) ──────
    def _draw_virus(self, talking):
        acc = self.theme["accent"]                     # green (eyes + fangs)
        acc2 = self.theme["accent2"]                   # purple (spikes)
        glow = self.theme["glow"]                      # violet (knobs/glow)
        dim = self.theme["grid"]
        body = self.theme.get("panel", self.theme["box"])
        e = self._energy
        breathe = 1.0 + 0.03 * math.sin(self._t * (3.0 if talking else 1.4))
        cr = self.R * 0.52 * breathe                   # capsid-body radius
        bob = self.R * 0.02 * math.sin(self._t * (2.2 if talking else 1.0))
        cy0 = self.cy + bob

        # corona spikes (slowly rotating, purple with glowing knobs)
        NS = 14
        base = 0.30 + (0.12 if talking else 0.04)
        for i in range(NS):
            ph = self._spk_phase[i]
            a = (i / NS) * 2 * math.pi + self._yaw
            wob = (0.09 if talking else 0.04) * math.sin(self._t * (6 if talking else 2.2) + ph)
            ln = self.R * (base + wob) + self.R * 0.22 * self._pulse
            x0, y0 = self.cx + math.cos(a) * cr, cy0 + math.sin(a) * cr
            x1, y1 = self.cx + math.cos(a) * (cr + ln), cy0 + math.sin(a) * (cr + ln)
            self.create_line(x0, y0, x1, y1, fill=acc2, width=3)
            kr = 3.0 + 2.4 * e
            self.create_oval(x1 - kr, y1 - kr, x1 + kr, y1 + kr, fill=glow, outline=acc2)

        # body
        self.create_oval(self.cx - cr, cy0 - cr, self.cx + cr, cy0 + cr,
                         fill=body, outline=acc2, width=3)
        self.create_oval(self.cx - cr * 0.9, cy0 - cr * 0.9,
                         self.cx + cr * 0.9, cy0 + cr * 0.9, outline=dim, width=1)

        def fx(u):
            return self.cx + u * cr

        def fy(u):
            return cy0 + u * cr

        # angry green eyes (sharp inward-pointing wedges) + bright cores
        le = [(-0.60, -0.24), (-0.10, -0.02), (-0.58, 0.08)]
        re = [(0.60, -0.24), (0.10, -0.02), (0.58, 0.08)]
        for eye in (le, re):
            pts = []
            for u, v in eye:
                pts += [fx(u), fy(v)]
            self.create_polygon(pts, fill=acc, outline=glow, width=1)
        for ex in (-0.36, 0.36):
            er = 2.5 + 2.6 * e
            self.create_oval(fx(ex) - er, fy(-0.07) - er, fx(ex) + er, fy(-0.07) + er,
                             fill=acc, outline="")

        # fanged maw - dark cavity, green interlocking teeth, drips
        y_t = 0.22
        gap = 0.22 + 0.10 * e + (0.05 if talking else 0.0)   # maw opens while talking
        y_b = y_t + gap
        xL, xR = -0.58, 0.58
        self.create_polygon(fx(xL), fy(y_t), fx(xR), fy(y_t),
                            fx(xR), fy(y_b), fx(0.0), fy(y_b + 0.07), fx(xL), fy(y_b),
                            fill=body, outline=acc, width=1)
        nt = 7
        flen = 0.09 + 0.05 * e
        span = xR - xL
        for k in range(nt):                               # upper fangs (point down)
            x0 = xL + span * k / nt
            x1 = xL + span * (k + 1) / nt
            self.create_polygon(fx(x0), fy(y_t), fx(x1), fy(y_t),
                                fx((x0 + x1) / 2), fy(y_t + flen), fill=acc, outline="")
        for k in range(nt):                               # lower fangs (point up)
            x0 = xL + span * (k + 0.5) / nt
            x1 = xL + span * (k + 1.5) / nt
            if x1 > xR:
                continue
            self.create_polygon(fx(x0), fy(y_b), fx(x1), fy(y_b),
                                fx((x0 + x1) / 2), fy(y_b - flen), fill=acc, outline="")
        for k in range(0, nt, 2):                         # dripping ooze
            x = xL + span * (k + 0.5) / nt
            dl = 0.05 + 0.22 * e
            self.create_line(fx(x), fy(y_b), fx(x), fy(y_b + dl), fill=acc, width=2)
            self.create_oval(fx(x) - 2, fy(y_b + dl) - 2, fx(x) + 2, fy(y_b + dl) + 2,
                             fill=acc, outline="")

    # ── style: occult sigil (⛧) ─────────────────────────────────────────
    def _draw_sigil(self, talking):
        acc = self.theme["accent"]        # crimson
        gold = self.theme["accent2"]      # gold
        glow = self.theme["glow"]
        dim = self.theme["grid"]
        lw = 2 if not talking else 3
        # outer ritual rings
        for s, col, w in ((0.98, gold, 2), (0.86, dim, 1), (0.80, gold, 1)):
            r = self.R * s
            self.create_oval(self.cx - r, self.cy - r, self.cx + r, self.cy + r,
                             outline=col, width=w)
        # perimeter tick-glyphs (counter-rotating little crosses)
        for i in range(8):
            a = (i / 8) * 2 * math.pi - self._yaw * 0.6
            x, y = self.cx + math.cos(a) * self.R * 0.90, self.cy + math.sin(a) * self.R * 0.90
            self.create_line(x - 4, y, x + 4, y, fill=gold, width=1)
            self.create_line(x, y - 4, x, y + 4, fill=gold, width=1)
        # hexagram (two triangles), slow spin
        up = self._rot([(0, -0.72), (0.624, 0.36), (-0.624, 0.36)], self._yaw * 0.5)
        dn = self._rot([(0, 0.72), (0.624, -0.36), (-0.624, -0.36)], self._yaw * 0.5)
        for tri in (up, dn):
            pts = []
            for ux, uy in tri:
                pts += list(self._u(ux, uy, s=1.0))
            self.create_polygon(pts, outline=acc, width=lw, fill="")
        # inverted pentagram (point down), opposite spin
        star = []
        for k in range(5):
            a = -math.pi / 2 + k * (2 * math.pi / 5)
            star.append((math.cos(a) * 0.46, -math.sin(a) * 0.46))  # flip -> point down
        star = self._rot(star, -self._yaw * 0.5)
        order = [0, 2, 4, 1, 3, 0]
        pen = []
        for k in order:
            pen += list(self._u(star[k][0], star[k][1], s=1.0, dy=self.R * 0.04))
        self.create_line(*pen, fill=glow if talking else acc, width=lw)
        # horned goat glyph in the middle
        gx, gy = self.cx, self.cy + self.R * 0.05
        # horns (two arcs sweeping up-out)
        self.create_arc(gx - self.R * 0.42, gy - self.R * 0.52,
                        gx + self.R * 0.02, gy - self.R * 0.04,
                        start=270, extent=120, style=tk.ARC, outline=acc, width=lw)
        self.create_arc(gx - self.R * 0.02, gy - self.R * 0.52,
                        gx + self.R * 0.42, gy - self.R * 0.04,
                        start=150, extent=120, style=tk.ARC, outline=acc, width=lw)
        # XX eyes
        for ex in (-0.14, 0.14):
            cxp, cyp = gx + ex * self.R, gy
            d = self.R * 0.06
            self.create_line(cxp - d, cyp - d, cxp + d, cyp + d, fill=gold, width=lw)
            self.create_line(cxp - d, cyp + d, cxp + d, cyp - d, fill=gold, width=lw)
        # little fanged snout
        self.create_line(gx - self.R * 0.10, gy + self.R * 0.14,
                         gx, gy + self.R * 0.24,
                         gx + self.R * 0.10, gy + self.R * 0.14,
                         fill=acc, width=lw)
        # crescent at the very top + flame flicker when talking
        self.create_arc(self.cx - self.R * 0.12, self.cy - self.R * 1.04,
                        self.cx + self.R * 0.12, self.cy - self.R * 0.80,
                        start=200, extent=140, style=tk.ARC, outline=gold, width=1)
        if talking:
            fy = self.cy - self.R * 0.70
            for k in (-1, 0, 1):
                j = 0.04 * self.R * math.sin(self._t * 13 + k)
                self.create_line(self.cx + k * self.R * 0.05, fy + self.R * 0.10,
                                 self.cx + k * self.R * 0.04 + j, fy - self.R * 0.06,
                                 fill=glow, width=2)

    # ── style: cyber-viking ─────────────────────────────────────────────
    def _draw_viking(self, talking):
        acc = self.theme["accent"]        # cyan
        acc2 = self.theme["accent2"]      # purple
        glow = self.theme["glow"]
        dim = self.theme["grid"]
        lw = 2 if not talking else 3
        bob = self.R * 0.03 * math.sin(self._t * (3.0 if talking else 1.2))
        # spinning "code ring" of ticks
        n = len(self._tick_phase)
        for i, ph in enumerate(self._tick_phase):
            a = (i / n) * 2 * math.pi + self._yaw
            lit = (math.sin(self._t * (7 if talking else 3) + ph) > 0.2)
            r0 = self.R * 0.98
            r1 = self.R * (1.06 if lit else 1.02)
            x0, y0 = self.cx + math.cos(a) * r0, self.cy + math.sin(a) * r0
            x1, y1 = self.cx + math.cos(a) * r1, self.cy + math.sin(a) * r1
            self.create_line(x0, y0, x1, y1, fill=(glow if lit else dim),
                             width=2 if lit else 1)
        rr = self.R * 0.90
        self.create_oval(self.cx - rr, self.cy - rr, self.cx + rr, self.cy + rr,
                         outline=acc2, width=1)

        fr = self.R * 0.80
        vio = acc2                               # official SK7LD viking purple
        dark = self.theme["glass2"]              # negative-space grooves
        eye_col = glow if talking else acc

        def P(u, v):
            return (self.cx + u * fr, self.cy + v * fr + bob)

        def poly(pts, fill, outline="", w=1, smooth=True):
            flat = []
            for (x, y) in pts:
                px, py = P(x, y)
                flat += [px, py]
            self.create_polygon(flat, fill=fill, outline=outline, width=w, smooth=smooth)

        # horns - big filled crescents sweeping up & out (drawn behind helmet)
        horn = [(0.40, -0.40), (0.68, -0.32), (0.96, -0.50), (1.04, -0.80),
                (0.93, -1.12), (0.84, -1.10), (0.84, -0.84), (0.72, -0.58), (0.48, -0.50)]
        poly([(-x, y) for x, y in horn], vio, dark, 1)
        poly(horn, vio, dark, 1)

        # helmet dome (filled) + ridge lines + centre flame crest
        self.create_arc(*(P(-0.46, -1.02) + P(0.46, 0.14)),
                        start=8, extent=164, style=tk.CHORD, fill=vio, outline=vio)
        for rx in (-0.30, -0.12, 0.12, 0.30):
            a, b = P(rx * 0.4, -0.92), P(rx, -0.46)
            self.create_line(a[0], a[1], b[0], b[1], fill=dark, width=2)
        flick = (0.05 if talking else 0.015) * self.R * math.sin(self._t * 12)
        fl, ft, frt = P(-0.06, -0.52), P(0.0, -0.84), P(0.06, -0.52)
        self.create_polygon(fl[0], fl[1], ft[0] + flick, ft[1], frt[0], frt[1],
                            fill=dark, outline="", smooth=True)

        # studded brow band
        poly([(-0.52, -0.46), (0.52, -0.46), (0.46, -0.26), (-0.46, -0.26)], vio, dark, 1,
             smooth=False)
        for i in range(7):
            rp = P(-0.40 + 0.80 * i / 6, -0.36)
            self.create_oval(rp[0] - 2.4, rp[1] - 2.4, rp[0] + 2.4, rp[1] + 2.4,
                             fill=dark, outline="")

        # face mass (cheeks/brow)
        poly([(-0.46, -0.26), (-0.56, 0.10), (-0.42, 0.42), (-0.20, 0.32),
              (0.20, 0.32), (0.42, 0.42), (0.56, 0.10), (0.46, -0.26)], vio)

        # furrowed angry brows + centre creases
        self.create_line(*(P(-0.44, -0.18) + P(-0.10, -0.03)), fill=dark, width=3)
        self.create_line(*(P(0.44, -0.18) + P(0.10, -0.03)), fill=dark, width=3)
        self.create_line(*(P(-0.06, -0.12) + P(-0.06, 0.04)), fill=dark, width=2)
        self.create_line(*(P(0.06, -0.12) + P(0.06, 0.04)), fill=dark, width=2)

        # eyes (glow with energy)
        for ex in (-0.26, 0.26):
            ep = P(ex, 0.00)
            er = 2.6 + 2.4 * self._energy
            self.create_oval(ep[0] - er, ep[1] - er, ep[0] + er, ep[1] + er,
                             fill=eye_col, outline="")

        # nose
        self.create_line(P(0.0, 0.02)[0], P(0.0, 0.02)[1],
                         P(-0.07, 0.26)[0], P(-0.07, 0.26)[1],
                         P(0.07, 0.26)[0], P(0.07, 0.26)[1],
                         fill=dark, width=2, smooth=True)

        # braided beard (filled, pointed) with strand grooves + mouth gap
        poly([(-0.52, 0.08), (-0.58, 0.38), (-0.46, 0.68), (-0.24, 0.94),
              (0.0, 1.14), (0.24, 0.94), (0.46, 0.68), (0.58, 0.38), (0.52, 0.08),
              (0.30, 0.16), (0.10, 0.44), (0.0, 0.42), (-0.10, 0.44), (-0.30, 0.16)],
             vio, dark, 1)
        # moustache over the beard top
        self.create_line(*(P(-0.02, 0.30) + P(-0.32, 0.22)), fill=dark, width=3, smooth=True)
        self.create_line(*(P(0.02, 0.30) + P(0.32, 0.22)), fill=dark, width=3, smooth=True)
        # strand grooves, flickering while talking
        for sx in (-0.30, -0.12, 0.12, 0.30):
            wig = (0.05 if talking else 0.02) * self.R * math.sin(self._t * 8 + sx * 7)
            a, b, tip = P(sx, 0.46), P(sx * 0.6, 0.82), P(0.0, 1.06)
            self.create_line(a[0], a[1], b[0] + wig, b[1], tip[0], tip[1],
                             fill=dark, width=2, smooth=True)
