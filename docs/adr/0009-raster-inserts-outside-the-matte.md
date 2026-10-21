# 0009 — Raster inserts and brand image layers are Python layers outside the person matte

Status: Accepted (2026-10-21). Amends ADR-0008.

## Context

The creator asks for pictures, screenshots and clips on a phrase («коли кажу X — покажи Y») and for full-screen
B-roll, and a brand may have a logo, strip, gradient or sticker. ADR-0008 draws graphics with the HTML renderer,
but that renderer's PNG is multiplied by (1 − person matte) on text-behind frames, so a picture drawn there would
get a person-shaped hole. A second per-frame Chrome pass would cost a second PNG folder and more RAM on an 8 GB Mac,
and pictures need no measuring: their size comes from their pixels.

## Decision

- Inserts and brand image layers are composited in Python (`pipeline/layers.py`), never through `overlay.html`.
  Each picture is styled once with cv2 into a straight-alpha sprite (card: rounded corners, border, shadow; cut-out:
  outline ring, shadow); the pop-in is one affine warp plus an opacity per frame.
- Layer order in the MP4, bottom to top: the picture (graded) or a full-screen insert (never graded), the flash,
  brand "under" layers, the card insert, the text cut by her matte, the front text, brand "over" layers. The
  editable project has the same order as lanes (`freeze, broll, transition, flash, brand_under, insert, text,
  doodle, brand_over`); each card insert and brand layer is its own ProRes 4444 alpha clip, streamed one frame at a
  time.
- `build_timeline` places card inserts before the subtitle blocks, clear of her face, of pinned blocks, of reserved
  brand rects and of the crop-safe area; blocks then flow around them. Overlaps it cannot avoid are check FAILs.
- Full-screen inserts leave the person bookkeeping (occupancy, `occlude_frames`, `front_frames`): she is not on
  screen there.
- Code-drawn graphics templates (callouts, counters, CTA lockups) stay on the HTML renderer, as ADR-0008 says.

## Consequences

- Inserts are never masked and never re-ingested; only the `src` window of a full-screen video is converted.
- Styling, animation state and compositing are pure numpy and testable without a render.
- Brand logos, stickers and photos are client material: they live untracked in `brands/<brand>/local/layers/` and
  are copied to the creator's Mac in person. Until a brand has them, `style.layers` stays `[]`.
