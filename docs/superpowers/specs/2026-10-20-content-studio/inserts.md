## Image and video inserts, and brand layers

### Goal

Marina can write «коли кажу X — покажи Y» or «на весь екран Y» in her brief and drop the files in. She gets a reel where:

- **Card inserts:** each screenshot, product photo or meme pops in over the talking head on the right phrase, with its own SFX. It stays clear of her face, of the subtitles (including hand-placed ones) and of the IG crop-safe area. The person matte never cuts it. Only one insert is on screen at a time.
- **Full-screen inserts:** an image or video replaces the picture for a span while her voice continues. Its own sound never reaches the mix, and a whoosh plays on the switch. The grade and per-take WB do not touch it. Nothing is re-ingested or re-prepped.
- **Brand layers:** if a brand defines a logo, strip, gradient or sticker, it is drawn as an unmasked layer in a fixed order. Today no brand defines any, so this ships unused (see open question 1).

The MP4 and the editable FCPXML project both carry all of this. Each card insert and each brand layer is its own alpha clip in the project.

**Main decision: inserts and brand layers are composited in Python (new `pipeline/layers.py`), not in the per-frame HTML overlay.**
- **Styling:** each insert is styled once with cv2 into a BGRA sprite: rounded corners, 1 px border and shadow for cards, a 1 px silhouette outline for cut-outs, plus gradients. The reviewer's prototype (`/private/tmp/claude-501/reviewer_scratch/ins/style_sprite.py`) renders a 430 px card in 30-50 ms. It gives exact source pixels in the interior, a #111 border, a soft shadow and a clean cut-out ring. Chrome and `overlay.html` are not involved.
- **Animation:** the pop is per frame, one affine warp plus an opacity value. At rest the scale is exactly 1 and the sprite is blended unwarped.

Why:
1. **No person-shaped holes.** The text PNG is multiplied by (1 − matte) on text-behind frames (`video_pass.py:216-217`), so inserts must not be in that PNG. Putting them in HTML would need a second per-frame Chrome pass and a second single-slot PNG folder.
2. **No measuring.** Insert sizes come from pixel dimensions.
3. **8 GB RAM.** The export streams insert frames to the encoder. It does not keep frames in RAM the way `render_layer` does (`export_fcpxml.py:115,133`).
4. **Cheap to test.** Styling, animation state and compositing are pure numpy and can be checked without a render.

ADR-0009 (short) amends ADR-0008: raster inserts and brand image layers are Python layers outside the person matte. Code-drawn graphics templates stay on the HTML renderer.

### Creator-facing behaviour (what Marina writes in Ukrainian and what she gets)

She drops the files (HEIC, JPG, PNG, WebP, MOV, MP4) for the reel. The intake section decides whether that is an inbox. The skill copies the files, never moves them, into `projects/<name>/inserts/`. She writes, for example:

```
коли кажу «подарувати турботу» — покажи фото набору
коли кажу про шампунь і маску — покажи скрін відгуку (тільки верх, де зірочки)
на весь екран відео з пакуванням, на словах «дуже красиве пакування»
```

| She writes | Script result |
|---|---|
| «коли кажу (про) X — покажи Y» | card insert at phrase X |
| «на весь екран Y [на словах X]», «повноекранне Y» | `mode: "full"` |
| «велике» / «маленьке» | `size: "l"` / `size: "s"` |
| «тільки верх / частину з …» | `crop`, chosen by Claude after looking at the image |
| «без звуку» | `sfx: null` |
| «довше» | `until` |
| «на весь екран» with no phrase | Claude picks the line where Y is talked about and reports which one |

Corrections she can ask for afterwards: «фото більше», «скрін на весь екран», «прибери вставку 2», «вставку 1 раніше/довше». Each is a one-key edit in `script.json` followed by a rebuild. Claude runs every command; she never sees a terminal.

The report section she gets is in Ukrainian with gender-neutral wording. The times below follow the auto-`until` rules in the Schema:

```
Вставки:
1. Фото набору (IMG_4412) — 5,7–7,2 с, на словах «подарувати турботу», під текстом, звук «свіш».
2. Скрін відгуку (IMG_4413, обрізано до верхньої частини із зірочками) — 10,5–12,5 с, на словах «шампунь, кондиціонер, маска».
3. На весь екран: відео пакування (pack.MOV) — 14,2–15,6 с; звук відео вимкнено, голос іде далі.
Не вставлено:
• IMG_4415 — на фото Balance, а мова про Repair Plex. Якщо все ж треба, напиши «встав IMG_4415 на словах …».
• promo.MOV — відео зняте в HDR, його поки не вдається вставити. Надішли версію без HDR.
Варто перевірити:
• Скрін 2 обрізано: видно лише верх із зірочками.
• Фото 1 зменшено до середнього розміру, бо велике закривало б обличчя.
```

