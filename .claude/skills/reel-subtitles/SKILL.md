---
name: reel-subtitles
description: Edit a vertical talking/skit video into an Instagram reel in the TOSUMI house style - small condensed white subtitles with pink serif-italic punch words, per-letter elastic typewriter, editorial placement beside the person (text-behind-subject), punch-ins, SFX, music, product freeze. Use when the user drops a .MOV/.MP4 and asks to "змонтуй", "додай субтитри", "зроби рілс", "edit this reel".
---

# Reel subtitles + edit (house style)

Everything is already researched and built. Do NOT re-research references, fonts or SFX, do NOT spawn
subagents or workflows, do NOT read pipeline source unless a command fails. The look is data: the subtitle system
in `docs/STYLE.md` (read it once), the brand's look in `brands/<brand>/`, the format's structure in
`formats/<format>/`; never copy style into a script.

Aim for one draft render + at most one fix render. The picture side (which takes, cuts, transitions, zooms,
freezes, SFX, beats) follows the `reel-videographer` skill - load it for any reel with movement or products. Watch
the footage and the whole draft on contact sheets (`pipeline/contact_sheet.py`); never cap the looking - a junk
take the creator finds costs more than the images.

## 0. One-time setup on a Mac (skip if `.venv/bin/python pipeline/prep.py --help` works)
```
zsh pipeline/setup_mac.sh
```
Installs Homebrew ffmpeg, the locked Python deps in `.venv` and the models; needs Google Chrome. Run every
step below with `.venv/bin/python`.

