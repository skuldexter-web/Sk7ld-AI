"""
cli.py - Sk7ld-AI headless / terminal mode.

A text REPL that drives the exact same orchestration engine as the GUI, so the
project is a true GUI/CLI hybrid. Useful over SSH or on headless boxes.

Built-ins:  help · quit · status · models · model <name> · arsenal ·
            target <x> · target clear
Everything else is classified: on a tool intent you are shown the candidate
tools (with descriptions) and asked which to run; missing tools confirm before
install; scan output can be analysed by the local model.
"""

from __future__ import annotations

import sys
from typing import Optional

from . import DEFAULT_MODEL, OLLAMA_BASE_URL, __version__
from . import orchestrator
from .orchestrator import analysis_prompt
from .ollama_client import OllamaClient
from . import arsenal
from .installer import is_available, describe_install

# ANSI colors
R = "\033[0;31m"; G = "\033[0;32m"; C = "\033[0;36m"
Y = "\033[1;33m"; B = "\033[1m"; D = "\033[2m"; NC = "\033[0m"

BANNER = f"""{Y}{B}
  ███████ ██    ██ ██████  ███████ ██████
  ██      ██    ██ ██   ██ ██      ██   ██   SK7LD-AI
  ███████ ██    ██ ██████  █████   ██████    Digital Longship v{__version__}
       ██ ██    ██ ██      ██      ██   ██   SKALDSEC · @s.k.7.l.d
  ███████  ██████  ██      ███████ ██   ██
{NC}{D}  GUI/CLI hybrid · local Ollama · arsenal orchestration{NC}
"""


