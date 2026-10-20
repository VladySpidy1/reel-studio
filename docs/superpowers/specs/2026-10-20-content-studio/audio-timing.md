## Audio and timing automation (dead-air trim, speed, ducking, music and SFX, report numbers)

### Goal

Six mechanics move from Claude's hand-work into deterministic code (ADR-0001). Claude keeps the taste calls: which take, which product moment, which track.

1. **`pipeline/trim.py` proposes the edit (EDL) and takes for a talking-head reel shot raw on the phone.**
   - **Pauses inside a phrase:** silences over 0.45 s are cut. The cut keeps 4 frames before the voice onset and 3 frames after the voice end, or 10 frames after a sentence end. The reel starts 0.15 s before the first onset.
   - **Measured on energy:** in- and out-points come from the audio energy, not from whisper's word times (whisper ends are early). Cuts snap to the quietest frame and never land in speech.
   - **Takes:** an attempt that ends in «стоп» is dropped deterministically (ADR-0006). When a line is repeated, the tool proposes keeping the last complete attempt. Claude confirms each proposal on contact sheets.
   - **Never cut silently:**
     - clips without speech are listed as B-roll candidates;
     - strong product moments (`motion.json` to_lens events) that fall in a cut range are listed with a ready `trim.keep` entry.
   - **Lint:** checks that no long pause is left and that no cut lands in speech.
   - **Crossfades:** every speech cut can get a 2-frame equal-power crossfade built from audio handles.
2. **Optional uniform speed-up**, applied once at ingest. It is off by default.
3. **Keyframed music ducking** from the output-time speech spans. The music level under speech is set in LU against the voice, the music comes up in long gaps, and the fades are short. The editable project gets the ducked music as a baked stem.
4. **Music by name:**
   - Claude turns Marina's «МУЗИКА: …» into an exact file with `assets.py music <query>` while writing the script. Nothing is fuzzy at render time.
   - «без музики» means no music.
   - The brand supplies the default.
5. **Robust assets.**
   - An SFX without a credits entry, or in mp3/m4a, works.
   - A missing music or SFX file gives a warning; the reel renders without it, and the report lists it.
6. **Final-report numbers** go in a per-render JSON, computed from the script, words and clips. Removed time is split into pauses, retakes and dead air between takes.

**Measured facts behind the design.** Scratch scripts are in `/private/tmp/claude-501/design/` and `/private/tmp/claude-501/reviewer_scratch/audio/`.

- **Whisper word ends are early.** On raw iPhone audio (`build/yocase_line`), the voice continues past whisper's `e` by a median of +0.15 / +0.16 / +0.20 s at activity thresholds 24 / 30 / 36 dB under speech (p90 about +0.3 s). On `yocase_2373`, the level 60 ms after whisper's `e` of «волосся.» (7.34) is still +0.3 dB re speech. Out-points must therefore be measured on energy.
- **Raw versus pre-edited.** The speech-to-gap level difference is 59.5 dB on raw `yocase_line` and 16.8 / 16.0 / 14.8 dB on the pre-edited `yocase_2371` / `2373` / `2477`. A 25 dB threshold separates them. Below it there is a constant bed (music or room noise) and trim refuses.
- **Repeat detection** on `yocase_line` (19 attempts, Latin folded to Cyrillic, with the length rule below) keeps the last attempt in all 5 repeat groups. For the heard audio, the developer's hand edit agrees on 4 of them. For «Відновлення структури…» he used the first attempt for picture reasons, so take choice stays a proposal.
- **Product moments are motion events.**
  - The developer's silent product shots in `yocase_line` coincide with `to_lens` events of growth at least 1.4:
    - 115.83 s, ×3.77;
    - 141.23 s, ×1.57;
    - 148.90 s, ×1.69;
    - 215.80 s, ×1.49.
  - Clip `IMG_2471` (209.7-211.33 s) has no words at all.
- **Fades and crossfades.**
  - The current 6 ms fades (`audio.py:45`) leave a −6.1 dB dip in room tone at every cut.
  - A handle-based 2-frame crossfade with `adelay` + `amix` is sample-identical to the concat path away from the cuts and reduces the dip to −0.1 dB.
  - Peak memory of that ffmpeg graph is 37 MB for 60 segments over a 600 s source (20 MB with concat), so it is safe on 8 GB.
- **Ducking expression.**
  - The expression works in ffmpeg 9: +4.00 dB in gaps of 0.8 s or more, 0.00 dB under speech and in short gaps, and a 0.4 s release.
  - The prototype's "open start" rule always kept the reel-start gap. With the first word at 0.14 s, it produced a +3.6 dB → 0 dB pump in the first 140 ms. This is fixed below.
- **Automatic SFX peaks.**
  - The time of the maximum absolute sample matches `credits_sfx.json` `t_peak_s` for 27 of 33 files within 1 frame, and 30 of 33 within 2 frames.
  - The misses beyond 2 frames are `whoosh_soft_02_wind_swoosh` (74 ms), `sparkle_hit_fairy` (212 ms) and `tada_brass` (1.29 s).
- **Fuzzy matching is unsafe for SFX.** difflib gives «whoosh_7» → `whoosh_06_synth` (0.61) and «sparkle» → `sparkle_poof_hit` (0.61). Every music query matches both the `_full` and the `_edit28s_…` file of a track.
- **The ingest speed chain is frame- and sample-exact.** At k = 1.25 a 10 s test gives 240 frames and 384,000 samples.

