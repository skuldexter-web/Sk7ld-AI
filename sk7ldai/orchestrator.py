"""
orchestrator.py - the brain that turns a chat prompt into a tool run.

Flow (UI-agnostic; GUI and CLI both drive it):

  1. plan(text)          -> detect intent + extract target + list candidate
                            ToolActions with their availability.
  2. (UI asks the operator which tool - showing each action's description)
  3. run_action(...)     -> if the tool is missing, call the confirm_install
                            callback FIRST; only install on an explicit yes;
                            then capture-run (stream output) or launch
                            interactively.
  4. analysis_prompt(...) -> build a prompt so the UI can ask the local LLM to
                            analyse captured output.

The confirm_install callback is the single enforcement point for the rule
"always prompt before installing anything".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

from . import arsenal
from .arsenal import Intent, ToolAction
from . import installer
from . import runner
from .control import JobControl

LogFn = Callable[[str], None]
ConfirmFn = Callable[[str, str], bool]   # (title, body) -> yes/no


@dataclass
class Plan:
    intent: Intent
    target: Optional[str]
    # (action, is_available) pairs in offer order
    options: List[Tuple[ToolAction, bool]]


def plan(text: str) -> Optional[Plan]:
    """Return a Plan if the text maps to a tool intent, else None (plain chat)."""
    intent = arsenal.detect_intent(text)
    if intent is None:
        return None
    target = arsenal.extract_target(text, intent.target_kind)
    options = [(a, installer.is_available(a.tool)) for a in intent.actions]
    return Plan(intent=intent, target=target, options=options)


def needs_target(action: ToolAction) -> bool:
    """True if any arg template references {target}."""
    return any("{target}" in tok for tok in action.cmd)


def run_action(
    action: ToolAction,
    target: Optional[str],
    log: LogFn,
    confirm_install: ConfirmFn,
    control: Optional[JobControl] = None,
) -> Optional[str]:
    """
    Execute one ToolAction.

    Returns captured output text for capture-mode tools (for optional AI
    analysis), or None for interactive tools / aborted runs. Pass a JobControl
    to make the install + run cancellable via the STOP button.
    """
    canonical = arsenal.resolve_name(action.tool)

    if control is not None and control.cancelled:
        log("[!] cancelled before start.")
        return None

    # ── 1. Missing-tool gate: ALWAYS confirm before installing ──────────
    if not installer.is_available(canonical):
        body = installer.describe_install(canonical)
        if not confirm_install(f"Install {canonical}?", body):
            log(f"[!] {canonical} not installed - run skipped.")
            return None
        log(f"[~] Installing {canonical} (operator confirmed)...")
        ok = installer.install_tool(canonical, log, control=control)
        if control is not None and control.cancelled:
            log("[!] install stopped by operator.")
            return None
        if not ok or not installer.is_available(canonical):
            log(f"[X] {canonical} still unavailable after install attempt.")
            return None

    # ── 2. Build argv ───────────────────────────────────────────────────
    if needs_target(action) and not target:
        log(f"[X] {canonical} needs a target (IP / URL / domain). None found.")
        return None

    argv, msg = runner.build_argv(action, target)
    if argv is None:
        log(f"[X] {msg}")
        return None

    if action.note:
        log(f"[i] {action.note}")

    # ── 3. Dispatch ─────────────────────────────────────────────────────
    if action.mode == "interactive":
        runner.run_interactive(argv, log)
        return None

    log(f"[~] Running {canonical}" + (f" -> {target}" if target else ""))
    output = runner.run_capture(argv, log, control=control)
    return output


def analysis_prompt(tool: str, target: Optional[str], output: str) -> str:
    """Prompt the LLM to analyse a captured scan, VIKING-style."""
    tgt = target or "the target"
    snippet = output[:1800]
    return (
        f"{tool} scan of {tgt}. Analyse the output: key findings, risk level, "
        f"notable open ports/services/endpoints, and the recommended next "
        f"command. Be tactical and concise.\n\nOutput:\n{snippet}"
    )
