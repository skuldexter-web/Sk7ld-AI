"""
updater.py - self-update (git pull) and Linux system update (apt flow).

  * self_update()   - pulls the newest Sk7ld-AI from GitHub into the repo it is
                      running from. If the folder is NOT a git clone (e.g. it was
                      unzipped), it falls back to cloning the repo fresh into a
                      sibling folder. Caller confirms [Y/n] first.
  * system_update() - Linux: `apt update`, then ask to `apt upgrade -y`, then ask
                      to `apt autoremove`. Each step is confirmed via a callback.

Both stream command output to a `log` callback and respect a JobControl so the
STOP button can abort. When anonymous mode is on, git traffic is torified.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Callable, Optional

from . import __version__
from .osenv import is_windows
from . import anon

LogFn = Callable[[str], None]
ConfirmFn = Callable[[str, str], bool]
GITHUB_REPO = "https://github.com/skuldexter-web/sk7ld-ai.git"


def _noop(_: str) -> None:
    pass


def repo_dir() -> Path:
    """The folder Sk7ld-AI runs from (two levels up from this file)."""
    return Path(__file__).resolve().parents[1]


def is_git_repo(path: Optional[Path] = None) -> bool:
    path = path or repo_dir()
    return (path / ".git").is_dir()


def _run(argv: list, log: LogFn, cwd: Optional[Path] = None, control=None,
         timeout: int = 1800) -> int:
    log("$ " + " ".join(argv))
    try:
        proc = subprocess.Popen(argv, cwd=str(cwd) if cwd else None,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                text=True, bufsize=1, start_new_session=True)
    except FileNotFoundError:
        log(f"[X] command not found: {argv[0]}")
        return 127
    if control is not None:
        control.register(proc)
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            log(line.rstrip("\n"))
            if control is not None and control.cancelled:
                break
        if control is not None and control.cancelled:
            log("[!] stopped by operator")
            return 130
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        log("[X] timed out")
        return 124
    finally:
        if control is not None:
            control.clear_proc()
    return proc.returncode


def _sudo(argv: list) -> list:
    if is_windows() or (hasattr(os, "geteuid") and os.geteuid() == 0):
        return argv
    if shutil.which("sudo"):
        return ["sudo"] + argv
    return argv


# ════════════════════════════════════════════════════════════════════════
#  SELF-UPDATE
# ════════════════════════════════════════════════════════════════════════
def _unique_dir(base: Path, name: str) -> Path:
    """A not-yet-populated target dir under `base` (name, name-2, name-3, ...)."""
    target = base / name
    i = 2
    while target.exists() and (not target.is_dir() or any(target.iterdir())):
        target = base / f"{name}-{i}"
        i += 1
    return target


def self_update(log: Optional[LogFn] = None, confirm: Optional[ConfirmFn] = None,
                control=None) -> bool:
    log = log or _noop
    confirm = confirm or (lambda t, b: True)
    path = repo_dir()
    if not shutil.which("git"):
        log("[X] git is not installed. Install it first (e.g. sudo apt install git).")
        return False

    # ── in-place pull when we're running from a real git clone ──────────
    if is_git_repo(path):
        if not confirm("Update Sk7ld-AI?",
                       f"Pull the newest Sk7ld-AI from GitHub into:\n{path}\n\n"
                       f"Current version: v{__version__}\nThis runs 'git pull'."):
            log("[!] Update cancelled.")
            return False
        argv = anon.torify_argv(["git", "-C", str(path), "pull", "--ff-only"])
        rc = _run(argv, log, control=control)
        if rc == 0:
            log("[OK] Updated. Restart Sk7ld-AI to load the new version.")
            return True
        log("[X] Update failed (local changes or network). Resolve and retry.")
        return False

    # ── fallback: not a git checkout (unzipped) -> clone a fresh copy ────
    target = _unique_dir(path.parent, "sk7ld-ai")
    if not confirm("Clone the latest Sk7ld-AI?",
                   f"This folder isn't a git clone, so I can't update it in place.\n\n"
                   f"Clone the newest Sk7ld-AI from GitHub into:\n{target}\n\n"
                   f"When it finishes, run Sk7ld-AI from there - future updates will\n"
                   f"then work in place."):
        log("[!] Update cancelled.")
        return False
    argv = anon.torify_argv(["git", "clone", GITHUB_REPO, str(target)])
    rc = _run(argv, log, control=control)
    if rc == 0:
        log(f"[OK] Cloned the latest Sk7ld-AI to:\n    {target}")
        log(f"    Launch it from there, e.g.:  cd '{target}' && python3 sk7ld_ai.py")
        log("    (Future 'update yourself' runs will git-pull in place.)")
        return True
    log("[X] Clone failed (network or permissions). Resolve and retry.")
    return False


# ════════════════════════════════════════════════════════════════════════
#  SYSTEM UPDATE (Linux)
# ════════════════════════════════════════════════════════════════════════
def system_update(log: Optional[LogFn] = None, confirm: Optional[ConfirmFn] = None,
                  control=None) -> None:
    log = log or _noop
    confirm = confirm or (lambda t, b: True)
    if is_windows():
        log("[!] System update is a Linux feature (apt). On Windows use "
            "'winget upgrade --all' or Windows Update.")
        return
    if not shutil.which("apt-get"):
        log("[X] apt-get not found - this is a Debian/Kali feature.")
        return

    log("[~] Refreshing package lists (apt update)...")
    if _run(_sudo(["apt-get", "update"]), log, control=control) != 0 or \
            (control is not None and control.cancelled):
        return

    if confirm("Upgrade packages?", "apt update finished.\n\nRun 'apt upgrade -y' "
                                    "to install available upgrades?"):
        log("[~] Upgrading packages (apt upgrade -y)...")
        if _run(_sudo(["apt-get", "upgrade", "-y"]), log, control=control) != 0 or \
                (control is not None and control.cancelled):
            return
    else:
        log("[!] Upgrade skipped.")

    if confirm("Clean up?", "Run 'apt autoremove' to remove unused packages?"):
        log("[~] Removing unused packages (apt autoremove -y)...")
        _run(_sudo(["apt-get", "autoremove", "-y"]), log, control=control)
    else:
        log("[!] Autoremove skipped.")
    log("[OK] System update finished.")