### Creator-facing behaviour

Marina writes in the brief. The first line is from the adopted dictionary; the second is optional and new:

```
МУЗИКА: groove            ← будь-яка частина назви треку, або «без музики»
ШВИДКІСТЬ: 1.15           ← необов'язково; без цього рядка мова звучить як записана
```

Free-text requests are also understood. For example, «залиш паузу після "Поїхали"» becomes `trim.punch`, and «покажи, як я підношу пляшку» becomes `trim.keep`.

What she gets:

- **Tighter pauses.**
  - Long pauses inside a phrase shrink to about 0.23 s; short natural pauses stay.
  - After a full sentence, a short beat of about 0.47 s is kept.
  - The breath before a phrase stays.
- **Failed takes removed.**
  - Takes she ended with «стоп» disappear on their own.
  - If she repeated a line without «стоп», the later attempt is used, unless Claude sees on the frames that an earlier one looks better. The report says so.
- **Product moments are not lost.** Moments where she brings the product to the lens, and clips without speech, are never thrown away silently. Claude decides whether to use them as a product shot.
- **Videos with a constant background under the voice are not cut.** This covers an already-edited video, or a recording with constant music or noise. The report says: «Паузи не вирізано: під голосом постійний фон (музика або шум).»
- **Music.**
  - She gets the track she named, or the brand's track by default.
  - It runs from the first frame, quiet under her voice. It comes up only where she is silent for 0.8 s or more: the product hold, the ending, or a silent visual hook.
  - It fades in over at most 50 ms and fades out over 0.8 s.
  - «без музики» means no music.
  - If the name fits several tracks, Claude asks her or uses the brand track and says so.
- **Her own sounds and tracks.** She sends a `.mp3`, `.m4a` or `.wav` file in the chat, or drops it into `assets/local/music` or `assets/local/sfx`. Claude puts it in place and uses it by name. These files never go to GitHub.
- **Missing files never stop the reel.** If a named file is not found, the reel is made without it and the report says so.
- **Report.** Claude writes it from `output/<name>.report.json`; the wording is fixed in the skill.

  ```
  Готово: output/yocase_2490.mp4
  • Тривалість: сирий запис 1:12 → рілс 0:31.
  • Прибрано 14 пауз (разом 9,6 с), 3 невдалі дублі (18,2 с) і 13,2 с тиші між дублями; у ролику 15 склейок.
  • Музика: «Gimme that Groove!» (на запит «groove») — тихо під голосом, голосніше там, де ти мовчиш.
  • Не знайшлося: звук «whoosh_7» — ролик змонтовано без нього.
  • Сумнівне: фраза «Відновлення структури…» — узято перший дубль, у другому пляшка не в фокусі.
  ```

### Schema

**`projects/<name>/script.json`.** `trim.py --write` writes the `trim` block. Code defaults are shown; format values override them.

```jsonc
"trim": {                        // present = edl/takes were produced by trim.py; lint (b) runs
  "min_cut": 0.45,               // s: an INNER pause (same attempt) longer than this is cut (playbook.md:221)
  "pad_before": 4,               // frames before the voice ONSET (energy) (3-5)
  "pad_after": 3,                // frames after the voice END (energy) (2-4)
  "keep_after_sentence": 10,     // frames after . ! ? … or a "punch" word (8-15, playbook.md:224)
  "head": 0.15, "tail": 0.4,     // s before the first onset / after the last voice end of the reel
  "min_shot": 1.0,               // s: an inner cut that would leave a shorter segment is undone (never across attempts)
  "take_gap": 1.0,               // s: a pause this long separates attempts
  "breath": "keep",              // "keep": an inhale up to 0.3 s before a phrase stays; "cut": to the onset
  "force": false,                // true = clips with a sound bed use whisper e + 0.2 s as voice end (trim --force)
  "drop": [[a, b]],              // source ranges removed; authoritative whenever present
  "keep": [[a, b]],              // source ranges never cut (product moment, deliberate silent beat)
  "punch": [t]                   // source time of a word followed by a kept long pause
},
"audio": {
  "xfade_frames": 0,             // 0 = today's 6 ms fades (string-identical filter); 2 = 2-frame crossfade. trim writes 2
  "music": null | {              // absent/null = no music (as today; no render-time brand fallback)
    "file": "music_03_gimme_that_groove_112bpm_full.wav",  // EXACT: library file, assets/local/music file, or path
    "asked": "groove",           // optional: Marina's words, only for the report
    "gain_db": -20,              // as today (audio.py:99)
    "under_lu": 15,              // optional, wins over gain_db: gain measured so the music sits N LU under the voice
    "offset": 0, "fade_in": 0, "fade_out": 0, "dropouts": [],  // unchanged (audio.py:96-107)
    "duck": {"rise_db": 4, "lead": 0.15, "release": 0.4, "min_gap": 0.8},  // optional keyframed duck
    "sidechain": {}              // unchanged; ignored with a warning when "duck" is set
  },
  "sfx": [{"name": "pop_04_light", "peak_at": 3.2, "gain_db": -20, "t_peak": 0.025}]
  // name = exact stem (any of .wav .mp3 .m4a .aac .aif .aiff .flac), file name or path; "t_peak" optional override
}
```

**`brands/<brand>/brand.json`.** The brand design owns this file; this area adds one key. While writing the script, Claude copies it into `audio.music`, unless:

- the brief says «МУЗИКА:» (the exact file from `assets.py music` replaces `file`);
- the brief says «без музики»;
- Claude judges the video pre-edited (learned rule, `.claude/skills/reel-subtitles/SKILL.md:103-105`).

