"""
installer.py - Sk7ld-AI tool installation engine.

Ported from the Viking AI install.sh logic (apt -> git fallback, pip -> git
fallback, git_python / git_go / git_generic post-build, plus per-tool
prerequisites). Every network/system action streams human-readable lines to a
`log` callback so the GUI or CLI can show progress.

IMPORTANT: this module never installs anything on its own. The caller (the
orchestrator) must obtain explicit operator confirmation first - see
`describe_install()` for the text shown on the confirmation prompt.
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

from .arsenal import (ARSENAL, TOOL_DEPS, TOOL_ENTRYPOINTS, BIN_MAP, Tool,
                      resolve_name, WIN_WINGET)
from .control import JobControl
from .osenv import is_windows

LogFn = Callable[[str], None]

# Set for the duration of an install so every _run() it drives is cancellable
# and killable via the STOP button. Only one install runs at a time.
_active_control: Optional[JobControl] = None

# Where git-cloned arsenal tools live (OS-aware; overridable via SK7LD_AI_DIR).
def _default_base() -> str:
    if is_windows():
        root = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return str(Path(root) / "Sk7ld-AI")
    return "/opt/viking"


VIKING_DIR = Path(os.environ.get("SK7LD_AI_DIR", _default_base()))
ARSENAL_DIR = VIKING_DIR / "arsenal"


def _noop(_: str) -> None:
    pass


def is_root() -> bool:
    return hasattr(os, "geteuid") and os.geteuid() == 0


def _sudo_prefix() -> list:
    """Return ['sudo', '-n'] when we need root and aren't root, else []."""
    if is_windows() or is_root():
        return []
    if shutil.which("sudo"):
        return ["sudo", "-n"]
    return []


def _pip(args: list) -> list:
    """OS-correct pip invocation. Linux needs --break-system-packages; Windows
    uses `python -m pip` with no such flag."""
    if is_windows():
        return [sys.executable, "-m", "pip", "install", "-q", *args]
    return ["pip3", "install", "-q", *args, "--break-system-packages"]


def _run(cmd: list, log: LogFn, cwd: Optional[Path] = None, timeout: int = 1800) -> int:
    """Run a command, streaming combined output to `log`. Returns exit code.
    Honors the active JobControl so an install can be stopped mid-step."""
    ctrl = _active_control
    if ctrl is not None and ctrl.cancelled:
        return 130
    log(f"$ {' '.join(cmd)}")
    try:
        proc = subprocess.Popen(
            cmd, cwd=str(cwd) if cwd else None,
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1, start_new_session=True,
        )
    except FileNotFoundError:
        log(f"[X] command not found: {cmd[0]}")
        return 127
    if ctrl is not None:
        ctrl.register(proc)
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            log(line.rstrip("\n"))
            if ctrl is not None and ctrl.cancelled:
                break
        if ctrl is not None and ctrl.cancelled:
            log("[!] install step stopped by operator")
            return 130
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        log("[X] timed out")
        return 124
    finally:
        if ctrl is not None:
            ctrl.clear_proc()
    return proc.returncode


# ════════════════════════════════════════════════════════════════════════
#  AVAILABILITY
# ════════════════════════════════════════════════════════════════════════
def binary_for(name: str) -> str:
    """Resolve the real binary name for a canonical tool name."""
    return BIN_MAP.get(name, name)


def is_available(name: str) -> bool:
    """
    True if the tool is runnable: on PATH (canonical, binary-map, or lowercase),
    or cloned into the arsenal dir with a known/real entrypoint.
    """
    canonical = resolve_name(name)
    candidates = {canonical, binary_for(canonical), canonical.lower()}
    for c in candidates:
        if shutil.which(c):
            return True
    dest = ARSENAL_DIR / canonical
    if dest.is_dir():
        ep = TOOL_ENTRYPOINTS.get(canonical)
        if ep:
            script = ep.split("|", 1)[0]
            if (dest / script).is_file():
                return True
        for pattern in ("*.py", "*.sh"):
            if any(dest.glob(pattern)):
                return True
    return False


# ════════════════════════════════════════════════════════════════════════
#  CONFIRMATION TEXT
# ════════════════════════════════════════════════════════════════════════
def describe_install(name: str) -> str:
    """
    Human-readable description of HOW a tool would be installed - shown on the
    confirmation prompt BEFORE anything runs.
    """
    tool = ARSENAL.get(resolve_name(name))
    if tool is None:
        return f"'{name}' is not in the arsenal. It would be attempted via apt/git."
    kind = tool.install_kind
    pkg = tool.package
    lines = [f"{tool.name}  ({tool.category})", tool.description, ""]
    if kind == "apt":
        if is_windows():
            wid = WIN_WINGET.get(tool.name)
            if wid:
                lines.append(f"Method : winget install {wid}")
            else:
                lines.append(f"Method : manual on Windows - see {tool.url or 'project page'}")
        else:
            lines.append(f"Method : apt-get install {pkg}")
            lines.append("Fallback: git clone + build if the apt package is missing")
    elif kind == "pip":
        pipcmd = (f"python -m pip install {pkg}" if is_windows()
                  else f"pip3 install {pkg} --break-system-packages")
        lines.append(f"Method : {pipcmd}")
        lines.append("Fallback: git clone + requirements if pip fails")
    elif kind == "git_go":
        lines.append(f"Method : git clone {tool.url} -> go build")
    elif kind == "git_python":
        lines.append(f"Method : git clone {tool.url} -> pip install requirements")
    else:  # git_generic
        lines.append(f"Method : git clone {tool.url} -> make/setup.sh/install.sh")
    dep = TOOL_DEPS.get(tool.name)
    if dep:
        lines.append(f"Prereqs: {dep}")
    if not is_root():
        lines.append("")
        lines.append("Note: not running as root - apt steps will try 'sudo -n'.")
    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════════
