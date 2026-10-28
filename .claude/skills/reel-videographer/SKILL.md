---
name: reel-videographer
description: Edit like a pro short-form videographer - pick the takes by watching the footage, cut on real gestures, and place swipes, zoom-throughs, punches, A/B framing, freezes, flashes, beat-synced cuts and SFX with frame-exact parameters in script.json, then lint the edit. Use for every reel with movement or products, and whenever the user says the edit is "мертве/мертвое", wants "більше руху/больше движения", asks to "обіграти рух", for transitions/zooms/swipes, or for a product-lineup reel.
---

# Reel videographer

The craft is researched and written down: `playbook.md` next to this file (effects with timings in frames,
format grammar, universal grammar, sources). Do NOT re-research. Read the playbook sections you need for the
reel at hand: section 1 (principles) once, section 2 for each effect you place, section 3 or
`formats/<format>/FORMAT.md` for the format, section 4 for any talking reel. The `reel` skill drives a creator
reel and `reel-subtitles` is the reference for the pipeline commands and the text; this skill decides the picture
and the sound around it. "The reel's script" is `inbox/<reel>/script.json` (creator) or `projects/<name>/script.json`
(developer).

Worked example: `projects/yocase_line/make_script.py` (4-product lineup). Generators like it are for the developer's
reels in `projects/` only, where hundreds of JSON numbers come from a small Python file; a creator reel's script is
JSON written in place (never Python under `inbox/`).

## 1. Watch the footage before choosing a single take

The transcript only tells you where she speaks. The edit is made from what she DOES.
```
.venv/bin/python pipeline/contact_sheet.py build/<name>/source.ffconcat 0 <dur> 1 --words build/<name>/words.json
.venv/bin/python pipeline/contact_sheet.py build/<name>/source.ffconcat <t0> <t1> 0.1 --words build/<name>/words.json
```
Survey every clip at 1 s, then 0.1 s around every candidate shot and gesture, 1/30 s to pick a cut frame.
`build/<name>/motion.json` (prep writes it; `times.py` prints it in output time) lists sweeps (hand or arm
across the frame: dir, peak) and `to_lens` pushes (where the moving object stops: `at`) - confirm each by eye.

Classify each candidate before using it:
- **Usable**: her talking the line to camera; a deliberate action with the product (raises it, pushes it to the
  lens, walks it up to the lens, sweeps it across, covers the lens, turns it); a steady close-up.
- **Junk, never in the reel**: between-take moments - lowering the hand, re-gripping, stepping into place,
  waiting, walking off, a half-raised bottle. A shot must show a line or an action, nothing in between.
- **Label check**: the product on screen is the product being named. If she held the wrong product while
  speaking, her words may go over the right product (`audio.voice_over` + `audio.mute`) only on shots where her
  mouth is hidden (bottle in front of the face, close-ups) - never over her talking face.
- **Natural transitions first**: a real walk-up to the lens, a real lens cover with a pull-back reveal, a real
  sweep. They beat designed effects; add designed moves only where the footage moves.

## 2. Order of work (playbook section 4)
Trim dead air -> pick takes -> match cuts -> A/B framing on same-setup cuts -> punches on stressed words ->
designed transitions only on named motions -> creeps on the remaining held shots -> pattern-interrupt scan (no
span over 3-4 s without a change) -> text -> SFX -> music on beats -> lint -> render -> look.

## 3. Effect -> script (camera spec is documented in `pipeline/camera.py`)

Times are OUTPUT seconds. C = the cut frame. e = total upscale (framing x punch x transition): held frames
<= 1.2, the last 2-3 blurred transition frames <= 1.65 (the 1080p intermediates go soft beyond).