```json
"music": {"file": "music_03_gimme_that_groove_112bpm_full.wav", "under_lu": 15, "offset": 18.423,
          "fade_in": 0.05, "fade_out": 0.8, "duck": {"rise_db": 4, "lead": 0.15, "release": 0.4, "min_gap": 0.8}}
```

**`formats/<talking-head>/format.json`.** The format design names the folder. `trim.py` reads the `trim` block and writes the effective values into the script. Claude passes `speed` to ingest.

```json
{"trim": {"min_cut": 0.45, "pad_before": 4, "pad_after": 3, "keep_after_sentence": 10, "head": 0.15, "tail": 0.4,
          "min_shot": 1.0, "take_gap": 1.0, "breath": "keep"},
 "speed": 1.0,
 "audio": {"xfade_frames": 2}}
```

The product-lineup and skit formats get no `trim` block: their cuts follow gestures and silent beats.

**`build/<name>/clips.json`** (ingest output). Each clip gets `"speed": 1.0` and `"orig_duration": <s before speed-up>`.

**`output/<render-name>.report.json`** (new, one per render name; other areas add their own keys):

```json
{"raw_s": 72.4, "speed": 1.0, "src_s": 72.4, "out_s": 31.2, "edits": 15,
 "removed": {"pauses": {"n": 14, "s": 9.6}, "retakes": {"n": 3, "s": 18.2}, "dead_air": {"n": 6, "s": 13.2}},
 "music": {"asked": "groove", "file": "music_03_gimme_that_groove_112bpm_full.wav", "title": "Gimme that Groove!",
           "gain_db": -17.3, "under_lu": 15, "ducked_gaps": 4, "short_by_s": null},
 "missing": [{"kind": "sfx", "name": "whoosh_7"}], "warnings": []}
```

**`.gitignore`** gets `assets/local/`. The delivery design may rename the folder; it is one constant, `assets.LOCAL`.

### Changes by file

**New file: `pipeline/trim.py`.** Dead-air trim and take proposal.

CLI: `.venv/bin/python pipeline/trim.py projects/<name>/script.json [--write] [--force]`. Without `--write` it only prints.

- **`levels(path)`**
  - Decodes 16 kHz mono with ffmpeg (`-vn`), one clip at a time from `clips.json`. The path is resolved like `build_timeline.py:297-300`.
  - Computes 20 ms RMS at 5 ms hops, broadband and first-difference (high-frequency, for sibilants), through cumulative sums.
  - Memory is about 20 MB per source minute, freed per clip.
  - This is the RMS idea of `prep.py:115-134`, which stays unchanged.
- **`analyse(script)`** works per clip that contains words.
  - Levels:
    - speech = median level inside words;
    - floor = 10th percentile;
    - gap = median outside words;
    - bed = speech minus gap.
  - **Bed under 25 dB in any speech clip:** print the clips and stop ("constant bed under the voice: no pause cutting"), exit 0. `--force` uses whisper `e` + 0.2 s as the voice end for those clips and writes `trim.force: true`.
  - **Active**, per band: level ≥ max(speech − 30, floor + 10).
  - **Per word:**
    - Voice end: scan forward from 60% into the word until 60 ms of inactivity, capped at the next word's `s` and at `e + 0.6`.
    - Onset: scan back from `s` while active, up to 0.3 s (`breath: keep`) or 0.05 s (`cut`).
  - Zero-length words get `e = s + 0.05`.
- **`attempts()`**
  - Splits at pauses of `take_gap` or more, at clip edges, and after «стоп».
  - **«стоп» attempts are dropped** (ADR-0006).
  - **Repeats:** attempt i is superseded by j (i < j ≤ i+3) when the prefix of j's folded text, of i's length, matches i with a ratio of at least 0.6, and len(j) ≥ 0.7·len(i).
    - Folding: lowercase; strip punctuation and hyphens; Latin → Cyrillic; brand `heard_as` aliases when the brand file has them.
    - The length rule stops a later fragment such as «Фікс-колор!» from superseding a complete take.
  - **Doubt flags** for a kept attempt: it is shorter than 0.7× the longest in its group, ends without sentence punctuation or in "…", or has a mean word probability under 0.7.
  - **Effective drops:** `trim.drop` when present, else the proposals. A word whose midpoint lies in a drop range is removed. The printed attempt range is [first onset, last voice end].
- **`kept_ranges()`**
  - **Inner gaps** (consecutive kept words of one attempt, shorter than `take_gap`, outside `trim.keep`) are cut only when two conditions hold:
    - the gap is longer than max(`min_cut`, (`pad_after` or `keep_after_sentence`) + `pad_before` + 1 frame);
    - the gap holds less than 150 ms of active frames. A laugh or «мм» is kept and flagged.
  - **Boundary gaps** (between kept attempts, around dropped attempts, across clip edges) are always cut. Activity inside them is ignored.
  - **Cut points:**
    - out-point = voice end + `pad_after` (or `keep_after_sentence` after . ! ? … or a `punch` word);
    - in-point = onset − `pad_before`.
    - The out-point rounds up and the in-point rounds down to the 1/30 grid, like `q()` in `projects/yocase_line/make_script.py`.
    - Each point may then move up to 2 frames away from the word, to the quietest frame. On a tie it does not move.
  - The head and tail of the reel are `head` / `tail`, clamped to the clip.
  - **`min_shot`** applies to inner cuts only: a segment shorter than 1 s undoes the smaller adjacent inner cut. A kept attempt shorter than `min_shot` is flagged, never merged.
  - `trim.keep` ranges are added to the kept set.
