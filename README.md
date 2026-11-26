<div align="center">

# ⚡ SK7LD-AI ⚡
### Digital Longship Intelligence System

**A local-AI red-team agent for Kali Linux (and Windows) — multi-theme GUI/CLI, powered by Ollama.**

`SK7LD` · GitHub: **skuldexter-web** · Instagram: **@s.k.7.l.d**

</div>

---

**SK7LD-AI is an AI agent for offensive security.** It's built for **red teamers, penetration testers, cybersecurity personnel and white-hat hackers** working on systems they're authorised to test. It runs primarily on **Kali Linux** (and, to a lesser extent, **Windows**), fully local through your own Ollama node.

The chat window doesn't just *talk* about security tools — it **detects your intent, offers the right tools with descriptions, installs what's missing (only after you confirm), runs them, and feeds the output back to the local model for analysis.** You can also talk to it, have it generate code or images, route its traffic through Tor, and let it update itself and the system.

> ⚠️ **Authorised use only.** SK7LD-AI is for legal, in-scope engagements and education. You are responsible for staying in scope and complying with the law.

---

## ✨ Features

### Agent & interface
- **Red-team AI agent** — understands the goal, suggests the next concrete step/command, and orchestrates the right arsenal tool when it helps.
- **Cozy frosted-glass UI** — floating rounded glass cards over a blurred, theme-tinted bokeh backdrop, with real window transparency.
- **Hexagon system HUD** — PC live feeds as a honeycomb of hexagon ring-gauges (CPU · GPU · RAM · NET · DISK) around a live clock, plus a live weather feed.
- **5 themes**: **`sk7ld`** (cyan + purple, default), **`v1ru5`** (green neural node), **`Cvlt of Baph0mau5`** (crimson + gold), **`black and white`** (monochrome dark) and **`white and black`** (monochrome light). Switch live from the sidebar.

