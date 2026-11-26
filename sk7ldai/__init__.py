"""
Sk7ld-AI - Digital Longship Intelligence System
====================================================

A unified GUI / CLI hybrid that fuses:

  * the multi-theme CustomTkinter Ollama chat front-end (formerly skuld.py /
    ai_terminal.py), and
  * the Viking AI weapon-arsenal orchestration engine (formerly viking /
    install.sh).

The chat core detects the operator's intent, offers the matching tools from the
arsenal (with short descriptions), confirms before installing anything that is
missing, then runs the tool and can feed the output back to the local LLM for
analysis.

Brand : SK7LD        GitHub : skuldexter-web        IG : @s.k.7.l.d
License: MIT
"""

__version__ = "3.3.0"
__app_name__ = "Sk7ld-AI"
__brand__ = "SK7LD"

# Default chat model: a small *instruct* model (not a base/completion model).
# Base models don't follow chat turns and degenerate into loops/echoes in a
# conversation; the instruct model stays on-persona and stops cleanly. It's in
# the requested small (3B) range; forge bigger ones from the sidebar.
DEFAULT_MODEL = "qwen2.5:3b"
OLLAMA_BASE_URL = "http://localhost:11434"
