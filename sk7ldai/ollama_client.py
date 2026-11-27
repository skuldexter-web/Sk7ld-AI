"""
ollama_client.py - thin stdlib-only wrapper around the local Ollama API.

No third-party HTTP dependency; uses urllib so the toolkit stays lean. Supports:
  * list_models()      - installed tags
  * pull_model()       - stream a model pull with progress callbacks
  * generate()         - one-shot completion
  * chat_stream()      - streaming chat reply
  * code_stream()      - streaming code file (Code Mode)
  * is_up()            - health check

Sk7ld-AI runs BASE (completion) models - qwen2.5-coder:*-base. A base model has
no chat template, so we don't use /api/chat. Instead we send a raw transcript to
/api/generate ("raw": true) that ends in "Scot:" and let the model complete the
next line, with:
  * stop sequences at the next turn marker ("\nUser:" ...), so it answers once;
  * repeat_penalty + a token cap;
  * a LoopGuard that cuts the stream if a sentence/line starts repeating
    (base models otherwise fall into "I am doing great. I am doing great...").
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
    "You are SK7LD-AI, also known as Scot — you answer to the name Scot. "
    "You are a Cyber Viking AI agent for offensive security work on "
    "Kali Linux (and, to a lesser extent, Windows). You assist red teamers, "
    "penetration testers, cybersecurity personnel and white-hat hackers who are "
    "operating on systems they are authorised to test.\n"
    "- ALWAYS reply in English only, no matter what language the user writes in.\n"
    "- Reply once, concisely. Do NOT repeat yourself, do NOT invent extra "
    "'You:'/'AI:' turns, and never continue the conversation on the user's "
    "behalf. Give one answer and stop.\n"
    "- Act like an operator's agent: understand the goal, suggest the next "
    "concrete step or command, and orchestrate the right tool from the arsenal "
    "when it helps. When you give a shell command, put it on its own line "
    "starting with 'COMMAND: '.\n"
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

# A couple of few-shot turns to keep the small model on-persona.
FEW_SHOT = [
    {"role": "user", "content": "hey"},
    {"role": "assistant", "content": "A warrior boards the longship! I am your Cyber Viking - here for anything cyber security. What's on your mind?"},
    {"role": "user", "content": "scan 192.168.1.1"},
    {"role": "assistant", "content": "On it.\nCOMMAND: nmap -sV --open -T4 192.168.1.1\nThat maps open ports and services. Want me to dig deeper once results land?"},
]

# ── base-model prompting ────────────────────────────────────────────────
USER_TAG = "User"
BOT_TAG = "Scot"

# Stop as soon as the model tries to write the next turn (or a file separator).
CHAT_STOPS = [
    f"\n{USER_TAG}:", "\nUser:", "\nUSER:", "\nYou:", "\nHuman:", "\nQuestion:",
    f"\n{BOT_TAG}:", "\nAssistant:", "\nAI:", "\nSK7LD-AI:", "\nSYSTEM:",
    "<|endoftext|>", "<|file_sep|>", "<|im_start|>", "<|im_end|>", "\n\n\n",
]
CODE_STOPS = ["\n```", "<|endoftext|>", "<|file_sep|>", "<|fim_prefix|>",
              "<|im_start|>", "\n# Task:", "\n// Task:"]

# (regex on the request, fence tag, display name, line-comment prefix)
_LANGS = [
    (r"\b(bash|shell script|\.sh\b|sh script)\b", "bash", "Bash", "#"),
    (r"\b(powershell|\.ps1\b|ps1)\b", "powershell", "PowerShell", "#"),
    (r"\b(typescript|\.ts\b)\b", "typescript", "TypeScript", "//"),
    (r"\b(javascript|node\.?js|\.js\b)\b", "javascript", "JavaScript", "//"),
    (r"\b(c\+\+|cpp)\b", "cpp", "C++", "//"),
    (r"\b(c#|csharp)\b", "csharp", "C#", "//"),
    (r"\b(golang|in go|go program)\b", "go", "Go", "//"),
    (r"\b(rust)\b", "rust", "Rust", "//"),
    (r"\b(java)\b", "java", "Java", "//"),
    (r"\b(php)\b", "php", "PHP", "//"),
    (r"\b(ruby)\b", "ruby", "Ruby", "#"),
    (r"\b(in c|c program|c code)\b", "c", "C", "//"),
    (r"\b(python|\.py\b)\b", "python", "Python", "#"),
]


def detect_lang(task: str):
    """Pick (fence_tag, display_name, comment_prefix) for a code request."""
    import re
    low = (task or "").lower()
    for pat, tag, name, cmt in _LANGS:
        if re.search(pat, low):
            return tag, name, cmt
    return "python", "Python", "#"


def build_chat_prompt(system: str, prompt: str, few_shot: bool = True) -> str:
    """Raw completion transcript for a base model, ending in 'Scot:'."""
    lines = [system.strip(), "", "The following is a conversation between "
             f"{USER_TAG} and {BOT_TAG}. {BOT_TAG} answers once, in English, then stops.", ""]
    if few_shot:
        for turn in FEW_SHOT:
            tag = USER_TAG if turn["role"] == "user" else BOT_TAG
            lines.append(f"{tag}: {turn['content']}")
    lines.append(f"{USER_TAG}: {prompt.strip()}")
    lines.append(f"{BOT_TAG}:")
    return "\n".join(lines)


def build_code_prompt(task: str):
    """
    Raw completion prompt that makes a base *coder* model write a code file.
    Returns (header, fence_tag). The header is the start of the file the model
    continues from, so it is also part of the saved code.
    """
    tag, name, c = detect_lang(task)
    header = (f"{c} {name} - generated by SK7LD-AI\n"
              f"{c} Task: {task.strip()}\n"
              f"{c} Complete, working, well-commented solution. No placeholders.\n\n")
    if tag == "python":
        header = "#!/usr/bin/env python3\n" + header
    elif tag == "bash":
        header = "#!/usr/bin/env bash\n" + header
    return header, tag


class LoopGuard:
    """
    Releases streamed text one segment at a time - a sentence in chat, a line in
    code - and drops the stream as soon as a segment repeats. Because text is
    only released once its segment is complete, a repeated sentence is caught
    BEFORE it reaches the screen (base models otherwise loop forever).
    """

    def __init__(self, code: bool = False):
        self.code = code
        self.min_len = 25 if code else 10      # ignore short lines like "}" / "Ok."
        self.max_repeats = 4 if code else 2    # code legitimately repeats a bit
        self.tripped = False
        self._pending = ""
        self._seen = {}

    def _is_repeat(self, seg: str) -> bool:
        key = " ".join(seg.strip().lower().split())
        if len(key) < self.min_len:
            return False
        self._seen[key] = self._seen.get(key, 0) + 1
        return self._seen[key] >= self.max_repeats

    def push(self, token: str):
        """Add a token; return the list of complete segments that are safe to show."""
        import re
        if self.tripped:
            return []
        self._pending += token
        pat = r"(\n)" if self.code else r"((?<=[.!?])\s+|\n)"
        parts = re.split(pat, self._pending)
        out = []
        i = 0
        while i + 1 < len(parts):
            seg, sep = parts[i], parts[i + 1]
            if self._is_repeat(seg):
                self.tripped = True
                self._pending = ""
                return out
            out.append(seg + sep)
            i += 2
        self._pending = parts[-1]
        return out

    def flush(self) -> str:
        """Whatever unfinished text is left at the end of the stream."""
        rest, self._pending = self._pending, ""
        if self.tripped or not rest or self._is_repeat(rest):
            return ""
        return rest


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

    # ── inference (base models: raw completion) ─────────────────────────
    def _options(self, code: bool = False) -> dict:
        return {
            "temperature": 0.2 if code else 0.35,
            "top_p": 0.9,
            "top_k": 40,
            "repeat_penalty": 1.1 if code else 1.25,
            "repeat_last_n": 256,
            "num_predict": 900 if code else 300,
            "num_ctx": 4096 if code else 2048,
            "stop": CODE_STOPS if code else CHAT_STOPS,
        }

    def _stream_generate(self, prompt_text: str, code: bool = False,
                         control=None) -> Iterator[str]:
        """Stream a raw /api/generate completion, guarded against loops."""
        payload = json.dumps({
            "model": self.model,
            "prompt": prompt_text,
            "raw": True,            # no chat template - base model completion
            "stream": True,
            "options": self._options(code),
        }).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/api/generate", data=payload,
            headers={"Content-Type": "application/json"},
        )
        guard = LoopGuard(code=code)
        started = False
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
                    if d.get("error"):
                        yield f"\n[!] Ollama: {d['error']}"
                        break
                    token = d.get("response", "")
                    if token:
                        for seg in guard.push(token):
                            if not started:        # trim the leading space/newline
                                seg = seg.lstrip()
                                if not seg:
                                    continue
                                started = True
                            yield seg
                        if guard.tripped:
                            break                  # model started looping - cut it
                    if d.get("done"):
                        break
            tail = guard.flush()
            if tail and not (control is not None and control.cancelled):
                yield tail.lstrip() if not started else tail
        except urllib.error.HTTPError as exc:
            hint = ""
            if exc.code == 404:
                hint = (f" - model '{self.model}' isn't installed. "
                        f"Use FORGE NEW MODEL or: ollama pull {self.model}")
            yield f"\n[!] Ollama error {exc.code}{hint}"
        except Exception as exc:  # noqa: BLE001
            yield f"\n[!] Cannot reach Ollama node at {self.base_url}: {exc}"

    def chat_stream(self, prompt: str, system: Optional[str] = None,
                    few_shot: bool = True, control=None) -> Iterator[str]:
        """
        Yield the assistant's reply token by token. Stops early if `control` is
        cancelled, at the next turn marker, or when the LoopGuard trips.
        (Passing system=CODE_SYSTEM_PROMPT routes to code_stream for
        backward compatibility.)
        """
        if system == CODE_SYSTEM_PROMPT:
            yield from self.code_stream(prompt, control=control)
            return
        text = build_chat_prompt(system or self.system_prompt, prompt, few_shot)
        yield from self._stream_generate(text, code=False, control=control)

    def code_stream(self, task: str, control=None) -> Iterator[str]:
        """
        Yield one fenced code block for `task`, written by the base coder model.
        Output looks like ```lang\n<header><code>\n``` so extract_code() and
        SAVE CODE work unchanged.
        """
        header, tag = build_code_prompt(task)
        yield f"```{tag}\n{header}"
        for tok in self._stream_generate(header, code=True, control=control):
            yield tok
        yield "\n```"

    def generate(self, prompt: str, system: Optional[str] = None,
                 timeout: float = 120.0) -> str:
        """One-shot (non-streaming) chat reply."""
        text = build_chat_prompt(system or self.system_prompt, prompt, True)
        payload = json.dumps({
            "model": self.model, "prompt": text, "raw": True, "stream": False,
            "options": self._options(False),
        }).encode("utf-8")
        req = urllib.request.Request(
            self.base_url + "/api/generate", data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            return res.get("response", "").strip()
