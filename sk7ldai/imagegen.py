"""
imagegen.py - local text-to-image generation.

Uses Hugging Face `diffusers`. The default is a small model so it runs on modest
hardware; users can switch to bigger ones from the dropdown (they download on
first use). A GPU is strongly recommended - on CPU generation is slow.

Lazy-imported and defensive: importing never fails; if torch/diffusers aren't
installed the GUI shows how to add them. Untestable here (no torch/GPU), so the
backend is best-effort.

Install the image stack with (pick the torch build for your GPU/CPU):
    pip install diffusers transformers accelerate torch
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Callable, List, Optional

LogFn = Callable[[str], None]

# Model dropdown: small/light first (default), heavier below. (label, repo id).
MODELS = [
    ("tiny-sd (small, default)", "segmind/tiny-sd"),
    ("small-sd", "segmind/small-sd"),
    ("sd-turbo (fast)", "stabilityai/sd-turbo"),
    ("stable-diffusion v1.5", "runwayml/stable-diffusion-v1-5"),
    ("sdxl-turbo (big)", "stabilityai/sdxl-turbo"),
    ("sdxl-base 1.0 (big)", "stabilityai/stable-diffusion-xl-base-1.0"),
]
DEFAULT_MODEL = MODELS[0][1]

OUT_DIR = Path(os.environ.get(
    "SK7LD_AI_IMAGES", str(Path.home() / "sk7ld-ai-images")))


def _can_import(name: str) -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def available() -> bool:
    return _can_import("diffusers") and _can_import("torch")


def missing_hint() -> str:
    return "pip install diffusers transformers accelerate torch"


def model_labels() -> List[str]:
    return [label for label, _ in MODELS]


def label_to_id(label: str) -> str:
    for lbl, rid in MODELS:
        if lbl == label:
            return rid
    return DEFAULT_MODEL


class ImageGen:
    def __init__(self, model_id: str = DEFAULT_MODEL, on_status: Optional[LogFn] = None):
        self.model_id = model_id
        self.on_status = on_status or (lambda _: None)
        self._pipe = None
        self._loaded_id = None

    def set_model(self, model_id: str):
        if model_id != self.model_id:
            self.model_id = model_id
            self._pipe = None

    def _device(self):
        import torch
        if torch.cuda.is_available():
            return "cuda"
        if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _load(self, log: LogFn):
        if self._pipe is not None and self._loaded_id == self.model_id:
            return
        from diffusers import AutoPipelineForText2Image
        import torch
        dev = self._device()
        log(f"[~] Loading image model '{self.model_id}' on {dev} "
            f"(first use downloads weights)...")
        dtype = torch.float16 if dev in ("cuda", "mps") else torch.float32
        self._pipe = AutoPipelineForText2Image.from_pretrained(
            self.model_id, torch_dtype=dtype)
        self._pipe = self._pipe.to(dev)
        self._loaded_id = self.model_id
        log("[OK] Image model ready.")

    def pull_model(self, model_id: str, log: Optional[LogFn] = None) -> bool:
        log = log or self.on_status
        if not available():
            log(f"[X] Image backend not installed. {missing_hint()}")
            return False
        try:
            self.set_model(model_id)
            self._load(log)
            return True
        except Exception as exc:  # noqa: BLE001
            log(f"[X] Could not prepare '{model_id}': {exc}")
            return False

    def generate(self, prompt: str, log: Optional[LogFn] = None,
                 steps: int = 8) -> Optional[str]:
        """Generate an image; returns the saved file path or None."""
        log = log or self.on_status
        if not available():
            log(f"[X] Image generation needs extra packages. {missing_hint()}")
            return None
        try:
            self._load(log)
            OUT_DIR.mkdir(parents=True, exist_ok=True)
            log(f"[~] Generating: {prompt!r} ...")
            # sd-turbo / sdxl-turbo want few steps and no guidance
            turbo = "turbo" in self.model_id.lower()
            kwargs = dict(prompt=prompt, num_inference_steps=max(1, steps))
            if turbo:
                kwargs["guidance_scale"] = 0.0
            image = self._pipe(**kwargs).images[0]
            import time
            path = OUT_DIR / f"sk7ld_{int(time.time())}.png"
            image.save(path)
            log(f"[OK] Saved image: {path}")
            return str(path)
        except Exception as exc:  # noqa: BLE001
            log(f"[X] Generation failed: {exc}")
            return None
