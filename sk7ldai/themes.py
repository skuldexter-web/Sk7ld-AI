"""
themes.py - Sk7ld-AI visual identity (cyberpunk edition).

Three curated themes only:
  * sk7ld     - cyan-blue + purple neon (default)
  * v1ru5     - the original V1RU5 green node (colors kept)
  * baphomet  - crimson + gold occult-cyber

Every theme carries the same full key schema so the modern HUD (live weather +
CPU/GPU/RAM/ethernet feeds) and all widgets style consistently. `_fill` back-
fills any missing key from sensible defaults so a partial theme can't crash the
GUI.
"""

from collections import OrderedDict

DEFAULT_THEME = "sk7ld"

# Canonical key set every theme should provide.
# glass  = cozy frosted panel fill (sits over the ambient background)
# glass2 = hexagon tile fill (a touch darker than glass)
_SCHEMA_DEFAULTS = {
    "emoji": "△", "subtitle": "", "show_v1ru5_ig": False,
    "bg": "#070a12", "sidebar": "#0b0f1c", "panel": "#0d1322", "box": "#0a0e1a",
    "glass": "#121a2e", "glass2": "#0e1626",
    "text": "#c9d6f0", "dim": "#6b7a99", "title": "#22d3ee", "sub_col": "#a855f7",
    "accent": "#22d3ee", "accent2": "#a855f7", "accent_text": "#04121a",
    "hover": "#0ea5c4", "border": "#1b2a44", "grid": "#142238",
    "entry_bg": "#0e1526", "entry_text": "#e8f4ff",
    "good": "#22d3ee", "warn": "#f5c542", "bad": "#ff4d6d", "glow": "#22d3ee",
}

_RAW = OrderedDict([
    # ── sk7ld : cyan-blue + purple neon (default) ───────────────────────
    ("sk7ld", {
        "emoji": "△", "subtitle": "SK7LD // Neon Longship", "show_v1ru5_ig": False,
        "bg": "#0a0f1c", "sidebar": "#11182b", "panel": "#141d33", "box": "#111a2e",
        "glass": "#18223b", "glass2": "#131d33",
        "text": "#d4e2f7", "dim": "#8294b5", "title": "#38d6f0", "sub_col": "#b388ff",
        "accent": "#38d6f0", "accent2": "#b388ff", "accent_text": "#04121a",
        "hover": "#5fe0f5", "border": "#2a3a5c", "grid": "#1d2a45",
        "entry_bg": "#16203a", "entry_text": "#eaf5ff",
        "good": "#38d6f0", "warn": "#f5c76a", "bad": "#ff6b8a", "glow": "#5aa0ff",
    }),
    # ── v1ru5 : original green neural node (COLORS KEPT) ─────────────────
    ("v1ru5", {
        "emoji": "\U0001f9a0", "subtitle": "V1RU5 Neural Node", "show_v1ru5_ig": True,
        "bg": "#0d0616", "sidebar": "#180a26", "panel": "#1c0e2e", "box": "#150722",
        "glass": "#231038", "glass2": "#1b0c2c",
        "text": "#d0a3ff", "dim": "#8a6aaa", "title": "#00ff66", "sub_col": "#a822e2",
        "accent": "#00ff66", "accent2": "#a822e2", "accent_text": "#09040d",
        "hover": "#00c853", "border": "#52207a", "grid": "#331550",
        "entry_bg": "#20103a", "entry_text": "#ffffff",
        "good": "#00ff66", "warn": "#ffcc00", "bad": "#ff3b6b", "glow": "#9b2dff",
    }),
    # ── Cvlt of Baph0mau5 : crimson + gold occult-cyber ─────────────────
    ("Cvlt of Baph0mau5", {
        "emoji": "⛧", "subtitle": "Sigil of the Black Goat", "show_v1ru5_ig": False,
        "bg": "#100808", "sidebar": "#1a0c0c", "panel": "#1f0e0e", "box": "#190a0a",
        "glass": "#241111", "glass2": "#1c0d0d",
        "text": "#edd0c6", "dim": "#9c6a60", "title": "#ff3350", "sub_col": "#e0bd54",
        "accent": "#ff3350", "accent2": "#e0bd54", "accent_text": "#100808",
        "hover": "#d6273f", "border": "#4a1a1c", "grid": "#331414",
        "entry_bg": "#241212", "entry_text": "#ffe9e0",
        "good": "#ff3350", "warn": "#e0bd54", "bad": "#ff7a5c", "glow": "#ff3350",
    }),
    # ── black and white : monochrome dark (white on black) ──────────────
    ("black and white", {
        "emoji": "◼", "subtitle": "Monochrome // Dark", "show_v1ru5_ig": False,
        "bg": "#000000", "sidebar": "#0b0b0b", "panel": "#101010", "box": "#0a0a0a",
        "glass": "#141414", "glass2": "#0e0e0e",
        "text": "#e6e6e6", "dim": "#8a8a8a", "title": "#ffffff", "sub_col": "#bdbdbd",
        "accent": "#ffffff", "accent2": "#9e9e9e", "accent_text": "#000000",
        "hover": "#cccccc", "border": "#2a2a2a", "grid": "#1c1c1c",
        "entry_bg": "#161616", "entry_text": "#ffffff",
        "good": "#ffffff", "warn": "#bdbdbd", "bad": "#8a8a8a", "glow": "#ffffff",
    }),
    # ── white and black : monochrome light (black on white) ─────────────
    ("white and black", {
        "emoji": "◻", "subtitle": "Monochrome // Light", "show_v1ru5_ig": False,
        "bg": "#f4f4f4", "sidebar": "#ffffff", "panel": "#fbfbfb", "box": "#ffffff",
        "glass": "#ffffff", "glass2": "#f0f0f0",
        "text": "#141414", "dim": "#6b6b6b", "title": "#000000", "sub_col": "#444444",
        "accent": "#000000", "accent2": "#555555", "accent_text": "#ffffff",
        "hover": "#333333", "border": "#d0d0d0", "grid": "#e4e4e4",
        "entry_bg": "#f0f0f0", "entry_text": "#000000",
        "good": "#000000", "warn": "#555555", "bad": "#888888", "glow": "#9e9e9e",
    }),
])


def _fill(d: dict) -> dict:
    out = dict(_SCHEMA_DEFAULTS)
    out.update(d)
    return out


THEMES = OrderedDict((k, _fill(v)) for k, v in _RAW.items())

# Social links shown in the sidebar (order matters).
SOCIAL_LINKS = {
    "github": "GitHub: skuldexter-web",
    "instagram": "Instagram: @s.k.7.l.d",
    "instagram_v1ru5": "Instagram: @v1ru5_0",  # only under the v1ru5 theme
}


def get_theme(name: str) -> dict:
    """Return a theme dict, falling back to the default."""
    return THEMES.get(name, THEMES[DEFAULT_THEME])
