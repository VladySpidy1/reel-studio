---
name: reel-subtitles
description: Edit a vertical talking/skit video into an Instagram reel in the TOSUMI house style - small condensed white subtitles with pink serif-italic punch words, per-letter elastic typewriter, editorial placement beside the person (text-behind-subject), punch-ins, SFX, music, product freeze. Use when the user drops a .MOV/.MP4 and asks to "змонтуй", "додай субтитри", "зроби рілс", "edit this reel".
---

# Reel subtitles + edit (house style)

Everything is already researched and built. Do NOT re-research references, fonts or SFX, do NOT spawn
subagents or workflows, do NOT read pipeline source unless a command fails. The style is fixed in
`docs/STYLE.md` + `pipeline/style_default.json`; read `docs/STYLE.md` once.

Token budget: aim for one draft render + at most one fix render. Look at no more than 3 images total.

## 0. One-time setup (skip if `python pipeline/prep.py --help` works)
```
pip install -r pipeline/requirements.txt
```
Needs ffmpeg on PATH and Google Chrome installed (the subtitle renderer uses it headless).

## 1. Prepare the video (no thinking needed, ~5-20 min CPU)
```
python pipeline/prep.py <video> build/prep_<name>
```
Outputs words.json (whisper large-v3, onset-snapped), cuts.json (takes), masks.npy (person matte),
track.json, sheet.jpg (1 fps contact sheet). Look at sheet.jpg once to understand the video.

## 2. Write the script  `projects/<name>/script.json`
Copy `projects/_template/script.json`. Fill:
- `source`, `src_duration` (cuts.json `duration`), `takes` (cuts.json `takes`), paths to prep outputs.
- `edl`: trim head silence (start ~0.15 s before the first word) and, if there is a product, add a
  1.2 s `hold` on the sharpest product frame right after the last word, then the rest of the source
  (so the person walks out and the end loops). Without a product: one `src` segment.
- Run `python pipeline/times.py projects/<name>/script.json` -> transcript per take in OUTPUT time.
  All other times in the script (camera, sfx, literal titles, doodles, freezes) are OUTPUT times.
- `screens`: one screen per take; blocks in spoken order. Markup: `*(fail word)*` pink serif,
  `_dream word_` white serif, `//` pink ornament, `№N` label, literal lines for a hook title.
  Write words in correct spelling - alignment to the transcript is fuzzy (typos, split/merged words OK).
  Rules: lowercase, no punctuation, 2-4 words per line, line breaks by meaning, ONE pink accent per
  half-sentence, pink only on the punch/fail/funny word.
  Interjections ("ой", "ну", "фу") -> own block, `{"text":"*ой*","anim":"pop","scale":3}`,
  `behind:false`, `until` ~0.9 s later, `place` beside the face.
  Final punchline -> own block, scale 1.55, leading 0.86, `behind:false`, `place.y` ~300.
- `camera`: push 1.00->1.04, cut_in 1.06, punches 1.05-1.07 on fail words (`target:"face"`), for an
  interjection after a silent beat: `freezes` on the beat + scale 1.05 inout punch + 1.07 snap + shake.
  `flashes` on the product hold start. Per-take `gains` only if takes differ in white balance.
- `audio.sfx` (names = files in assets/sfx without .wav, `peak_at` = output time): whoosh_soft_01_air_sweep
  on every cut (-11 dB), boing_01_spring / punch_soft_impact on gags (-13..-16), record_scratch_01 at a
  freeze (-9), bass_thump_02_synth on a big pop (-9), pop_04_light on pink words (-23), camera_shutter_01 +
  sparkle_hit_fairy + shimmer_sparkle_whoosh on the product hold. Music: copy the template block
  (Gummies, -17 dB, no sidechain); add `dropouts` for a gag freeze. Keep `voice.process` false.
- `doodles` (optional, max 3): `circle` around the product during the hold, `sparkle` stars.

## 3. Draft render (~2 min)
```
X264_PRESET=veryfast python pipeline/build.py projects/<name>/script.json --name <name>_draft
python pipeline/review_frames.py output/<name>_draft.mp4
```
The build prints the block layout; lines with `!! no free spot` need a `place` hint or a shorter `until`.
Open the ONE review sheet (one frame per screen). Fix only: overlaps with the face/product, clipped or
unreadable text, wrong words. Do not polish taste.

## 4. Final render
```
python pipeline/build.py projects/<name>/script.json --name <name>
```
Deliver `output/<name>.mp4` (H.264 1080x1920 30 fps, AAC 320k, -14 LUFS). Mention in one line which
creative extras were added (hook title, freeze, doodles) so the user can drop them.
