"""
voice.py - Voice mode: let the operator talk to Sk7ld-AI and have it talk back.

Ollama models are text-only, so "listening" and "speaking" are done by dedicated
local engines, kept small by default and pullable to larger ones:

  * Listening (STT) : Whisper via faster-whisper (preferred) or openai-whisper.
                      Models = tiny / base / small / medium / large-v3.
                      Default "base" (~140 MB) so it won't blow up a laptop.
  * Speaking  (TTS) : Piper voices (.onnx) if present (pullable, high quality),
                      otherwise pyttsx3 using the OS voices (no download).

Everything is lazy-imported and defensive: importing this module never fails,
and if the audio stack isn't installed the GUI just shows how to add it. Nothing
here could be tested without a mic/speaker, so treat the backends as best-effort.

Install the audio stack with:
    pip install faster-whisper sounddevice soundfile pyttsx3
"""

from __future__ import annotations

import os
import shutil
import threading
from pathlib import Path
from typing import Callable, List, Optional

LogFn = Callable[[str], None]

# "Listening models" shown in the dropdown (Whisper sizes). Default = base.
STT_MODELS = ["tiny", "base", "small", "medium", "large-v3"]
DEFAULT_STT = "base"

# Wake word: in Voice Mode, Sk7ld-AI reacts when it hears its name "Hey Scot".
# (Whisper transcribes it a few different ways, so we accept close variants.)
WAKE_WORD = "hey scot"
# Longest/most-specific first so strip_wake removes the full phrase, not just "scot".
WAKE_VARIANTS = (
    "hey scott", "hey scot", "hey scout", "hey skot", "hey skott",
    "hi scott", "hi scot", "a scott", "a scot",
    "scott", "scot", "skot", "skott",
)


def strip_wake(text: str) -> str:
    """Remove a leading wake word (e.g. 'Hey Scot,') from a spoken command."""
    import re
    # variants are longest-first already, so the alternation is greedy-correct
    return re.sub(r"^\s*(?:hey|hi|a)?[\s,]*(" + "|".join(WAKE_VARIANTS) + r")[\s,:.!-]*",
                  "", text or "", flags=re.IGNORECASE).strip()


def has_wake(text: str) -> bool:
    low = " " + (text or "").lower() + " "
    # match "scot"/"scott" as a whole word (so it doesn't fire on, e.g., "scotch")
    import re
    return bool(re.search(r"\b(hey |hi |)(scot|scott|scout|skot|skott)\b", low))

VOICE_DIR = Path(os.environ.get(
    "SK7LD_AI_VOICES", str(Path.home() / ".local" / "share" / "sk7ld-ai" / "piper")))


# ── capability checks (all lazy, never raise) ───────────────────────────
def _can_import(name: str) -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def stt_available() -> bool:
    has_whisper = _can_import("faster_whisper") or _can_import("whisper")
    return has_whisper and _can_import("sounddevice")


def tts_available() -> bool:
    return _can_import("piper") or bool(shutil.which("piper")) or _can_import("pyttsx3")


def missing_hint() -> str:
    return "pip install faster-whisper sounddevice soundfile pyttsx3"


def list_tts_voices() -> List[str]:
    """Piper .onnx voices if any are present, else system voices, else a default."""
    voices = []
    try:
        if VOICE_DIR.is_dir():
            voices = sorted(p.stem for p in VOICE_DIR.glob("*.onnx"))
    except Exception:
        voices = []
    if voices:
        return voices
    if _can_import("pyttsx3"):
        try:
            import pyttsx3
            eng = pyttsx3.init()
            vs = [v.name for v in eng.getProperty("voices")][:12]
            eng.stop()
            if vs:
                return vs
        except Exception:
            pass
    return ["(system default)"]


