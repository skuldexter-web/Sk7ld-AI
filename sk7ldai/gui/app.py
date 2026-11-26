"""
app.py - Sk7ld-AI main window (cozy frosted-glass edition).

Floating glass cards over a blurred, theme-tinted bokeh backdrop, with real
window transparency so the desktop shows through subtly:

  * LEFT   sidebar card - identity, theme (sk7ld / v1ru5 / baphomet), model, actions
  * CENTER console card - the orchestration chat (intent -> tool -> run + STOP)
  * RIGHT  HUD cards    - weather forecast + a honeycomb of hexagon ring-gauges
                          (CPU / GPU / RAM / NET / DISK around a live clock)

Note: Tk can't blur the live desktop behind individual panels, so the "frosted"
look is produced by the in-window bokeh backdrop plus the glass card palette;
window alpha adds the genuine partial see-through to the real desktop.
"""

from __future__ import annotations

import os
import sys
import threading
import time
import tkinter.font as tkfont
import tkinter.filedialog as filedialog
from datetime import datetime
from typing import Optional

import customtkinter as ctk

from .. import DEFAULT_MODEL, OLLAMA_BASE_URL, __app_name__, __version__
from ..themes import THEMES, DEFAULT_THEME, SOCIAL_LINKS, get_theme
from ..ollama_client import OllamaClient
from .. import orchestrator
from ..orchestrator import analysis_prompt
from ..control import JobControl
from ..feeds import SystemStats, Weather, human_rate, human_bytes
from ..ollama_client import DEFAULT_SYSTEM_PROMPT, CODE_SYSTEM_PROMPT, extract_code
from .. import config
from .. import voice as voicemod
from .. import imagegen as imgmod
from .. import vision as visionmod
from .. import devices as devmod
from .. import anon as anonmod
from .. import netinfo
from .. import updater
from ..osenv import is_windows
from .dialogs import (ConfirmDialog, ToolChoiceDialog, InstallModelDialog,
                      PersonaDialog, DisclaimerDialog, INSTALL_OPTIONS)
from .visuals import Honeycomb, make_ambient, VoiceOrb
import re as _re

try:
    from PIL import Image  # noqa: F401
    _HAS_PIL = True
except Exception:  # noqa: BLE001
    _HAS_PIL = False

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("dark-blue")

_MONO_PREF = ["JetBrains Mono", "Fira Code", "Hack", "Source Code Pro",
              "DejaVu Sans Mono", "Consolas", "Menlo", "Courier New"]
STATS_INTERVAL_MS = 1000
WEATHER_INTERVAL_S = 900
WINDOW_ALPHA = 0.95          # subtle see-through (needs a desktop compositor)
CARD_RADIUS = 16


def _net_compact(bps: float) -> str:
    if bps < 1000:
        return f"{bps:.0f} B"
    if bps < 1_000_000:
        return f"{bps/1000:.0f} k"
    return f"{bps/1_000_000:.1f} M"