- **`--write`**
  - `edl` = one `src` segment per kept range, in source order. `takes` = the same ranges: one take per segment, the convention of `make_script.py`, so A/B framing can switch at every jump cut through `push_takes` (`camera.py:24-26`).
  - Writes the `trim` block (effective parameters, plus `drop` if it was absent) and `audio.xfade_frames = 2` if absent.
  - On re-runs it prints the take renumbering and "output times moved: re-derive camera/sfx/literal/screens with times.py". Holds are not preserved, so trim runs first in the order of work.
- **Printout**
  - per-clip levels and bed;
  - the attempt table with proposals and "?" doubts;
  - one `contact_sheet.py build/<name>/source.ffconcat <t0> <t1> 0.25 --words build/<name>/words.json` command per repeat group;
  - **"no speech: B-roll candidate"** for every clip without words;
  - **product moments:** each `motion.json` to_lens event with growth ≥ 1.4 whose t0-t_settle lies in a cut range, with a ready `"keep": [[t0-0.2, t_settle+0.3]]` entry and a contact-sheet command;
  - the cut list in output time, marked "same-clip jump cut (A/B framing)";
  - totals from `stats`.
- **`stats(script)`**: pure Python, no audio decode; used by build and the report.
  - `raw_s` = Σ `orig_duration` (fallback `duration`, then `src_duration`); `src_s` = Σ `duration`.
  - `out_s` = `EDL.duration`; `edits` = number of edl item boundaries.
  - Removed ranges = each clip's span minus (edl `src` ∪ `voice_over` src), ignoring slivers under 1 frame. Each range is classified:
    - `retakes`: a word midpoint lies inside;
    - `pauses`: silent, and both the word before and the word after are heard, in the same clip, less than `take_gap` (default 1.0) apart;
    - `dead_air`: everything else (clip heads/tails, between takes, wordless clips).

**New file: `pipeline/assets.py`.** Asset lookup; Claude also calls it from the CLI.

- **`find(kind, name)`**: exact resolution only.
  - Search order: absolute or ROOT-relative path → `assets/<kind>/<name>` → stem with any of `.wav .mp3 .m4a .aac .aif .aiff .flac` → the same in `assets/local/<kind>/` → None.
  - For a library hit it returns the same `ROOT / "assets" / kind / name` path that `build.py:24,58` builds today, so existing filter strings do not change.
- **`search(kind, query)`**
  - Used by Claude at authoring time, never at render time.
  - Rows:
    - music: one row per `credits_music.json` entry (its `file`; `edit` derivatives are not separate rows) plus local files;
    - SFX: one row per file.
  - Ranking: all query tokens inside the stem or title (digits match the track number), then difflib ≥ 0.6.
- **`sfx_peak(path)`**: credits `t_peak_s` by stem; otherwise the time of the maximum absolute sample of the ffmpeg-decoded file, cached in memory only. Nothing is written to the tracked `credits_*.json`, so `git pull` never conflicts.
- **`music_info(path)`**: bpm and title from `credits_music.json`, falling back to the `(\d+)bpm` filename regex now at `lint_edit.py:166`.
- **CLI**: `assets.py music [query]` and `assets.py sfx [query]` print the ranked rows with title, tags and bpm.

**`pipeline/build.py`**

- **`sfx_cues` (`:18-25`)**
  - Uses `assets.find` and `assets.sfx_peak`: no KeyError at `:22`, no hard-coded `.wav` at `:24`. `t_peak` in a cue overrides the measured peak.
  - Returns `(cues, missing)`; a missing cue prints `WARNING sfx «x» not found - skipped`.
- **Music (`:55-58`)**
  - `assets.find("music", m["file"])`. If unresolved: warning, music = None, and an entry in `missing`.
  - Warns when the track length minus `offset` is shorter than `dur` (`short_by_s`).
- **Audio render call (`:59-61`)** gains:
  - `xfade_frames`;
  - `clip_edges` from `clips.json` (as `build_timeline.py:297-300`);
  - `speech = edl.speech_spans(VoiceMap(...).heard_words(words), hang=0.2, join=duck.min_gap)`, only when `duck` is set;
  - `music_stem = BUILD / f"{name}_music.wav"`. Any old stem is deleted before every audio render, so a `--no-music` re-render under the same name cannot leave a stale stem for the export.
- **Report:** writes `output/<name>.report.json` from `trim.stats`, the music block (gain returned by `audio.render`), `missing` and the collected warnings. With `--skip-audio` the music gain is null.

**`pipeline/audio.py`**

- **`_voice_edl` (`:33-52`)**
  - With `xfade_frames > 0`, each cut between two `src` pieces gets one handle h for both sides: h = min(xf/2 frames, the source room past the out-point and before the in-point inside their clips (`clip_edges`) and the source).
  - The pieces get `afade curve=qsin` over 2h around the cut, are placed with `adelay=<n>S` and summed with `amix normalize=0` (the voice-over pattern, `:73-82`).
  - If h < 6 ms, if a hold is next to the cut, or at the reel ends, the old 6 ms fades stay.
  - Contiguous source pieces (a_k equal to b_{k−1} on the frame grid) get no fades at all: an equal-power crossfade of identical audio would bump +3 dB.
  - With 0, the code path and filter string are unchanged.
