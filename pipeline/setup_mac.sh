#!/bin/zsh
# One-time setup of the reel pipeline on an Apple Silicon Mac (ADR-0005).
#   zsh pipeline/setup_mac.sh
# Installs Homebrew ffmpeg and uv if missing, checks Google Chrome, creates .venv with the locked Python
# deps, then downloads the models (whisper large-v3 ~3 GB, RVM resnet50 ~100 MB) so the first batch
# does not stall on downloads. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v brew >/dev/null; then
  echo "Homebrew is missing: install it from https://brew.sh first." >&2; exit 1
fi
brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg
command -v uv >/dev/null || brew install uv
ffmpeg -hide_banner -encoders 2>/dev/null | grep -q prores_ks || { echo "ffmpeg lacks prores_ks" >&2; exit 1; }

if [[ ! -d "/Applications/Google Chrome.app" ]]; then
  echo "Google Chrome is missing (the subtitle renderer drives it headless): install it from google.com/chrome" >&2
  exit 1
fi

uv venv .venv --python 3.12 --allow-existing
VIRTUAL_ENV=.venv uv pip install -r pipeline/requirements.lock.txt

.venv/bin/python - <<'EOF'
import torch
from faster_whisper import WhisperModel
WhisperModel("large-v3", device="cpu", compute_type="int8")
torch.hub.load("PeterL1n/RobustVideoMatting", "resnet50", trust_repo=True)
print("models ready; torch MPS:", torch.backends.mps.is_available())
EOF
echo "OK: run the pipeline with .venv/bin/python pipeline/<step>.py"
