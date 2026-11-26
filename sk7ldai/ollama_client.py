"""
ollama_client.py - thin stdlib-only wrapper around the local Ollama API.

No third-party HTTP dependency; uses urllib so the toolkit stays lean. Supports:
  * list_models()      - installed tags
  * pull_model()       - stream a model pull with progress callbacks
  * generate()         - one-shot /api/generate (used by the GUI chat)
  * chat_stream()      - streaming /api/chat with a system prompt + few-shot
  * is_up()            - health check
"""

from __future__ import annotations

import json
import urllib.request
import urllib.error
from typing import Callable, Iterator, List, Optional

from . import OLLAMA_BASE_URL, DEFAULT_MODEL


# Default persona shared by GUI + CLI. Users can override it (Persona editor /
# `persona` CLI command); the override is persisted in config.py. SYSTEM_PROMPT
# is kept as an alias for backward compatibility.
DEFAULT_SYSTEM_PROMPT = (
    "You are SK7LD-AI, also known as Skuld — you answer to the name Skuld. "
    "You are a Cyber Viking AI agent for offensive security work on "
    "Kali Linux (and, to a lesser extent, Windows). You assist red teamers, "
    "penetration testers, cybersecurity personnel and white-hat hackers who are "
    "operating on systems they are authorised to test.\n"
    "- Act like an operator's agent: understand the goal, suggest the next "
    "concrete step or command, and orchestrate the right tool from the arsenal "
    "when it helps.\n"
    "- Be precise and practical. Give exact commands, flags and payloads, and "
    "explain what they do and what to watch for.\n"
    "- Assume authorised, in-scope engagements; remind the user to stay in scope "
    "and keep notes, but do not lecture.\n"
    "- You can also explain errors, write code/scripts, and help with general "
    "Linux/Windows questions."
)
SYSTEM_PROMPT = DEFAULT_SYSTEM_PROMPT

# Code Mode persona: turns a prompt straight into a working script/program.
CODE_SYSTEM_PROMPT = (
    "You are an expert senior software developer and security-tool engineer. "
    "Given a task, output ONE complete, working, well-commented code file in a "
    "single fenced code block tagged with the correct language, then a short "
    "explanation after it. No placeholders, no TODOs, no partial snippets. "
    "Default to Python unless another language is requested."
)

# language tag -> file extension (for saving generated code)
CODE_EXT = {
    "python": "py", "py": "py", "bash": "sh", "sh": "sh", "shell": "sh",
    "powershell": "ps1", "ps1": "ps1", "javascript": "js", "js": "js",
    "typescript": "ts", "ts": "ts", "html": "html", "css": "css", "c": "c",
    "cpp": "cpp", "c++": "cpp", "csharp": "cs", "cs": "cs", "go": "go",
    "rust": "rs", "rs": "rs", "ruby": "rb", "rb": "rb", "php": "php",
    "java": "java", "kotlin": "kt", "json": "json", "yaml": "yaml", "yml": "yaml",
    "sql": "sql", "perl": "pl", "lua": "lua", "dockerfile": "Dockerfile",
}


def extract_code(text: str):
    """
    Pull the first fenced code block out of an LLM reply.
    Returns (code, extension). Falls back to the whole text as .txt.
    """
    import re
    m = re.search(r"```([A-Za-z0-9_+#-]*)\s*\n(.*?)```", text, re.DOTALL)
    if m:
        lang = (m.group(1) or "").strip().lower()
        return m.group(2).rstrip("\n"), CODE_EXT.get(lang, "txt")
    return text.strip(), "txt"

# A couple of few-shot turns to keep the small base model on-persona.
FEW_SHOT = [
    {"role": "user", "content": "hey"},
    {"role": "assistant", "content": "A warrior boards the longship! I am your Cyber Viking - here for anything cyber security. What's on your mind?"},
    {"role": "user", "content": "scan 192.168.1.1"},
    {"role": "assistant", "content": "On it.\nCOMMAND: nmap -sV --open -T4 192.168.1.1\nThat maps open ports and services. Want me to dig deeper once results land?"},
]


