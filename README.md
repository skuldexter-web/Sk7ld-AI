<div align="center">

# ⚡ SK7LD-AI ⚡
### Digital Longship Intelligence System

**A multi-theme, local-AI GUI/CLI hybrid that orchestrates a full red-team arsenal — powered by Ollama.**

`SKALDSEC` · GitHub: **skuldexter-web** · Instagram: **@s.k.7.l.d**

</div>

---

Sk7ld-AI fuses two tools into one:

| Source project | What it brought |
|---|---|
| **Multi-Theme AI Terminal** (`skuld.py` / `ai_terminal.py`) | The 8-theme CustomTkinter chat front-end, Ollama model management, the "Forge New Model" installer. |
| **Viking AI** (`viking` / `install.sh`) | The weapon arsenal (~100 security tools), the apt→pip→go→git install engine, and natural-language tool dispatch. |

The result is a single desktop app whose chat window doesn't just *talk* about security tools — it **detects your intent, offers the right tools with descriptions, installs what's missing (only after you confirm), runs them, and feeds the output back to the local model for analysis.** The same engine runs headless in `--cli` mode.

---

## ✨ Features

- **Cozy frosted-glass UI** — floating rounded glass cards over a blurred, theme-tinted bokeh backdrop, with real window transparency (subtle see-through to your desktop on any compositor).
- **Hexagon system HUD** — the PC live feeds render as a honeycomb of hexagon ring-gauges (CPU · GPU · RAM · NET · DISK) around a live clock.
- **3 themes**: **`sk7ld`** (cyan-blue + purple neon, default), **`v1ru5`** (the original green neural node, with its hidden `@v1ru5_0` sidebar link), and **`baphomet`** (crimson + gold occult-cyber). Switch live from the sidebar.
- **Editable persona** — change Sk7ld-AI's system prompt from the sidebar (**Edit Persona**) or the CLI (`persona set ...`); it's saved to `~/.config/sk7ld-ai/config.json` and used on every chat.
- **Live weather feed** — current conditions + 3-day forecast in the HUD (via keyless wttr.in, IP-located; degrades to "offline" with no connection).
- **Live system feeds** — CPU, GPU, RAM and ethernet (up/down) throughput update every second, with bars that turn amber/red under load. Uses `psutil` when present, else parses `/proc` + `/sys` directly.
- **Local & private** — everything runs through your own Ollama node. No cloud, no keys.
- **Base models only**, default **`qwen2.5-coder:1.5b-base`**; forge heavier `7b` / `14b` / `32b` base variants from the sidebar.
- **Intent-driven tool orchestration** — type *"scan 10.0.0.5"* or *"find subdomains of example.com"* and Sk7ld-AI asks **which tool** you want, each with a one-line description.
- **Confirm-before-install** — any missing tool or dependency shows exactly *how* it would be installed (apt / pip / go / git) and installs **only on your explicit yes**.
- **Scan → AI analysis loop** — capture-style tools stream their output into the chat, then offer a tactical breakdown from the model.
- **RTL-SDR / war-driving ready** — dump1090, rtl_433, gqrx, URH, multimon-ng and more are first-class arsenal entries.
- **1,700+ BlackArch tools on tap** — a bundled catalog (`sk7ldai/data/blackarch.json`) merges the BlackArch repo into the arsenal, filtered to tools that run on Kali/Debian (upstream git source available; language-libraries, config packages, source-less and Windows/.NET-only packages removed) and de-duped against the curated set. Each installs on-demand via upstream git clone, with the same confirm-before-install gate.
- **GUI _and_ CLI** from one engine — same orchestration over SSH with `--cli`.

---

## 🚀 Install

```bash
git clone https://github.com/skuldexter-web/Sk7ld-AI.git
cd Sk7ld-AI
sudo bash install.sh
```

The bootstrap installs Python + CustomTkinter, Ollama, and pulls the default base model. It does **not** mass-install offensive tools — those install on-demand, with your confirmation, from inside the app.

Manual route:

```bash
pip install -r requirements.txt      # or: pip install .
# make sure Ollama is running:  ollama serve
```

---

## 🖥️ Usage

```bash
python3 sk7ld_ai.py          # GUI
python3 sk7ld_ai.py --cli     # headless terminal mode
sk7ld-ai                      # if install.sh made the launcher
```

**Talk to it like an operator:**

| You type | Sk7ld-AI does |
|---|---|
| `scan 192.168.1.10` | offers nmap / RustScan / naabu / masscan → runs → analyses |
| `check example.com for vulns` | offers nuclei / nikto |
| `find subdomains of example.com` | offers subfinder / amass / theHarvester / dnsx |
| `dir scan https://target/` | offers ffuf / feroxbuster / gobuster / dirsearch |
| `crack this hash` | offers hashcat / john / hydra (launched in a terminal) |
| `wifi audit` | offers wifite / OneShot / bettercap / hcxdumptool |
| `track aircraft` | launches dump1090 ADS-B radar |
| *anything else* | plain chat with the VIKING persona |

Scan-style tools stream their output into the chat; interactive TUIs/GUIs (metasploit, wifite, gqrx…) open in a new terminal window.

---

## 🧱 Architecture

```
Sk7ld-AI/
├── sk7ld_ai.py              # launcher  (GUI by default, --cli flag)
├── install.sh                   # system bootstrap (deps + Ollama + model)
├── sk7ldai/
│   ├── themes.py                # the 8 themes + sidebar social links
│   ├── arsenal.py               # tool registry, aliases, entrypoints, INTENT map
│   ├── themes.py                # 3 themes (sk7ld / v1ru5 / baphomet)
│   ├── config.py                # persisted settings (editable persona)
│   ├── gui/visuals.py           # hexagon honeycomb + ambient backdrop
│   ├── feeds.py                 # live system stats + weather for the HUD
│   ├── control.py               # JobControl - cancel/STOP for running jobs
│   ├── data/blackarch.json      # 1,700+ BlackArch tools, Kali-filtered + de-duped
│   ├── ollama_client.py         # stdlib Ollama wrapper (list/pull/generate/chat)
│   ├── installer.py             # apt→pip→go→git install engine (confirm-gated)
│   ├── runner.py                # launch tools: capture vs. interactive terminal
│   ├── orchestrator.py          # intent → choose tool → confirm install → run
│   ├── cli.py                   # headless REPL (same engine as the GUI)
│   └── gui/
│       ├── app.py               # main CustomTkinter window
│       └── dialogs.py           # tool chooser · install confirm · forge model
└── assets/sk7ld-ai.desktop  # desktop launcher entry
```

**The flow** (`orchestrator.py`): `plan(text)` detects an intent and extracts the target → the UI shows the candidate `ToolAction`s → on selection, `run_action()` checks availability, and if the tool is missing it calls the **confirm-install gate** before `installer.install_tool()` runs → then `runner` either streams captured output or launches the tool interactively.

---

## 🎨 Themes & Models

- Switch themes live from the sidebar dropdown;
- **Model** dropdown lists your installed Ollama tags; **Ping Models** refreshes them; **Forge New Model** pulls base models (`1.5b` → `32b`). Streaming pull progress prints into the chat.

---

## ⚠️ Authorized use only

Sk7ld-AI is built for **professional penetration testing, red-team engagements, research, and education on systems you own or are explicitly authorized to test**. You are responsible for complying with all applicable laws and for having written permission before testing any target. The authors assume no liability for misuse.

---

<div align="center">

*The longship is crewed. The raid begins.* **Skål.**

MIT © SKALDSEC · @s.k.7.l.d

</div>
