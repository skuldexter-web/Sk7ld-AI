"""
config.py - persisted user settings for Sk7ld-AI.

Currently stores the editable persona (system prompt). Lives at
~/.config/sk7ld-ai/config.json (override dir with SK7LD_AI_CONFIG_DIR).
Everything is best-effort: a missing or unwritable config never breaks the app,
it just falls back to defaults.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict

from .ollama_client import DEFAULT_SYSTEM_PROMPT

CONFIG_DIR = Path(os.environ.get(
    "SK7LD_AI_CONFIG_DIR", str(Path.home() / ".config" / "sk7ld-ai")))
CONFIG_FILE = CONFIG_DIR / "config.json"


def load() -> Dict:
    try:
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save(cfg: Dict) -> bool:
    try:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


# ── persona (system prompt) ─────────────────────────────────────────────
def get_system_prompt() -> str:
    val = load().get("system_prompt")
    return val.strip() if isinstance(val, str) and val.strip() else DEFAULT_SYSTEM_PROMPT


def set_system_prompt(text: str) -> bool:
    cfg = load()
    text = (text or "").strip()
    if not text:
        cfg.pop("system_prompt", None)
    else:
        cfg["system_prompt"] = text
    return save(cfg)


def reset_system_prompt() -> bool:
    cfg = load()
    cfg.pop("system_prompt", None)
    return save(cfg)


def is_custom_persona() -> bool:
    return get_system_prompt() != DEFAULT_SYSTEM_PROMPT


# ── one-time authorised-use disclaimer ──────────────────────────────────
def disclaimer_accepted() -> bool:
    return bool(load().get("disclaimer_accepted"))


def accept_disclaimer() -> bool:
    cfg = load()
    cfg["disclaimer_accepted"] = True
    return save(cfg)