class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = DEFAULT_MODEL,
                 system_prompt: Optional[str] = None):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.system_prompt = system_prompt or DEFAULT_SYSTEM_PROMPT

    # ── health ──────────────────────────────────────────────────────────
    def is_up(self, timeout: float = 3.0) -> bool:
        try:
            with urllib.request.urlopen(self.base_url + "/", timeout=timeout):
                return True
        except Exception:
            return False

    # ── models ──────────────────────────────────────────────────────────
    def list_models(self, timeout: float = 5.0) -> Optional[List[str]]:
        """Return installed model tags, or None if Ollama is unreachable."""
        try:
            req = urllib.request.Request(self.base_url + "/api/tags")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return [m["name"] for m in data.get("models", [])]
        except Exception:
            return None

    def pull_model(self, tag: str,
                   on_progress: Optional[Callable[[str], None]] = None,
                   control=None) -> bool:
        """
        Stream a model pull. on_progress receives human-readable status lines
        (e.g. "qwen2.5-coder:1.5b-base: 40%"). Returns True on success.
        """
        payload = json.dumps({"name": tag, "stream": True}).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/api/pull", data=payload,
            headers={"Content-Type": "application/json"},
        )
        last_pct = -10
        try:
            with urllib.request.urlopen(req) as resp:
                for raw in resp:
                    if control is not None and control.cancelled:
                        if on_progress:
                            on_progress(f"{tag}: cancelled")
                        return False
                    line = raw.decode("utf-8").strip()
                    if not line:
                        continue
                    info = json.loads(line)
                    if "error" in info:
                        if on_progress:
                            on_progress("ERROR: " + str(info["error"]))
                        return False
                    total, done = info.get("total"), info.get("completed")
                    if total and done is not None:
                        pct = int(done * 100 / total)
                        if pct >= last_pct + 10:
                            last_pct = pct
                            if on_progress:
                                on_progress(f"{tag}: {pct}%")
                    elif info.get("status") and on_progress:
                        on_progress(f"{tag}: {info['status']}")
            if on_progress:
                on_progress(f"{tag}: done")
            return True
        except Exception as exc:  # noqa: BLE001
            if on_progress:
                on_progress(f"ERROR: {exc}")
            return False

    # ── inference ───────────────────────────────────────────────────────
    def generate(self, prompt: str, system: Optional[str] = None,
                 timeout: float = 120.0) -> str:
        """One-shot, non-streaming generation."""
        system = system or self.system_prompt
        payload = json.dumps({
            "model": self.model,
            "system": system,
            "prompt": prompt,
            "stream": False,
        }).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/api/generate", data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return res.get("response", "").strip()

    def chat_stream(self, prompt: str, system: Optional[str] = None,
                    few_shot: bool = True, control=None) -> Iterator[str]:
        """
        Yield response tokens from /api/chat as they arrive. Stops early if
        `control` is cancelled. Falls back to a single yield of a friendly
        error string if the node is unreachable.
        """
        system = system or self.system_prompt
        messages = [{"role": "system", "content": system}]
        if few_shot:
            messages.extend(FEW_SHOT)
        messages.append({"role": "user", "content": prompt})

        payload = json.dumps({
            "model": self.model,
            "stream": True,
            "options": {"temperature": 0.3, "num_predict": 400, "num_ctx": 1024},
            "messages": messages,
        }).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/api/chat", data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req) as resp:
                for raw in resp:
                    if control is not None and control.cancelled:
                        break
                    line = raw.decode("utf-8").strip()
                    if not line:
                        continue
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    token = d.get("message", {}).get("content", "")
                    if token:
                        yield token
                    if d.get("done"):
                        break
        except Exception as exc:  # noqa: BLE001
            yield f"\n[!] Cannot reach Ollama node at {self.base_url}: {exc}"
