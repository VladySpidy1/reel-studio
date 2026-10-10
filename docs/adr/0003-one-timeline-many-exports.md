# 0003 — One timeline, several exports

Status: Accepted (2026-10-10)

## Context

Fixing small things through chat ("move this caption half a second") costs a full re-render; in an editor it
takes seconds. The creator is an editor with taste, and brands sometimes send revisions. Some reels are fine
as rendered and should be postable straight away.

## Decision

The per-reel timeline (`projects/<name>/script.json`) is the single source of truth. Exporters:

1. **Draft MP4** — ready to post; also the preview the creator watches first.
2. **Editable project** — FCPXML + media: subtitle blocks and graphics as separate alpha ProRes 4444 clips,
   SFX and music as separate audio clips with levels, zooms as transform keyframes (ADR-0004).
3. **No-music variant** — SFX kept, music bed removed, for adding a trending Instagram sound in the app
   (in-app sounds cannot be baked into the file).
4. **Hook variants** — 2–3 alternative openings for Instagram trial reels.

Rule of separation: anything the creator may want to move or remove is its own clip in the project; technical
processing (WB match, HDR→SDR, grade) is baked into shared intermediate media so all exports look identical.

## Consequences

- Each new effect type must be supported by every exporter (roughly +20% work per effect).
- Subtitle text is not editable inside the editor (blocks are rendered animation); typos are fixed by
  re-rendering a single block clip on request.
