# 0004 — Finish in DaVinci Resolve via FCPXML

Status: Accepted (2026-10-10)

## Context

The creator edits in CapCut, which has no timeline import: another project can only come in as a rendered
video file (CapCut help centre, Jan 2026), so a layered project cannot be delivered there. Final Cut Pro is the
best fit (FCPXML is its native format; connected clips follow their take when a take is trimmed) but costs
$299.99 or $12.99/month (Creator Studio), which was judged too expensive to start with. DaVinci Resolve is free
and imports FCPXML.

## Decision

- Finishing editor: DaVinci Resolve (free) on Mac.
- Export format: FCPXML, so Final Cut Pro can be adopted later without rewriting the exporter.
- Final Cut Pro is bought only if DaVinci does not work out for the creator.
- First implementation step is a spike: check what Resolve imports from our FCPXML (alpha ProRes 4444 clips,
  audio levels, transform keyframes, stills/freezes). Whatever it drops is baked into intermediate media.

## Consequences

- Resolve has no magnetic connected clips: after deleting a take, the creator must ripple-delete across all
  tracks to keep subtitles and SFX in sync. Teach this once.
- Media handed to Resolve is 1080×1920 ProRes intermediates, not 4K iPhone originals, to keep editing smooth.