class VikingCLI:
    def __init__(self):
        from . import config
        self.client = OllamaClient(OLLAMA_BASE_URL, DEFAULT_MODEL)
        self.client.system_prompt = config.get_system_prompt()   # load saved persona
        self.target: Optional[str] = None

    # ── helpers ─────────────────────────────────────────────────────────
    def _confirm(self, title: str, body: str) -> bool:
        print(f"\n{Y}  {title}{NC}")
        for line in body.splitlines():
            print(f"  {D}{line}{NC}")
        ans = input(f"  {Y}Proceed? [y/N]: {NC}").strip().lower()
        return ans == "y"

    def _log(self, line: str):
        print(f"  {line}")

    def _stream_chat(self, prompt: str):
        print(f"{G}", end="", flush=True)
        for token in self.client.chat_stream(prompt):
            sys.stdout.write(token)
            sys.stdout.flush()
        print(f"{NC}\n")

    # ── built-ins ───────────────────────────────────────────────────────
    def _status(self):
        up = "online" if self.client.is_up() else "offline"
        print(f"\n  Model  : {G}{self.client.model}{NC}")
        print(f"  Target : {G}{self.target or 'none'}{NC}")
        print(f"  Ollama : {up}\n")

    def _models(self):
        models = self.client.list_models() or []
        print(f"\n{B}{Y}  Installed models:{NC}")
        for m in models:
            star = f" {G}<- active{NC}" if m == self.client.model else ""
            print(f"  {C}-{NC} {m}{star}")
        print()

    def _arsenal(self):
        print(f"\n{B}{Y}  WEAPON ARSENAL{NC}")
        for cat, names in arsenal.CATEGORIES.items():
            print(f"\n  {B}{C}-- {cat} --{NC}")
            for name in names:
                tag = f"{G}[installed]{NC}" if is_available(name) else f"{D}[ ]{NC}"
                print(f"    {tag} {name}")
        print()

    def _help(self):
        print(f"""
{B}{Y}  SK7LD-AI COMMANDS{NC}
  {C}help{NC}                 this menu
  {C}status{NC}               model / target / ollama status
  {C}models{NC}               list installed models
  {C}model <name>{NC}         switch active model
  {C}arsenal{NC}              list the weapon arsenal + install status
  {C}target <ip/url>{NC}      lock a default target
  {C}target clear{NC}         clear the locked target
  {C}persona{NC}              show the current persona (system prompt)
  {C}persona set <text>{NC}   set a new persona
  {C}persona reset{NC}        restore the default persona
  {C}quit{NC}                 leave

  Anything else is classified: 'scan 10.0.0.5', 'subdomains of site.com',
  'check site.com for vulns', 'crack this hash', or just chat.
""")

    # ── intent handling ─────────────────────────────────────────────────
    def _handle_intent(self, text: str, plan: orchestrator.Plan):
        tgt = plan.target or self.target
        print(f"\n{B}{Y}  Intent: {plan.intent.label}{NC}"
              + (f"   {D}target: {tgt}{NC}" if tgt else ""))
        for i, (action, avail) in enumerate(plan.options, 1):
            tag = f"{G}[installed]{NC}" if avail else f"{D}[missing]{NC}"
            mode = "live" if action.mode == "interactive" else "scan"
            print(f"  {C}[{i}]{NC} {B}{action.tool}{NC} {tag} {D}({mode}){NC}")
            print(f"       {action.desc}")
        print(f"  {C}[c]{NC} Just chat with the AI instead")
        print(f"  {C}[0]{NC} Cancel")

        choice = input(f"\n  {Y}Choose: {NC}").strip().lower()
        if choice in ("0", ""):
            return
        if choice == "c":
            self._stream_chat(text)
            return
        if not choice.isdigit() or not (1 <= int(choice) <= len(plan.options)):
            print(f"  {R}Invalid choice.{NC}")
            return

        action = plan.options[int(choice) - 1][0]

        # Ask for a target if needed and none known.
        if orchestrator.needs_target(action) and not tgt:
            tgt = input(f"  {Y}Target ({plan.intent.target_kind}): {NC}").strip() or None
        if tgt:
            self.target = tgt

        from .control import JobControl
        control = JobControl()
        print(f"  {D}(press Ctrl-C to stop the running tool){NC}")
        try:
            output = orchestrator.run_action(action, tgt, self._log,
                                             confirm_install=self._confirm,
                                             control=control)
        except KeyboardInterrupt:
            control.cancel()
            print(f"\n  {Y}[!] stopped by operator.{NC}")
            return
        if control.cancelled:
            return
        if output and action.mode != "interactive":
            if input(f"\n  {Y}Analyse output with {self.client.model}? [Y/n]: {NC}").strip().lower() != "n":
                print()
                self._stream_chat(analysis_prompt(action.tool, tgt, output))

    # ── main loop ───────────────────────────────────────────────────────
    def run(self):
        print(BANNER)
        if not self.client.is_up():
            print(f"{R}  [!] Ollama node not reachable at {OLLAMA_BASE_URL}.{NC}")
            print(f"{D}      Start it with: ollama serve{NC}\n")
        self._help()

        while True:
            try:
                prompt_str = (f"{Y}viking{NC}{D}[{self.target}]{NC}{Y}> {NC}"
                              if self.target else f"{Y}viking> {NC}")
                text = input(prompt_str).strip()
            except (EOFError, KeyboardInterrupt):
                print("\n  The longship returns to port. Skal.\n")
                break
            if not text:
                continue

            low = text.lower()
            if low in ("quit", "exit", "/bye"):
                print("\n  The longship returns to port. Skal.\n")
                break
            if low == "help":
                self._help(); continue
            if low == "status":
                self._status(); continue
            if low == "models":
                self._models(); continue
            if low == "arsenal":
                self._arsenal(); continue
            if low == "target clear":
                self.target = None; print("  [OK] target cleared"); continue
            if low.startswith("model "):
                self.client.model = text.split(None, 1)[1].strip()
                print(f"  [OK] model -> {self.client.model}"); continue
            if low.startswith("target "):
                self.target = text.split(None, 1)[1].strip()
                print(f"  [OK] target locked: {self.target}"); continue
            if low == "persona":
                print(f"\n  {C}Current persona:{NC}\n  {self.client.system_prompt}\n")
                continue
            if low == "persona reset":
                from . import config
                config.reset_system_prompt()
                from .ollama_client import DEFAULT_SYSTEM_PROMPT
                self.client.system_prompt = DEFAULT_SYSTEM_PROMPT
                print("  [OK] persona reset to default"); continue
            if low.startswith("persona set "):
                from . import config
                new = text.split(None, 2)[2].strip()
                self.client.system_prompt = new
                ok = config.set_system_prompt(new)
                print("  [OK] persona updated" if ok
                      else "  [OK] persona updated (session only; config not writable)")
                continue

            plan = orchestrator.plan(text)
            if plan is None:
                self._stream_chat(text)
            else:
                self._handle_intent(text, plan)


def main():
    VikingCLI().run()


if __name__ == "__main__":
    main()