class VoiceEngine:
    """Mic -> Whisper -> text, and text -> speech. Toggle listen; async speak."""

    def __init__(self, stt_model: str = DEFAULT_STT, tts_voice: Optional[str] = None,
                 on_status: Optional[LogFn] = None):
        self.stt_model = stt_model
        self.tts_voice = tts_voice
        self.on_status = on_status or (lambda _: None)
        self._whisper = None
        self._whisper_backend = None
        self._frames = []
        self._stream = None
        self._listening = False
        self._speak_proc = None
        self._wake_on = False
        self._wake_thread = None

    # ── STT ─────────────────────────────────────────────────────────────
    def set_stt_model(self, name: str):
        if name != self.stt_model:
            self.stt_model = name
            self._whisper = None   # force reload on next use

    def pull_stt_model(self, name: str, log: Optional[LogFn] = None) -> bool:
        """Pre-download a Whisper model by instantiating it once."""
        log = log or self.on_status
        try:
            log(f"[~] Preparing listening model '{name}' (first use downloads it)...")
            self.set_stt_model(name)
            self._load_whisper()
            log(f"[OK] Listening model '{name}' ready.")
            return True
        except Exception as exc:  # noqa: BLE001
            log(f"[X] Could not prepare '{name}': {exc}")
            return False

    def _load_whisper(self):
        if self._whisper is not None:
            return
        try:
            from faster_whisper import WhisperModel
            self._whisper = WhisperModel(self.stt_model, device="cpu", compute_type="int8")
            self._whisper_backend = "faster-whisper"
        except Exception:
            import whisper
            self._whisper = whisper.load_model(self.stt_model)
            self._whisper_backend = "whisper"

    def start_listening(self) -> bool:
        if self._listening:
            return True
        try:
            import sounddevice as sd
        except Exception as exc:  # noqa: BLE001
            self.on_status(f"[X] Microphone backend missing: {exc} ({missing_hint()})")
            return False
        self._frames = []

        def cb(indata, frames, time_info, status):  # noqa: ANN001
            self._frames.append(indata.copy())

        try:
            self._stream = sd.InputStream(samplerate=16000, channels=1,
                                          dtype="float32", callback=cb)
            self._stream.start()
            self._listening = True
            self.on_status("[*] Listening... click the mic again to stop.")
            return True
        except Exception as exc:  # noqa: BLE001
            self.on_status(f"[X] Could not open microphone: {exc}")
            return False

    def stop_and_transcribe(self) -> Optional[str]:
        if not self._listening:
            return None
        self._listening = False
        try:
            self._stream.stop(); self._stream.close()
        except Exception:
            pass
        try:
            import numpy as np
            if not self._frames:
                return ""
            audio = np.concatenate(self._frames, axis=0).flatten().astype("float32")
            self.on_status("[~] Transcribing...")
            return self._transcribe(audio)
        except Exception as exc:  # noqa: BLE001
            self.on_status(f"[X] Transcription failed: {exc}")
            return None

    def _transcribe(self, audio) -> str:
        # Force English so the model never switches languages on noisy audio.
        self._load_whisper()
        if self._whisper_backend == "faster-whisper":
            segments, _ = self._whisper.transcribe(audio, language="en")
            return " ".join(s.text for s in segments).strip()
        return self._whisper.transcribe(audio, language="en")["text"].strip()

    @property
    def listening(self) -> bool:
        return self._listening

    # ── wake word ("Hey Scot") - only runs while Voice Mode is on ───────
    def start_wake(self, on_wake: Callable[[str], None]) -> bool:
        """Continuously listen for the name 'Hey Scot' and fire on_wake(command)."""
        if self._wake_on:
            return True
        if not stt_available():
            self.on_status(f"[X] Wake word needs the audio stack: {missing_hint()}")
            return False
        self._wake_on = True
        self._wake_thread = threading.Thread(
            target=self._wake_loop, args=(on_wake,), daemon=True)
        self._wake_thread.start()
        self.on_status('[*] Say "Hey Scot" to wake me.')
        return True

    def stop_wake(self):
        self._wake_on = False

    def _wake_loop(self, on_wake: Callable[[str], None]):
        try:
            import sounddevice as sd
            import numpy as np
        except Exception:
            self._wake_on = False
            return
        win = 4  # seconds per window
        while self._wake_on:
            if self._listening:          # manual capture in progress
                import time
                time.sleep(0.3)
                continue
            try:
                rec = sd.rec(int(win * 16000), samplerate=16000, channels=1,
                             dtype="float32")
                sd.wait()
            except Exception:
                import time
                time.sleep(1.0)
                continue
            if not self._wake_on:
                break
            try:
                text = self._transcribe(rec.flatten())
            except Exception:
                text = ""
            if text and has_wake(text) and self._wake_on and not self._listening:
                on_wake(strip_wake(text))

    # ── TTS ─────────────────────────────────────────────────────────────
    def speak(self, text: str, on_start=None, on_done=None):
        """Speak text asynchronously (best-effort). on_start/on_done fire around it."""
        if not text.strip():
            if on_done:
                on_done()
            return

        def run():
            if on_start:
                try:
                    on_start()
                except Exception:
                    pass
            try:
                self._speak_blocking(text)
            finally:
                if on_done:
                    try:
                        on_done()
                    except Exception:
                        pass
        threading.Thread(target=run, daemon=True).start()

    def _speak_blocking(self, text: str):
        # Piper voice (.onnx) if the chosen voice exists
        voice_path = None
        if self.tts_voice and self.tts_voice not in ("(system default)",):
            cand = VOICE_DIR / f"{self.tts_voice}.onnx"
            if cand.is_file():
                voice_path = cand
        if voice_path and shutil.which("piper"):
            try:
                import subprocess
                wav = str(VOICE_DIR / "_sk7ld_tts.wav")
                self._speak_proc = subprocess.run(
                    ["piper", "--model", str(voice_path), "--output_file", wav],
                    input=text, text=True, capture_output=True, timeout=120)
                self._play_wav(wav)
                return
            except Exception:
                pass
        # Fallback: pyttsx3 (system voices, no download)
        com_ready = False
        try:
            # On Windows, pyttsx3 uses SAPI5 (COM). This runs in a worker thread,
            # so COM must be initialised here or SAPI raises "CoInitialize was not
            # called". Needs pywin32 (installed by the installer / requirements).
            if os.name == "nt":
                try:
                    import pythoncom
                    pythoncom.CoInitialize()
                    com_ready = True
                except Exception:
                    pass  # pyttsx3 may still work; if not, the except below reports
            import pyttsx3
            eng = pyttsx3.init()
            self._select_voice(eng)
            eng.say(text); eng.runAndWait(); eng.stop()
        except Exception as exc:  # noqa: BLE001
            hint = ""
            if os.name == "nt" and ("pywintypes" in str(exc) or "pywin32" in str(exc)
                                    or "CoInitialize" in str(exc)):
                hint = "  (run: pip install pywin32)"
            self.on_status(f"[!] Speech unavailable: {exc}{hint}")
        finally:
            if com_ready:
                try:
                    import pythoncom
                    pythoncom.CoUninitialize()
                except Exception:
                    pass

    def _select_voice(self, eng) -> None:
        """Pick the chosen voice, or auto-pick an English one for English output."""
        try:
            voices = eng.getProperty("voices")
        except Exception:
            return
        # explicit choice wins
        if self.tts_voice and self.tts_voice != "(system default)":
            for v in voices:
                if v.name == self.tts_voice:
                    eng.setProperty("voice", v.id)
                    return
        # otherwise prefer an English voice so speech matches English replies
        for v in voices:
            langs = ""
            for lg in (getattr(v, "languages", None) or []):
                langs += (lg.decode("latin-1") if isinstance(lg, bytes) else str(lg)).lower()
            name = (getattr(v, "name", "") or "").lower()
            vid = (getattr(v, "id", "") or "").lower()
            if "en" in langs or "english" in name or "en-" in vid or "en_us" in vid:
                eng.setProperty("voice", v.id)
                return

    @staticmethod
    def _play_wav(path: str):
        try:
            import soundfile as sf
            import sounddevice as sd
            data, sr = sf.read(path, dtype="float32")
            sd.play(data, sr); sd.wait()
        except Exception:
            pass
