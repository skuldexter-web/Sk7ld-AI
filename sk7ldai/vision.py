"""
vision.py - local real-time webcam object detection for Sk7ld-AI.

Captures live video from the default webcam and runs a fast, lightweight local
model (YOLOv8n via `ultralytics`) entirely on the machine - no cloud. Draws
bounding boxes + labels in a preview window, and exposes the detected labels so
the rest of Sk7ld-AI (the assistant, intents, logging) can consume them.

Everything is lazy-imported and defensive: importing this module never fails,
and if the vision stack isn't installed the GUI just shows how to add it.

Install the vision stack with:
    pip install ultralytics opencv-python

Clean label feed for the assistant:
    eng = VisionEngine(on_labels=lambda counts: ...)   # counts = {"person": 2, ...}
    eng.start()
    eng.latest_labels()   # -> ["laptop", "person"]  (what's on screen right now)
    eng.describe()        # -> "I can see: 2 person, 1 laptop"
"""

from __future__ import annotations

import threading
import time
from typing import Callable, Dict, List, Optional

LogFn = Callable[[str], None]
LabelsFn = Callable[[Dict[str, int]], None]

# Model dropdown: nano first (default, fastest), heavier below. They download on
# first use from Ultralytics.
MODELS = [
    ("yolov8n (nano, default)", "yolov8n.pt"),
    ("yolov8s (small)", "yolov8s.pt"),
    ("yolov8m (medium)", "yolov8m.pt"),
]
DEFAULT_MODEL = MODELS[0][1]
DEFAULT_CONF = 0.40          # ignore detections below this confidence


def _can_import(name: str) -> bool:
    import importlib.util
    try:
        return importlib.util.find_spec(name) is not None
    except Exception:
        return False


def available() -> bool:
    return _can_import("ultralytics") and _can_import("cv2")


def missing_hint() -> str:
    return "pip install ultralytics opencv-python"


def model_labels() -> List[str]:
    return [label for label, _ in MODELS]


def label_to_id(label: str) -> str:
    for lbl, rid in MODELS:
        if lbl == label:
            return rid
    return DEFAULT_MODEL


class VisionEngine:
    """
    Webcam -> YOLOv8 -> boxes/labels, with the detected labels exposed cleanly.

    Thread-safe reads of `latest` / `latest_labels()`. The capture + inference
    loop runs in its own thread with its own OpenCV preview window, so it never
    blocks the Tk main loop.
    """

    def __init__(self, model_id: str = DEFAULT_MODEL, camera_index: int = 0,
                 conf: float = DEFAULT_CONF,
                 on_labels: Optional[LabelsFn] = None,
                 on_status: Optional[LogFn] = None):
        self.model_id = model_id
        self.camera_index = camera_index
        self.conf = conf
        self.on_labels = on_labels or (lambda _: None)
        self.on_status = on_status or (lambda _: None)
        self._model = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._latest: Dict[str, int] = {}

    # ── public, thread-safe accessors (the "clean feed") ────────────────
    @property
    def running(self) -> bool:
        return self._running

    def latest(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._latest)

    def latest_labels(self) -> List[str]:
        with self._lock:
            return sorted(self._latest.keys())

    def describe(self) -> str:
        counts = self.latest()
        if not counts:
            return ("Nothing detected right now."
                    if self._running else "Object-detection mode is off.")
        parts = ", ".join(f"{n} {lbl}" for lbl, n in
                          sorted(counts.items(), key=lambda kv: -kv[1]))
        return f"I can see: {parts}."

    def set_model(self, model_id: str):
        if model_id != self.model_id:
            self.model_id = model_id
            self._model = None     # reload on next start

    def set_camera(self, index: int):
        self.camera_index = int(index)

    # ── control ─────────────────────────────────────────────────────────
    def start(self) -> bool:
        if self._running:
            return True
        if not available():
            self.on_status(f"[X] Object detection needs the vision stack. "
                           f"{missing_hint()}")
            return False
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        self._running = False

    # ── capture + inference loop (own thread, own window) ───────────────
    def _loop(self):
        try:
            import cv2
            from ultralytics import YOLO
        except Exception as exc:  # noqa: BLE001
            self.on_status(f"[X] Vision backend import failed: {exc}")
            self._running = False
            return

        if self._model is None:
            try:
                self.on_status(f"[~] Loading {self.model_id} "
                               f"(first use downloads weights)...")
                self._model = YOLO(self.model_id)
            except Exception as exc:  # noqa: BLE001
                self.on_status(f"[X] Could not load model: {exc}")
                self._running = False
                return

        if _is_windows() and hasattr(cv2, "CAP_DSHOW"):
            cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
        else:
            cap = cv2.VideoCapture(self.camera_index)
        if not cap or not cap.isOpened():
            self.on_status(f"[X] Could not open webcam {self.camera_index}.")
            self._running = False
            return

        self.on_status('[*] Object detection ON. Press ESC on the preview '
                       'window (or toggle off) to stop.')
        win = "SK7LD-AI // Object Detection"
        last_emit = 0.0
        try:
            while self._running:
                ok, frame = cap.read()
                if not ok:
                    time.sleep(0.05)
                    continue
                counts: Dict[str, int] = {}
                try:
                    res = self._model(frame, verbose=False, conf=self.conf)[0]
                    names = res.names
                    for box in res.boxes:
                        cls = int(box.cls[0])
                        conf = float(box.conf[0])
                        label = names.get(cls, str(cls)) if isinstance(names, dict) \
                            else names[cls]
                        counts[label] = counts.get(label, 0) + 1
                        x1, y1, x2, y2 = (int(v) for v in box.xyxy[0])
                        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 230, 255), 2)
                        cv2.putText(frame, f"{label} {conf:.2f}", (x1, max(18, y1 - 6)),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 230, 255), 2)
                except Exception:
                    pass

                # publish the clean label feed (rate-limited to ~5/s)
                with self._lock:
                    self._latest = counts
                now = time.time()
                if now - last_emit > 0.2:
                    last_emit = now
                    try:
                        self.on_labels(dict(counts))
                    except Exception:
                        pass

                try:
                    cv2.imshow(win, frame)
                    if cv2.waitKey(1) & 0xFF == 27:   # ESC
                        break
                except Exception:
                    # no GUI backend (e.g. headless) - keep detecting without preview
                    pass
        finally:
            self._running = False
            try:
                cap.release()
            except Exception:
                pass
            try:
                import cv2
                cv2.destroyWindow(win)
            except Exception:
                pass
            with self._lock:
                self._latest = {}
            self.on_status("[*] Object detection stopped.")


def _is_windows() -> bool:
    import os
    return os.name == "nt"
