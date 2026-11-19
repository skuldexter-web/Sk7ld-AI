"""
runner.py - Sk7ld-AI tool launcher.

Resolves a ToolAction into a concrete argv (PATH binary, arsenal clone
entrypoint, or alias), then either:
  * run_capture()     - runs a scan-style tool, streaming stdout to a callback
                        and returning the full text (for AI analysis), or
  * run_interactive() - launches a TUI/GUI tool in an external terminal window
                        (or reports the command when no terminal is available).
"""

from __future__ import annotations

import os
import shlex
import shutil
import subprocess
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from .arsenal import TOOL_ENTRYPOINTS, ToolAction, resolve_name
from .installer import ARSENAL_DIR, binary_for, is_root
from .control import JobControl
from .osenv import is_windows

LogFn = Callable[[str], None]

# Terminal emulators we will try, in order, for interactive tools.
_TERMINALS = [
    ("x-terminal-emulator", ["-e"]),
    ("gnome-terminal", ["--"]),
    ("konsole", ["-e"]),
    ("xfce4-terminal", ["-x"]),
    ("xterm", ["-e"]),
    ("kitty", []),
    ("alacritty", ["-e"]),
]


def _interpreter_cmd(interp: str, script: Path) -> List[str]:
    mapping = {
        "python3": ["python3", str(script)],
        "bash": ["bash", str(script)],
        "ruby": ["ruby", str(script)],
        "php": ["php", str(script)],
        "binary": [str(script)],
    }
    return mapping.get(interp, [str(script)])


def resolve_binary(name: str) -> Optional[List[str]]:
    """
    Turn a canonical tool name into an argv prefix:
      * on PATH               -> [binary]
      * cloned w/ entrypoint  -> [interp, script]
      * cloned, auto-detected -> [interp, guessed_script]
    Returns None if nothing runnable is found.
    """
    canonical = resolve_name(name)

    # 1. PATH (binary-map, canonical, lowercase)
    for cand in (binary_for(canonical), canonical, canonical.lower()):
        if shutil.which(cand):
            return [cand]

    # 2. Arsenal clone with a known entrypoint
    dest = ARSENAL_DIR / canonical
    ep = TOOL_ENTRYPOINTS.get(canonical)
    if ep and dest.is_dir():
        script, _, interp = ep.partition("|")
        full = dest / script
        if full.is_file():
            return _interpreter_cmd(interp, full)

    # 3. Arsenal clone, auto-detect common entrypoints
    if dest.is_dir():
        for py in ("main.py", f"{canonical}.py", f"{canonical.lower()}.py", "run.py", "app.py"):
            if (dest / py).is_file():
                return ["python3", str(dest / py)]
        for sh in (f"{canonical}.sh", f"{canonical.lower()}.sh", "run.sh", "start.sh"):
            if (dest / sh).is_file():
                return ["bash", str(dest / sh)]
    return None


def build_argv(action: ToolAction, target: Optional[str]) -> Tuple[Optional[List[str]], str]:
    """
    Build the full argv for a ToolAction. Substitutes {target}.
    Returns (argv_or_None, message). argv is None when the tool is not runnable.
    """
    prefix = resolve_binary(action.tool)
    if prefix is None:
        return None, f"{action.tool} is not installed."

    args: List[str] = []
    for token in action.cmd[1:]:
        if "{target}" in token:
            if not target:
                return None, f"{action.tool} needs a target."
            token = token.replace("{target}", target)
        args.append(token)

    argv = prefix + args
    if action.needs_root and not is_root():
        sudo = shutil.which("sudo")
        if sudo:
            argv = ["sudo", *argv]
    return argv, "ok"


# ════════════════════════════════════════════════════════════════════════
#  CAPTURE MODE  (scan-style tools)
# ════════════════════════════════════════════════════════════════════════
def run_capture(argv: List[str], log: LogFn, timeout: int = 900,
                control: Optional[JobControl] = None) -> str:
    """
    Run a tool, streaming stdout to `log`, and return the full output text.
    If `control` is cancelled (STOP button), the process group is killed and
    the read loop ends promptly.
    """
    log(f"$ {' '.join(shlex.quote(a) for a in argv)}")
    collected: List[str] = []
    try:
        proc = subprocess.Popen(
            argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, start_new_session=True,
        )
    except FileNotFoundError:
        msg = f"[X] command not found: {argv[0]}"
        log(msg)
        return msg
    if control is not None:
        control.register(proc)
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            collected.append(line.rstrip("\n"))
            log(line.rstrip("\n"))
            if control is not None and control.cancelled:
                break
        if control is not None and control.cancelled:
            log("[!] stopped by operator")
        else:
            proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        log("[X] tool timed out and was killed")
    except KeyboardInterrupt:
        proc.kill()
        log("[!] interrupted")
    finally:
        if control is not None:
            control.clear_proc()
    return "\n".join(collected)


# ════════════════════════════════════════════════════════════════════════
#  INTERACTIVE MODE  (TUI / GUI tools)
# ════════════════════════════════════════════════════════════════════════
def _find_terminal() -> Optional[Tuple[str, List[str]]]:
    for term, flag in _TERMINALS:
        if shutil.which(term):
            return term, flag
    return None


def run_interactive(argv: List[str], log: LogFn) -> bool:
    """
    Launch an interactive tool in a new terminal window so its TUI works.
    Returns True if a window was spawned, False if we could only print guidance.
    """
    # Windows: open the tool in a new console (Windows Terminal if present, else cmd).
    if is_windows():
        win_cmd = subprocess.list2cmdline(argv)
        try:
            if shutil.which("wt"):
                subprocess.Popen(["wt", "cmd", "/k", win_cmd])
            else:
                subprocess.Popen(f'start "Sk7ld-AI" cmd /k {win_cmd}', shell=True)
            log(f"[OK] launched in a new console: {argv[0]}")
            return True
        except Exception as exc:  # noqa: BLE001
            log(f"[!] could not open a console: {exc}")
            log(f"    run this yourself: {win_cmd}")
            return False

    has_display = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
    cmdline = " ".join(shlex.quote(a) for a in argv)

    if has_display:
        term = _find_terminal()
        if term:
            name, flag = term
            inner = f"{cmdline}; echo; echo '[Sk7ld-AI] tool exited - press Enter'; read"
            if name == "gnome-terminal":
                spawn = [name, "--", "bash", "-c", inner]
            elif flag:
                spawn = [name, *flag, "bash", "-c", inner]
            else:
                spawn = [name, "bash", "-c", inner]
            try:
                subprocess.Popen(spawn)
                log(f"[OK] launched in a new terminal: {argv[0]}")
                return True
            except Exception as exc:  # noqa: BLE001
                log(f"[!] could not open terminal: {exc}")

    # Headless / no terminal emulator: hand the operator the command.
    log("[!] No GUI terminal available - run this in your own shell:")
    log(f"    {cmdline}")
    return False