- **Music chain**
  - Extracted from `build_filter` (`:93-115`) into `music_chain(music, dur, speech)`. Without `duck` it returns today's string exactly.
  - **With `duck`:**
    - `asetnsamples=n=48:p=0` goes before the dropouts and the duck, as the mute code does at `:65-67`.
    - One `volume=eval=frame:volume='1+(G−1)·Σ max(0,min(1,min((t−a)/release,(b−t)/lead)))'` follows, with G = 10^(rise_db/20). This is the expression style of the dropouts at `:104-107`.
    - **Gaps:** [0, first span start], the spaces between spans, and [last span end, dur]. A gap is kept only if its length inside [0, dur] is at least `min_gap`. Then a kept first gap that starts at 0 gets a = −1 (no ramp at frame 0), and a kept last gap gets b = dur + 1.
  - The sidechain flag at `:62` becomes `sidechain and not duck`. Otherwise `[vsc]` would be a dangling `asplit` output; the sidechain is skipped with a warning.
- **`music_gain(spec)`** for `under_lu`
  - Two loudnorm measurement passes:
    - the voice-only graph (`build_filter` with no SFX and no music);
    - the music file over `offset .. offset+dur`.
  - gain_db = I_voice − under_lu − I_music. It is printed as "music gain −xx.x dB = 15 LU under the voice" and returned for the report. A gain outside −30 to −6 dB gives a WARN.
- **`render()` (`:129-143`)**
  - When `music_stem` is given: `[music]asplit=2[music][ms];[ms]apad=whole_dur=<dur>,atrim=0:<dur>[mstem]`, plus a second output `-map [mstem] -c:a pcm_s24le` in the same first pass. The stem is exactly `dur` long and at raw-mix level, like `_mix_raw.wav`.
  - Docstring `:1-13` updated; the line "ducked under the voice" was untrue until now.

**`pipeline/edl.py`**

- **`VoiceMap.heard_words(words_json)`** returns sorted `{w, s, e, p, o, oe, sentence_end}`: source s/e, output o/oe. It replaces the loop at `times.py:21-27` only.
- **`speech_spans(heard, hang=0.2, join=0.8)`** returns merged output-time spans.
- The EDL maths does not change.
- `build_timeline.py:283-289` stays as it is: it rewrites `s` to the rounded output time that `assign_times` (`:57-102`) relies on.

**`pipeline/ingest.py`**

- **`--speed k`:** default 1.0, allowed 1.0-1.3, warns above 1.2. With k == 1.0 the filter strings are unchanged.
  - `:60`: `n = round(video_duration / k * FPS)`.
  - `:64`: `setpts=(PTS-STARTPTS)/k`; the existing `fps=30` resamples by nearest frame.
  - `:79`: `atempo=k,` inserted after the start shift (`:69-72`, still in source time) and before `apad,atrim=end_sample`. The end sample uses the new `n`, so the frame check at `:82-84` holds unchanged.
  - `:85`: adds `"speed"` and `"orig_duration"`.
- **Judder** (30 fps output):

  | Speed | 30 fps source | 60 fps source |
  |---|---|---|
  | 1.1 | a skip every 10 output frames (3 per second) | alternating 2- or 3-frame steps (gentler) |
  | 1.2 | a skip every 5 output frames (6 per second) | alternating 2- or 3-frame steps (gentler) |
  | 1.25 | a skip every 4 output frames (1 of 5 source frames dropped) | alternating 2- or 3-frame steps (gentler) |

  Lips survive; hand and bottle moves stutter.
- **Why ingest:**
  - The EDL, camera, captions and FCPXML stay untouched.
  - "Never ramp speech" (`playbook.md:582`) is about ramps, and a uniform rate is not one.
  - The music is never sped up.
  - Per-segment speed (`playbook.md:623`) is rejected (M-L).
- Speed is decided from the brief before ingest; changing it later means a re-ingest plus prep.

**`pipeline/lint_edit.py`**: new checks appended before `return` at `:177`.

- **(a) Cut in speech** (every reel)
  - Checks each side of each edl `src` edge, and both ends of each `voice_over` src, when that side is heard. A side is muted when the frame on that side lies in `audio.mute`.
  - WARN "cut at X s lands in speech (Y dB)" when the 20 ms level at the source point is above max(speech − 24 dB, gap + 6 dB) of its clip.
- **(b) Remaining pauses** (only with `script["trim"]`)
  - Pauses are measured between heard words in output time, on trim's voice ends (whisper `e` + 0.2 s when `trim.force`), outside `trim.keep`.
  - WARN when an inner pause is over `min_cut`, or over (`keep_after_sentence` + `pad_before` + 2)/30 after a sentence end or `punch`.
- **(c) Same-setup jump cut**
  - Applies to two consecutive `src` segments from one clip with no designed transition at the cut.
  - WARN "head teleports: A/B switch (push_takes) or no cut" (`playbook.md:228`) when the camera scale ratio across the cut differs from 1 by less than 0.10 AND the screen position of the tracked face moves less than 55 px. The face is mapped with `cam.face_track` and `cam.matrix`, as at `build_timeline.py:339-341`.
- **(d) Beat check (`:165-176`)**
  - bpm comes from `assets.music_info` and the path from `assets.find`.
  - With `script["trim"]` only, it skips cuts between consecutive same-clip segments, because speech-driven cuts are not beat cuts. Scripts without trim lint exactly as today.
- (a) and (b) import `trim.levels`, which decodes about 1-2 s per source minute.

