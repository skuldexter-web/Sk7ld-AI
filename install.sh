#!/bin/bash
# ================================================================
#  SK7LD-AI - bootstrap installer
#  Sets up the GUI/CLI hybrid: Python deps, Ollama, default base
#  model. The security arsenal installs on-demand from inside the
#  app (always with your confirmation) - this script does NOT mass-
#  install offensive tools.
#  Target: Debian / Kali / Ubuntu.  License: MIT  |  @s.k.7.l.d
# ================================================================
set -u

R='\033[0;31m'; G='\033[0;32m'; C='\033[0;36m'; Y='\033[1;33m'
B='\033[1m'; D='\033[2m'; NC='\033[0m'

DEFAULT_MODEL="qwen2.5:3b"
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_LINK="/usr/local/bin/sk7ld-ai"

ok()   { echo -e "${G}[OK]${NC} $*"; }
info() { echo -e "${C}[~]${NC} $*"; }
warn() { echo -e "${Y}[!]${NC} $*"; }
err()  { echo -e "${R}[X]${NC} $*" >&2; }
step() { echo -e "\n${B}${C}-- $* --${NC}"; }

banner() {
  clear
  echo -e "${Y}${B}"
  echo "  ███████ ██    ██ ██████  ███████ ██████"
  echo "  ██      ██    ██ ██   ██ ██      ██   ██   SK7LD-AI"
  echo "  ███████ ██    ██ ██████  █████   ██████    Digital Longship"
  echo "       ██ ██    ██ ██      ██      ██   ██   SK7LD"
  echo "  ███████  ██████  ██      ███████ ██   ██   @s.k.7.l.d"
  echo -e "${NC}${D}  GUI/CLI hybrid local-AI security console${NC}\n"
}

need_root() {
  if [[ "$EUID" -ne 0 ]]; then
    warn "Some steps (apt, symlink) need root."
    warn "Re-run with: sudo bash install.sh   (or they'll be skipped)"
  fi
}

install_system_deps() {
  step "System dependencies"
  if ! command -v apt-get &>/dev/null; then
    warn "apt-get not found - skipping system packages (install python3, tk, git manually)."
    return
  fi
  local SUDO=""; [[ "$EUID" -ne 0 ]] && SUDO="sudo"
  $SUDO apt-get update -qq 2>/dev/null
  # core app + tor (anon) + audio drivers for the voice stack:
  #   portaudio19-dev -> sounddevice (mic),  libsndfile1 -> soundfile,
  #   espeak-ng       -> pyttsx3 spoken replies,  ffmpeg -> whisper decoding
  # core app + tor + audio drivers + usbutils (device scan) + OpenCV runtime libs
  DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq \
    python3 python3-pip python3-tk python3-venv git curl \
    build-essential tor torsocks \
    portaudio19-dev libportaudio2 libsndfile1 espeak-ng ffmpeg \
    usbutils libgl1 libglib2.0-0 2>/dev/null
  ok "System packages ready (tor, portaudio, espeak-ng, ffmpeg, usbutils, OpenCV libs)"
}

# pip wrapper that works on PEP-668 "externally managed" systems (Kali/Debian)
_pip() {
  pip3 install -q --break-system-packages "$@" 2>/dev/null \
    || pip3 install -q "$@" 2>/dev/null
}

