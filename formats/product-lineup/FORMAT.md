# Format: product lineup ("our lines - which one is for you")

One creator presents 3-5 products of one brand, one block per product, each block the same grammar, then the
whole lineup and a CTA. First reel: YOCASE shampoos, 2026-10-10 (`projects/yocase_line/make_script.py`).
Full research: `.claude/skills/reel-videographer/playbook.md` section 3; this file is the working summary plus
what the real footage taught us. Start from `template.json`; `format.json` adds the hook preset and the music
fade-out (the bed itself is the brand's). `make_script.py`'s placement hints (x 56-60, y 110) predate the
2026-10-13 crop-safe area (x 128-952, y 250-1480): fix them before it is shown as the worked example.

## Skeleton (21-34 s)
| Section | Length | Content |
|---|---|---|
| Hook | 1-3 s | motion + product by frame 0; hook text <= 7 words by frame 3 (y 270-700). Options: cold open on the best zoom-through, 4-bottle teaser on beats, phone mock-up pop-out (graphic template, see ADR-0008) |
| Product block x N | 4-7 s each, within +-10 % of each other | the block template below |
| Ending | 2.5-3.5 s + CTA | all products together (re-shows every product), CTA spoken and on screen >= 2 s, `ding_02_soft_chime`; end on a downbeat |

## Block template
1. **Hard cut on a beat** into the product's medium shot; motion in the first 1-3 frames (she swings the bottle
   up, walks in, or a creep from frame 1). A swipe-whip instead of the hard cut when she sweeps her hand.
2. **Name**: label callout pops on the spoken name (`label()` literal, product colour, scale 1.3, `pop` + pop SFX).
3. **Punch** 1.15 anchored on the face on the line's stressed word (the hair type), held to the cut.
4. **Push slot**: she pushes the bottle to the lens -> zoom-through (scale 1.3-1.45, land 1.0) on the largest
   sharp frame -> close-up lands with an expo 1.00 -> 1.08-1.12 push.
5. **Read-hold**: close-up 2-4 s, label steady, benefit line (her voice or voice-over) as a callout beside the
   pump on the wall - never over the label.
6. **Next block** on the next beat.

Energy curve: the first block full, the middle ones ~20 % lighter (smaller zoom-through scale and landing), the
hero block gets the accent: freeze 15-24 f (30-36 f at the reel's end) on the sharpest label frame with a
1.00 -> 1.03 creep through it + flash + shutter, on a beat (playbook 2.12).
Budget per 30-34 s: 4 zoom-throughs, 2-4 whips, 3-5 punches, 1-2 flashes, 0-1 shake (only with a hit), about
12-15 cuts (playbook 3.7).

## Shooting notes (send to the creator before the next lineup)
- One clean take per product: name + hair type to camera, push to the lens, then a steady close-up (hold 3 s,
  label to camera, then say the benefits off-camera while still holding it).
- Check the bottle in hand before each take: in the YOCASE shoot Balance and Fix Color were swapped in two
  clips, which forced a voice-over rebuild.
- A sideways hand sweep between lines and a lens cover with all products at the end give free transitions.

## Learned rules
- 2026-10-10: blocks rebuilt around a swapped product use only shots with her mouth hidden (bottle in front of
  the face, close-ups); between-take fragments (hand lowering, re-gripping) are never filler.
- 2026-10-10: a real walk-up to the lens that overshoots into defocus: cut the overshoot out (last sharp
  approaching frame -> settled close-up), a light zoom-through on that cut.
- 2026-10-10: the lens-cover reveal with the whole lineup is the ending transition (frame-fill), not a designed
  swipe over an empty wall.