**`pipeline/export_fcpxml.py`**

- **SFX (`:531-538`):** the new `(cues, missing)` shape. A non-WAV, or a WAV that is not 48 kHz stereo, is transcoded with ffmpeg into `media/<stem>.wav`, because `audio_asset` (`:348-358`) declares 48 kHz stereo. This also makes the mp3/AAC decoder delay match the MP4. All library files are already 48 kHz stereo 24-bit, so existing projects keep hard links.
- **Music (`:539-545`)**
  - When `build/<name>_music.wav` exists:
    - the music clip is that stem at `norm` dB (`:362`) with no fade params;
    - the raw track (offset and flat gain, transcoded as above if it is not WAV) goes on its own lane at −96 dB, named "music raw (muted)".
  - Otherwise the current behaviour stays, using the report's `music.gain_db` when `under_lu` is set.
- The docstring `:14-16` changes: music fades, dropouts and ducking are now carried (baked); voice crossfades are not.

**`pipeline/times.py`**: uses `heard_words`; output unchanged. The 0.22 s whisper-gap print (`:34-36`) stays as information.

**`pipeline/prep.py`**: no change. The energy analysis replaces any need for VAD chunks at trim time.

**Docs, skill and template** (wording owned by the skill and format design):

- `reel-subtitles/SKILL.md:41-43` becomes: "talking head, raw: `trim.py` (print) → watch the repeat groups and product moments → set `trim.drop`/`keep` → `--write`; constant bed or pre-edited: skip."
- The skill gets the music step (`assets.py music <query>` → exact file + `asked`) and the report wording.
- `_template` audio gets `xfade_frames` and the music `duck` block.

### Interactions

- **Person matte and track.** Trim changes only the EDL, and masks are indexed by source frame (`edl.py:34-43`), so nothing is recomputed. A speed-up means prep runs on the new media, with the same RAM use.
- **Safe zone and layout solver.** Unchanged. Shorter takes mean shorter screen windows (`build_timeline.py:128-142`). Insert, CTA and hook timing from other areas use `heard_words` output times taken after trim.
- **Subtitle timing.**
  - `assign_times` uses the heard words (`build_timeline.py:283-289`, untouched). Trim never cuts an onset, so the clipped-word rule at `edl.py:102-107` does not fire.
  - Screens are per take and takes are the kept segments, so a screen cannot span a trim cut unless it uses `t1_override`. Screens are written after `--write`; a re-trim prints the renumbering.
- **FCPXML export.**
  - One spine clip per kept segment already works (`export_fcpxml.py:385-404`).
  - Voice crossfades are MP4-only; the editor adds audio cross-fades in Resolve.
  - Music is the baked stem; non-WAV audio is transcoded.
- **lint_edit.** Gains checks (a)-(d). Dead spans (`:157-160`) see more cuts, which is correct. Existing scripts get only new (a)/(c) warnings. On the hand-edited `yocase_line`, (a) finds exactly one: the voice-over 1 end at source 114.63 s (output 17.60 s, −12.6 dB re speech), which clips «волосся».
- **Audio mix order:**
  1. voice EDL (crossfade);
  2. mute;
  3. voice-over;
  4. voice chain;
  5. SFX (exact resolution, measured peaks);
  6. music (gain or `under_lu` → fades → [asetnsamples → dropouts → duck] → stem split);
  7. amix;
  8. the unchanged two-pass loudnorm (`audio.py:129-143`).
- **No-music variant.** `--no-music` (`build.py:34`) skips music, duck and stem, deletes any old stem, and records `music: null`.
- **Shared build state.**
  - `trim.py` writes only the script it is given; `assets.py` writes nothing.
  - The new files are per render name (`build/<name>_music.wav`, `output/<name>.report.json`).
  - Nothing new goes into the single-slot `build/{timeline,meta,camera}.json`, and the build-then-export order rule (`SKILL.md:94-96`) is unchanged.
- **8 GB RAM.** Analysis runs per clip at 16 kHz (about 20 MB per minute). The crossfade graph measured 37 MB at 60 segments. `under_lu` adds two short ffmpeg passes.
- **Inserts, CTA and censorship (other areas).** Insert pops and CTA chimes are ordinary `audio.sfx` cues, so they get the same resolver and peak measurement, and missing ones land in `missing`.
- **Brand, format and public repo.**
  - Values are copied into the script at authoring time, so render is a pure function of the script.
  - An absent `audio.music` stays "no music", so the pre-edited YOCASE scripts render exactly as before.
  - Marina's files live in the gitignored `assets/local/`.

### Verification

**Pure Python and ffmpeg-only checks (seconds each; nothing under build/ is touched)**

1. **Mix regression.**
   - Before editing `audio.py` and `build.py`, dump `audio.build_filter(spec)` for every `projects/*/script.json` to `/private/tmp/claude-501/design/filters_before.json`. The spec is built as `build.py:56-61` does, with the script's `edl` and the old `sfx_cues`.
   - After the change, with `xfade_frames` 0 and no `duck`: every string is identical, including `tosumi_hair` with its dropouts `[[14.44, 14.75]]`.
2. **Trim print on yocase_line:** `.venv/bin/python pipeline/trim.py projects/yocase_line/script.json` (print only). Expected:
   - a quiet floor, bed ≈ 59 dB;
   - 19 attempts: keep #1, 2, 3, 5, 7, 8, 11, 16, 19; drop #4, 6, 9, 10, 12-15, 17, 18 as repeats;
   - 0 inner pause cuts;
   - 5 contact-sheet commands;
   - "no speech: B-roll candidate" for IMG_2471;
   - product moments at 115.83 (×3.77), 141.23 (×1.57) and 215.80 (×1.49).
