#!/bin/zsh
# One-time setup of the reel pipeline on an Apple Silicon Mac (ADR-0005).
#   zsh pipeline/setup_mac.sh
# Installs Homebrew ffmpeg and uv if missing, creates .venv with the locked Python deps, installs the
# Chromium build the locked playwright pins (the subtitle renderer; Google Chrome is not needed), then
# downloads the models (whisper large-v3 ~3 GB, RVM resnet50 ~100 MB) so the first batch does not stall
# on downloads. Safe to re-run.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v brew >/dev/null; then
  echo "Homebrew is missing: install it from https://brew.sh first." >&2; exit 1
fi
brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg
command -v uv >/dev/null || brew install uv
ffmpeg -hide_banner -encoders 2>/dev/null | grep -q prores_ks || { echo "ffmpeg lacks prores_ks" >&2; exit 1; }

uv venv .venv --python 3.12 --allow-existing
VIRTUAL_ENV=.venv uv pip install -r pipeline/requirements.lock.txt
# stamp of the lock this .venv was built from; doctor.py compares it with the current lock after every pull
shasum -a 256 pipeline/requirements.lock.txt | cut -d' ' -f1 > .venv/reel-studio.lock.sha256
# the renderer: Playwright's own Chromium, pinned by the locked playwright version, so subtitles render the same
# until the lock changes (a self-updating Chrome would shift the text rendering)
.venv/bin/python -m playwright install chromium

.venv/bin/python - <<'EOF'
import torch
from faster_whisper import WhisperModel
WhisperModel("large-v3", device="cpu", compute_type="int8")
torch.hub.load("PeterL1n/RobustVideoMatting", "resnet50", trust_repo=True)
print("models ready; torch MPS:", torch.backends.mps.is_available())
EOF
echo "OK: run the pipeline with .venv/bin/python pipeline/<step>.py"
