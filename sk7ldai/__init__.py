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

__version__ = "3.4.0"
__app_name__ = "Sk7ld-AI"
__brand__ = "SK7LD"

# Chat + code use BASE models only (qwen2.5-coder base family). Base models are
# completion models, so ollama_client drives them with a raw transcript prompt,
# stop sequences and a loop guard instead of a chat template.
DEFAULT_MODEL = "qwen2.5-coder:1.5b-base"
ALLOWED_MODELS = (
    "qwen2.5-coder:1.5b-base",     # default, light
    "qwen2.5-coder:3b-base",       # medium
    "qwen2.5-coder:14b-base",      # strong (~9 GB VRAM)
)
OLLAMA_BASE_URL = "http://localhost:11434"


def sanitize_model(name) -> str:
    """Return `name` if it's an allowed base model, else the default."""
    return name if name in ALLOWED_MODELS else DEFAULT_MODEL