| Effect | When | Script |
|---|---|---|
| Swipe-whip | sweep >= 25 px/f; C = sweep peak = END of the outgoing take | `{"type":"push","at":C,"dir":<sweep dir>,"out":4,"in":9,"ease_in":"expo","roll":3,"shutter":0.6}` (preset B) or `"out":5,"in":5` (preset A). Max 1 per block, 2-4 per 30 s |
| Zoom-through | product pushed to the lens (to_lens), then its close-up; C = largest sharp frame = END of the outgoing take | `{"type":"zoom_through","at":C,"target":<to_lens at>,"scale":1.3-1.45,"land":1.0,"out":5-6,"in":6,"shutter":0.6}` + close-up take `push_takes`: `{"from":1.0,"to":1.08-1.12,"ease":"expo","dur":0.3,"creep":0.012,"target":[540,900]}` |
| Real push / overshoot | she walks it up to the lens, it defocuses past the close-up | cut from the last sharp approaching frame to the settled close-up; optional light zoom_through (scale 1.3) on that cut |
| Frame-fill | the product really covers the lens | cut inside the cover, 1-3 covered frames each side; whoosh at the covered frame with `"move": "<what>"` |
| Punch | stressed word / product name / turn, >= 15 f after any other move | `{"t":<word onset>,"scale":1.15,"in":0.1,"until":<next cut>,"out":0,"target":"face","anchor":true}` - from A framing only |
| A/B framing | same-setup jump cut | B take: `push_takes {"from":1.16,"to":<creep>,"ease":"linear","target":"face"}` (>= 10 % step); product shots: `"target":[x,y]` on the label |
| Creep | every held take without another move | `push_takes {"from":1,"to":1+0.01*dur,"ease":"linear"}`; global `"push": {"from":1,"to":1}`; no `cut_in` |
| Hero freeze | once per reel, sharpest label frame (max Laplacian in the bottle box) | edl `{"hold": t_src, "dur": 0.8-1.2}` + `flashes [{"t":hold,"dur":0.15,"amount":0.6}]` + `camera_shutter_01` at the hold; creep through it with the next take's `push_takes` (no zoom step after the freeze) |
| Beat sync | product changes, transitions, the freeze | per-shot frame budgets ("knobs") + `beats.snap` / `beats.fit` (see make_script.py): the cut moves to the frame at or before the beat; gesture-pinned cuts move by trimming the shot's head |
| Callout | product name + benefit (<= 4 words) | name pops on the word, never on the cut frame (land first: C+6..15 f); beside the bottle on the wall, never over label or face; same position and animation for every product |

Never in brand/beauty reels: glitch, cube/flip/page-curl, full-frame glitter, lens flares, staged hand covers,
cartoon SFX (`record_scratch`, `boing`, `cartoon_*`, `tada_brass`, `cha_ching`), shake without a hit, more than two
designed transition types, a flash on routine cuts.

**SFX**: one family per event, peak on C or C+1. Whip: swish (`whoosh_quick_03_swish`, `whoosh_soft_02_wind_swoosh`)
-12. Zoom-through: riser (`whoosh_05_swipe_zoom`, `whoosh_04_air_into_cut`) at C -12 plus a different thump per
product (`bass_thump_01_sub`, `punch_soft_impact`, `bass_thump_02_synth`) at C+1 f -14. Name pop -20 (rotate
`pop_04_light`, `pop_02_bubble_a`, `pop_03_bubble_b`). Hero: `camera_shutter_01` -10. CTA: `ding_02_soft_chime` -18.
No whoosh on plain or jump cuts.

## 4. Lint, render, LOOK
```
.venv/bin/python pipeline/lint_edit.py <the reel's script>
.venv/bin/python pipeline/build.py <the reel's script> --draft
.venv/bin/python pipeline/contact_sheet.py output/<name>_draft.mp4 0 <dur> 0.3 --phone
```
(In a creator reel the `reel` skill runs the build in the background with a log.)
lint_edit must show 0 FAIL; fix each WARN or know why it stays. Then go through the WHOLE draft sheet (0.25-0.3 s
tiles) shot by shot before anyone sees it: Does every shot show a line or an action? Is the label the product
being named? Any junk frame (hand dropping, walking in, empty wall, defocused mush longer than 3 f)? Text over a
label, face or bottle? Captions inside the phone crop lines (x 128-952, y 250-1480)? A cut that jumps for no reason?
Fix and re-render; the creator should never be the one who finds these.

## 5. Learned rules (with the date)
Corrections from reels go to the tracked `learned/` first (the `reel` skill appends them); rules that hold are folded
in here.
- 2026-10-10, YOCASE: "видео мертвое" - every visible gesture is an edit point: the sideways hand sweep becomes a
  swipe ("камера поворачивается"), the bottle pushed to the lens becomes a zoom into the close-up. Moves under
  10 % and in-out blips read as nothing.
- 2026-10-10, YOCASE: "недачные дубли, где Марина просто руку опускает... кадры не в тему, прыгают" - a block
  stitched from between-take fragments to cover a voice-over is worse than a shorter block. Build such blocks
  only from deliberate actions (raise to the lens, walk-up to the lens, held at the face), and watch them on a
  0.25 s sheet before delivering.