### New in this build
- **🛡️ Authorised-use disclaimer** — a one-time gate on first launch states the rules of engagement (own/authorised targets only). Accept once (**I AGREE — ENTER**) and it's remembered; **Decline & Exit** closes the app.
- **🎤 Voice mode** — talk to SK7LD-AI and hear it reply. Listening uses **Whisper** (dropdown: `tiny`→`large-v3`, default **`base`** so it won't blow up your PC); speaking uses **Piper voices** or your OS voices. Pull heavier listening/speaking models from the dropdowns. *(Optional audio stack — see Install.)*
- **🗣️ Wake word "Hey Scot"** — in Voice mode, SK7LD-AI listens for its name. Say *"Hey Scot, scan 10.0.0.5"* and it wakes, strips the name and runs the command. Wake listening is **only** active in Voice mode (never in CLI).
- **🪐 Animated voice orb — one per theme** — an orb appears over the console while it works, with **two distinct motions**: **calm & slow** when **listening**, **faster, pulsing & morphing** when **speaking**. Each theme gets its *own* shape, auto-tinted to its colours:
  - **`sk7ld`** → the **SK7LD viking** — the official horned-helmet warrior (ridged dome + flame crest, studded band, furrowed brow, braided beard) inside a spinning code-ring.
  - **`v1ru5`** → the **V1RU5 virus** 🦠 — the official spiky capsid with glowing-green angry eyes and a fanged, dripping grin; spikes jab and the maw opens as it talks.
  - **`Cvlt of Baph0mau5`** → an **occult sigil** — ritual rings, a hexagram, an inverted pentagram and a horned XX-eyed goat glyph (flame flickers while speaking).
  - **`black and white` / `white and black`** → the **plexus globe** (rotating wireframe sphere).
- **🖼️ Text-to-image** — generate images from a prompt. Default is a **small** model (`tiny-sd`); switch to bigger ones (`sd-turbo`, `SD 1.5`, `SDXL`) from the dropdown, downloaded on first use. *(Optional image stack — GPU recommended.)*
- **🧅 Anonymous mode (Tor)** — one switch routes SK7LD-AI's outbound traffic (public-IP check, weather, self-update) through the Tor SOCKS tunnel. Ollama stays local.
- **🌐 Public-IP indicator** — top-right, above the weather: your public IP with a **red blinking dot** and *"PUBLIC IP VISIBLE"*. Turn on anonymous mode and it flips to the **Tor exit IP** with a **green blinking dot** and *"SAFE — ANONYMOUS"*.
- **🧱 System update (Linux)** — say *"system update"* and it runs `apt update`, then asks **[Y/n]** to `apt upgrade -y`, then **[Y/n]** to `apt autoremove`.
- **♻️ Self-update** — say *"update yourself"* and it `git pull`s the newest repo into place (after your **[Y/n]**), then restart to load it. If you **unzipped** instead of cloning (no `.git`), it offers to **clone a fresh copy** next to the current folder so updates work from then on. Pulls from `github.com/skuldexter-web/sk7ld-ai`.

### Core
- **Editable persona** — change Sk7ld-AI's system prompt from the sidebar (**Edit Persona**) or the CLI (`persona set ...`); it's saved to `~/.config/sk7ld-ai/config.json` and used on every chat.
- **Code Mode** — flip the sidebar switch (or `code` in the CLI) and every prompt becomes a code/script request; generated code streams in, then **Save Code** writes it out with the right extension.
- **Runs on Windows too** — the same engine auto-detects the OS and, on Windows, exposes only Windows-capable tools and uses Windows install/launch paths. A ready-to-run Windows build ships as `Sk7ld-AI-Windows.zip`.
- **Live weather feed** — current conditions + 3-day forecast in the HUD (via keyless wttr.in, IP-located; degrades to "offline" with no connection).
- **Live system feeds** — CPU, GPU, RAM and ethernet (up/down) throughput update every second, with bars that turn amber/red under load. Uses `psutil` when present, else parses `/proc` + `/sys` directly.
- **Local & private** — everything runs through your own Ollama node. No cloud, no keys.
- **Small instruct models**, default **`qwen2.5:3b`** (coherent for chat + voice; base/completion models loop and echo in a conversation); forge heavier `7b` / `14b` / `32b` variants from the sidebar.
- **Intent-driven tool orchestration** — type *"scan 10.0.0.5"* or *"find subdomains of example.com"* and Sk7ld-AI asks **which tool** you want, each with a one-line description.
- **Confirm-before-install** — any missing tool or dependency shows exactly *how* it would be installed (apt / pip / go / git) and installs **only on your explicit yes**.
- **Scan → AI analysis loop** — capture-style tools stream their output into the chat, then offer a tactical breakdown from the model.
- **RTL-SDR / war-driving ready** — dump1090, rtl_433, gqrx, URH, multimon-ng and more are first-class arsenal entries.
- **1,700+ BlackArch tools on tap** — a bundled catalog (`sk7ldai/data/blackarch.json`) merges the BlackArch repo into the arsenal, filtered to tools that run on Kali/Debian (upstream git source available; language-libraries, config packages, source-less and Windows/.NET-only packages removed) and de-duped against the curated set. Each installs on-demand via upstream git clone, with the same confirm-before-install gate.
- **GUI _and_ CLI** from one engine — same orchestration over SSH with `--cli`.

---

## 🚀 Install

One repo runs on **both Linux and Windows** — the same engine auto-detects the OS and adapts its tools, paths and installers.

**Linux / Kali / Debian**

```bash
git clone https://github.com/skuldexter-web/sk7ld-ai.git
cd Sk7ld-AI
sudo bash install.sh
```

**Windows** (PowerShell, in the repo folder)

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

See [`README-WINDOWS.md`](README-WINDOWS.md) for the Windows specifics (it exposes only Windows-capable tools — the full list is in [`windows_tools.txt`](windows_tools.txt)).

The bootstrap installs Python + CustomTkinter + psutil + Pillow, the **voice stack** (faster-whisper, sounddevice, pyttsx3 + the audio drivers: PortAudio, eSpeak-NG, ffmpeg on Linux / pywin32 on Windows), optionally the **image stack** (diffusers + torch), installs Ollama, and pulls the default model. It does **not** mass-install offensive tools — those install on-demand, with your confirmation, from inside the app.

Manual route (either OS):

```bash
pip install -r requirements.txt      # or: pip install .
# make sure Ollama is running:  ollama serve
```

### Optional extras

These power the new heavy features and are **not** installed by default (they're large):

```bash
# Voice mode (microphone + spoken replies)
pip install -r requirements-voice.txt

# Text-to-image generation (GPU strongly recommended; pick your torch build)
pip install -r requirements-image.txt

# Anonymous mode (Tor), Linux:
sudo apt install -y tor torsocks
```

If an extra isn't installed, its control simply shows an "install: …" hint — the rest of the app runs fine.

---

## 🖥️ Usage

```bash
# Linux
python3 sk7ld_ai.py          # GUI
python3 sk7ld_ai.py --cli     # headless terminal mode
sk7ld-ai                      # if install.sh made the launcher

# Windows
run.bat                       # GUI
run.bat --cli                 # headless terminal mode
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
│   ├── themes.py                # the 5 themes + sidebar social links
│   ├── arsenal.py               # tool registry, aliases, entrypoints, INTENT map
│   ├── config.py                # persisted settings (persona + disclaimer flag)
│   ├── feeds.py                 # live system stats + weather for the HUD
│   ├── control.py               # JobControl - cancel/STOP for running jobs
│   ├── netinfo.py               # public-IP / Tor-exit-IP / geo lookups
│   ├── anon.py                  # anonymous mode — Tor SOCKS tunnel control
│   ├── updater.py               # self-update (git pull) + Linux system update
│   ├── voice.py                 # STT/TTS engine + "Hey Scot" wake word (English-only)
│   ├── imagegen.py              # text-to-image (diffusers, optional)
│   ├── data/blackarch.json      # 1,700+ BlackArch tools, Kali-filtered + de-duped
│   ├── ollama_client.py         # stdlib Ollama wrapper (list/pull/generate/chat)
│   ├── installer.py             # apt→pip→go→git install engine (confirm-gated)
│   ├── runner.py                # launch tools: capture vs. interactive terminal
│   ├── orchestrator.py          # intent → choose tool → confirm install → run
│   ├── cli.py                   # headless REPL (same engine as the GUI)
│   └── gui/
│       ├── app.py               # main CustomTkinter window
│       ├── visuals.py           # voice globe + hexagon honeycomb + backdrop
│       └── dialogs.py           # disclaimer · tool chooser · install · forge model
└── assets/sk7ld-ai.desktop  # desktop launcher entry
```

**The flow** (`orchestrator.py`): `plan(text)` detects an intent and extracts the target → the UI shows the candidate `ToolAction`s → on selection, `run_action()` checks availability, and if the tool is missing it calls the **confirm-install gate** before `installer.install_tool()` runs → then `runner` either streams captured output or launches the tool interactively.

---

## 🎨 Themes & Models

- Switch themes live from the sidebar, exactly as in the original.
- **Model** dropdown lists your installed Ollama tags; **Ping Models** refreshes them; **Forge New Model** pulls instruct models (`3b` → `32b`). Streaming pull progress prints into the chat.

---

## ⚠️ Authorized use only

Sk7ld-AI is built for **professional penetration testing, red-team engagements, research, and education on systems you own or are explicitly authorized to test**. You are responsible for complying with all applicable laws and for having written permission before testing any target. The authors assume no liability for misuse.

---

<div align="center">

*The longship is crewed. The raid begins.* **Skål.**

MIT © SK7LD · @s.k.7.l.d

</div>