3. **Refusals:** trim on `yocase_2371`, `yocase_2373` and `yocase_2477` prints beds of about 16.8 / 16.0 / 14.8 dB and "no pause cutting", exits 0, and leaves the script byte-identical.
4. **Synthetic cutter test** (scratch). Tone bursts at −18 dB as words, with a fake words list whose `e` is 0.15 s early. Assert:
   - on a −78 dB floor:
     - in-points = onset − 4 frames, floored to the grid;
     - out-points ≥ energy end + 3 frames;
     - post-sentence gap = 14 frames;
     - inner gaps under 0.45 s untouched;
     - a 200 ms burst inside an inner gap is kept and flagged;
     - a 300 ms rustle inside a 5 s boundary gap is cut;
     - `min_shot` never re-joins across a dropped attempt;
     - all `src` values on the 1/30 grid;
   - on a −46 dB floor (bed 28 dB): the same cuts are found.
5. **`trim.stats`.**
   - On the hand-edited `yocase_line`: raw 228.63 s, out 30.00 s, 13 edits; pauses 1 / 0.30 s (20.30-20.60), retakes 6 / 91.93 s, dead_air 17 / 100.47 s.
   - On `yocase_2373`: 28.83 → 28.83, 0 edits, nothing removed.
6. **Assets.**
   - `assets.sfx_peak` over the 33 credits files with their credits ignored: 27 within 1 frame of `t_peak_s`.
   - `find("sfx", "whoosh_7")` → None, and `find("sfx", "pop_04_light")` → the same path string as today.
   - `assets.py music groove` → one row, «Gimme that Groove!» → `music_03_gimme_that_groove_112bpm_full.wav`.
7. **Duck expression** (scratch, sine input):
   - gaps of 0.8 s or more: +4.00 dB; speech and short gaps: 0.00 dB; release 0.4 s;
   - with the first word at 0.14 s, the 0-0.14 s level is within ±0.3 dB of the speech level (no start pump);
   - with the last word 0.2 s before the end, there is no end swell.

**Audio-only renders (no video, no shared state, about 10 s each, outputs in `/private/tmp/claude-501/design/`)**

8. **Hand-edited yocase_line.** Call `audio.render` with the spec plus `xfade_frames: 2`, `music.under_lu: 15` and `duck` → `yl_mix.wav` and stem `yl_music.wav`. Then a second time with `xfade_frames: 0`. Expected:
   - both raw mixes are exactly 1,440,000 samples;
   - the voice is identical outside ±40 ms of the 11 src-src cuts (the 2 hold-adjacent edges keep 6 ms fades);
   - the stem rises only in the single gap 23.44-24.82: +4 ± 0.3 dB over 23.95-24.60 against 20.0-23.0. The hold is not a gap, because voice-over 2 plays over it;
   - the stem level over 0-0.14 s matches 1-2 s within ±0.3 dB;
   - the log prints the music gain line.
9. **Trim end to end on raw footage.**
   - Copy `projects/yocase_line/script.json` to `/private/tmp/claude-501/design/yl_trim/script.json`. Delete `screens`, `doodles`, `camera`, `audio.voice_over` and `audio.mute`, and set `edl` to null.
   - Run `trim.py … --write` on the copy, then `lint_edit.py` on it, then `audio.render` of its spec (`xfade_frames: 2`).
   - Expected:
     - 9 segments = the 9 kept attempts;
     - takes = segments;
     - lint: 0 "lands in speech", 0 "pause left", same-setup warnings only where the same clip continues;
     - the mix length = EDL frames × 1600 samples;
     - listening at each cut: no clipped word ends or onsets.

**Speed (about 40 s, scratch only)**

10. Run `.venv/bin/python pipeline/ingest.py /private/tmp/claude-501/speed_2373 исходники/IMG_2373.MOV --speed 1.25`. Expected:
    - "692 frames, 23.067s", with ingest's own frame check passing;
    - `ffprobe` audio `duration_ts` = 1,107,200;
    - clips.json has `speed: 1.25` and `orig_duration: 28.833`;
    - a 1/30 s contact sheet over the 3.07-3.47 s source gesture shows a skip every 4 output frames.

    Delete the directory afterwards.

**Integration: draft render of yocase_2373 (about 2-3 min on the M2 Pro)**

