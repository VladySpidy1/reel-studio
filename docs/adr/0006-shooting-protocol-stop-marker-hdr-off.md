# 0006 — Shooting protocol: «стоп» after a failed take; iPhone HDR video off

Status: Accepted (2026-10-10)

## Context

Guessing from video which take failed is unreliable. iPhones record HDR (HLG/Dolby Vision) by default, and
converting HDR to SDR for social platforms without proper tone-mapping shifts colours.

## Decision

- When a take fails, the creator says «стоп». The pipeline finds the marker in the transcript and cuts the
  failed take deterministically, no model judgement involved.
- The creator turns off HDR video on the iPhone (Settings → Camera → Record Video → HDR Video).
- The pipeline still detects HDR input and tone-maps it to SDR as a safety net.

## Consequences

- The take cutter needs a robust «стоп» detector (word-level timestamps; tolerate «стоп стоп», laughter,
  restarts mid-sentence).
- Footage shot before this protocol falls back to the existing take-cut heuristics.