**Skill rules (English, in the reel skill):**
- **Look at every candidate before using it.**
  - Run `.venv/bin/python pipeline/inserts.py projects/<name>/script.json`. It writes viewable JPEGs, because Claude's Read tool cannot open HEIC, and a 4-frame strip per video. It does not convert videos yet.
  - Open every candidate. When Y is a description such as «скрін зі статистикою», open all of them.
  - Write `why`: one line saying what the image shows that proves the phrase.
  - Place an image only if it shows what is being said: the same product, a readable number or quote, the same claim. Otherwise list it under «Не вставлено».
  - Never place a file Claude has not opened.
- **Anchor on what was heard.** Copy X from the `times.py` transcript, not from the brief's spelling. Whisper garbles Latin brand names ("-Case Repair Plex"), so anchor on the Ukrainian words next to them.
- **Tall phone screenshots** get a `crop` to the part that proves the point, or go `full`. Every crop Claude chooses, and every automatic size step-down, is listed under «Варто перевірити».
- **Before delivery:**
  - Every `!!` line in the build log must be fixed (`!! ins …`, `!! bN overlaps insert iM`, OUTSIDE).
  - Check the insert tiles on the review sheet and the phone-crop preview.
  - When an insert has no spot, fix it in this order: unpin a nearby subtitle block, crop, size `s`, `full`.
- **Suggesting extra inserts.** If a brand has a permanent photo folder (open question 1), Claude may propose at most two extra inserts that directly prove a line. They are labelled «додано самостійно» so she can drop them.

### Schema

**`script.json` → `"inserts": [...]`.** New top-level key; the template gets `[]`. Only one insert is on screen at a time: a later insert ends the previous one 1 f before its start, with a WARN if that leaves less than `min_dur`.

