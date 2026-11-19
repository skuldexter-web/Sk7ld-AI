"""
control.py - cooperative cancellation for long-running jobs.

A JobControl is handed to any operation that can run for a while (a scan, an
install, an AI stream). The worker:
  * registers its subprocess with the control so it can be killed, and
  * checks `.cancelled` in its read/stream loop so it stops promptly.

The GUI's STOP button (and the CLI's Ctrl-C) call `.cancel()`, which sets the
flag and terminates the tracked process group - so even a blocked `nmap` or
`feroxbuster` dies immediately rather than after it finishes.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
from typing import Optional


class JobControl:
    def __init__(self):
        self._event = threading.Event()
        self._proc: Optional[subprocess.Popen] = None
        self._lock = threading.Lock()

    # ── worker side ─────────────────────────────────────────────────────
    def register(self, proc: subprocess.Popen) -> None:
        """Track the active process. If cancel already fired, kill it now."""
        with self._lock:
            self._proc = proc
        if self._event.is_set():
            self._kill(proc)

    def clear_proc(self) -> None:
        with self._lock:
            self._proc = None

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    # ── controller side (GUI / CLI) ─────────────────────────────────────
    def cancel(self) -> None:
        """Request cancellation and kill the tracked process group."""
        self._event.set()
        with self._lock:
            proc = self._proc
        if proc is not None:
            self._kill(proc)

    def reset(self) -> None:
        """Reuse this control for a fresh job."""
        self._event.clear()
        with self._lock:
            self._proc = None

    # ── internals ───────────────────────────────────────────────────────
    @staticmethod
    def _kill(proc: subprocess.Popen) -> None:
        """Terminate the process and, where possible, its whole group."""
        if proc.poll() is not None:
            return
        try:
            pgid = os.getpgid(proc.pid)
            os.killpg(pgid, signal.SIGTERM)
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
        # Escalate to SIGKILL shortly after if it's still alive.
        def _hard():
            try:
                proc.wait(timeout=3)
            except Exception:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except Exception:
                    try:
                        proc.kill()
                    except Exception:
                        pass
        threading.Thread(target=_hard, daemon=True).start()
