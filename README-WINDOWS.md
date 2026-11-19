# Sk7ld-AI — Windows build

This is the Windows edition of Sk7ld-AI. It's the same engine as the Linux build,
with the OS-specific bits handled for you:

- **Only Windows-capable tools** are exposed in the arsenal and in the chat
  tool-chooser (cross-platform Python/Go tools + apt tools that ship official
  Windows builds). Linux-only categories — Wi-Fi injection, Bluetooth, Tor
  anonymity — are filtered out. The full included list is in
  [`windows_tools.txt`](windows_tools.txt) (**1,131** tools).
- **Install paths** use `%LOCALAPPDATA%\Sk7ld-AI` (no `/opt`, no `sudo`).
- **Package managers**: pip and `go`/`git` work as-is; apt tools with a known
  winget id install via **winget**, the rest show a manual-install note with the
  project link.
- **Interactive tools** open in **Windows Terminal** (`wt`) if present, otherwise
  a new `cmd` window.
- **Window transparency** and the frosted-glass look work natively on Windows.

> Best-effort note: perfectly classifying 1,700+ upstream projects as
> Windows-compatible isn't possible from metadata, so the filter errs toward
> excluding the obviously-Linux ones. A listed tool may still need Npcap, Go, or
> a C toolchain — install those if a build step asks for it.

## Requirements

- **Python 3.9+** — <https://python.org> (or `winget install Python.Python.3.12`)
- **Ollama for Windows** — <https://ollama.com/download> (the installer below can
  fetch it via winget)

## Setup

From this folder, in PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

That installs the Python dependencies (CustomTkinter, psutil, Pillow), installs
Ollama if winget is available, and pulls the default base model.

## Run

```bat
run.bat            :: GUI
run.bat --cli      :: headless terminal mode
```

Everything else — themes (`sk7ld`, `v1ru5`, `Cvlt of Baph0mau5`), Edit Persona,
Code Mode, the weather + hexagon system HUD, and the confirm-before-install gate
— works exactly as in the main [README](README.md).