class Sk7ldAIApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.current_theme_name = DEFAULT_THEME
        theme = get_theme(self.current_theme_name)

        self.client = OllamaClient(OLLAMA_BASE_URL, DEFAULT_MODEL)
        self.client.system_prompt = config.get_system_prompt()   # load saved persona
        self.is_busy = False
        self.code_mode = False
        self.voice_mode = False
        self.anon_on = False
        self._last_code = None            # (code_text, extension)
        self.locked_target: Optional[str] = None
        self.active_control: Optional[JobControl] = None
        self._alive = True
        self._themed = []
        self.mono = self._pick_mono()

        # voice + image + vision engines (lazy backends; safe when not installed)
        self.voice = voicemod.VoiceEngine(on_status=self._voice_status)
        self.imggen = imgmod.ImageGen(on_status=lambda m: self.after(0, self._append_line, m))
        self.vision = visionmod.VisionEngine(
            on_labels=self._on_vision_labels,
            on_status=lambda m: self.after(0, self._append_line, m))
        self.vision_on = False
        self._public_ip = None
        self._blink = True

        self.stats = SystemStats()
        self.weather = Weather()
        self._wx_temp: Optional[str] = None
        self._bg_img = None
        self._bg_size = (0, 0)
        self._cfg_job = None

        self.title(f"{__app_name__} // Digital Longship v{__version__}")
        self.geometry("1380x840")
        self.minsize(1180, 720)
        self.configure(fg_color=theme["bg"])
        try:
            self.attributes("-alpha", WINDOW_ALPHA)
        except Exception:
            pass

        # ambient background (behind everything)
        self._bg_label = ctk.CTkLabel(self, text="")
        self._bg_label.place(x=0, y=0, relwidth=1, relheight=1)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_center()
        self._build_hud()
        self._build_orb()

        self._apply_theme()
        self._render_ambient(force=True)
        self.fetch_models()
        self.after(300, self._check_disclaimer)
        self.after(800, self.check_first_run)
        self._greet()

        self.after(200, self._tick_system)
        threading.Thread(target=self._weather_loop, daemon=True).start()
        self.after(400, self._blink_dot)
        self.after(600, self._refresh_ip)
        self.bind("<Configure>", self._on_configure)
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ════════════════════════════════════════════════════════════════════
    #  HELPERS
    # ════════════════════════════════════════════════════════════════════
    def _pick_mono(self) -> Optional[str]:
        try:
            fams = set(tkfont.families())
        except Exception:
            return None
        for f in _MONO_PREF:
            if f in fams:
                return f
        return None

    def font(self, size: int, weight: str = "normal", mono: bool = False,
             slant: str = "roman"):
        kw = {"size": size, "weight": weight, "slant": slant}
        if mono and self.mono:
            kw["family"] = self.mono
        return ctk.CTkFont(**kw)

    def _reg(self, widget, **propmap):
        self._themed.append((widget, propmap))
        return widget

    def _apply_theme(self):
        th = get_theme(self.current_theme_name)
        for widget, pm in self._themed:
            try:
                widget.configure(**{prop: th[key] for prop, key in pm.items()})
            except Exception:
                pass

    def _card(self, parent, **grid):
        c = ctk.CTkFrame(parent, corner_radius=CARD_RADIUS, border_width=1)
        self._reg(c, fg_color="glass", border_color="border")
        if grid:
            c.grid(**grid)
        return c

    def _section_header(self, parent, text: str):
        wrap = ctk.CTkFrame(parent, fg_color="transparent")
        lbl = ctk.CTkLabel(wrap, text=text.upper(), anchor="w",
                           font=self.font(12, "bold", mono=True))
        lbl.pack(fill="x", padx=2)
        self._reg(lbl, text_color="title")
        bar = ctk.CTkFrame(wrap, height=2, corner_radius=2)
        bar.pack(fill="x", padx=2, pady=(3, 0))
        self._reg(bar, fg_color="accent")
        return wrap

    # ════════════════════════════════════════════════════════════════════
    #  AMBIENT BACKGROUND
    # ════════════════════════════════════════════════════════════════════
    def _render_ambient(self, force: bool = False):
        if not _HAS_PIL:
            return
        w = max(self.winfo_width(), 1); h = max(self.winfo_height(), 1)
        if w < 50 or h < 50:
            w, h = 1380, 840
        if not force and abs(w - self._bg_size[0]) < 12 and abs(h - self._bg_size[1]) < 12:
            return
        img = make_ambient(w, h, get_theme(self.current_theme_name))
        if img is None:
            return
        self._bg_size = (w, h)
        self._bg_img = ctk.CTkImage(light_image=img, dark_image=img, size=(w, h))
        self._bg_label.configure(image=self._bg_img)
        self._bg_label.lower()

    def _on_configure(self, event):
        if event.widget is not self:
            return
        if self._cfg_job is not None:
            self.after_cancel(self._cfg_job)
        self._cfg_job = self.after(180, lambda: self._render_ambient())

    # ════════════════════════════════════════════════════════════════════
    #  SIDEBAR
    # ════════════════════════════════════════════════════════════════════
    def _build_sidebar(self):
        th = get_theme(self.current_theme_name)
        self.sidebar = self._card(self, row=0, column=0, sticky="nsew",
                                  padx=(14, 7), pady=14)
        self.sidebar.configure(width=292)
        self.sidebar.grid_propagate(False)
        # scrollable inner frame so the growing control set always fits
        self.side = ctk.CTkScrollableFrame(self.sidebar, fg_color="transparent")
        self.side.pack(fill="both", expand=True, padx=2, pady=2)
        P = self.side

        self.title_label = ctk.CTkLabel(P, text="", font=self.font(19, "bold", mono=True))
        self.title_label.pack(padx=14, pady=(12, 2))
        self._reg(self.title_label, text_color="title")
        self.subtitle_label = ctk.CTkLabel(P, text=th["subtitle"],
                                           font=self.font(11, slant="italic"))
        self.subtitle_label.pack(padx=14, pady=(0, 10))
        self._reg(self.subtitle_label, text_color="sub_col")

        self.github_label = ctk.CTkLabel(P, text=SOCIAL_LINKS["github"],
                                         font=self.font(10, mono=True), anchor="w")
        self.github_label.pack(padx=14, pady=(2, 0), anchor="w")
        self._reg(self.github_label, text_color="title")
        self.insta_label = ctk.CTkLabel(P, text=SOCIAL_LINKS["instagram"],
                                        font=self.font(10, mono=True), anchor="w")
        self.insta_label.pack(padx=14, pady=(0, 2), anchor="w")
        self._reg(self.insta_label, text_color="sub_col")
        self.insta2_label = ctk.CTkLabel(P, text=SOCIAL_LINKS["instagram_v1ru5"],
                                         font=self.font(10, mono=True), anchor="w")
        self._reg(self.insta2_label, text_color="sub_col")
        if th["show_v1ru5_ig"]:
            self.insta2_label.pack(padx=14, pady=(0, 8), anchor="w")

        # THEME
        self.theme_label = self._slabel(P, "THEME")
        self.theme_dropdown = ctk.CTkOptionMenu(
            P, values=list(THEMES.keys()), command=self.change_theme,
            font=self.font(12, mono=True), corner_radius=10)
        self.theme_dropdown.set(self.current_theme_name)
        self.theme_dropdown.pack(padx=14, pady=(0, 8), fill="x")
        self._reg(self.theme_dropdown, fg_color="glass2", button_color="accent",
                  button_hover_color="hover", text_color="entry_text")

        # MODEL (chat / LLM)
        self.model_label = self._slabel(P, "CHAT MODEL")
        self.model_dropdown = ctk.CTkOptionMenu(
            P, values=[DEFAULT_MODEL], command=self._on_model_change,
            font=self.font(12, mono=True), corner_radius=10)
        self.model_dropdown.pack(padx=14, pady=(0, 6), fill="x")
        self._reg(self.model_dropdown, fg_color="glass2", button_color="accent",
                  button_hover_color="hover", text_color="entry_text")
        self.refresh_btn = self._sbtn(P, "PING MODELS", self.fetch_models)
        self.install_btn = self._sbtn(P, "FORGE NEW MODEL", self.open_install_dialog)
        self.persona_btn = self._sbtn(P, "EDIT PERSONA", self.open_persona_dialog, pad=(0, 8))

        # CODE
        crow = ctk.CTkFrame(P, fg_color="transparent"); crow.pack(padx=14, pady=(2, 2), fill="x")
        self.code_switch = ctk.CTkSwitch(crow, text="CODE MODE",
                                         font=self.font(12, "bold", mono=True),
                                         command=self._toggle_code_mode)
        self.code_switch.pack(side="left")
        self._reg(self.code_switch, text_color="title", progress_color="accent",
                  button_color="entry_text", fg_color="glass2")
        self.save_code_btn = self._sbtn(P, "SAVE CODE", self._save_code, state="disabled", pad=(2, 8))

        # VOICE
        self._slabel(P, "VOICE")
        vrow = ctk.CTkFrame(P, fg_color="transparent"); vrow.pack(padx=14, pady=(0, 2), fill="x")
        self.voice_switch = ctk.CTkSwitch(vrow, text="VOICE MODE",
                                          font=self.font(12, "bold", mono=True),
                                          command=self._toggle_voice)
        self.voice_switch.pack(side="left")
        self._reg(self.voice_switch, text_color="title", progress_color="accent",
                  button_color="entry_text", fg_color="glass2")
        self.stt_dropdown = ctk.CTkOptionMenu(
            P, values=voicemod.STT_MODELS, command=self._on_stt_model,
            font=self.font(11, mono=True), corner_radius=10)
        self.stt_dropdown.set(voicemod.DEFAULT_STT)
        self.stt_dropdown.pack(padx=14, pady=(4, 4), fill="x")
        self._reg(self.stt_dropdown, fg_color="glass2", button_color="accent",
                  button_hover_color="hover", text_color="entry_text")
        self.tts_dropdown = ctk.CTkOptionMenu(
            P, values=voicemod.list_tts_voices(), command=self._on_tts_voice,
            font=self.font(11, mono=True), corner_radius=10)
        self.tts_dropdown.pack(padx=14, pady=(0, 2), fill="x")
        self._reg(self.tts_dropdown, fg_color="glass2", button_color="accent",
                  button_hover_color="hover", text_color="entry_text")
        # microphone + speaker pickers (detected local audio devices)
        self.mic_dropdown = ctk.CTkOptionMenu(
            P, values=self._audio_labels("inputs"), command=self._on_mic,
            font=self.font(10, mono=True), corner_radius=10)
        self.mic_dropdown.pack(padx=14, pady=(2, 2), fill="x")
        self._reg(self.mic_dropdown, fg_color="glass2", button_color="accent",
                  button_hover_color="hover", text_color="entry_text")
        self.spk_dropdown = ctk.CTkOptionMenu(
            P, values=self._audio_labels("outputs"), command=self._on_speaker,
            font=self.font(10, mono=True), corner_radius=10)
        self.spk_dropdown.pack(padx=14, pady=(0, 2), fill="x")
        self._reg(self.spk_dropdown, fg_color="glass2", button_color="accent",
                  button_hover_color="hover", text_color="entry_text")
        self.voice_hint = ctk.CTkLabel(P, text="", anchor="w", font=self.font(9, mono=True))
        self.voice_hint.pack(padx=14, pady=(0, 8), anchor="w", fill="x")
        self._reg(self.voice_hint, text_color="dim")
        self._refresh_voice_hint()

        # VISION (object detection)
        self._slabel(P, "OBJECT DETECTION")
        drow = ctk.CTkFrame(P, fg_color="transparent"); drow.pack(padx=14, pady=(0, 2), fill="x")
        self.vision_switch = ctk.CTkSwitch(drow, text="DETECT MODE",
                                           font=self.font(12, "bold", mono=True),
                                           command=self._toggle_vision)
        self.vision_switch.pack(side="left")
        self._reg(self.vision_switch, text_color="title", progress_color="accent",
                  button_color="entry_text", fg_color="glass2")
        self.vmodel_dropdown = ctk.CTkOptionMenu(
            P, values=visionmod.model_labels(), command=self._on_vision_model,
            font=self.font(11, mono=True), corner_radius=10)
        self.vmodel_dropdown.pack(padx=14, pady=(4, 2), fill="x")
        self._reg(self.vmodel_dropdown, fg_color="glass2", button_color="accent",
                  button_hover_color="hover", text_color="entry_text")
        self.cam_dropdown = ctk.CTkOptionMenu(
            P, values=["camera 0 (default)", "camera 1", "camera 2", "camera 3"],
            command=self._on_camera, font=self.font(10, mono=True), corner_radius=10)
        self.cam_dropdown.pack(padx=14, pady=(0, 2), fill="x")
        self._reg(self.cam_dropdown, fg_color="glass2", button_color="accent",
                  button_hover_color="hover", text_color="entry_text")
        self.vision_hint = ctk.CTkLabel(P, text="", anchor="w", font=self.font(9, mono=True))
        self.vision_hint.pack(padx=14, pady=(0, 8), anchor="w", fill="x")
        self._reg(self.vision_hint, text_color="dim")
        self._refresh_vision_hint()

        # DEVICES (hardware discovery)
        self._slabel(P, "DEVICES")
        self.scan_btn = self._sbtn(P, "SCAN HARDWARE", self._scan_devices, pad=(0, 8))

        # IMAGE
        self._slabel(P, "IMAGE (txt2img)")
        self.img_dropdown = ctk.CTkOptionMenu(
            P, values=imgmod.model_labels(), command=self._on_image_model,
            font=self.font(11, mono=True), corner_radius=10)
        self.img_dropdown.pack(padx=14, pady=(0, 4), fill="x")
        self._reg(self.img_dropdown, fg_color="glass2", button_color="accent",
                  button_hover_color="hover", text_color="entry_text")
        self.img_btn = self._sbtn(P, "GENERATE IMAGE", self._gen_image, pad=(0, 2))
        self.img_hint = ctk.CTkLabel(P, text="", anchor="w", font=self.font(9, mono=True))
        self.img_hint.pack(padx=14, pady=(0, 8), anchor="w", fill="x")
        self._reg(self.img_hint, text_color="dim")
        self._refresh_img_hint()

        # ANONYMOUS
        self._slabel(P, "ANONYMOUS")
        arow = ctk.CTkFrame(P, fg_color="transparent"); arow.pack(padx=14, pady=(0, 2), fill="x")
        self.anon_switch = ctk.CTkSwitch(arow, text="ANON (Tor)",
                                         font=self.font(12, "bold", mono=True),
                                         command=self._toggle_anon)
        self.anon_switch.pack(side="left")
        self._reg(self.anon_switch, text_color="title", progress_color="good",
                  button_color="entry_text", fg_color="glass2")
        self.anon_hint = ctk.CTkLabel(P, text="", anchor="w", font=self.font(9, mono=True))
        self.anon_hint.pack(padx=14, pady=(0, 8), anchor="w", fill="x")
        self._reg(self.anon_hint, text_color="dim")
        if is_windows():
            self.anon_hint.configure(text="needs Tor on 127.0.0.1:9050")
        elif anonmod.tor_available():
            self.anon_hint.configure(text="Tor ready")
        else:
            self.anon_hint.configure(text="install: sudo apt install tor")

        self.hint_label = ctk.CTkLabel(
            P, justify="left", anchor="w", font=self.font(10, mono=True),
            text="> try:\n  scan 10.0.0.5\n  subdomains of site.com\n"
                 "  what do you see?\n  make a wolf image\n"
                 "  system update\n  update yourself")
        self.hint_label.pack(padx=14, pady=(6, 10), anchor="w")
        self._reg(self.hint_label, text_color="dim")

    # small sidebar helpers
    def _slabel(self, parent, text):
        lbl = ctk.CTkLabel(parent, text=text, anchor="w",
                           font=self.font(11, "bold", mono=True))
        lbl.pack(padx=14, pady=(10, 2), anchor="w")
        self._reg(lbl, text_color="title")
        return lbl

    def _sbtn(self, parent, text, cmd, state="normal", pad=(0, 6)):
        b = ctk.CTkButton(parent, text=text, command=cmd, corner_radius=10, state=state,
                          font=self.font(12, "bold", mono=True))
        b.pack(padx=14, pady=pad, fill="x")
        self._reg(b, fg_color="glass2", hover_color="hover", text_color="title")
        return b

    # ════════════════════════════════════════════════════════════════════
    #  CENTER (console card + input row)
    # ════════════════════════════════════════════════════════════════════
    def _build_center(self):
        col = ctk.CTkFrame(self, fg_color="transparent")
        col.grid(row=0, column=1, sticky="nsew", padx=7, pady=14)
        col.grid_rowconfigure(0, weight=1)
        col.grid_columnconfigure(0, weight=1)

        card = self._card(col, row=0, column=0, sticky="nsew")
        self.console_card = card
        card.grid_rowconfigure(1, weight=1)
        card.grid_columnconfigure(0, weight=1)
        self._section_header(card, "Console").grid(row=0, column=0, sticky="ew",
                                                    padx=16, pady=(14, 8))
        self.chat_box = ctk.CTkTextbox(card, font=self.font(13, mono=True),
                                       border_width=0, wrap="word", corner_radius=10,
                                       fg_color="transparent")
        self.chat_box.grid(row=1, column=0, sticky="nsew", padx=14, pady=(0, 12))
        self.chat_box.configure(state="disabled")
        self._reg(self.chat_box, text_color="text")

        self.loading_label = ctk.CTkLabel(card, text="", anchor="w",
                                          font=self.font(12, mono=True, slant="italic"))
        self.loading_label.grid(row=2, column=0, sticky="w", padx=16, pady=(0, 10))
        self._reg(self.loading_label, text_color="title")

        # input row (separate floating pill + buttons)
        row = ctk.CTkFrame(col, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", pady=(12, 0))
        row.grid_columnconfigure(0, weight=1)

        self.input_entry = ctk.CTkEntry(
            row, placeholder_text="enter prompt or action...",
            font=self.font(14, mono=True), height=46, border_width=1, corner_radius=CARD_RADIUS)
        self.input_entry.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        self.input_entry.bind("<Return>", lambda e: self.send_message())
        self._reg(self.input_entry, fg_color="glass", text_color="entry_text",
                  border_color="border")

        self.mic_btn = ctk.CTkButton(
            row, text="🎤", width=52, height=46, corner_radius=CARD_RADIUS,
            font=self.font(16, "bold"), command=self._mic_click)
        self.mic_btn.grid(row=0, column=1, sticky="e", padx=(0, 8))
        self._reg(self.mic_btn, fg_color="glass2", text_color="title", hover_color="hover")

        self.send_btn = ctk.CTkButton(
            row, text="EXECUTE", width=110, height=46, corner_radius=CARD_RADIUS,
            font=self.font(13, "bold", mono=True), command=self.send_message)
        self.send_btn.grid(row=0, column=2, sticky="e", padx=(0, 8))
        self._reg(self.send_btn, fg_color="accent", text_color="accent_text", hover_color="hover")

        self.stop_btn = ctk.CTkButton(
            row, text="■ STOP", width=92, height=46, corner_radius=CARD_RADIUS,
            fg_color="#8b1a1a", text_color="#ffffff", hover_color="#b22222",
            font=self.font(13, "bold", mono=True), command=self.stop_current,
            state="disabled")
        self.stop_btn.grid(row=0, column=3, sticky="e")

    # ════════════════════════════════════════════════════════════════════
    #  HUD (right): weather card + honeycomb card
    # ════════════════════════════════════════════════════════════════════
    def _build_hud(self):
        col = ctk.CTkFrame(self, fg_color="transparent", width=316)
        col.grid(row=0, column=2, sticky="nsew", padx=(7, 14), pady=14)
        col.grid_propagate(False)

        # ── Public IP indicator (top-right, above weather) ──
        ipc = self._card(col)
        ipc.pack(fill="x", pady=(0, 12))
        iprow = ctk.CTkFrame(ipc, fg_color="transparent")
        iprow.pack(fill="x", padx=14, pady=(10, 2))
        self.ip_dot = ctk.CTkLabel(iprow, text="●", font=self.font(16, "bold"))
        self.ip_dot.pack(side="left")
        self.ip_dot.configure(text_color=get_theme(self.current_theme_name)["bad"])
        self.ip_value = ctk.CTkLabel(iprow, text="public IP: …", anchor="w",
                                     font=self.font(13, "bold", mono=True))
        self.ip_value.pack(side="left", padx=(8, 0))
        self._reg(self.ip_value, text_color="text")
        self.ip_note = ctk.CTkLabel(ipc, text="PUBLIC IP VISIBLE", anchor="w",
                                    font=self.font(9, "bold", mono=True))
        self.ip_note.pack(fill="x", padx=14, pady=(0, 10))
        self.ip_note.configure(text_color=get_theme(self.current_theme_name)["bad"])

        # ── Weather card ──
        wc = self._card(col)
        wc.pack(fill="x", pady=(0, 12))
        self._section_header(wc, "Weather").pack(fill="x", padx=14, pady=(12, 6))
        self.w_loc = ctk.CTkLabel(wc, text="locating...", anchor="w",
                                  font=self.font(11, mono=True))
        self.w_loc.pack(fill="x", padx=14, pady=(0, 0))
        self._reg(self.w_loc, text_color="dim")
        row = ctk.CTkFrame(wc, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(0, 2))
        self.w_temp = ctk.CTkLabel(row, text="--°", font=self.font(40, "bold", mono=True))
        self.w_temp.pack(side="left")
        self._reg(self.w_temp, text_color="title")
        self.w_desc = ctk.CTkLabel(row, text="", font=self.font(12), justify="left")
        self.w_desc.pack(side="left", padx=(10, 0))
        self._reg(self.w_desc, text_color="text")
        self.w_feels = ctk.CTkLabel(wc, text="", anchor="w", font=self.font(10, mono=True))
        self.w_feels.pack(fill="x", padx=14, pady=(0, 8))
        self._reg(self.w_feels, text_color="sub_col")
        self.w_days = ctk.CTkFrame(wc, fg_color="transparent")
        self.w_days.pack(fill="x", padx=14, pady=(0, 12))
        self.w_day_rows = []
        for _ in range(3):
            r = ctk.CTkLabel(self.w_days, text="", anchor="w", font=self.font(10, mono=True))
            r.pack(fill="x")
            self._reg(r, text_color="text")
            self.w_day_rows.append(r)

        # ── System honeycomb card ──
        sc = self._card(col)
        sc.pack(fill="both", expand=True)
        self._section_header(sc, "System Feed").pack(fill="x", padx=14, pady=(12, 6))
        holder = ctk.CTkFrame(sc, fg_color="transparent")
        holder.pack(expand=True)
        self.honey = Honeycomb(holder, get_theme(self.current_theme_name))
        self.honey.pack(padx=6, pady=(0, 6))
        self.sys_backend = ctk.CTkLabel(sc, text="", anchor="e", font=self.font(9, mono=True))
        self.sys_backend.pack(fill="x", padx=14, pady=(0, 8))
        self._reg(self.sys_backend, text_color="dim")

    # ════════════════════════════════════════════════════════════════════
    #  LIVE FEEDS
    # ════════════════════════════════════════════════════════════════════
    def _tick_system(self):
        if not self._alive:
            return
        threading.Thread(target=self._sample_and_push, daemon=True).start()
        self.after(STATS_INTERVAL_MS, self._tick_system)

    def _sample_and_push(self):
        try:
            data = self.stats.sample()
        except Exception:
            return
        if self._alive:
            self.after(0, self._update_system, data)

    @staticmethod
    def _ckey(pct: float) -> str:
        return "bad" if pct >= 90 else "warn" if pct >= 70 else "accent"

    def _update_system(self, d: dict):
        if not self._alive:
            return
        try:
            self.honey.set("cpu", d["cpu"], f"{d['cpu']:.0f}%", "CPU", self._ckey(d["cpu"]))
            if d["gpu"] is None:
                self.honey.set("gpu", None, "n/a", "GPU", "dim")
            else:
                self.honey.set("gpu", d["gpu"], f"{d['gpu']:.0f}%", "GPU", self._ckey(d["gpu"]))
            self.honey.set("ram", d["ram_pct"], f"{d['ram_pct']:.0f}%", "RAM", self._ckey(d["ram_pct"]))
            self.honey.set("disk", d["disk_pct"], f"{d['disk_pct']:.0f}%", "DISK", self._ckey(d["disk_pct"]))
            netpct = min(100.0, d["net_down"] / (5 * 1024 * 1024) * 100)
            self.honey.set("net", netpct, _net_compact(d["net_down"]), "NET↓", "glow")
            now = datetime.now()
            self.honey.set_clock(now.strftime("%H:%M"), now.strftime("%d %b"), now.second)
            self.sys_backend.configure(text=f"src: {d['backend']}")
        except Exception:
            pass

    def _weather_loop(self):
        while self._alive:
            data = self.weather.fetch()
            if self._alive:
                self.after(0, self._update_weather, data)
            for _ in range(WEATHER_INTERVAL_S):
                if not self._alive:
                    return
                time.sleep(1)

    def _update_weather(self, w: Optional[dict]):
        if not self._alive:
            return
        try:
            if w is None:
                self.w_loc.configure(text="weather offline")
                self.w_temp.configure(text="--°")
                self.w_desc.configure(text="no connection")
                self.w_feels.configure(text="")
                for r in self.w_day_rows:
                    r.configure(text="")
                self.honey.set("weather", None, "--°", "WX", "accent2")
                return
            self.w_loc.configure(text=f"◉ {w['location']}")
            self.w_temp.configure(text=f"{w['temp']}°")
            self.w_desc.configure(text=w["desc"])
            self.w_feels.configure(
                text=f"feels {w['feels']}° · hum {w['humidity']}% · wind {w['wind']}km/h")
            for row, day in zip(self.w_day_rows, w["days"]):
                row.configure(text=f"{day['date'][5:]}  {day['hi']:>3}°/{day['lo']:>3}°  "
                                   f"{day['desc'][:16]}")
            try:
                t = float(w["temp"]); pct = max(0.0, min(100.0, (t + 10) / 50 * 100))
            except Exception:
                pct = None
            self.honey.set("weather", pct, f"{w['temp']}°", "WX", "accent2")
        except Exception:
            pass

    # ════════════════════════════════════════════════════════════════════
    #  GREETING / TITLE
    # ════════════════════════════════════════════════════════════════════
    def _greet(self):
        self._refresh_title()
        self.append_chat("SK7LD-AI",
                         "The longship is crewed. Name a target and the raid begins.\n"
                         "Try: 'scan 192.168.1.10', 'find subdomains of example.com', "
                         "'check example.com for vulns', or just chat.")

    def _refresh_title(self):
        th = get_theme(self.current_theme_name)
        self.title_label.configure(
            text=f"{th['emoji']}  {self.current_theme_name.upper()}  {th['emoji']}")

    # ════════════════════════════════════════════════════════════════════
    #  THEMING
    # ════════════════════════════════════════════════════════════════════
    def change_theme(self, selected_theme: str):
        self.current_theme_name = selected_theme
        th = get_theme(selected_theme)
        self.configure(fg_color=th["bg"])
        self._apply_theme()
        self.honey.retheme(th)
        self._refresh_title()
        self.subtitle_label.configure(text=th["subtitle"])
        if th["show_v1ru5_ig"]:
            self.insta2_label.pack(padx=14, pady=(0, 8), anchor="w", before=self.theme_label)
        else:
            self.insta2_label.pack_forget()
        self._update_ip_label(self._public_ip)   # recolor dot/note for new theme
        self.orb.set_theme(th)
        self._render_ambient(force=True)

    # ════════════════════════════════════════════════════════════════════
    #  MODELS
    # ════════════════════════════════════════════════════════════════════
    def _on_model_change(self, value: str):
        self.client.model = value

    def fetch_models(self):
        def run():
            models = self.client.list_models()
            if models and self._alive:
                self.after(0, lambda: self._apply_models(models))
        threading.Thread(target=run, daemon=True).start()

    def _apply_models(self, models):
        self.model_dropdown.configure(values=models)
        if DEFAULT_MODEL in models:
            self.model_dropdown.set(DEFAULT_MODEL); self.client.model = DEFAULT_MODEL
        else:
            self.model_dropdown.set(models[0]); self.client.model = models[0]

    def check_first_run(self):
        models = self.client.list_models()
        if models is None:
            return
        known = [tag for tag, _ in INSTALL_OPTIONS.values()]
        if not any(m in known for m in models):
            self.open_install_dialog()

    def open_install_dialog(self):
        tag = InstallModelDialog(self, get_theme(self.current_theme_name)).show()
        if tag:
            self.install_model(tag)

    def open_persona_dialog(self):
        res = PersonaDialog(self, self.client.system_prompt,
                            get_theme(self.current_theme_name)).show()
        if res is None:
            return
        kind, text = res
        if kind == "reset":
            config.reset_system_prompt()
            self.client.system_prompt = DEFAULT_SYSTEM_PROMPT
            self.append_chat("SYSTEM", "Persona reset to default.")
        else:
            self.client.system_prompt = text
            saved = config.set_system_prompt(text)
            self.append_chat("SYSTEM", "Persona updated." if saved
                             else "Persona updated for this session (could not write config).")

    def install_model(self, tag: str):
        control = self._new_job()
        self._set_busy(True)
        self.update_loading_animation(True, f"Forging {tag}...")
        self.append_chat("SYSTEM", f"Forging model {tag} via Ollama... this can take a while.")

        def run():
            ok = self.client.pull_model(
                tag, on_progress=lambda line: self.after(0, self._append_line, f"  {line}"),
                control=control)
            if ok:
                self.after(0, self.append_chat, "SYSTEM", f"Model {tag} installed.")
                self.after(0, self.fetch_models)
            elif control.cancelled:
                self.after(0, self.append_chat, "SYSTEM", f"Pull of {tag} stopped.")
            else:
                self.after(0, self.append_chat, "SYSTEM ERROR", f"Install failed for {tag}.")
            self.after(0, lambda: self._set_busy(False))
        threading.Thread(target=run, daemon=True).start()

    # ════════════════════════════════════════════════════════════════════
    #  LOADING ANIMATION
    # ════════════════════════════════════════════════════════════════════
    def update_loading_animation(self, active: bool, custom_text: Optional[str] = None):
        if not active:
            self.loading_label.configure(text="")
            return
        chars = ["⠋", "⠙", "⠹", "⠸", "⠼",
                 "⠴", "⠦", "⠧", "⠇", "⠏"]

        def animate(step=0):
            if not self.is_busy or not self._alive:
                self.loading_label.configure(text="")
                return
            icon = chars[step % len(chars)]
            self.loading_label.configure(text=f"{icon} {custom_text or 'Processing node parameters...'}")
            self.after(100, lambda: animate(step + 1))
        animate()

    # ════════════════════════════════════════════════════════════════════
    #  CHAT OUTPUT
    # ════════════════════════════════════════════════════════════════════
    def append_chat(self, sender: str, message: str):
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", f"{sender}:\n{message}\n\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def _append_line(self, line: str):
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", line + "\n")
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def _insert(self, text: str):
        self.chat_box.configure(state="normal")
        self.chat_box.insert("end", text)
        self.chat_box.see("end")
        self.chat_box.configure(state="disabled")

    def _set_busy(self, busy: bool):
        self.is_busy = busy
        self.send_btn.configure(state="disabled" if busy else "normal")
        self.stop_btn.configure(state="normal" if busy else "disabled")
        self.update_loading_animation(busy)

    def _new_job(self) -> JobControl:
        self.active_control = JobControl()
        return self.active_control

    def stop_current(self):
        if self.active_control is not None:
            self.active_control.cancel()
            self._append_line("[!] STOP requested - terminating current job...")
            self.loading_label.configure(text="Stopping...")

    # ════════════════════════════════════════════════════════════════════
    #  SEND / ORCHESTRATION
    # ════════════════════════════════════════════════════════════════════
    def send_message(self):
        if self.is_busy:
            return
        prompt = self.input_entry.get().strip()
        if not prompt:
            return
        self.input_entry.delete(0, "end")
        self.append_chat("You", prompt)

        low = prompt.lower()
        # self-update intent
        if _re.search(r"\b(update|upgrade)\s+(your ?self|sk7ld|the app|the tool)\b|"
                      r"\bself[ -]?update\b|\bpull (the )?(latest|newest)( repo)?\b", low):
            self._run_self_update()
            return
        # linux system update intent
        if _re.search(r"\b(system update|update (the )?system|apt update|"
                      r"update (kali|linux|debian|packages)|upgrade (the )?system)\b", low):
            self._run_system_update()
            return

        # vision query -> answer from the live object detector
        if _re.search(r"\bwhat\b.*\b(do you |can you |you )?see\b|"
                      r"\bwhat'?s? (on |in )?(the )?(camera|webcam|screen|view)\b|"
                      r"\bdescribe\b.*\b(see|camera|view)\b", low):
            desc = self.vision.describe()
            self.append_chat("SK7LD-AI", desc)
            if self.voice_mode and voicemod.tts_available():
                self.voice.speak(desc,
                                 on_start=lambda: self.after(0, self._show_orb, "talking"),
                                 on_done=lambda: self.after(0, self._hide_orb))
            return

        # image-generation intent -> real image model, NOT the chat LLM
        # (otherwise the LLM "draws" ASCII art). e.g. "make a cyberviking image".
        if _re.search(r"\b(make|generate|create|draw|render|paint|gen(?:erate)?)\b"
                      r"[^.]*?\b(image|images|picture|pic|photo|png|jpe?g|"
                      r"artwork|wallpaper|logo|portrait)\b", low):
            self._gen_image_run(self._image_subject(prompt))
            return

        if self.code_mode:
            self._start_code(prompt)
            return

        plan = orchestrator.plan(prompt)
        if plan is None:
            self._start_ai_chat(prompt)
            return
        theme = get_theme(self.current_theme_name)
        target = plan.target or self.locked_target
        actions = [a for a, _ in plan.options]
        choice = ToolChoiceDialog(self, plan.intent, target, theme, actions=actions).show()
        if choice is None:
            self.append_chat("SK7LD-AI", "Raid called off.")
            return
        kind, action, chosen_target = choice
        if kind == "chat":
            self._start_ai_chat(prompt)
            return
        if chosen_target:
            self.locked_target = chosen_target
        self._start_tool_run(action, chosen_target)

    def _start_ai_chat(self, prompt: str):
        control = self._new_job()
        self._set_busy(True)
        self.append_chat("AI", "")
        buf = []

        def run():
            try:
                for token in self.client.chat_stream(prompt, control=control):
                    buf.append(token)
                    self.after(0, self._insert, token)
                if control.cancelled:
                    self.after(0, self._insert, "  [stopped]")
                elif self.voice_mode and voicemod.tts_available():
                    self.voice.speak(
                        "".join(buf),
                        on_start=lambda: self.after(0, self._show_orb, "talking"),
                        on_done=lambda: self.after(0, self._hide_orb))
            finally:
                self.after(0, self._insert, "\n\n")
                self.after(0, lambda: self._set_busy(False))
        threading.Thread(target=run, daemon=True).start()

    # ── Code Mode ───────────────────────────────────────────────────────
    def _toggle_code_mode(self):
        self.code_mode = bool(self.code_switch.get())
        self.append_chat("SYSTEM", "Code Mode ON - prompts now generate code/scripts."
                         if self.code_mode else "Code Mode OFF - back to the console.")

    def _start_code(self, prompt: str):
        control = self._new_job()
        self._set_busy(True)
        self.append_chat("CODE", "")
        buf = []

        def run():
            try:
                for token in self.client.chat_stream(
                        prompt, system=CODE_SYSTEM_PROMPT, few_shot=False, control=control):
                    buf.append(token)
                    self.after(0, self._insert, token)
                if control.cancelled:
                    self.after(0, self._insert, "  [stopped]")
                else:
                    code, ext = extract_code("".join(buf))
                    if code:
                        self._last_code = (code, ext)
                        self.after(0, lambda: self.save_code_btn.configure(state="normal"))
            finally:
                self.after(0, self._insert, "\n\n")
                self.after(0, lambda: self._set_busy(False))
        threading.Thread(target=run, daemon=True).start()

    def _save_code(self):
        if not self._last_code:
            return
        code, ext = self._last_code
        path = filedialog.asksaveasfilename(
            title="Save generated code", defaultextension=f".{ext}",
            initialfile=f"sk7ld_code.{ext}")
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(code)
            self.append_chat("SYSTEM", f"Saved code to {os.path.basename(path)}")
        except Exception as exc:  # noqa: BLE001
            self.append_chat("SYSTEM ERROR", f"Could not save: {exc}")

    def _start_tool_run(self, action, target):
        control = self._new_job()
        self._set_busy(True)
        self.append_chat("SK7LD-AI", f"Preparing {action.tool}...")

        def log(line: str):
            self.after(0, self._append_line, line)

        def run():
            try:
                output = orchestrator.run_action(
                    action, target, log, confirm_install=self._confirm_on_main,
                    control=control)
                if control.cancelled:
                    return
                if output and action.mode != "interactive":
                    if self._confirm_on_main(
                            "Analyse output?",
                            f"Feed the {action.tool} output to {self.client.model} "
                            f"for a tactical breakdown?"):
                        self.after(0, self._stream_analysis, action.tool, target, output)
                        return
            finally:
                self.after(0, lambda: self._set_busy(False))
        threading.Thread(target=run, daemon=True).start()

    def _stream_analysis(self, tool, target, output):
        control = self._new_job()
        self._set_busy(True)
        self.append_chat("AI", "")
        prompt = analysis_prompt(tool, target, output)

        def run():
            try:
                for token in self.client.chat_stream(prompt, control=control):
                    self.after(0, self._insert, token)
                if control.cancelled:
                    self.after(0, self._insert, "  [stopped]")
            finally:
                self.after(0, self._insert, "\n\n")
                self.after(0, lambda: self._set_busy(False))
        threading.Thread(target=run, daemon=True).start()

    def _confirm_on_main(self, title: str, body: str) -> bool:
        event = threading.Event()
        holder = {"val": False}

        def ask():
            holder["val"] = ConfirmDialog(self, title, body,
                                          get_theme(self.current_theme_name)).show()
            event.set()
        self.after(0, ask)
        event.wait()
        return holder["val"]

    # ════════════════════════════════════════════════════════════════════
    # ════════════════════════════════════════════════════════════════════
    #  FIRST-LAUNCH DISCLAIMER
    # ════════════════════════════════════════════════════════════════════
    def _check_disclaimer(self):
        if config.disclaimer_accepted():
            return
        agreed = DisclaimerDialog(self, get_theme(self.current_theme_name),
                                  version=__version__).show()
        if agreed:
            config.accept_disclaimer()
        else:
            self._on_close()

    # ════════════════════════════════════════════════════════════════════
    #  VOICE ORB (animated globe overlay)
    # ════════════════════════════════════════════════════════════════════
    def _build_orb(self):
        th = get_theme(self.current_theme_name)
        self.orb_panel = ctk.CTkFrame(self.console_card, corner_radius=16,
                                      border_width=1, fg_color=th["glass2"],
                                      border_color=th["accent"])
        self._reg(self.orb_panel, fg_color="glass2", border_color="accent")
        self.orb_label = ctk.CTkLabel(self.orb_panel, text="LISTENING",
                                      font=self.font(13, "bold", mono=True))
        self.orb_label.pack(padx=20, pady=(14, 4))
        self._reg(self.orb_label, text_color="title")
        self.orb = VoiceOrb(self.orb_panel, th, size=230)
        self.orb.pack(padx=18, pady=(0, 18))

    def _show_orb(self, mode: str):
        if not self._alive:
            return
        label = "LISTENING" if mode == "listening" else "SPEAKING"
        self.orb_label.configure(text=f"● {label}")
        self.orb.start(mode)
        self.orb_panel.place(relx=0.5, rely=0.5, anchor="center")
        self.orb_panel.lift()

    def _hide_orb(self):
        try:
            self.orb.stop()
            self.orb_panel.place_forget()
        except Exception:
            pass

    # ════════════════════════════════════════════════════════════════════
    #  VOICE
    # ════════════════════════════════════════════════════════════════════
    def _voice_status(self, msg: str):
        self.after(0, self._append_line, msg)

    def _refresh_voice_hint(self):
        if voicemod.stt_available() and voicemod.tts_available():
            txt = "ready (STT+TTS)"
        elif voicemod.stt_available():
            txt = "listening ok; TTS missing"
        elif voicemod.tts_available():
            txt = "speaking ok; STT missing"
        else:
            txt = "install: " + voicemod.missing_hint()
        self.voice_hint.configure(text=txt)

    def _refresh_img_hint(self):
        self.img_hint.configure(text="ready" if imgmod.available()
                                else "install: " + imgmod.missing_hint())

    # ── audio device pickers ────────────────────────────────────────────
    def _audio_labels(self, kind: str):
        try:
            devs = devmod.list_audio().get(kind, [])
            labels = [f"[{d['index']}] {d['name']}"[:40] for d in devs]
            return labels or ["(none found)"]
        except Exception:
            return ["(none found)"]

    def _on_mic(self, label):
        self._set_audio_device(label, is_input=True)

    def _on_speaker(self, label):
        self._set_audio_device(label, is_input=False)

    def _set_audio_device(self, label, is_input: bool):
        m = _re.match(r"\[(\d+)\]", label or "")
        if not m:
            return
        idx = int(m.group(1))
        try:
            import sounddevice as sd
            cur = list(sd.default.device) if sd.default.device else [None, None]
            if len(cur) < 2:
                cur = [None, None]
            cur[0 if is_input else 1] = idx
            sd.default.device = tuple(cur)
            self._append_line(f"[~] {'Mic' if is_input else 'Speaker'} -> {label}")
        except Exception as exc:  # noqa: BLE001
            self._append_line(f"[!] Could not set audio device: {exc}")

    # ── object detection (vision) ───────────────────────────────────────
    def _refresh_vision_hint(self):
        self.vision_hint.configure(
            text="ready — flip DETECT MODE" if visionmod.available()
            else "install: " + visionmod.missing_hint())

    def _on_vision_model(self, label):
        self.vision.set_model(visionmod.label_to_id(label))
        self._append_line(f"[~] Detection model -> {label}")

    def _on_camera(self, label):
        m = _re.search(r"(\d+)", label or "0")
        self.vision.set_camera(int(m.group(1)) if m else 0)
        self._append_line(f"[~] Camera -> {label}")

    def _toggle_vision(self):
        want = bool(self.vision_switch.get())
        if want:
            if not visionmod.available():
                self.append_chat("SYSTEM", "Object detection needs the vision stack:\n  "
                                 + visionmod.missing_hint())
                self.vision_switch.deselect()
                return
            self.append_chat("SYSTEM", "Object-detection mode ON — opening the webcam. "
                             "Ask me \"what do you see?\" any time.")
            self.vision_on = self.vision.start()
            if not self.vision_on:
                self.vision_switch.deselect()
        else:
            self.vision.stop()
            self.vision_on = False
            self.append_chat("SYSTEM", "Object-detection mode OFF.")

    def _on_vision_labels(self, counts: dict):
        """Clean label feed from the detector -> live sidebar readout."""
        if not self._alive:
            return
        if counts:
            txt = "seeing: " + ", ".join(f"{v}×{k}" for k, v in
                                         sorted(counts.items(), key=lambda kv: -kv[1]))
        else:
            txt = "seeing: (nothing)" if self.vision_on else "ready — flip DETECT MODE"
        self.after(0, lambda: self.vision_hint.configure(text=txt[:48]))

    # ── hardware discovery ──────────────────────────────────────────────
    def _scan_devices(self):
        self.append_chat("SYSTEM", "Scanning for USB radios, audio and cameras...")

        def run():
            try:
                for line in devmod.scan_lines():
                    self.after(0, self._append_line, line)
                # refresh the audio + camera pickers with what we found
                self.after(0, self._refresh_device_pickers)
            except Exception as exc:  # noqa: BLE001
                self.after(0, self._append_line, f"[X] Scan failed: {exc}")
        threading.Thread(target=run, daemon=True).start()

    def _refresh_device_pickers(self):
        try:
            self.mic_dropdown.configure(values=self._audio_labels("inputs"))
            self.spk_dropdown.configure(values=self._audio_labels("outputs"))
            cams = devmod.list_cameras()
            if cams:
                self.cam_dropdown.configure(
                    values=[f"camera {c['index']}" for c in cams])
        except Exception:
            pass

    def _toggle_voice(self):
        self.voice_mode = bool(self.voice_switch.get())
        if self.voice_mode:
            if not (voicemod.stt_available() or voicemod.tts_available()):
                self.append_chat("SYSTEM", "Voice mode needs the audio stack:\n  "
                                 + voicemod.missing_hint())
                return
            self.append_chat("SYSTEM", 'Voice mode ON — say "Hey Scot" to wake me, or use '
                             "the 🎤 button. Replies are spoken aloud (English).")
            if voicemod.stt_available():
                self.voice.start_wake(self._on_wake)
        else:
            self.voice.stop_wake()
            self._hide_orb()
            self.append_chat("SYSTEM", "Voice mode OFF.")

    def _on_wake(self, command: str):
        """Called from the wake-word thread when 'Hey Scot' is heard."""
        self.after(0, self._wake_fire, command)

    def _wake_fire(self, command: str):
        if not self._alive or self.is_busy:
            return
        self._show_orb("listening")
        self.after(1200, self._hide_orb)
        cmd = voicemod.strip_wake(command).strip()
        if cmd:
            self.append_chat("SYSTEM", f'Scot heard: "{cmd}"')
            self._voice_submit(cmd)
        else:
            self._append_line('[*] Scot: yes? — say "Hey Scot, <command>".')

    def _on_stt_model(self, name):
        self.voice.set_stt_model(name)
        self._append_line(f"[~] Listening model -> {name}")
        threading.Thread(target=lambda: self.voice.pull_stt_model(name, self._voice_status),
                         daemon=True).start()

    def _on_tts_voice(self, name):
        self.voice.tts_voice = name
        self._append_line(f"[~] Speaking voice -> {name}")

    def _mic_click(self):
        if not self.voice.listening:
            if self.voice.start_listening():
                self.mic_btn.configure(text="●", fg_color="#8b1a1a")
                self._show_orb("listening")
        else:
            self.mic_btn.configure(text="🎤", fg_color=get_theme(self.current_theme_name)["glass2"])
            self._hide_orb()
            self._set_busy(True)

            def run():
                text = self.voice.stop_and_transcribe()
                self.after(0, lambda: self._set_busy(False))
                if text:
                    self.after(0, self._voice_submit, text)
            threading.Thread(target=run, daemon=True).start()

    def _voice_submit(self, text: str):
        text = voicemod.strip_wake(text)   # drop a leading "Hey Scot," if present
        self.input_entry.delete(0, "end")
        self.input_entry.insert(0, text)
        self.send_message()

    # ════════════════════════════════════════════════════════════════════
    #  IMAGE
    # ════════════════════════════════════════════════════════════════════
    def _on_image_model(self, label):
        self.imggen.set_model(imgmod.label_to_id(label))
        self._append_line(f"[~] Image model -> {label}")

    def _gen_image(self):
        if self.is_busy:
            return
        prompt = self.input_entry.get().strip()
        if not prompt:
            self.append_chat("SYSTEM", "Type an image prompt first, then GENERATE IMAGE.")
            return
        self.input_entry.delete(0, "end")
        self._gen_image_run(prompt)

    _STOP_SUBJ = {"me", "you", "us", "it", "this", "that", "one", "him", "her", "them"}

    @classmethod
    def _image_subject(cls, text: str) -> str:
        """Pull the actual subject out of 'make a <subject> image for me'."""
        t = _re.sub(r"^\s*please[,\s]+", "", (text or "").strip(), flags=_re.I)
        noun = _re.search(r"\b(image|images|picture|pic|photo|png|jpe?g|"
                          r"artwork|wallpaper|logo|portrait)\b", t, _re.I)
        if not noun:
            return t.strip(" .!,:") or text
        after = _re.sub(r"^(?:of|for|showing|with|about|:|,)\s+", "",
                        t[noun.end():].strip(), flags=_re.I)
        after = _re.sub(r"\bfor (?:me|you|us)\b", "", after, flags=_re.I).strip(" .!,:")
        before = _re.sub(r"\b(make|generate|create|draw|render|paint|gen(?:erate)?|"
                         r"me|a|an|the|some|cool|nice|of|please)\b", "",
                         t[:noun.start()], flags=_re.I).strip(" .!,:")

        def meaningful(s: str) -> bool:
            return len(s) >= 2 and s.lower() not in cls._STOP_SUBJ

        if meaningful(after):
            subj = after
        elif meaningful(before):
            subj = before
        else:
            subj = (before + " " + after).strip()
        return subj.strip(" .!,:") or text

    def _gen_image_run(self, prompt: str):
        if self.is_busy:
            return
        if not imgmod.available():
            self.append_chat("SYSTEM", "Image generation needs the image stack:\n  "
                             + imgmod.missing_hint())
            return
        self.append_chat("IMAGE", prompt)
        self._set_busy(True)

        def run():
            path = None
            try:
                path = self.imggen.generate(
                    prompt, log=lambda m: self.after(0, self._append_line, m))
            finally:
                self.after(0, lambda: self._set_busy(False))
                if path:
                    self.after(0, self._show_image, path)
        threading.Thread(target=run, daemon=True).start()

    def _show_image(self, path: str):
        """Open the finished PNG in the OS image viewer so the user sees it."""
        try:
            if is_windows():
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                import subprocess
                opener = "open" if sys.platform == "darwin" else "xdg-open"
                subprocess.Popen([opener, path],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as exc:  # noqa: BLE001
            self._append_line(f"[!] Saved, but couldn't auto-open it: {exc}")

    # ════════════════════════════════════════════════════════════════════
    #  ANONYMOUS MODE (Tor)
    # ════════════════════════════════════════════════════════════════════
    def _toggle_anon(self):
        want = bool(self.anon_switch.get())
        if want:
            self.append_chat("SYSTEM", "Enabling anonymous mode (Tor)...")

            def run():
                ok = anonmod.enable(log=lambda m: self.after(0, self._append_line, m))
                self.anon_on = ok
                if not ok:
                    self.after(0, lambda: self.anon_switch.deselect())
                self.after(0, self._refresh_ip)
            threading.Thread(target=run, daemon=True).start()
        else:
            anonmod.disable(log=lambda m: self.after(0, self._append_line, m))
            self.anon_on = False
            self._refresh_ip()

    # ════════════════════════════════════════════════════════════════════
    #  PUBLIC IP INDICATOR
    # ════════════════════════════════════════════════════════════════════
    def _blink_dot(self):
        if not self._alive:
            return
        self._blink = not self._blink
        th = get_theme(self.current_theme_name)
        col = th["good"] if self.anon_on else th["bad"]
        try:
            self.ip_dot.configure(text_color=col if self._blink else th["glass"])
        except Exception:
            pass
        self.after(600, self._blink_dot)

    def _refresh_ip(self):
        def run():
            ip = netinfo.tor_ip() if self.anon_on else netinfo.public_ip()
            if self._alive:
                self.after(0, self._update_ip_label, ip)
        threading.Thread(target=run, daemon=True).start()

    def _update_ip_label(self, ip):
        self._public_ip = ip
        th = get_theme(self.current_theme_name)
        shown = ip or "unknown"
        if self.anon_on:
            self.ip_value.configure(text=f"Tor exit: {shown}")
            self.ip_note.configure(text="SAFE — ANONYMOUS (Tor)", text_color=th["good"])
            self.ip_dot.configure(text_color=th["good"])
        else:
            self.ip_value.configure(text=f"public IP: {shown}")
            self.ip_note.configure(text="PUBLIC IP VISIBLE", text_color=th["bad"])
            self.ip_dot.configure(text_color=th["bad"])

    # ════════════════════════════════════════════════════════════════════
    #  UPDATES
    # ════════════════════════════════════════════════════════════════════
    def _run_self_update(self):
        if self.is_busy:
            return
        control = self._new_job()
        self._set_busy(True)
        self.append_chat("SYSTEM", "Checking for a Sk7ld-AI update...")

        def run():
            try:
                updater.self_update(log=lambda m: self.after(0, self._append_line, m),
                                    confirm=self._confirm_on_main, control=control)
            finally:
                self.after(0, lambda: self._set_busy(False))
        threading.Thread(target=run, daemon=True).start()

    def _run_system_update(self):
        if self.is_busy:
            return
        control = self._new_job()
        self._set_busy(True)
        self.append_chat("SYSTEM", "System update...")

        def run():
            try:
                updater.system_update(log=lambda m: self.after(0, self._append_line, m),
                                      confirm=self._confirm_on_main, control=control)
            finally:
                self.after(0, lambda: self._set_busy(False))
        threading.Thread(target=run, daemon=True).start()

    def _on_close(self):
        self._alive = False
        try:
            self.voice.stop_wake()
            self.vision.stop()
            self.orb.stop()
        except Exception:
            pass
        if self.active_control is not None:
            self.active_control.cancel()
        self.destroy()


def main():
    app = Sk7ldAIApp()
    app.mainloop()


if __name__ == "__main__":
    main()