| key | default | meaning |
|---|---|---|
| `file` | required | Name inside `<script dir>/inserts/`, or a repo-relative path |
| `at` | required | The phrase as heard (string), or output seconds (number). A phrase survives pause cutting and EDL edits; a number does not. |
| `occurrence` | 1 | Which match of the phrase to use («своїй» is at 1.70 s and 19.74 s in 2373) |
| `offset` | 0.0 | Seconds added to the phrase start |
| `until` | auto | A phrase (ends on its last word) or seconds. Auto for a card: max(t0 + `min_dur`, phrase end + `hold`). Auto for full: max(t0 + `full_min_dur`, phrase end + 0.2), at most the video's `src` length. Always clipped to the next insert and to the end of the reel. |
| `mode` | `"overlay"` | `"overlay"` = card over the picture; `"full"` = replaces the picture |
| `size` / `w` | `"m"` | `s`/`m`/`l` = `style.insert.widths`, or an explicit `w` px (≤ `max_w`). The width shrinks so that h ≤ `max_h`. |
| `style` | auto | `card`, `cutout` (picked when more than 2% of the PNG's pixels are transparent) or `plain` |
| `crop` | none | `[x0,y0,x1,y1]`, fractions of the oriented image (card mode) |
| `focus` | `[0.5,0.5]` | Full mode: the point that survives the cover crop |
| `src` | `[0, end]` | Full-mode video: seconds of the clip to use. Only this part is converted. |
| `creep` | `style.insert.full_creep` | Full-mode still: slow push per second about `focus` |
| `place` | `{}` | `x`, `y` (soft preference, top-left), `safe` (hard box, clipped to the global safe area), `exclude` (hard rects) |
| `sfx`, `sfx_gain` | from `style.insert.sfx` | Card → swish family, cut-out → pop family, full → whoosh family. The sample is chosen so it differs from the previous whoosh in the merged cue list. `null` = silent (lint WARN). |
| `why` | — | Claude's one-line proof; goes into the report |

**`style.insert`.** Defaults go in `style_default.json`. Today they are overridden only by `script.style`, through the existing one-level merge (`build_timeline.py:272-274`), so a nested `widths`, `shadow` or `sfx` replaces the default whole. When the brand/format section adds `brand.json` and format styles to that merge, they feed the same key. This section adds no loader.

```json
"insert": {"widths": {"s": 315, "m": 430, "l": 580}, "max_w": 700, "max_h": 900,
  "min_dur": 1.5, "hold": 0.5, "full_min_dur": 1.0, "full_creep": 0.015,
  "anim": "snap", "exit": 0.13,
  "radius": 12, "border_px": 1, "border": "#111111",
  "shadow": {"dy": 6, "blur": 22, "alpha": 0.30}, "outline": "#111111",
  "margin_face": 40, "margin_text": 20, "min_face_px": 120, "person_cost": 600, "prefer_y": 260,
  "sfx": {"card": [["whoosh_quick_03_swish", -14], ["whoosh_soft_02_wind_swoosh", -14]],
          "cutout": [["pop_04_light", -20], ["pop_02_bubble_a", -20], ["pop_03_bubble_b", -20]],
          "full": [["whoosh_soft_01_air_sweep", -12], ["whoosh_quick_03_swish", -12]]}}
```

- **`anim`** is a preset name or a dict with keys `dur`, `scale` keys and `opacity` keys. Presets:
  - `snap` (third-party): 0.085 s, opacity 0→1, scale 0.965→1.00.
  - `pop` (playbook 2.15): 0.30 s, scale keys `[[0,0.85],[0.6,1.04],[1,1.0]]`, opacity `[[0,0],[0.25,1]]`.
- **Progress** at frame i is p = (i − f0 + 1)/(FPS·dur), interpolated with smoothstep like `kf()` (`overlay.html:316-327`). For `snap` the first frame is at opacity 0.34 and scale 0.977, and from f0+2 the insert is at rest. The SFX `peak_at` is f0/FPS.
- **`exit`** is the fade-out in seconds; 0 = hard cut. Full-screen inserts always switch with a hard cut.
- **The hard placement rect** is the sprite's bounding box where alpha ≥ 5%, so the shadow and outline must also stay inside the safe area (the third-party rule).

**`style.layers` (brand layers).** A list inside `style`, so a later level replaces it whole and `"layers": []` turns it off. The default in `style_default.json` is `[]`. Pre-edited sources with baked graphics (the YOCASE 2371/2373/2477 kind, reel-subtitles SKILL.md learned rule of 2026-10-13) set `[]`.

```json
"layers": [
  {"id": "gradient", "kind": "gradient", "z": "under", "y0": 1248, "y1": 1920, "color": "#000000", "opacity": 0.55},
  {"id": "logo", "kind": "image", "file": "brands/<brand>/layers/logo.png", "z": "over", "x": 760, "y": 262, "w": 170,
   "t0": 0, "t1": null, "fade": 0.3},
  {"id": "strip", "kind": "image", "file": "brands/<brand>/layers/strip.png", "z": "over", "x": 0, "y": 230, "w": 1080,
   "reserve": false, "safe_check": false},
  {"id": "sticker", "kind": "image", "file": "brands/<brand>/layers/sticker.png", "z": "under", "x": 128, "y": 1255,
   "w": 150, "style": "cutout"}]
```

- `x`, `y` are the image's top-left in screen px, excluding shadow and outline, like block positions.
- `z: "under"` sits above the picture and below inserts and text. `z: "over"` sits above everything.
- `reserve` (default true for images, false for gradients) makes the rect a hard exclusion for subtitles and inserts during t0..t1.
- `safe_check` (default true) reports OUTSIDE when the visible rect leaves the safe area. The third-party sticker centre x 190 fails for a 150 px sticker; x = 128 (centre 203) passes.

**`timeline.json` → `"layers"`.** Written by `build_timeline`. Read by `video_pass`, `build`, `export_fcpxml`, `review_frames` and `times`. One resolved entry per insert or brand layer:

```
{id, cat: insert|brand, mode: overlay|full, z, f0, f1 (exclusive, includes the exit fade), x, y, w, h,
 sprite, pad, anim, exit, rides (bool), media, kind: still|video, src_f0, n_media, creep, focus,
 sfx, sfx_gain, label}
```

Paths are repo-relative. Media and sprites live under `build/<src>/inserts/` (`<src>` = the folder of `script["source"]`), with names hashed from the inputs.

### Changes by file

**New `pipeline/inserts.py`: what to show and when.**
- **`prepare(script, script_path, full_videos=())`** inventories `<script dir>/inserts/*` into `build/<src>/inserts/inserts.json`. The cache key is path, size and mtime (plus `src`/`focus` for converted videos). The CLI prints the inventory: kind, size, cut-out or not, duration, refused files.
  - **Stills:**
    - HEIC/HEIF go through `sips -s format png -Z 2560 --matchTo "/System/Library/ColorSync/Profiles/sRGB Profile.icc"`. `sips` keeps the EXIF orientation tag (checked on `rot6_sips.png`).
    - Then Pillow `ImageOps.exif_transpose`, and `ImageCms` converts any non-sRGB ICC profile (P3 JPEGs and PNGs) to sRGB.
    - Output: an RGBA PNG with long side ≤ 2560, plus `view/<stem>.jpg` (≤ 1400 px).
  - **Videos:**
    - Every video gets a probe (duration, size, HDR flag) and `view/<stem>.jpg`, a 4-frame strip.
    - Only videos referenced by a `mode: "full"` insert are converted, and only their `src` window. This goes through `ingest.ingest(..., audio=False, focus=…, trim=src)`, so unused candidates never become ProRes. ProRes 422 HQ at 1080×1920/30 is about 27 MB/s.
    - `ingest` raises `SystemExit` on HDR (`ingest.py:57-59`). `prepare` catches it per file and lists the file as refused with a Ukrainian reason.
- **`find_phrase(words, phrase, occurrence, after)`:** normalised word windows of n−1..n+1 words, `SequenceMatcher` ratio ≥ 0.8, non-overlapping matches in time order. Returns t0, t1, the ratio and the heard text. It needs output end times; see `heard_words`.
- **`resolve_times(script, words, duration, style, inventory)`:** pure, with no image work. Turns `at`/`until`/defaults into frame spans, mode, kind, style kind and SFX choice, plus warnings. Used by `build_timeline`, `lint_edit` and `times.py`.

**New `pipeline/layers.py`: how a layer looks on a frame.**
- **`style_sprite(img, kind, style)`:** cv2 only.
  - `card`: rounded-rect mask drawn at 4× and area-downscaled, a `border_px` ring in `border` colour (erode with a zero border), and a Gaussian shadow (σ = blur/2) offset by `dy`.
  - `cutout`: a 1 px dilated alpha ring in `outline` colour plus a soft shadow.
  - `gradient`: a vertical alpha ramp.
  - Returns straight-alpha BGRA plus its pad. Cached as `sprites/<hash>.png`.
- **`state(layer, i) → (opacity, scale)`:** pure.
- **`Compositor(layers)`:**
  - `full(i)` returns the ungraded BGR frame for a full-screen span. Video uses its own `video_pass.FrameSource`; a still is cover-cropped once about `focus`, with `creep` as a warp.
  - `composite(img, i, z, ovm)` blends the visible layers of that z. For `under` that is brand-under first, then the insert. It warps only while scale ≠ 1 or `ovm` is set (cards ride `ovm`; brand layers are screen-locked), and warps in premultiplied alpha to avoid dark fringes.
  - `rgba(layer, i)` returns a full-frame straight-alpha BGRA frame for the export (`ALPHA = "straight"`, `export_fcpxml.py:46`).
- **`cues(layers)`** returns `{"name","peak_at","gain_db","move": true}` entries.

**`pipeline/build_timeline.py:main` (269-360).** New order:
1. camera (301), unchanged;
2. `measure()` (314), unchanged, because it measures at the origin and does not depend on positions;
3. masks (316);
4. `inserts.prepare` (cache check only) and `resolve_times` on heard words with output ends;
5. place the inserts;
6. place the blocks with insert exclusions;
7. overlap check;
8. styled sprites written, `timeline["layers"]`.

- **New `place_insert(...)`** next to `solve_block`. The integral-image window sum (214-216) becomes a module-level `window_sum(m, qh, qw)` used by both.
  - **Hard constraints:**
    - the global safe area ∩ `place.safe`, plus `style.layout.exclude` and `place.exclude`, as at 200-207;
    - face boxes from `track.json` with width ≥ `min_face_px`, taken from the nearest sample to `edl.src_time`, mapped through `cam.matrix` over the span and dilated by `margin_face`;
    - reserved brand rects;
    - the boxes of concurrently visible pinned subtitle blocks, inflated by `margin_text`. A block is pinned when its merged `place` has `safe` (use that box ∩ global safe) or both `x` and `y` (use the measured rect at x, y). 2373 pins all 18 blocks, 2371 five, yocase_line six.
  - **Soft cost:** person-matte overlap (`occupancy()`, 168-179) × `person_cost`, plus |y − `prefer_y`| and 0.5·|x − centre|.
  - **No room:** step down l → m → s and report it. If nothing fits, place the insert with the least face overlap and print `!! ins iN: no spot clear of the face/subtitles — unpin a block, crop, size s, or на весь екран`.
- **Blocks avoid inserts.** After `place` is built (329), set `place["exclude"] = list(place.get("exclude", [])) + rects`. It must be a new list, because `place` is a shallow merge and `build_screens` keeps the script's own `place` dict by reference (125). The rects are those of inserts and reserved brand layers whose span overlaps the block's visible window [t_first, t_end + fade], inflated by `margin_text`. Line 205 then applies them, and `solve_block`'s signature does not change.
- **Overlap check.** After each block is placed, intersect its rect with concurrent insert rects. A hit prints `!! bN overlaps insert iM`. The fallback at 249-253 is unconstrained when the block's own safe box is fully covered (`(out == 0).any()` is False), so the check catches what the solver cannot prevent.
- **Full-screen frames:**
  - `occupancy()` gets a `skip` set of frames;
  - the `person_box` sampling (343) skips them;
  - `occlude_frames` (357-359) drops them, so text over B-roll gets no person hole.
- **Report:** one `ins`/`brand` line per layer, with `!!` flags (face, subtitles, OUTSIDE, shortened, size step-down).
- **`norm`** (31-32) moves to `common.py`.

**`pipeline/edl.py`:** new `heard_words(script, edl)` next to `VoiceMap` (63-107). It returns the output start and output end of each heard word. `inserts.py` uses it. Replacing the duplicates at `build_timeline.py:283-289` and `times.py:21-27` is optional; the regression run covers it if done.

**`pipeline/video_pass.py`.**
- **`segment` (222-245):** load `timeline_path` whenever it is given (today only together with `masks_path`, 225-227). Build one `Compositor` per process.
- **`render_frame` (201-219)**, in this order:
  1. `img = comp.full(i)` on full-screen frames, else `gr(picture(...))`, so full-screen frames skip the grade and WB gains;
  2. flash;
  3. `composite(img, i, "under", fr.get("ovm"))`;
  4. the existing masked text PNG;
  5. `composite(img, i, "over")`.

**`pipeline/build.py:main`.** Load `BUILD/"timeline.json"` after the timeline step. Pass `sfx_cues({"sfx": au.get("sfx", []) + layers.cues(tl.get("layers", []))})` at 59-61. `sfx_cues` (18-25) turns the bare `KeyError` at 22 into a message naming the missing credits entry.

**`pipeline/export_fcpxml.py`.**
- **New `write_layer(layer)`** streams `Compositor.rgba` for f0..f1 into `encode(..., alpha=True)`. It runs sequentially in the main process after the Pool (494-496), so only one frame is held. Results go into `layers.json` so `--skip-layers` (491-492) reuses them.
- **Categories:** card insert → `cat: "insert"`; brand layer → `"brand_under"` or `"brand_over"`; full-screen insert → `"broll"`.
- **Full-screen media:**
  - A video becomes an asset-clip of the converted insert `.mov` (`video_asset(path, n_media, False, label)`, so no audio is declared; `collect()` hard-links it; `start` = `src_f0`).
  - A still with creep is baked to ProRes 422 via `encode((Compositor.full(i) …), alpha=False)`.
- **Lane order (506-515):** `freeze, broll, transition, flash, brand_under, insert, text, doodle, brand_over`.
- **`clip_xml` (593-596):** `insert` joins the `overlay_at` branch with `doodle`/`text`; `broll` and `brand_*` join the no-transform exclusions with `flash`/`transition`.
- **SFX (531):** use the merged cue list.
- **`--procs` default:** 2 when RAM < 15e9 bytes, measured as in `prep.py:245-246`, unless the portability section already does this.

**`pipeline/ingest.py`.**
- `probe` (33): `float(d["format"].get("duration") or 0)`. PNG, HEIC and WebP have no format duration (checked with ffprobe), so today this line raises a KeyError.
- `ingest` (55-85) gets `audio=True`, `focus=(.5,.5)` and `trim=None`.
  - `audio=False`: `-an`, no anullsrc, no audio map.
  - `trim`: `-ss`/`-t` before `-i`, with n computed from the trimmed length.
  - `focus`: the x:y crop arguments are added only when focus ≠ centre, so existing ingests stay byte-identical.
- `main` rejects stills with a message pointing to `inserts/`.

**`pipeline/lint_edit.py:lint` (40-177).** Calls `inserts.resolve_times`.
- **FAIL:** a designed transition window overlaps a full-screen span; a file is missing.
- **WARN:**
  - a card under `min_dur`;
  - a phrase matched with a ratio under 1, or not found;
  - an insert while a literal title line is on screen;
  - a punch, shake or flash starting during a card insert (playbook:594);
  - `sfx: null`;
  - an insert cue within 2 f of a manual `audio.sfx` peak.
- Insert cues carry `move: true`, so the whoosh-on-plain-cut rule (145-149) skips them. The rotation check (150-154) runs on the merged cue list.
- Each insert t0 and each full-screen t1 is added to `changes` (157).

**Smaller changes:**
- `pipeline/review_frames.py:main` (31-36): one tile per insert at t0 + anim + 0.2 s.
- `pipeline/times.py`: print the resolved inserts.
- `pipeline/style_default.json`: the `insert` block and `"layers": []`.
- `pipeline/requirements.txt`: `pillow`. It is already locked at 12.3.0 with WebP and LittleCMS (checked), so nothing new is installed.
- `projects/_template/script.json`: `"inserts": []`.
- `.gitignore`: `projects/*/inserts/`, `*.heic`, `*.HEIC`. Screenshots can contain private chats, and the repo is public. `*.mov`/`*.mp4` are already ignored.
- Skill text: an Inserts section, brief dictionary rows and the report template.
- `docs/adr/0009-raster-inserts.md`.
- `preview.py` is not changed in v1: its stills skip camera and grade anyway (preview.py:1), and the review sheet is the check.

### Interactions

- **Person matte.** Inserts and brand layers are composited outside the `a *= 1 − person_alpha` step, so they are never masked. Full-screen frames leave `occlude_frames`, `occupancy` and `person_box`, because the person is not visible on them. The export's `render_layer` reads the same `occlude_frames`, so text baking matches. Captions on top of an insert are out of scope for v1.
- **Safe zone and layout solver.**
  - Inserts are placed after `measure()` and before blocks. They avoid the face, reserved brand rects and pinned subtitle blocks.
  - Unpinned blocks then flow around inserts through `place.exclude`, and any remaining overlap is a blocking `!!`.
  - Inserts and brand layers use the same safe area (x 128-952, y 250-1480) with the rail and `style.layout.exclude`, which is where YOCASE scripts put baked graphics. The y≈170 top and x 60 edge from the third-party skill are not adopted.
  - **On talking heads (yocase_2477 prototype):** face + 40 covers about x 262-804, y 367-938. Neither the 117 px above it nor the ~140 px beside it fits a card, so 315-580 px cards land centred just under the chin (y ≈ 870-940), 100% over her chest. A 315×683 phone screenshot fits nowhere and gets `!!`. Subtitles below such a card have about 250 px left.
- **Subtitle timing.** Reveal times and screen windows do not change. Inserts are anchored on heard words through `VoiceMap`, so voice-overs and an automatically cut EDL keep them on the phrase.
- **FCPXML export.**
  - Each card insert and brand layer is its own ProRes 4444 alpha clip, streamed. Cards get `overlay_at` keyframes like text.
  - B-roll is a video-only clip on the lane above the spine. The spine keeps the voice, so nothing needs muting.
  - The grade is still not carried over (unchanged).
  - A whole-reel brand layer is a full-length alpha clip, which costs disk; a PNG still via `still_asset` (334-346) is a possible later optimisation once Resolve's alpha-PNG import is checked.
- **lint_edit and the pre-export checklist.** The "don't export if…" items in this area:
  - an insert without sound: WARN;
  - an insert over the face, over subtitles or outside the safe area: `!!` in the build report, treated as blocking by the skill;
  - a cropped sticker: OUTSIDE on brand layers.
- **Audio mix.**
  - Insert cues join the SFX cues before `audio.render`. The no-music variant keeps them.
  - Keyframed ducking, if built elsewhere, keys on words, not on these cues.
  - Insert media never enters the mix: `audio.render` reads only the reel's source, and converted inserts have no audio stream.
- **Shared build state.**
  - `timeline.json`, `camera.json`, `meta.json` and `build/overlay/` stay single-slot, so builds still run one at a time and review/export follow the build of the same project.
  - Insert media and sprites live under `build/<src>/inserts/` with hashed names, so variants of one source don't collide.
- **Archiving to `done/`** must keep each project's `inserts/` next to `script.json`, or re-renders lose their files.

### Verification

Fixtures in scratch, `D=/private/tmp/claude-501/design/inserts_test`:
- `script.json`: a copy of `projects/yocase_2373/script.json`;
- `inserts/set.jpg`: `ffmpeg -ss 10.5 -i build/yocase_2373/media/IMG_2373.mov -frames:v 1`;
- `inserts/review.png`: 1179×2556, drawn with Pillow;
- `inserts/sticker.png`: a 400×400 RGBA flat-colour disc;
- `inserts/rot.heic`: a Pillow JPEG with EXIF orientation 6, then `sips -s format heic`;
- `inserts/broll.mp4`: `ffmpeg -f lavfi -i testsrc2=s=1920x1080:r=25:d=3 -f lavfi -i sine=f=1000:d=3 -shortest`.

**0. Baseline, before any code change.** `output/yocase_2373_draft.mp4` (Oct 13 10:24) predates the last `build_timeline.py` change (11:47), so it is not a valid baseline.
- Run `X264_PRESET=veryfast .venv/bin/python pipeline/build.py projects/yocase_2373/script.json --name yocase_2373_base_draft`.
- Keep the log, and `cp build/timeline.json $D/base_timeline.json`.

**1. Pure Python** (`.venv/bin/python -B`, no render):
- **`find_phrase` on 2373** (values re-run and confirmed from `proto_inserts.py`):

  | Phrase | Expected |
  |---|---|
  | «подарувати турботу» | 5.68-6.66 |
  | «дуже красиве пакування» | 14.16-15.36 |
  | «шампунь кондиціонер маска» | 10.46-11.98 |
  | «своїй» occurrence 2 | 19.74 |
  | «repair plex» | 8.245-8.86 |
  | «yocase repair plex» | 7.86, ratio 0.93, "-Case Repair Plex", WARN |
  | «після салону» | 27.66-28.46 |
  | «салон» | only 28.02 («Салонний» at 15.565 scores below 0.8) |

- **`resolve_times`:**
  - card «подарувати турботу» → 5.68-7.18 (f 170-215);
  - «після салону» → t1 = 28.833 with WARN 1.17 s < 1.5 s;
  - full «дуже красиве пакування» → 14.16-15.56.
- **`prepare`:**
  - `rot.heic` → 200×400 PNG;
  - `sticker.png` → `cutout`; `set.jpg` → `card`;
  - an unreferenced `broll.mp4` → only `view/broll.jpg`, no `.mov`;
  - referenced with `src [0.5, 2.5]` → 1080×1920, 60 frames, and `ffprobe -show_streams` lists no audio stream.
- **`style_sprite`** (numbers from the reviewer prototype):
  - card: corner alpha < 16, interior pixel = source ±1, border pixel #111 ±2, shadow alpha > 0 below the card;
  - cut-out: a #111 ring 1 px outside the alpha edge.
- **`state`:** snap at f0 → (0.34, 0.977); f0+2 → (1, 1). Pop at f0+9 → (1, 1).
- **`place_insert` on yocase_2477** (no pinned blocks): a 430×322 card at 4.0-5.8 s does not intersect face + 40 (the prototype spot was (324, 940)); 315×683 → `!!`.
- **`place_insert` on 2373:** a 430×322 card at 5.68-7.18 must not intersect blocks 3/4's pinned boxes [128,250,538,400] / [128,252,538,340] + 20. The naive prototype spot (324, 260) does intersect them; this is the case the check guards. Expect y ≥ 420.

**2. Integration draft.** Add to `$D/script.json`:
- i0: card `set.jpg` at «подарувати турботу»;
- i1: `review.png` with `crop [0,0,1,0.35]` at «шампунь кондиціонер маска»;
- i2: full `broll.mp4` at «дуже красиве пакування»;
- i3: cut-out `sticker.png` at «своїй» occurrence 2, `size: "s"`, `place: {"safe": [128,1130,840,1480]}`. That box is below the tracked face + 40 (y ≤ 1122) and the person matte covers 83-93% of it at 19.8-21.0 s;
- `behind: true` on screen 13 (19.62-21.18), so these frames are text-behind;
- i4: card at «після салону»;
- `grade: {"contrast": 1.3, "saturation": 1.3}`.

Run `X264_PRESET=veryfast .venv/bin/python pipeline/build.py $D/script.json --name ins_test_draft`. Expect:
- **Log:** `ins i0..i4` lines with no `!!`, only the short-final-insert WARN. No block line has a `!!` that the baseline log lacked, and no `overlaps insert` line.
- **Video:** `[video] rc=0`; `ffprobe -count_frames` → 865.
- **No grade on B-roll:** output frame 441 (14.7 s) vs frame 16 of the converted broll `.mov` gives PSNR ≥ 38 dB on the crop x 100-980, y 700-1800 (below block 9). Output frame 90 (3.0 s) differs clearly from the source frame (graded).
- **Never masked (decisive):** in output frame 609 (20.3 s), the disc interior (centre ± 40 px) has the disc colour ±8 per channel. A person-shaped hole would show the video, which covers 89% of that box.
- **Same, in pure Python:** `video_pass.render_frame(…, i=609)` with `masks = np.broadcast_to(np.uint8(255), (865, 480, 270))` and occl ⊇ {609}, vs `masks=None`. The insert rect is identical, while text pixels lose their alpha in the masked call, which proves the matte was applied.
- **SFX timing:** in the merged cue list, every insert cue has `t + t_peak_s = f0/30` within 1 ms; i2's cue is a whoosh peaking at 425/30.
- **Review:** the `review_frames.py output/ins_test_draft.mp4` tiles show the rounded card with border and shadow and the cut-out outline. The phone-crop preview (`SKILL.md:111`) shows nothing clipped.
- **Time:** render time ≤ baseline + 10%.

**3. Lint.** `lint_edit.py $D/script.json`: 0 FAIL. The "28.8 s with no visible change" WARN is split. No "whoosh on a plain cut" WARN for insert cues.

**4. Export.** `.venv/bin/python pipeline/export_fcpxml.py $D/script.json --name ins_test_draft --procs 2`. Expect:
- i0, i1, i3 and i4 as ProRes 4444 `yuva444p10le`;
- i2 as an asset-clip of the converted `.mov`, with no `hasAudio`;
- lanes in the order above.

RAM: a small harness runs `write_layer` for i0 and reports `resource.getrusage(RUSAGE_SELF).ru_maxrss` growth < 100 MB. `/usr/bin/time -l` reports only the largest single process, which is a text worker. If Resolve and the bridge are running: `resolve_check.py`.

**5. Regression.** After the change, rebuild the unchanged `projects/yocase_2373/script.json` with `--name yocase_2373_regress_draft`.
- The `psnr` filter against `output/yocase_2373_base_draft.mp4` → inf.
- `build/timeline.json` equals `$D/base_timeline.json` except `"layers": []` and the new `style.insert` / `style.layers` keys.
- Afterwards, delete the regenerable `build/yocase_2373/inserts/` and rebuild 2373 before any review or export of it (single-slot state).

### Risks

- **Face boxes on non-talking footage.** `prep.track` never leaves `face` empty when the matte has a blob: without a Haar hit it estimates a face from the top of the blob (`prep.py:219-222`). On product B-roll (2373) the "faces" are hands and bottles (42-249 px). `min_face_px` drops small ones; the rest only over-constrain placement. A real face narrower than 120 px (a wide shot) relies on `person_cost` and the review tile.
- **Talking-head geometry.** Cards cover her chest and hands, possibly the product she holds. Tall screenshots need a crop or full-screen. Subtitles get squeezed below the card.
- **Pinned subtitles.** Reels with many hand-placed blocks (2373) leave little room. Expect `!!` that Claude resolves by unpinning.
- **Colour.** A missed ICC conversion makes product colours dull or oversaturated. Mitigation: sips `--matchTo` for HEIC, `ImageCms` for the rest. Sprites stay 8-bit sRGB, the same convention as the text layer.
- **HDR.** HDR video (brand-supplied clips often are) is refused: there is no tone-mapping (no zscale/libplacebo). HEIC gain maps are dropped by sips (SDR base image).
- **Animated media.** Animated GIF/WebP cards are stills (first frame plus a WARN). Animated GIF works only as full-screen video; animated WebP may not decode in ffmpeg.
- **macOS only:** `sips` (fine per ADR-0005).
- **Public repo:** insert media and brand assets must stay untracked.
- **Phrase limits:** inflection and Latin brand names can miss. Numeric `at` drifts when the EDL changes.
- **Disk:** full-screen video inserts are ProRes, about 27 MB per second of `src`. Only referenced spans are converted.
- **RAM:** the export's text layers still buffer frames (`export_fcpxml.py:133`, up to about 1.4 GB per measured layer). A doodle without `t1` buffers every frame to the end. `--procs 2` lowers the peak but does not fix that; streaming text layers belongs to the portability work. Inserts add under 100 MB in total.

### Effort

| Piece | Effort |
|---|---|
| `inserts.py` prepare/inventory/CLI (stills, video previews, convert-on-reference) + `ingest.py` audio/focus/trim | M |
| `find_phrase`/`resolve_times` + `heard_words` + `norm` move | S |
| `place_insert` + build_timeline integration (pinned-block exclusions, new exclude list, overlap check, skip frames, occl, report, layers) | M |
| `layers.style_sprite` (cv2) + `state` + `Compositor` + video_pass integration | M |
| Auto SFX cues (build + export + lint `move`) | S |
| export_fcpxml: `write_layer`, broll, lanes, `--skip-layers`, procs | M |
| Brand layers (`style.layers`, gradient/image, reserve, safe check, export) on top of the above | S |
| lint, review_frames, times | S |
| Skill text, brief rows, Ukrainian report, ADR-0009, template, .gitignore | S |
| Fixtures + baseline + verification run | S |

Overall: L.

### Open questions for the developer

1. **Brand assets in a public repo.** Logos, strips, stickers and permanent per-brand product photos are client trademarks or material. Should they be tracked in `brands/<brand>/layers/`, or kept untracked on Marina's Mac, copied at setup and not updated by `git pull`? No YOCASE or TOSUMI layer assets exist today, so brand layers ship unused until this is decided.
2. **Default insert look.**
   - Animation: `snap` (85 ms, third-party) or `pop` (0.85→1.04→1.00, playbook 2.15)?
   - SFX levels: studio levels (swish −14, pop −20, from the playbook SFX table) or the third-party ~−13?
3. **Talking-head placement and crops.**
   - On centred talking heads the only free spot is over her chest just under the chin. Is that acceptable for brand reels, or should talking-head reels default to `s` cards and send anything larger full-screen?
   - The third-party skill forbids cropping inserts. May Claude crop a screenshot to the part that proves the point on its own (always reported), or only when Marina asks?
