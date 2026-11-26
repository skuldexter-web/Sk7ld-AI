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

__version__ = "3.1.0"
__app_name__ = "Sk7ld-AI"
__brand__ = "SK7LD"

# Only base models, per spec.
DEFAULT_MODEL = "qwen2.5-coder:1.5b-base"
OLLAMA_BASE_URL = "http://localhost:11434"
