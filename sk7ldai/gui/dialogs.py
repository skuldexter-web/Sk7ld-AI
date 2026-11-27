"""
dialogs.py - modal CustomTkinter dialogs for Sk7ld-AI.

  * ConfirmDialog      - generic Yes/No, used as the install-confirmation gate.
  * ToolChoiceDialog   - lists the candidate tools for a detected intent, each
                         with its description + install status, lets the operator
                         confirm/edit the target and pick one (or fall back to
                         plain AI chat).
  * InstallModelDialog - the "Forge New Model" base-model installer wizard.
  * PersonaDialog      - edit Sk7ld-AI's persona (system prompt).

All dialogs are modal and block via wait_window; they are always created on the
Tk main thread.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

import customtkinter as ctk

from ..arsenal import ToolAction, Intent
from ..installer import is_available
from ..ollama_client import DEFAULT_SYSTEM_PROMPT

# Model install options - BASE models only (qwen2.5-coder base family).
INSTALL_OPTIONS = {
    "default": ("qwen2.5-coder:1.5b-base", "Light (default), ~1 GB"),
    "1": ("qwen2.5-coder:3b-base", "Medium, ~2 GB"),
    "2": ("qwen2.5-coder:14b-base", "Strong, ~9 GB VRAM"),
}


class ConfirmDialog(ctk.CTkToplevel):
    """Yes/No confirmation. `.show()` returns True (yes) or False (no/closed)."""

    def __init__(self, master, title: str, body: str, theme: dict):
        super().__init__(master)
        self.result = False
        self.title(title)
        self.geometry("520x380")
        self.configure(fg_color=theme["sidebar"])
        self.transient(master)
        self.after(150, self.grab_set)

        ctk.CTkLabel(self, text=title, text_color=theme["title"],
                     font=ctk.CTkFont(size=15, weight="bold")).pack(padx=20, pady=(18, 6))

        box = ctk.CTkTextbox(self, fg_color=theme["box"], text_color=theme["text"],
                             border_color=theme["border"], border_width=1,
                             font=ctk.CTkFont(family="Consolas", size=12), wrap="word")
        box.pack(padx=20, pady=6, fill="both", expand=True)
        box.insert("end", body)
        box.configure(state="disabled")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=20, pady=(6, 16), fill="x")
        ctk.CTkButton(row, text="Yes, proceed", fg_color=theme["accent"],
                      text_color=theme["accent_text"], hover_color=theme["hover"],
                      command=self._yes).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ctk.CTkButton(row, text="No", fg_color=theme["border"],
                      hover_color=theme["hover"], text_color=theme["title"],
                      command=self._no).pack(side="left", expand=True, fill="x", padx=(6, 0))
        self.protocol("WM_DELETE_WINDOW", self._no)

    def _yes(self):
        self.result = True
        self.destroy()

    def _no(self):
        self.result = False
        self.destroy()

    def show(self) -> bool:
        self.master.wait_window(self)
        return self.result


class ToolChoiceDialog(ctk.CTkToplevel):
    """
    Present the candidate tools for a detected intent.

    `.show()` returns one of:
        ("tool", ToolAction, target_str)  - run this tool
        ("chat", None, None)              - ignore tools, just chat
        None                              - cancelled
    """

    def __init__(self, master, intent: Intent, target: Optional[str], theme: dict,
                 actions=None):
        super().__init__(master)
        self.selected: Optional[Tuple[str, Optional[ToolAction], Optional[str]]] = None
        self._intent = intent
        self._theme = theme

        self.title("Choose a weapon")
        self.geometry("620x560")
        self.configure(fg_color=theme["sidebar"])
        self.transient(master)
        self.after(150, self.grab_set)

        ctk.CTkLabel(self, text=f"Intent detected: {intent.label}",
                     text_color=theme["title"],
                     font=ctk.CTkFont(size=16, weight="bold")).pack(padx=20, pady=(18, 2))
        ctk.CTkLabel(self, text="Pick the tool to deploy. Missing tools will ask "
                                "to install before running.",
                     text_color=theme["sub_col"],
                     font=ctk.CTkFont(size=11)).pack(padx=20, pady=(0, 10))

        # Target entry (operator can confirm / edit / supply it).
        if intent.target_kind != "none":
            trow = ctk.CTkFrame(self, fg_color="transparent")
            trow.pack(padx=20, pady=(0, 10), fill="x")
            ctk.CTkLabel(trow, text=f"Target ({intent.target_kind}):",
                         text_color=theme["title"],
                         font=ctk.CTkFont(size=12)).pack(side="left", padx=(0, 8))
            self.target_entry = ctk.CTkEntry(
                trow, fg_color=theme["entry_bg"], text_color=theme["entry_text"],
                border_color=theme["border"])
            self.target_entry.pack(side="left", fill="x", expand=True)
            if target:
                self.target_entry.insert(0, target)
        else:
            self.target_entry = None

        scroll = ctk.CTkScrollableFrame(self, fg_color=theme["box"],
                                        border_color=theme["border"], border_width=1)
        scroll.pack(padx=20, pady=6, fill="both", expand=True)

        for action in (actions if actions is not None else intent.actions):
            self._add_option(scroll, action)

        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.pack(padx=20, pady=(6, 16), fill="x")
        ctk.CTkButton(bottom, text="Just chat with AI instead",
                      fg_color=theme["border"], hover_color=theme["hover"],
                      text_color=theme["title"], command=self._chat).pack(
            side="left", expand=True, fill="x", padx=(0, 6))
        ctk.CTkButton(bottom, text="Cancel", fg_color=theme["box"],
                      hover_color=theme["hover"], text_color=theme["text"],
                      command=self._cancel).pack(side="left", expand=True, fill="x", padx=(6, 0))
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _add_option(self, parent, action: ToolAction):
        theme = self._theme
        avail = is_available(action.tool)
        tag = "[installed]" if avail else "[missing]"
        tag_col = theme["title"] if avail else theme["sub_col"]
        mode_tag = "live" if action.mode == "interactive" else "scan"
        root_tag = " · root" if action.needs_root else ""

        card = ctk.CTkFrame(parent, fg_color=theme["entry_bg"],
                            border_color=theme["border"], border_width=1)
        card.pack(padx=6, pady=5, fill="x")

        header = ctk.CTkFrame(card, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(8, 0))
        ctk.CTkLabel(header, text=action.tool, text_color=theme["title"],
                     font=ctk.CTkFont(size=14, weight="bold")).pack(side="left")
        ctk.CTkLabel(header, text=f"  {tag}", text_color=tag_col,
                     font=ctk.CTkFont(size=11)).pack(side="left")
        ctk.CTkLabel(header, text=f"  ({mode_tag}{root_tag})", text_color=theme["sub_col"],
                     font=ctk.CTkFont(size=11)).pack(side="left")

        ctk.CTkLabel(card, text=action.desc, text_color=theme["text"],
                     font=ctk.CTkFont(size=12), wraplength=520, justify="left").pack(
            anchor="w", padx=10, pady=(2, 6))

        ctk.CTkButton(card, text="Deploy this", fg_color=theme["accent"],
                      text_color=theme["accent_text"], hover_color=theme["hover"],
                      height=28,
                      command=lambda a=action: self._pick(a)).pack(
            anchor="e", padx=10, pady=(0, 8))

    def _current_target(self) -> Optional[str]:
        if self.target_entry is None:
            return None
        val = self.target_entry.get().strip()
        return val or None

    def _pick(self, action: ToolAction):
        self.selected = ("tool", action, self._current_target())
        self.destroy()

    def _chat(self):
        self.selected = ("chat", None, None)
        self.destroy()

    def _cancel(self):
        self.selected = None
        self.destroy()

    def show(self):
        self.master.wait_window(self)
        return self.selected


class InstallModelDialog(ctk.CTkToplevel):
    """Two-step base-model installer. `.show()` returns a model tag or None."""

    def __init__(self, master, theme: dict):
        super().__init__(master)
        self.chosen: Optional[str] = None
        self.title("Forge a Model")
        self.geometry("470x340")
        self.configure(fg_color=theme["sidebar"])
        self.transient(master)
        self.after(150, self.grab_set)
        self._theme = theme

        self.label = ctk.CTkLabel(self, text="", text_color=theme["text"],
                                  wraplength=420, font=ctk.CTkFont(size=13),
                                  justify="left")
        self.label.pack(padx=20, pady=(20, 10))
        self.holder = ctk.CTkFrame(self, fg_color="transparent")
        self.holder.pack(padx=20, pady=10, fill="x")
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self._step_default()

    def _clear(self):
        for w in self.holder.winfo_children():
            w.destroy()

    def _choose(self, tag: str):
        self.chosen = tag
        self.destroy()

    def _cancel(self):
        self.chosen = None
        self.destroy()

    def _step_default(self):
        theme = self._theme
        self._clear()
        tag, desc = INSTALL_OPTIONS["default"]
        self.label.configure(text=f"Install the default base model?\n{tag} - {desc}\n\n[Y/n]")
        ctk.CTkButton(self.holder, text="Y (install default)", fg_color=theme["accent"],
                      text_color=theme["accent_text"], hover_color=theme["hover"],
                      command=lambda: self._choose(tag)).pack(pady=5, fill="x")
        ctk.CTkButton(self.holder, text="n (pick a heavier base model)",
                      fg_color=theme["border"], hover_color=theme["hover"],
                      text_color=theme["title"], command=self._step_pick).pack(pady=5, fill="x")

    def _step_pick(self):
        theme = self._theme
        self._clear()
        self.label.configure(text="Choose a heavier base model:")
        for key in ("1", "2"):
            tag, desc = INSTALL_OPTIONS[key]
            ctk.CTkButton(self.holder, text=f"{key}) {tag} - {desc}",
                          fg_color=theme["border"], hover_color=theme["hover"],
                          text_color=theme["title"],
                          command=lambda t=tag: self._choose(t)).pack(pady=5, fill="x")
        ctk.CTkButton(self.holder, text="Cancel", fg_color=theme["box"],
                      hover_color=theme["hover"], text_color=theme["text"],
                      command=self._cancel).pack(pady=5, fill="x")

    def show(self) -> Optional[str]:
        self.master.wait_window(self)
        return self.chosen


class PersonaDialog(ctk.CTkToplevel):
    """
    Edit the persona (system prompt) that drives Sk7ld-AI's chat.

    `.show()` returns:
        ("save", text)  - apply + persist this persona
        ("reset", None) - restore the default persona
        None            - cancelled
    """

    def __init__(self, master, current: str, theme: dict):
        super().__init__(master)
        self.result: Optional[Tuple[str, Optional[str]]] = None
        self.title("Edit Persona")
        self.geometry("620x460")
        self.configure(fg_color=theme["sidebar"])
        self.transient(master)
        self.after(150, self.grab_set)
        self._theme = theme

        ctk.CTkLabel(self, text="SK7LD-AI PERSONA", text_color=theme["title"],
                     font=ctk.CTkFont(size=15, weight="bold")).pack(padx=20, pady=(18, 2))
        ctk.CTkLabel(self, text="This is the system prompt the model is given on every "
                                "chat. Describe who Sk7ld-AI is and how it should behave.",
                     text_color=theme["sub_col"], font=ctk.CTkFont(size=11),
                     wraplength=560, justify="left").pack(padx=20, pady=(0, 10))

        self.box = ctk.CTkTextbox(self, fg_color=theme["box"], text_color=theme["entry_text"],
                                  border_color=theme["border"], border_width=1,
                                  wrap="word", corner_radius=8)
        self.box.pack(padx=20, pady=6, fill="both", expand=True)
        self.box.insert("1.0", current)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=20, pady=(8, 16), fill="x")
        ctk.CTkButton(row, text="Save persona", fg_color=theme["accent"],
                      text_color=theme["accent_text"], hover_color=theme["hover"],
                      command=self._save).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ctk.CTkButton(row, text="Reset to default", fg_color=theme["glass2"],
                      hover_color=theme["hover"], text_color=theme["title"],
                      command=self._reset).pack(side="left", expand=True, fill="x", padx=6)
        ctk.CTkButton(row, text="Cancel", fg_color=theme["box"],
                      hover_color=theme["hover"], text_color=theme["text"],
                      command=self._cancel).pack(side="left", expand=True, fill="x", padx=(6, 0))
        self.protocol("WM_DELETE_WINDOW", self._cancel)

    def _save(self):
        text = self.box.get("1.0", "end").strip()
        self.result = ("save", text or DEFAULT_SYSTEM_PROMPT)
        self.destroy()

    def _reset(self):
        self.box.delete("1.0", "end")
        self.box.insert("1.0", DEFAULT_SYSTEM_PROMPT)
        self.result = ("reset", None)
        self.destroy()

    def _cancel(self):
        self.result = None
        self.destroy()

    def show(self):
        self.master.wait_window(self)
        return self.result


class DisclaimerDialog(ctk.CTkToplevel):
    """
    One-time authorised-use disclaimer shown on first launch.
    `.show()` returns True (agreed) or False (declined / closed).
    """

    TEXT = (
        "SK7LD-AI is an offensive-security AI agent built for red teamers, "
        "penetration testers, cybersecurity personnel and white-hat hackers.\n\n"
        "By continuing you confirm that:\n\n"
        "  •  You will ONLY use SK7LD-AI, and any tool it launches, against "
        "systems you OWN or have EXPLICIT WRITTEN AUTHORISATION to test.\n\n"
        "  •  You will stay within the agreed scope and rules of engagement, "
        "and keep proper records of your activity.\n\n"
        "  •  You are solely responsible for complying with all applicable "
        "laws and regulations in your jurisdiction.\n\n"
        "Unauthorised access to computer systems is illegal. The authors "
        "accept no liability for misuse.\n\n"
        "Use responsibly. Hack the planet — ethically."
    )

    def __init__(self, master, theme: dict, version: str = ""):
        super().__init__(master)
        self.result = False
        self.title("SK7LD-AI — Authorised Use Only")
        self.geometry("620x520")
        self.configure(fg_color=theme["sidebar"])
        self.transient(master)
        self.after(150, self.grab_set)

        ctk.CTkLabel(self, text="⚠  AUTHORISED USE ONLY  ⚠", text_color=theme["title"],
                     font=ctk.CTkFont(size=17, weight="bold")).pack(padx=20, pady=(20, 2))
        if version:
            ctk.CTkLabel(self, text=f"SK7LD-AI v{version}", text_color=theme["sub_col"],
                         font=ctk.CTkFont(size=11)).pack(padx=20, pady=(0, 10))

        box = ctk.CTkTextbox(self, fg_color=theme["box"], text_color=theme["text"],
                             border_color=theme["border"], border_width=1,
                             wrap="word", corner_radius=8)
        box.pack(padx=20, pady=6, fill="both", expand=True)
        box.insert("end", self.TEXT)
        box.configure(state="disabled")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(padx=20, pady=(8, 18), fill="x")
        ctk.CTkButton(row, text="I AGREE — ENTER", fg_color=theme["accent"],
                      text_color=theme["accent_text"], hover_color=theme["hover"],
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=self._agree).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ctk.CTkButton(row, text="Decline & Exit", fg_color="#8b1a1a",
                      text_color="#ffffff", hover_color="#b22222",
                      command=self._decline).pack(side="left", expand=True, fill="x", padx=(6, 0))
        self.protocol("WM_DELETE_WINDOW", self._decline)

    def _agree(self):
        self.result = True
        self.destroy()

    def _decline(self):
        self.result = False
        self.destroy()

    def show(self) -> bool:
        self.master.wait_window(self)
        return self.result
