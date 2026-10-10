# 0005 — Mac is the target platform; quality over speed

Status: Accepted (2026-10-10)

## Context

The pipeline was built on Windows. The creator uses a Mac M1 with 8 GB RAM, and the developer can lend his work
laptop; development moves to the developer's Mac M3 Pro. Speed is explicitly not a concern: a batch of reels
rendering overnight is fine.

## Decision

- macOS on Apple Silicon is the supported platform; develop and test on the M3 Pro.
- Use full-quality models (whisper large-v3; consider RVM resnet50 on MPS for a cleaner matte). Do not swap in
  lighter models to save time or memory.
- Heavy preparation (transcription, matting) runs as an overnight batch when the editor is closed.
- Toolchain: Homebrew ffmpeg with VideoToolbox and ProRes encoders, Google Chrome (for the Playwright
  renderer), a Python virtual environment.

## Consequences

- On 8 GB machines, prep may be slow; that is accepted. If it fails outright (out of memory), run prep on the
  developer's laptop.
- The design discussion transcript stays on Windows; decisions live in this repo (`CONTEXT.md`, `docs/adr/`).
