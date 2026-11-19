# ============================================================
#  Sk7ld-AI - Windows bootstrap (PowerShell)
#  Installs Python deps, optionally Ollama (via winget), and pulls
#  the default base model. Security tools install on-demand from
#  inside the app, always after your confirmation.
#
#  Run from this folder:
#     powershell -ExecutionPolicy Bypass -File .\install.ps1
# ============================================================
$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $here

function Info($m){ Write-Host "[~] $m" -ForegroundColor Cyan }
function Ok($m){   Write-Host "[OK] $m" -ForegroundColor Green }
function Warn($m){ Write-Host "[!] $m" -ForegroundColor Yellow }

Write-Host ""
Write-Host "  SK7LD-AI  //  Windows setup" -ForegroundColor Magenta
Write-Host ""

# --- Python ---
$py = $null
foreach ($c in @("py","python")) {
    if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break }
}
if (-not $py) {
    Warn "Python not found. Install Python 3.9+ from https://python.org or: winget install Python.Python.3.12"
    exit 1
}
Ok "Using Python: $py"

# --- Python dependencies ---
Info "Installing Python dependencies (customtkinter, psutil, Pillow)..."
& $py -m pip install --upgrade pip | Out-Null
& $py -m pip install -r requirements.txt
Ok "Python dependencies ready"

# --- Ollama ---
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Ok "Ollama already installed"
} else {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Info "Installing Ollama via winget..."
        try { winget install -e --id Ollama.Ollama --silent --accept-package-agreements --accept-source-agreements } catch { Warn "winget install failed - get it from https://ollama.com/download" }
    } else {
        Warn "Install Ollama from https://ollama.com/download, then re-run this script."
    }
}

# --- default model ---
if (Get-Command ollama -ErrorAction SilentlyContinue) {
    Info "Pulling default base model: qwen2.5-coder:1.5b-base"
    try { ollama pull qwen2.5-coder:1.5b-base } catch { Warn "Model pull failed - you can forge it from inside the app." }
}

Write-Host ""
Ok "Sk7ld-AI is ready."
Write-Host "  GUI     : .\run.bat" -ForegroundColor Cyan
Write-Host "  Headless: .\run.bat --cli" -ForegroundColor Cyan
Write-Host ""