#  PREREQUISITES
# ════════════════════════════════════════════════════════════════════════
def _install_tool_deps(name: str, log: LogFn) -> None:
    dep_str = TOOL_DEPS.get(name)
    if not dep_str:
        return
    for group in dep_str.split("|"):
        gtype, _, pkgs = group.partition(":")
        items = [p for p in pkgs.split(",") if p]
        if gtype == "apt":
            for p in items:
                if not shutil.which(p):
                    _run(_sudo_prefix() + ["apt-get", "install", "-y", "-qq", p], log)
        elif gtype == "pip":
            _run(_pip(list(items)), log)
        elif gtype == "go":
            if shutil.which("go"):
                for p in items:
                    _run(["go", "install", "-v", p], log)


# ════════════════════════════════════════════════════════════════════════
#  POST-CLONE BUILD
# ════════════════════════════════════════════════════════════════════════
def _post_install(dest: Path, itype: str, log: LogFn) -> None:
    if itype == "git_python" and (dest / "requirements.txt").is_file():
        _run(_pip(["-r", str(dest / "requirements.txt")]), log)
    elif itype == "git_go" and (dest / "go.mod").is_file():
        if shutil.which("go"):
            _run(["go", "build", "./..."], log, cwd=dest)
    elif itype == "git_generic":
        # Best-effort build for the bulk catalog: Makefile, setup scripts,
        # a Go module, or a Python requirements/setup file - whichever exists.
        if (dest / "Makefile").is_file():
            _run(["make", "-s"], log, cwd=dest)
        elif (dest / "setup.sh").is_file():
            _run(["bash", "setup.sh"], log, cwd=dest)
        elif (dest / "install.sh").is_file():
            _run(["bash", "install.sh"], log, cwd=dest)
        elif (dest / "go.mod").is_file() and shutil.which("go"):
            _run(["go", "build", "./..."], log, cwd=dest)
        elif (dest / "requirements.txt").is_file():
            _run(_pip(["-r", str(dest / "requirements.txt")]), log)


def _git_clone(name: str, url: str, dest: Path, itype: str, log: LogFn) -> bool:
    if (dest / ".git").is_dir():
        log(f"[~] updating existing clone: {name}")
        _run(["git", "-C", str(dest), "pull", "-q"], log)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
        rc = _run(["git", "clone", "--depth=1", "-q", url, str(dest)], log)
        if rc != 0:
            log(f"[X] git clone failed: {name}")
            return False
    _install_tool_deps(name, log)
    _post_install(dest, itype, log)
    if itype in ("apt", "pip") and (dest / "requirements.txt").is_file():
        _run(_pip(["-r", str(dest / "requirements.txt")]), log)
    log(f"[OK] {name} installed via git")
    return True


# ════════════════════════════════════════════════════════════════════════
#  MAIN INSTALL  (caller must have confirmed first)
# ════════════════════════════════════════════════════════════════════════
def install_tool(name: str, log: Optional[LogFn] = None,
                 control: Optional[JobControl] = None) -> bool:
    """
    Install one arsenal tool. The caller is responsible for confirmation.
    Returns True if the tool ends up available. Pass a JobControl to make the
    install cancellable (STOP button).
    """
    global _active_control
    log = log or _noop
    _active_control = control
    try:
        return _install_tool_inner(name, log)
    finally:
        _active_control = None


def _install_tool_inner(name: str, log: LogFn) -> bool:
    canonical = resolve_name(name)
    tool: Optional[Tool] = ARSENAL.get(canonical)

    if tool is None:
        log(f"[X] '{name}' is not in the arsenal.")
        return False

    if is_available(canonical):
        log(f"[OK] {canonical} already available")
        return True

    dest = ARSENAL_DIR / canonical
    kind = tool.install_kind
    log(f"[~] Installing {canonical}  ({tool.itype})")

    if kind == "apt":
        if is_windows():
            wid = WIN_WINGET.get(canonical)
            if wid and shutil.which("winget"):
                rc = _run(["winget", "install", "-e", "--id", wid, "--silent",
                           "--accept-package-agreements", "--accept-source-agreements"], log)
                if rc == 0 and is_available(canonical):
                    log(f"[OK] {canonical} installed via winget")
                    return True
            log(f"[!] {canonical} has no automatic Windows installer here. "
                f"Install it manually: {tool.url or 'see the project page'}")
            return is_available(canonical)
        rc = _run(_sudo_prefix() + ["apt-get", "install", "-y", "-qq", tool.package], log)
        if rc == 0 and is_available(canonical):
            log(f"[OK] {canonical} installed via apt")
            return True
        if not tool.url:
            log(f"[X] apt failed for {tool.package} and no git fallback is defined.")
            return False
        log(f"[!] apt failed for {tool.package} - falling back to git clone")
        return _git_clone(canonical, tool.url, dest, "git_generic", log)

    if kind == "pip":
        rc = _run(_pip([tool.package]), log)
        if rc == 0:
            log(f"[OK] {canonical} installed via pip")
            return True
        log(f"[!] pip failed for {tool.package} - falling back to git clone")
        return _git_clone(canonical, tool.url, dest, "git_python", log)

    # git_python / git_go / git_generic
    ok = _git_clone(canonical, tool.url, dest, kind, log)
    return ok and is_available(canonical)
