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
Info "Installing core Python dependencies (customtkinter, psutil, Pillow)..."
& $py -m pip install --upgrade pip | Out-Null
& $py -m pip install -r requirements.txt
Ok "Core Python dependencies ready"

# --- Voice stack (mic + speech). pywin32 is required for spoken replies (SAPI5). ---
Info "Installing voice stack (faster-whisper, sounddevice, pyttsx3, pywin32)..."
try {
    & $py -m pip install -r requirements-voice.txt
    # pywin32 needs a post-install step to register its COM DLLs for SAPI5 TTS
    try { & $py -m pywin32_postinstall -install | Out-Null } catch { }
    Ok "Voice stack ready"
} catch {
    Warn "Voice stack failed - Voice Mode stays off until: $py -m pip install -r requirements-voice.txt"
}

# --- Image stack (optional, large: pulls in torch) ---
$ans = Read-Host "Install the text-to-image stack now? It pulls in torch (large). [y/N]"
if ($ans -match '^(y|yes)$') {
    Info "Installing image stack (diffusers, transformers, torch)..."
    try { & $py -m pip install -r requirements-image.txt; Ok "Image stack ready" }
    catch { Warn "Image stack failed - install later: $py -m pip install -r requirements-image.txt" }
} else {
    Info "Skipped image stack. Install later: $py -m pip install -r requirements-image.txt"
}

# --- Vision stack (optional, large: webcam object detection) ---
$vans = Read-Host "Install the webcam object-detection stack now? ultralytics + torch (large). [y/N]"
if ($vans -match '^(y|yes)$') {
    Info "Installing vision stack (ultralytics, opencv-python)..."
    try { & $py -m pip install -r requirements-vision.txt; Ok "Vision stack ready" }
    catch { Warn "Vision stack failed - install later: $py -m pip install -r requirements-vision.txt" }
} else {
    Info "Skipped vision stack. Install later: $py -m pip install -r requirements-vision.txt"
}

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
    Info "Pulling default model: qwen2.5:3b"
    try { ollama pull qwen2.5:3b } catch { Warn "Model pull failed - you can forge it from inside the app." }
}

Write-Host ""
Ok "Sk7ld-AI is ready."
Write-Host "  GUI     : .\run.bat" -ForegroundColor Cyan
Write-Host "  Headless: .\run.bat --cli" -ForegroundColor Cyan
Write-Host ""