install_python_deps() {
  step "Python dependencies"
  if _pip -r "$APP_DIR/requirements.txt"; then
    ok "Core Python deps installed (customtkinter, psutil, Pillow)"
  else
    err "pip install failed - try: pip3 install customtkinter"
  fi

  info "Installing voice stack (mic + speech)..."
  if _pip -r "$APP_DIR/requirements-voice.txt"; then
    ok "Voice stack installed (faster-whisper, sounddevice, pyttsx3)"
  else
    warn "Voice stack failed - Voice Mode will be disabled until you run:"
    warn "  pip3 install --break-system-packages -r requirements-voice.txt"
  fi

  step "Image stack (optional, large)"
  warn "The text-to-image stack pulls in torch and can be >2 GB."
  local _ans="n"
  if [[ -t 0 ]]; then
    read -r -p "  Install it now? [y/N] " _ans
  else
    warn "Non-interactive shell - skipping image stack."
  fi
  if [[ "${_ans,,}" == "y" || "${_ans,,}" == "yes" ]]; then
    info "Installing image stack (this can take a while)..."
    if _pip -r "$APP_DIR/requirements-image.txt"; then
      ok "Image stack installed (diffusers, transformers, torch)"
    else
      warn "Image stack failed - install later with:"
      warn "  pip3 install --break-system-packages -r requirements-image.txt"
    fi
  else
    info "Skipped. Install later with: pip3 install -r requirements-image.txt"
  fi

  step "Vision stack (object detection, optional, large)"
  warn "The webcam object-detection stack pulls in ultralytics + torch (large)."
  local _vans="n"
  if [[ -t 0 ]]; then
    read -r -p "  Install it now? [y/N] " _vans
  else
    warn "Non-interactive shell - skipping vision stack."
  fi
  if [[ "${_vans,,}" == "y" || "${_vans,,}" == "yes" ]]; then
    info "Installing vision stack (ultralytics, opencv)..."
    if _pip -r "$APP_DIR/requirements-vision.txt"; then
      ok "Vision stack installed (ultralytics, opencv-python)"
    else
      warn "Vision stack failed - install later with:"
      warn "  pip3 install --break-system-packages -r requirements-vision.txt"
    fi
  else
    info "Skipped. Install later with: pip3 install -r requirements-vision.txt"
  fi
}

install_ollama() {
  step "Ollama (local LLM runtime)"
  if command -v ollama &>/dev/null; then
    ok "Ollama already installed"
  else
    info "Installing Ollama..."
    if curl -fsSL https://ollama.com/install.sh | sh; then
      ok "Ollama installed"
    else
      err "Ollama install failed - see https://ollama.com/download"
      return
    fi
  fi
  systemctl enable ollama &>/dev/null || true
  systemctl start  ollama &>/dev/null || true
  local tries=5
  until curl -sf http://localhost:11434/ &>/dev/null || (( --tries == 0 )); do sleep 2; done
}

pull_default_model() {
  step "Default model: $DEFAULT_MODEL"
  if ! command -v ollama &>/dev/null; then
    warn "Ollama missing - skipping model pull."
    return
  fi
  if ollama list 2>/dev/null | awk '{print $1}' | grep -Fxq "$DEFAULT_MODEL"; then
    ok "Model already present"
  else
    info "Pulling $DEFAULT_MODEL (you can forge heavier models in-app)..."
    ollama pull "$DEFAULT_MODEL" || warn "Pull failed - retry from inside the app (Forge New Model)."
  fi
}

make_launcher() {
  step "Launcher"
  local SUDO=""; [[ "$EUID" -ne 0 ]] && SUDO="sudo"
  if [[ -w "$(dirname "$BIN_LINK")" ]] || [[ "$EUID" -eq 0 ]]; then
    cat > /tmp/sk7ld-ai.$$ << EOF
#!/bin/bash
exec python3 "$APP_DIR/sk7ld_ai.py" "\$@"
EOF
    $SUDO install -m 755 /tmp/sk7ld-ai.$$ "$BIN_LINK" 2>/dev/null \
      && ok "Run it anywhere with:  ${C}sk7ld-ai${NC}  (or ${C}sk7ld-ai --cli${NC})" \
      || warn "Could not create $BIN_LINK - launch with: python3 sk7ld_ai.py"
    rm -f /tmp/sk7ld-ai.$$
  else
    warn "No write access to /usr/local/bin - launch with: python3 sk7ld_ai.py"
  fi
}

done_banner() {
  echo ""
  echo -e "${B}${G}  Sk7ld-AI is ready.${NC}"
  echo -e "  GUI     : ${C}python3 sk7ld_ai.py${NC}   (or ${C}sk7ld-ai${NC})"
  echo -e "  Headless: ${C}python3 sk7ld_ai.py --cli${NC}"
  echo -e "  ${D}Arsenal tools install on-demand, always after your confirmation.${NC}"
  echo ""
}

main() {
  banner
  need_root
  install_system_deps
  install_python_deps
  install_ollama
  pull_default_model
  make_launcher
  done_banner
}

main "$@"