11. Copy `projects/yocase_2373/script.json` to `/private/tmp/claude-501/it/script.json` and set:
    - **edl:** `[{"src": [0, 7.5]}, {"src": [7.6667, 13.9333]}, {"src": [14.1, 28.8333]}]`. This removes 5 frames from each of the pauses after «волосся.». `takes` stays `[[0, 28.8333]]`, so the screens keep working.
    - **audio:**
      - `xfade_frames: 2`;
      - music `{"file": "music_03_gimme_that_groove_112bpm_full.wav", "asked": "groove", "under_lu": 15, "offset": 18.423, "fade_in": 0.05, "fade_out": 0.8, "duck": {…}}`;
      - sfx: `pop_04_light` peak_at 1.29; `no_such_sound` at 5.0; `/private/tmp/claude-501/it/whoosh.mp3` at 8.24, made with `ffmpeg -i assets/sfx/whoosh_quick_03_swish.wav -c:a libmp3lame -q:a 2 …`.

    Then run:

    ```
    .venv/bin/python pipeline/lint_edit.py /private/tmp/claude-501/it/script.json
    X264_PRESET=veryfast .venv/bin/python pipeline/build.py /private/tmp/claude-501/it/script.json --name it_2373_draft
    .venv/bin/python pipeline/export_fcpxml.py /private/tmp/claude-501/it/script.json --name it_2373_draft --procs 2
    ```

    Expected:
    - **lint:** 0 FAIL; 2 WARN "same-setup jump cut" (push 1.0 → 1.0); 0 "lands in speech". The cut levels are −15.5 / −17.9 / −18.0 / −18.9 dB re speech against a −10.2 dB threshold. The existing "no visible change" warnings, and possibly beat-miss warnings, also appear.
    - **Build log:**
      - the music gain line;
      - `WARNING sfx «no_such_sound» not found - skipped`;
      - the mp3 peak measured at 0.082 ± 0.005 s.
    - **MP4:** 855 frames = 28.500 s.
    - **`output/it_2373_draft.report.json`:** pauses n = 2, s = 0.333; `missing` = [`no_such_sound`]; music `ducked_gaps: 0` (speech is continuous).
    - **`build/it_2373_draft_music.wav`:** exactly 1,368,000 samples, a ≤ 50 ms fade-in and a 0.8 s fade-out.
    - **FCPXML:** two music clips (the stem at norm dB and the raw clip at −96 dB), `media/whoosh.wav` present, and no `.mp3` asset.

    Then delete `build/it_2373_draft_*` and `output/it_2373_draft*`. If the single-slot state is needed, rebuild `yocase_2373`.

### Risks

- **Pacing.** Too-tight pacing, or jump cuts without A/B framing, read as amateur. The defaults are the playbook's gentle values, and lint (c) forces a framing decision at every same-clip cut.
- **Constant beds.** A noisy room (air conditioning, street) or a pre-edited video makes trim refuse. This is a safe failure: hand edits. The 25 dB threshold is fitted on four reels, so the measured bed is printed every time.
- **«стоп» lost.** prep's noise filter (`prep.py:67`) or VAD can drop a lone «стоп». The failed take then shows up as a repeat proposal instead of a deterministic drop.
- **Repeat detection** can misfire on deliberate repetition, or on mid-sentence restarts without a pause. It only proposes; Claude watches the sheets.
- **Product moments** below growth 1.4, or not detected by `motion.py`, are still cut. Claude watches the contact sheets for the cut ranges.
- **Re-running trim** after camera, SFX, screens or holds are placed moves output times. Trim runs first; generator scripts that anchor to source times are immune.
- **Ducking on fully trimmed reels** rarely has gaps of 0.8 s or more. The music level is then just `under_lu`, and the duck acts only on holds, B-roll and endings.
- **`under_lu` on unusual reels.** The measured gain is printed and reported, with a WARN outside −30 to −6 dB.
- **Speed-up costs:**
  - re-ingest plus prep (the matte takes minutes on the M1);
  - whisper accuracy on fast speech;
  - `atempo` artefacts;
  - judder at 30 fps.

  Off by default for brand talking heads.
- **Baked music stem.** The ducking can't be edited in Resolve; the raw track sits muted beside it.
- **Measured SFX peaks** are wrong for swells and long tails (3 of 33 in the library). Override with `t_peak`. Marina's own SFX have unknown loudness, so the default −12 dB may be loud; the draft review catches it.
- **Ending on a downbeat** is out of scope: `beats.py` knows no downbeats (`playbook.md:623` table, row 7). The fade-out covers the ending.
- **Licensing.** Marina's own tracks have unknown licences. `assets/local/` keeps them out of the public repo, and the report names the track used.

### Effort

| Piece | Size |
|---|---|
| `trim.py`: levels, attempts and proposals, kept ranges, product-moment and B-roll listing, `--write`, printout, stats | M |
| Crossfade with handles in `audio._voice_edl` | S |
| Ducking, `under_lu` and the music stem in `audio.py` | M |
| `assets.py`, `build.py` robustness and the report JSON | S |
| `lint_edit` checks (a)-(d) | S |
| FCPXML stem, raw muted lane and transcoding | S |
| `ingest --speed` | S |
| `edl.heard_words` / `speech_spans` and the `times.py` refactor | S |
| Skill, template and format text (with the other areas) | S |

### Open questions for the developer

1. **Speed-up:** should it exist at all for brand talking heads? Proposal: default 1.0; «ШВИДКІСТЬ:» capped at 1.2 (code allows up to 1.3); Marina shoots at 60 fps whenever she plans to use it.
2. **Breaths before phrases:** keep them (proposed default) or cut to the word onset (tighter, CapCut-like)?
3. **Music level under speech:** the playbook's 15 LU under the voice, with +4 dB in gaps of 0.8 s or more, or the third-party's louder bed (about −18 dB with a 2-4 dB dip)? One A/B listen on a real YOCASE talking head is needed before it becomes the brand default.
4. **Music in the editable project:** the baked ducked stem (exact match, ducking not editable), or FCPXML volume keyframes (editable, but Resolve's import of them is untested and needs a `resolve_check.py` spike)?
5. **How Marina shoots:** does she actually say «стоп» after a failed take? Does she record one clip per take or one long recording? And are product close-ups separate clips or moments inside the talking clips? This decides how much rests on «стоп», on clip boundaries and on the product-moment listing.
