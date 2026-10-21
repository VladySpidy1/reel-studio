---
name: reel-subtitles
description: "Reference: pipeline commands, subtitle markup, layout fixes and the TOSUMI skit style. Read by the reel skill (and by the developer as /reel-subtitles); not an entry point: a new reel starts with the reel skill."
disable-model-invocation: true
---

# Reel subtitles and pipeline (reference)

A reference, read by section: the `reel` skill drives a creator reel step by step and points here. Everything is
already researched and built: do not re-research references, fonts or SFX, do not spawn subagents or workflows, do
not read pipeline source unless a command fails. The look is data: the subtitle system in `docs/STYLE.md`, the
brand's look in `brands/<brand>/`, the format's structure in `formats/<format>/`; never copy style into a script.

"The reel's script" is `inbox/<reel>/script.json` for a creator reel (the `reel` skill) and
`projects/<name>/script.json` for the developer's example reels. `<reel>` below is either folder's name.

## 0. Health
`.venv/bin/python pipeline/doctor.py`; on a FAIL stop (creator: CLAUDE.md "Health"). Never run setup in a reel
session: `pipeline/setup_mac.sh` is the developer's, done in person (INSTALL.md).

## 1. Prepare the footage (~10 min per 4 min of raw clips on an M2 Pro)
- Creator reel: `.venv/bin/python pipeline/inbox.py prep <reel>` (her videos in shooting order; insert files in
  `inbox/<reel>/inserts/` are never ingested).
- Developer reel: `.venv/bin/python pipeline/ingest.py build/<name> <clip> [<clip> ...]`, then
  `.venv/bin/python pipeline/prep.py build/<name>/source.ffconcat build/<name>`.

ingest makes 1080x1920 30 fps ProRes intermediates and `source.ffconcat` (the clips back to back = the script's
`source`; clip boundaries are the cuts). prep writes words.json (whisper large-v3 per speech chunk, so every
repeated take is kept), cuts.json, masks.npy (person matte), track.json, motion.json and sheet.jpg.

## 2. The script
**Brand and format.** `.venv/bin/python pipeline/resolve.py --list` gives the ids and aliases; map her words to ids
yourself (Ukrainian inflects). Read `brands/<brand>/BRAND.md`, `formats/<format>/FORMAT.md` and the learned rules
(`learned/general.md`, `learned/brands/<brand>.md`, `learned/formats/<format>.md` where they exist). Start from
`formats/<format>/template.json`; `.venv/bin/python pipeline/resolve.py <script>` shows what it resolves to (fonts,
colours, music, grade, lint profile, warnings). A script key overrides the brand («без музики»:
`"audio": {"music": null}`).

**Paths and the cut.** `source`, `words`, `masks`, `track` point at `build/<reel>/`; `src_duration` is cuts.json
`duration`.
- Talking head shot raw: `.venv/bin/python pipeline/trim.py <script>` prints the attempts, a contact-sheet command per
  group of repeated takes and the product moments the cut would lose; watch them, set `trim.drop` / `trim.keep` /
  `trim.punch` only to change its choice, then `trim.py <script> --write` (edl, takes, `audio.xfade_frames`).
  A constant bed under the voice or a pre-edited video: no trim.
- Subtitles only (pre-edited): one `src` segment over the whole source, `takes` the same.
- Skit or lineup: the edl by hand or by a generator in `projects/<name>/`; trim head silence (start ~0.15 s before
  the first word); with a product, a 1.2 s `hold` on the sharpest product frame after the last word, then the rest
  of the source so the end loops.
- Voice independent of the picture: `audio.voice_over` `[{"src": [a, b], "at": out_t}]` plus `audio.mute`
  `[[t0, t1]]`; extend the screen with `t1_override` when the line runs past the take.

`.venv/bin/python pipeline/times.py <script>` prints what is heard per take in OUTPUT time, brand words as the
script types them (`yocase`, `repair plex`), `CTA spoken` lines, the resolved inserts and the gestures. Every other
time in the script (camera, sfx, literal titles, inserts, doodles, freezes) is an OUTPUT time.

**Screens.** One screen per take; blocks in spoken order; 2-4 words per line, lowercase, no punctuation, line breaks
by meaning, ONE accent per half-sentence. Write words in correct spelling: alignment is fuzzy.
- `*word*` accent (brand accent colour, serif italic), `_word_` emphasis (serif, main colour), `//` ornament, `№N`
  take label, `\\*` (JSON) a literal asterisk.
- `display{heard}`: shows `display`, aligns to what whisper heard (`погано{башко}`); brand words come from the
  brand's `terms` instead, so type their display form.
- A literal line `{"text": "…", "literal": true, "t": <output s>}` shows unspoken text (a title).
- `"preset": "hook"` (first block of screen 1): her ХУК verbatim, 0-2.5 s, centred near the top, off the face.
  `"preset": "cta"`: the block of a spoken call to action becomes a card with a chime, at least 2 s; the code word
  is its `*accent*`. Other presets: `interjection`, `punchline`, `brand_name`, `product_label`.
- Censorship: `"censor+": ["гроші", …]` (or `"@standard"`) shows `гр*ші` in every form; literal lines only with
  `"censor": true`.
- Let the solver place blocks. A `place` hint (`x`, `y`, `safe` box, `exclude`) only to fix a finding, always inside
  x 128-952, y 250-1480 and off the rail (x > 850 and y > 1050); plan lines for ~820 px, <= 17 characters beside a
  person.