## 1. Prepare the footage (no thinking needed, ~10 min for 4 min of raw clips on an M2 Pro)
```
.venv/bin/python pipeline/ingest.py build/<name> <clip> [<clip> ...]
.venv/bin/python pipeline/prep.py build/<name>/source.ffconcat build/<name>
```
ingest turns the raw phone clips (any number, in shooting order) into 1080x1920 30 fps ProRes intermediates and
`source.ffconcat` (the clips back to back = the script's `source`; clip boundaries are the cuts). prep writes
words.json (whisper large-v3 per speech chunk, so every repeated take is kept), cuts.json (takes = clips),
masks.npy (person matte), track.json, sheet.jpg (up to 48 frames). Look at sheet.jpg once.

## 2. Write the script  `projects/<name>/script.json`
Brand and format first:
- `.venv/bin/python pipeline/resolve.py --list` -> brand and format ids with their aliases. Map the brief's words to
  ids yourself (Ukrainian inflects: «для йокейсу» = `yocase`, «говорючу голову» = `talking-head`). If the brand is
  missing, ask only for the brand. The format defaults to `talking-head`; when the footage has baked graphics
  (logo, insets, chat bubble) it is `subtitles-only` - say so in the report.
- Read `brands/<brand>/BRAND.md` and `formats/<format>/FORMAT.md`, plus `learned/brands/<brand>.md` and
  `learned/formats/<format>.md` when they exist.
- Copy `formats/<format>/template.json`, set `"brand"` (and keep `"format"`), then check what it resolves to:
  `.venv/bin/python pipeline/resolve.py projects/<name>/script.json` (fonts, colours, music, grade, lint profile,
  warnings). The brand's music bed, grade and SFX palette come from there; a script key overrides them
  («без музики»: `"audio": {"music": null}`).

Fill:
- `source` (`build/<name>/source.ffconcat`), `src_duration` (cuts.json `duration`), `takes` (the source ranges
  you use, in output order), paths to prep outputs.
- Voice independent of the picture (a line over B-roll or over the right product shot): `audio.voice_over`
  `[{"src": [a, b], "at": out_t}]` plus `audio.mute` `[[t0, t1]]` for the picture's own sound there; extend the
  screen with `t1_override` when the line runs past the take. build/times warn about doubled voice.
- `edl`: trim head silence (start ~0.15 s before the first word) and, if there is a product, add a
  1.2 s `hold` on the sharpest product frame right after the last word, then the rest of the source
  (so the person walks out and the end loops). Without a product: one `src` segment.
- Run `.venv/bin/python pipeline/times.py projects/<name>/script.json` -> transcript per take in OUTPUT time.
  All other times in the script (camera, sfx, literal titles, doodles, freezes) are OUTPUT times.
- `screens`: one screen per take; blocks in spoken order. Markup: `*(fail word)*` pink serif,
  `_dream word_` white serif, `//` pink ornament, `№N` label, literal lines for a hook title.
  Write words in correct spelling - alignment to the transcript is fuzzy (typos, split/merged words OK).
  Rules: lowercase, no punctuation, 2-4 words per line, line breaks by meaning, ONE pink accent per
  half-sentence, pink only on the punch/fail/funny word.
  Interjections ("ой", "ну", "фу") -> own block, `{"text":"*ой*","anim":"pop","scale":3}`,
  `behind:false`, `until` ~0.9 s later, `place` beside the face.
  Final punchline -> own block, scale 1.55, leading 0.86, `behind:false`, `place.y` ~300.
- `camera` and `audio.sfx`: product, brand and any reel with gestures -> the `reel-videographer` skill (its effect
  table replaces the two bullets below; `formats/<format>/FORMAT.md` when the format has one). The two bullets
  below are the TOSUMI comedy-skit style only.
- `camera` (TOSUMI skit): push 1.00->1.04, cut_in 1.06, punches 1.05-1.07 on fail words (`target:"face"`), for an
  interjection after a silent beat: `freezes` on the beat + scale 1.05 inout punch + 1.07 snap + shake.
  `flashes` on the product hold start. Per-take `gains` only if takes differ in white balance.
- `audio.sfx` (TOSUMI skit; names = files in assets/sfx without .wav, `peak_at` = output time): whoosh_soft_01_air_sweep
  on every cut (-11 dB), boing_01_spring / punch_soft_impact on gags (-13..-16), record_scratch_01 at a
  freeze (-9), bass_thump_02_synth on a big pop (-9), pop_04_light on pink words (-23), camera_shutter_01 +
  sparkle_hit_fairy + shimmer_sparkle_whoosh on the product hold. Music: the brand's bed (no sidechain); add
  `audio.music.dropouts` for a gag freeze. Keep `voice.process` false.
- `doodles` (optional, max 3): `circle` around the product during the hold, `sparkle` stars.

## 3. Draft render (~2 min)
```
.venv/bin/python pipeline/lint_edit.py projects/<name>/script.json
X264_PRESET=veryfast .venv/bin/python pipeline/build.py projects/<name>/script.json --name <name>_draft
.venv/bin/python pipeline/review_frames.py output/<name>_draft.mp4
.venv/bin/python pipeline/contact_sheet.py output/<name>_draft.mp4 0 <dur> 0.3
```
lint_edit must show 0 FAIL. The build prints the block layout; lines with `!! no free spot` need a `place` hint
or a shorter `until`. Open the review sheet (one frame per screen) for the text: overlaps with the face/product,
clipped or unreadable text, wrong words. Then the 0.3 s contact sheet for the picture: every shot a line or a
deliberate action, no junk frames, the label on screen = the product named.

## 4. Final render
```
.venv/bin/python pipeline/build.py projects/<name>/script.json --name <name>
```
Deliver `output/<name>.mp4` (H.264 1080x1920 30 fps, AAC 320k, -14 LUFS). Mention in one line which
creative extras were added (hook title, freeze, doodles) so the user can drop them.

## 5. Editable project (DaVinci Resolve / Final Cut Pro)
```
.venv/bin/python pipeline/export_fcpxml.py projects/<name>/script.json --name <name>
```
Writes `output/<name>_project/` (self-contained): `<name>.fcpxml` + media (takes, product holds, every subtitle
block as a ProRes 4444 alpha clip, SFX, music, voice-overs). In Resolve: new project, File > Import > Timeline,
tick "Use sizing information". Not in the project yet: grade/white balance, zoom blur, audio fades, limiter.

**Order matters:** build.py, review_frames.py and export_fcpxml.py share `build/timeline.json` / `build/meta.json`,
so run review and export right after the build of the SAME project (looping all builds first gives every
project the last reel's subtitles).

## Learned rules (creator/developer corrections, with the date)
- 2026-10-13, YOCASE: "между текстом должны быть хорошие отступы, нормальные, чтоб текст не был впритык" - the
  TOSUMI tight spacing is TOSUMI-only. The YOCASE spacing and colours are in `brands/yocase/brand.json`:
  `"brand": "yocase"`, no `style` in the script. With taller lines keep blocks to 2-3 lines and split long screens.
- 2026-10-13, YOCASE: already-edited videos (logo, insets, chat bubble baked in) get subtitles only:
  `"format": "subtitles-only"` (one `src` segment, no grade/music/SFX); exclude the baked graphics with
  `style.layout.exclude+` or `place.exclude`, and don't caption a line that is already on screen (e.g. a chat
  bubble).
- 2026-10-13, all brands: subtitles were cut off at the left edge on a phone in Instagram - IG fills 19.5:9 /
  20:9 screens and crops ~100 px per side. Safe area is now x 128-952, y 250-1480, rail x>850 & y>1050
  (`style_default.json`); hand-placed `place.x` / `place.safe` must stay inside it (the solver clips them).
  Plan lines for ~820 px of width, e.g. <=17 characters beside a lamp; any `OUTSIDE the IG crop-safe area`
  in the build log must be fixed before delivery. Check on a crop preview:
  `ffmpeg -i output/<name>.mp4 -vf crop=886:1920:97:0 -an <scratch>/phone.mp4` + `contact_sheet.py`.