**Camera and sound.** Product, brand and any reel with gestures: the `reel-videographer` skill (its effect table
and `formats/<format>/FORMAT.md`). The TOSUMI comedy skit only:
- `camera`: push 1.00->1.04, punches 1.05-1.07 on fail words (`target: "face"`, `anchor: true`); an interjection
  after a silent beat: `freezes` on the beat + scale 1.05 inout punch + 1.07 snap + shake; `flashes` on the product
  hold start; per-take `gains` only if takes differ in white balance.
- Interjections («ой», «ну», «фу»): own block `{"preset": "interjection", "lines": ["*ой*"]}`, `behind: false`,
  `until` ~0.9 s later, `place` beside the face. Final punchline: `"preset": "punchline"`, `behind: false`,
  `place.y` ~300.
- `audio.sfx` (names = files in assets/sfx without .wav, `peak_at` = output time; `assets.py sfx <query>` lists
  them): a soft whoosh on every cut (-11 dB), boing / soft punch on gags (-13..-16), record scratch at a freeze
  (-9), bass thump on a big pop (-9), a light pop on pink words (-23), shutter + sparkle on the product hold. Music:
  the brand's bed; `audio.music.dropouts` for a gag freeze. `doodles` (max 3): `circle` around the product during
  the hold, `sparkle` stars.

## 3. Draft and its findings
```
.venv/bin/python pipeline/lint_edit.py <script>
.venv/bin/python pipeline/build.py <script> --draft
.venv/bin/python pipeline/review_frames.py output/<reel>_draft.mp4
.venv/bin/python pipeline/contact_sheet.py output/<reel>_draft.mp4 0 <dur> 0.3 --phone
```
lint must show 0 FAIL (a creator reel also gets `brief:` lines). The build prints problems first; its checks
(`build/meta.json` "checks", and the report's `checks`) FAIL before the render. `--allow-check-fail` renders anyway:
developer only. The review sheet has one tile per screen and insert; the `--phone` sheet draws the Instagram crop.

| Finding | Fix |
|---|---|
| `OUTSIDE the IG crop-safe area`, `letters reach … past` | shorter lines, or `place` inside the safe area |
| `no free spot` (WARN) | a `place` hint or a shorter `until`; if it stays, look at its tile and report it |
| two blocks overlap, letters collide | split the screen, shorten `until`, or `place` |
| hook or CTA `over her face` | `place.y` in the preset's zone, shorter lines |
| `hook shown …` | hook lines literal from 0, shown 2.0-3.0 s, at most 7 words |
| `spoken CTA … not in a CTA block` | `"preset": "cta"` on that phrase's block |
| `CTA … cut by the reel end` | extend the last edl segment, or end with a hold |
| `NOT FOUND` | type it as heard, or `display{heard}`; brand words via `terms` |
| a glyph not in the font | drop or replace the character (emoji, exotic quotes) |
| insert `while the hook is up` | anchor it later |
| insert `no spot clear of the face / subtitles` | unpin a nearby block, crop (if asked), `"size": "s"`, `"mode": "full"` |
| insert `is silent` | drop `"sfx": null` unless the brief says «без звуку» |

## 4. Final render
```
.venv/bin/python pipeline/build.py <script>
.venv/bin/python pipeline/build.py <script> --skip-timeline --skip-overlay --no-music --name <reel>_no_music
```
`output/<reel>.mp4` (H.264 1080x1920 30 fps, AAC 320k, -14 LUFS) and the no-music variant (for a trending in-app
sound). `output/<reel>.report.json` holds the report's numbers.

## 5. Editable project (DaVinci Resolve / Final Cut Pro)
```
.venv/bin/python pipeline/export_fcpxml.py <script>
```
Writes `output/<reel>_project/` (self-contained): the `.fcpxml` plus media (takes, holds, every subtitle block,
insert and brand layer as a ProRes 4444 alpha clip, SFX, the music as mixed with its ducking baked in plus the raw
track muted). In Resolve: new project, File > Import > Timeline, tick "Use sizing information". Not in the project:
the grade and white balance, zoom and punch-in blur, the voice's crossfades at speech cuts, the limiter. Never move
the repository folder afterwards (absolute file URLs).

**Order matters:** build.py, review_frames.py and export_fcpxml.py share the build slot (`build/timeline.json`,
`build/meta.json`); review and export run right after the build of the SAME reel, and they refuse another reel's
slot.

## Learned rules (developer-promoted, with the date)
Creator corrections go to `learned/` (the `reel` skill); only the developer promotes them into the brand, format or
this file.
- 2026-10-13, YOCASE: "между текстом должны быть хорошие отступы, нормальные, чтоб текст не был впритык" - the
  TOSUMI tight spacing is TOSUMI-only. The YOCASE spacing and colours are in `brands/yocase/brand.json`:
  `"brand": "yocase"`, no `style` in the script. With taller lines keep blocks to 2-3 lines and split long screens.
- 2026-10-13, YOCASE: already-edited videos (logo, insets, chat bubble baked in) get subtitles only:
  `"format": "subtitles-only"` (one `src` segment, no grade/music/SFX); exclude the baked graphics with
  `style.layout.exclude+` or `place.exclude`, and don't caption a line that is already on screen (e.g. a chat
  bubble).
- 2026-10-13, all brands: subtitles were cut off at the left edge on a phone in Instagram - IG fills 19.5:9 /
  20:9 screens and crops ~100 px per side. Safe area x 128-952, y 250-1480, rail x>850 & y>1050
  (`style_default.json`); hand-placed `place.x` / `place.safe` stay inside it, and any `OUTSIDE the IG crop-safe
  area` is a build FAIL. Check on the phone crop: `contact_sheet.py … --phone`.
