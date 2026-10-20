
## Conflicts and resolutions

**What I checked before ruling (read-only, 2026-10-20):**
- **The commit is done, the push is not.** HEAD `b910950` (21:50) already holds the working tree, `git status` is clean, and `main` is 1 commit ahead of `origin/main`. marina-layer's "commit 17 modified + 20 untracked (B2)" step is finished. Only the push remains, and it waits on open question 1. `origin` (`a17cc27`) already exposes the licensed WAVs and the family details in CONTEXT.md.
- **Current-code baselines already exist.** They were rendered from HEAD at 21:51: `output/base_yocase_2373.mp4` (veryfast, `subme=2`, 35.9 s), `output/base_yocase_line.mp4`, and `/private/tmp/claude-501/baseline/{timeline_2373.json, meta_2373.json, timeline_line.json, camera_line.json, build.log}`.
- **The shared build slot holds yocase_line today, not yocase_2373.** `build/meta.json` shows `n_frames` 900 and an EDL starting at `[19.1333, 20.3]`. Every section assumes 2373. A `--skip-*` run, an export or a review of 2373 before a rebuild would use yocase_line's state, which is the exact trap the slot guard exists to stop.
- **The baseline log shows existing warnings:**
  - 2373 renders today with 7 `!! no free spot` blocks (b1, b10–b13, b15, b16).
  - yocase_line has 5 `OUTSIDE the IG crop-safe area` blocks (b6–b10).

### A. The same function or file changed in incompatible ways

**A1. The build-slot stamp and guard are designed three times, and all three share a latent bug.**
- How each section does it:
  - marina-layer: `meta["script"]` is a relpath, written at `build_timeline.py:303-305`. Guards sit in `build.py` (both `--skip-*` flags), in export before `:267`, and in `review_frames` via `renders`, with `--force`.
  - brands-formats: the stamp is an absolute path plus brand and format. The guard covers `--skip-timeline` only, plus export.
  - text-features: a separate `build/text_checks.json` with `gate()`.
- The bug: `meta.json` is written at `:303-305`, before measuring and layout (`:314-360`). If layout crashes (for example the ValueError at `:253` for a block wider than 1080 px), `meta.json` names the new script while `timeline.json` still belongs to the old reel, and every guard passes.
- **Resolution:** one stamp and one guard.
  1. `build_timeline.main` deletes `build/meta.json` at the start and writes it last, after `timeline.json` (`:360`).
  2. The file holds `script: str(Path(p).resolve())` (cwd-independent, and works for `/private/tmp` scratch scripts), plus `brand`, `format`, `renders: []`, and `checks: {fail, warn, applied}`, which replaces `text_checks.json`.
  3. One function, `common.require_slot(script, need_pass, force)`, is called by:
     - `build.py`: any `--skip-*`, plus checks before the overlay step;
     - `export_fcpxml.py`: before `:265`;
     - `review_frames.py`: the `renders` check.
  4. Flags: `--force` overrides a slot mismatch (developer only); `--allow-check-fail` renders despite FAILs. This renames text-features' flag, because the checks now include inserts too.

**A2. SFX cue assembly (`build.py:18-25`, `:59-61`; `export_fcpxml.py:531`).**
- How each section does it:
  - text-features merges `tl["sfx"]`.
  - inserts merges `layers.cues(tl["layers"])`.
  - audio-timing makes `sfx_cues` resolve through `assets.find` and return `(cues, missing)`.
  - inserts' "KeyError → name the missing credits entry" contradicts audio's "missing → WARNING, skip", and the third-party rule ("make it without, say so").
- **Resolution:**
  - `build_timeline` writes every automatic cue (the CTA chime, insert pops and whooshes) into one `timeline["sfx"]` list, already expanded from `sfx_palette`.
  - `sfx_cues(list) -> (cues, missing)` takes audio's form.
  - `build.py` and export both call `sfx_cues(au.get("sfx", []) + tl.get("sfx", []))`.
  - inserts' KeyError message is dropped.

**A3. `video_pass.render_frame` (`:201-219`) and `segment` (`:222-227`).**
- text-features adds a "front" PNG after the masked composite. inserts restructures the function into full/grade → under → text → over. Both change `segment` to load the timeline whenever it is given; today it loads only together with `masks_path`, at `:225`.
- **Resolution:** one edit to `segment` and one compositor with ordered slots (order in C1).
- marina-layer's `preset` parameter is unnecessary: `build.py --draft` can set `os.environ["X264_PRESET"]`. Spawned workers inherit the environment and re-read it at `:23`, so `video_pass` stays untouched.

**A4. The layout loop in `build_timeline.main` (`:318-360`).**
- text-features: preset blocks placed first, `placed` hoisted out of `:320`, block windows at `:326`, face-avoid at `:334`, `front_frames`, OUTSIDE as FAIL.
- inserts: `place_insert` runs first, `place["exclude"]` is copied at `:329`, and full-screen frames are removed from occupancy, `person_box` and `occl`.
- brands-formats adds a warning that a "front block will be cut by the matte".
- **Resolution: the merged order.**
  1. camera
  2. measure
  3. masks
  4. inserts, placed with pinned blocks (including preset `safe` boxes) as hard exclusions
  5. preset blocks
  6. other blocks, which exclude concurrent insert rects. "Concurrent" uses text-features' per-block `t0`/`t1`, not the screen window.
  7. `occl` minus full-screen frames
  8. `front_frames`, computed from that reduced `occl`
  9. checks
- Drop brands-formats' front-block warning. It contradicts text-features' front layer, which makes `behind:false` exact. Accept yocase_line's `*поїхали*` diff as the intended fix.

**A5. Who applies presets.**
- brands-formats' `resolve.apply_presets` merges a preset and then removes the `preset` key. text-features' `build_screens` (`:111-121`) merges presets itself and needs the name afterwards for:
  - the hook and CTA windows;
  - placing preset blocks first;
  - lint's "trigger inside a cta block";
  - the face FAIL.
- **Resolution:**
  - The resolver is the only place that merges presets, and it keeps the name on the block (`"preset": "hook"`).
  - `build_screens` merges nothing.
  - `text_rules.load_rules`' "until the resolver lands" fallback is dead code, because the resolver lands first (Phase 2).

**A6. `lint_edit.py` is edited by all five sections.**
- **Beat check (`:165-176`).** brands-formats skips it via `beat_cuts: false`; audio-timing skips same-clip cuts when `script.trim` exists. The two are redundant: keep brands-formats' profile key, and audio-timing only swaps the bpm and path lookup to `assets.music_info` / `assets.find`.
- **Bans and whooshes (`:143-154`).** These must run on the merged cue list, so automatic cues are checked too. Automatic cues carry `move: true`.
- **CTA check default.** text-features' universal `cta_check: true` would make yocase_2371, yocase_2477 and yocase_line FAIL lint on day one. That contradicts brands-formats' rule that a script without brand or format behaves exactly as today.
  - **Resolution:** the studio default is `cta_check: false`. `formats/talking-head` sets `true`; `subtitles-only` sets `false`.
- **Structure.** `lint()` calls `text_rules.lint_text`, `inserts.lint_inserts` and `trim.lint_audio` (each returns `(t, msg)` lists). The seams phase adds these three call lines once, so the feature phases never edit `lint_edit.py` together.

**A7. `ingest.ingest` (`:55-85`).**
- inserts adds `audio=False`, `focus` and `trim` (and `probe:33` `... or 0`). audio-timing adds `speed` (n at `:60`, `setpts` at `:64`, `atempo` at `:79`, clips.json at `:85`).
- **Resolution:** land one signature, `ingest(clip, media_dir, name, audio=True, focus=None, trim=None, speed=1.0)`, in the seams phase. Compute n = round(trimmed length / k × FPS). With all defaults, the filter strings stay byte-identical.

**A8. `times.py` is edited by four sections.** Order the edits: the seams phase adds `heard_words`; text-features adds the term and CTA prints; inserts adds its block last.

**A9. Where the glyph check runs.**
- brands-formats runs `fontcheck` inside `load_script`, before tokenizing. But text-features' censorship (`*`) and `case: upper` are display passes applied after alignment, so the characters actually drawn are not known at load time. brands-formats' probe set also lacks `*`; marina-layer's has it.
- **Resolution:**
  - One `fontcheck.check_glyphs(...)` runs on the final display tokens: in `build_timeline` after `build_screens` and before Chrome starts.
  - `doctor --script` and `resolve.py --check` reach the same function through a timing-free `text_rules.display_tokens(script)`.
  - The probe set is marina-layer's (including `*`, digits, both alphabets in both cases).
  - Drop text-features' CDP `getPlatformFontsForNode` check. The cmap check on the final text plus brands-formats' FontFace load-throw covers it, and Chrome is unpinned on Marina's Mac.

### B. Schema key collisions

- **B1. `terms`: two syntaxes and two engines.**
  - brands-formats uses norm phrases (`"u case"`) and `resolve.apply_terms`, which renames the first word, blanks the rest and adds a "skip empty w" change at `:96-101`.
  - text-features uses letter patterns with `-?` between letters and a `*` prefix wildcard, and canonicalises both sides inside `assign_times`.
  - **Resolution:**
    - `text_rules` owns matching and the syntax. Drop `apply_terms` and the empty-word change.
    - Keep from brands-formats the term `color` (term tokens are coloured in `build_screens`) and its guard: a brand term rewrites the transcript only when its display text appears in the script's spoken lines. This protects ordinary words like «баланс».
    - The universal list is text-features' plus brands-formats' `instagram` (`інстаграм*`).
    - Rewrite YOCASE's `heard_as` in text-features' syntax.
- **B2. `censor`.**
  - text-features merges lists by union; brands-formats replaces lists, with `key+` to append.
  - **Resolution:**
    - The resolver is the only merger, so ЦЕНЗУРА: writes `censor+`. The universal default is `[]`.
    - «ЦЕНЗУРА: стандартна» expands from a studio `censor_sets.standard` (the four money words).
- **B3. `presets` shape and values.**
  - brands-formats uses line presets (`hook_line`, `brand_name`, …) plus block presets limited to structure keys (hook at `y` 270, `until` 2.5).
  - text-features uses block presets with nested `lines` and the keys `dur`, `hold`, `tail`, `align`, `reveal`, `case`, `stroke`, `sfx` (hook at `y` 300, `dur` 2.5, `safe` [128,270,952,700]).
  - **Resolution:**
    - Use text-features' block shape, with `hook_line` folded into `presets.hook.lines`. Keep line-level `preset` only for `brand_name`, `product_label` and similar. The studio default holds text-features' hook and CTA values.
    - The format allow-list gains `dur`, `hold`, `tail`, `reveal`, `place`, `behind`, `fade`, `until`, `literal`, `t`.
    - These are brand-owned: `lines.scale`, `lines.anim`, `align`, `case`, `stroke`, `sfx`.
    - Drop `grammar.hook_s` and `grammar.cta_min_s`. Hook length is `presets.hook.dur`; CTA minimum is `presets.cta.hold`. Lint uses a 2.0–3.0 s hook range, per the third-party rule; brands-formats' FORMAT.md "1–3 s" is updated to match.
- **B4. Three sources for SFX samples.**
  - brands-formats' `sfx_palette.{cta, insert_pop, insert_swish}`, text-features' `presets.cta.sfx {name, gain_db}`, and inserts' `style.insert.sfx {card, cutout, full}`.
  - **Resolution:**
    - `sfx_palette` is the only sample source: brand-owned, rotated by occurrence, and subject to the ban list.
    - `presets.cta.sfx` becomes `{"event": "cta"}` or `null`.
    - Inserts use the events `insert_card`, `insert_cutout` and `insert_full`; per-insert `sfx_gain` remains as an override.
- **B5. Trim parameters.**
  - brands-formats' `grammar.trim` is `{min_pause, pad_before 0.13 s, pad_after 0.10 s, keep_after_claim 0.40}`. audio-timing's `trim` is `{min_cut, pad_before 4 f, pad_after 3 f, keep_after_sentence 10 f, head, tail, min_shot, take_gap, breath}`.
  - audio-timing also puts a `trim` block in `format.json`. But `script.trim` existing means "this EDL was produced by trim.py" and turns on lint (b). A format-level `trim` would merge into every talking-head script and switch lint (b) on for scripts that were never trimmed.
  - **Resolution:** the parameters live in `grammar.trim`, with audio-timing's names and units. `script.trim` is written only by `trim.py --write`: the marker, plus `drop`/`keep`/`punch` and the effective values.
- **B6. Speed.**
  - brands-formats uses `grammar.speed`; audio-timing puts a top-level `"speed"` in `format.json`, which brands-formats' allow-list rejects as an error.
  - **Resolution:**
    - `grammar.speed_max`; absent means no speed-up allowed.
    - The actual k is an ingest argument recorded in `clips.json` (`speed`, `orig_duration`); there is no script key.
- **B7. `audio.xfade_frames`.** audio-timing puts it in `format.json`, which the allow-list forbids; it is also redundant, because `trim --write` sets it. Drop it from the format.
- **B8. Brand music: the biggest semantic clash.**
  - audio-timing adds a top-level `music` key to `brand.json` and copies it into the script "at authoring time; no render-time fallback". brands-formats uses `audio.music`, merged by the resolver at render time.
  - marina-layer writes «без музики» as an **absent** `audio.music`, which the resolver would fill with the brand bed.
  - **Resolution:**
    - Use `audio.music` with resolver layering, which is the point of ADR-0002.
    - The brand owns `file`, `gain_db` or `under_lu`, and `offset`. The format owns `fade_in`, `fade_out` and `duck`.
    - `fade_in` is 0.05 (audio-timing's value), not brands-formats' 0.1.
    - «без музики» must write `"music": null` explicitly; the format's sticky off-switch rule makes that hold.
    - «МУЗИКА:» puts an exact file, found with `assets.py music`, into the script.
    - For reproducibility, `build.py` saves the resolved script to `build/<id>/resolved_<name>.json`, and `report.json` names the track.
- **B9. Brand layers.**
  - inserts uses `style.layers`; brands-formats mentions "a brand `layers` key". Formats may not set `style`, yet subtitles-only (baked graphics) must switch brand layers off.
  - **Resolution:**
    - Use `style.layers`, and allow a format exactly `style.layers: []` as a sticky off switch.
    - Files go in `brands/<b>/local/layers/` (untracked), not `brands/<b>/layers/`.
- **B10. Face margin.** text-features has `layout.face_margin` and inserts has `style.insert.margin_face`. Use one key, `style.layout.face_margin`, read with a default.
- **B11. Insert defaults.** A "talking-head uses `s` cards" rule is format-owned, but formats may not set `style`. Put it in `grammar.insert.size_default`; `style.insert` keeps the look only.
- **B12. Resolver allow-lists (otherwise these are errors or typo warnings).**
  - Formats gain `cta_check`, `style.layers: []`, `audio.music.duck`, the B3 preset keys, and `grammar.{trim, speed_max, insert}`.
  - Brands' known keys gain `cta_phrases`, `censor`, `terms`, `sfx_palette`.
- **B13. `.gitignore`.** brands-formats' `*.local.json` and `*.local.md` match marina-layer's **tracked** templates `docs/creator/claude-settings.local.json` and `docs/creator/CLAUDE.local.md`. `git add` would silently skip them, and INSTALL step 8 would fail on a clone. E2 removes the need for `*.local.*`; anchor `/CLAUDE.local.md` at the repo root.

### C. Layer order

**C1. The MP4 (`video_pass.render_frame`), bottom to top:**
1. The camera picture with grade and white balance, or a full-screen insert, which is never graded.
2. Flash.
3. `brand_under` (gradient, sticker), then the card insert.
4. The text "back" layer: the overlay PNG × (1 − matte) on `occlude_frames` (`:210-217`).
5. The text "front" layer: `behind:false` blocks on `front_frames`, with no matte and the same `ovm` warp.
6. `brand_over` (logo, strip).

Notes on the order:
- The third-party order differs only in where the sticker sits relative to inserts. Reserved brand rects are hard exclusions for inserts, so the two never overlap; keep the order above.
- text-features says "inserts reuse the front layer"; that is wrong and must be fixed in its text. Inserts are Python layers outside the matte.
- FCPXML lanes (`export_fcpxml.py:508`): `freeze, broll, transition, flash, brand_under, insert, text, doodle, brand_over`. This matches the MP4 order. The front layer needs no lane, only per-block occlusion at `:482`. The music stem and the muted raw track are audio lanes.

**C2. Occlusion bookkeeping.** Full-screen frames must leave `occl` before `front_frames` is computed. Otherwise front PNGs are rendered for frames where no person is visible.

### D. Duplicated tools

- **D1. Glyph checkers ×3** (marina-layer's doctor cmap reader, brands-formats' `fontcheck`, text-features' CDP check). Keep one `fontcheck.py` (A9).
- **D2. Slot guards ×3.** Keep one `common.require_slot` (A1).
- **D3. Heard-word helpers ×3** (inserts `edl.heard_words(script, edl)`, audio-timing `VoiceMap.heard_words`, text-features `text_rules.heard_words`).
  - Keep one `VoiceMap.heard_words` in `edl.py`, with audio-timing's shape `{w, s, e, p, o, oe, sentence_end}`.
  - `build_timeline.py:280-289` keeps its own `s` → output rewrite, because `assign_times` depends on it. Extract it unchanged as `build_timeline.align_words(script)` so `lint_text` can call `build_screens`.
- **D4. Face boxes ×2** (text-features' median `face_occupancy`, inserts' nearest sample with `min_face_px`). Keep one `face_boxes(track, cam, edl, f0, f1, min_px)` that returns the median box and drops boxes under `min_px`. That also removes prep's blob-estimated "faces" on hands and bottles (`prep.py:219-222`).
- **D5. Picture converters ×2.** marina-layer's `inbox.py prep` makes `build/<id>/stills/`; `inserts.prepare` makes PNGs plus `view/*.jpg` and also handles ICC profiles, EXIF orientation and HDR refusal. Keep `inserts.prepare`; drop `stills/`. The skill runs `inserts.py <script>` before choosing inserts.
- **D6. Report generators ×4**:
  - marina-layer's template, fed by grepping the build log, `clips.json` and `meta.json`;
  - text-features' «Текст», from `text_checks.json`;
  - inserts' «Вставки», from log lines;
  - audio-timing's `report.json`, with its own wording.

  **Resolution:** `build.py` writes one `output/<name>.report.json` on audio-timing's schema. Each feature adds a section: `text` (= `meta.checks.applied`), `inserts` (from `timeline.layers`, plus refused files from `inserts.json`), `brand` (resolver summary and term rewrites), `checks`, `music`, `removed`, `missing`. The single Ukrainian template, `.claude/skills/reel/report.uk.md`, reads only that JSON. Nothing greps the log.
- **D7. Pre-export gates ×3** (marina-layer's checklist with log greps, text-features' coded gate, inserts' `!!` lines enforced by the skill).
  - Every blocking geometry finding goes into `meta.checks.fail`, and one gate in `build.py` reads it. This covers insert-over-face, insert-over-subtitle, insert OUTSIDE, block/insert overlap, and brand-layer OUTSIDE (a cropped sticker).
  - `no free spot` stays a WARN. 2373, which was approved, has 7 today, so marina-layer's "no `!! no free spot`" gate would block it. The skill instead lists each one under «Сумнівні рішення» after looking at its review tile.
- **D8. RAM thresholds ×3** (marina-layer `<12e9`, inserts `<15e9`, prep `>=15e9` at `prep.py:245-246`).
  - Use one `common.low_ram()` at `<15e9`, and `default_procs()` built on it.
  - text-features' "overlay_render keeps 4 processes" gives way: `build.py` passes `default_procs()`.
- **D9. B-roll ×2.** audio-timing keeps wordless ingested clips via `trim.keep`, which plays their own sound; inserts' `mode: "full"` keeps her voice. Full-screen is `mode: "full"` only. `trim` still lists wordless clips, but as "move to `inserts/` for full-screen".
- **D10. Learned-rule stores ×2.** See E2.

### E. Inconsistent names and paths

- **E1. Intake folder.**
  - The third-party skill uses `input/`; marina-layer uses `inbox/<reel>/`, with clips and pictures mixed. inserts uses `projects/<name>/inserts/`, but the creator deny list has `Edit(/projects/**)`.
  - **Resolution:**
    - Creator reels live at `inbox/<reel>/script.json`, and `inbox.py new` also creates `inbox/<reel>/inserts/`.
    - Videos in the reel folder's root are her talking footage. `inbox.py prep` ingests them in `creation_time` order, which is load-bearing: trim's "keep the last attempt" relies on it.
    - Pictures, memes and brand-supplied clips go in `inserts/` and are never ingested. An HDR brand clip is then refused per file by `inserts.prepare`, instead of aborting the whole prep batch at `ingest.py:57-59`.
- **E2. Local corrections.**
  - brands-formats writes `brands/<b>/brand.local.json` + `BRAND.local.md` and `formats/<f>/format.local.*`. marina-layer's creator deny list includes `Edit(/brands/**)` and `Edit(/formats/**)`, so her Claude cannot write them; text-features' "brand-local override" has the same problem.
  - **Resolution:**
    - Everything lives under the gitignored `learned/`: `learned/brands/<id>.{md,json}`, `learned/formats/<id>.{md,json}`, `learned/general.md`.
    - `resolve.py` loads the JSON files as layers 4 and 5, after all tracked layers (brands-formats' order is kept).
    - JSON patches are keyed by learned-rule id, and ids listed in `learned/PROMOTED.md` are skipped. That fixes brands-formats' "stale override" risk.
- **E3. Her own audio.** audio-timing has Claude place files into `assets/local/`, but the creator deny list blocks `Edit(/assets/**)` and no `cp` rule exists. Instead, Marina drags files in Finder into `assets/local/{music,sfx}` or into the reel folder. `assets.find` also searches `<script dir>` and `<script dir>/inserts/`. Gitignore `assets/local/`.
- **E4. The template.** brands-formats deletes `projects/_template/`, which inserts and audio-timing both edit. Put `"inserts": []` in `formats/*/template.json`; templates carry no `xfade_frames` and no `duck`.
- **E5. Format names.**
  - marina-layer writes «говоряча» (a typo), refers to "TOSUMI skit (reel-subtitles reference)", and has no subtitles-only. Use brands-formats' ids and aliases: `talking-head` «говорюча голова», `subtitles-only`, `skit-hoche-a`, `product-lineup`.
  - Blocking questions: ask for the brand only. Default the format to talking-head. Claude picks subtitles-only when the contact sheet shows baked graphics (the 2026-10-13 rule) and reports that choice.
- **E6. `--draft` versus the glossary.** CONTEXT.md:47 defines "Draft MP4" as the reel ready to post, but the repo already uses `_draft` for fast previews. Keep marina-layer's `--draft` and fix the glossary instead.
- **E7. Brand assets** go in `brands/<b>/local/` (see B9).
- **E8.** `build/text_checks.json` becomes `build/meta.json["checks"]`.
- **E9.** CONTEXT.md:124 says "private"; the repo is public.

### F. Verification conflicts

- **F1.** The slot holds yocase_line, so step one of every gate is a plain 2373 draft.
- **F2. Byte-identity claims across phases.** Phases change `timeline.json` and `meta.json` on purpose: style fonts, `style.insert`/`style.layers`, `layers: []`, and the new meta keys. So each phase re-baselines at its start from the previous phase's accepted outputs and diffs with a list of keys to strip.
- **F3.** text-features' "V0 `fail: []` for yocase_line" is wrong. With OUTSIDE as a FAIL, its 5 OUTSIDE blocks (b6–b10) FAIL; that is the expected result.
- **F4.** Use `output/base_yocase_2373.mp4` and `/private/tmp/claude-501/baseline/timeline_2373.json` as the Phase-0 baseline. Never use `output/yocase_2373_draft.mp4` (Oct 13 10:24, stale).

## Gaps

- **G1. Trim is missing from the creator flow.**
  - marina-layer's session goes straight from prep to "write script.json", with no trim step, no review of repeat groups and no skeleton script.
  - **Fix:** after prep:
    1. copy `formats/<f>/template.json` and fill the paths and `src_duration`;
    2. run `trim.py` in print mode and look at the repeat-group and product-moment contact sheets;
    3. set `trim.drop` / `trim.keep`;
    4. run `trim.py --write`, then `times.py`;
    5. write screens, inserts and the CTA.
- **G2. ШВИДКІСТЬ has no plumbing.**
  - `inbox.py prep` never passes `--speed` to ingest.
  - `inbox.py reopen` must re-ingest at `clips.json`'s `speed`.
  - doctor's disk estimate ignores speed and full-screen insert ProRes (about 27 MB per second of `src`).
- **G3. КОДОВЕ СЛОВО has no key.** `brief.check` FAILs unless the code word is an accent token in the `preset: "cta"` block and is aligned (not NOT FOUND). There is no new script key.
- **G4. Hook versus insert.** The third-party rule is "no inserts and no CTA while the hook is up". Only CTA∩hook is a FAIL. inserts has a WARN for "insert during a literal title"; make insert∩hook-window a FAIL.
- **G5. Cleanup does not know the new artefacts.**
  - `build/<name>_music.wav`: export reads it, so delete it only together with `<name>_project`.
  - `build/<id>/inserts/`: regenerable while the originals exist in `inbox/` or `done/`.
  - `output/<name>.report.json`: keep it.
  - `build/overlay/front/`: covered by `--temp`.
- **G6. Lint must stay read-only and must survive cleanup.**
  - `inserts.resolve_times` reads `inserts.json` if it exists; otherwise it probes sizes read-only with Pillow and ffprobe, and never runs `sips` or ingest.
  - The audio checks (a) and (b) skip with a WARN when `build/<id>/media` was cleaned.
- **G7. Two third-party "don't export" items are uncovered.**
  - "Music not from the first frame": `report.json` records music start and `fade_in`; lint WARNs when `fade_in` > 0.1 s.
  - "Insert without sound": `sfx: null` without Marina's «без звуку» is treated as blocking by the skill.
- **G8. A missing brand font.** brands-formats stops the build; the third-party rule is "make it without and say so". Keep the stop, because the font is the brand look. doctor catches it at session start, and Marina sees «Потрібен Влад».
- **G9. The skill must read learned rules.** It reads `learned/brands/<b>.md` and `learned/formats/<f>.md`, minus the ids in PROMOTED.md, before writing a script. `resolve.py` reads the matching JSON files.
- **G10. INSTALL gaps.** It must copy `brands/*/local/` (licensed fonts, layers, permanent photos) and, if open question 1 untracks them, the WAVs. doctor must check all of them.
- **G11. `brief.check` key mapping.** marina-layer's "skip with a WARN until the other designs' keys exist" is replaced by the final names: `censor+`, `presets.hook` / `presets.cta`, `inserts[]`, `audio.music` (null for «без музики»), and `grammar.speed_max` with `clips.json` `speed`.
- **G12. The lock with a direct `build_timeline.py` run.** Take `studio_lock` only in CLI entry points (`if __name__ == "__main__"`). Locking inside `main()` as well would self-deadlock when `build.py` calls `build_timeline.main` in the same process.

## Phases (ordered, with files touched, deps, gate, parallelisable?)

**Every gate:**
- runs on the dev Mac with `--draft` (from Phase 1 on);
- compares against the previous phase's accepted outputs;
- ends with a plain `projects/yocase_2373/script.json` draft, so the slot holds 2373 again.

Renders are serialised by `studio_lock`; a gate that gets exit 2 waits and retries.

### Phase 0: baseline and repo hygiene (S, about half a day)
- **Files:** `.gitignore` and the WAV untracking, if chosen; `CONTEXT.md:12,124`. Commit locally; **no push until open question 1 is answered.** Every phase commits locally; the push happens in Phase 6.
- **Deps:** none (open question 1 decides the hygiene commit).
- **Gate:**
  - The baseline is `output/base_yocase_2373.mp4` plus `/private/tmp/claude-501/baseline/*`. Add to `/private/tmp/claude-501/golden/`:
    - the output of `lint_edit.py` and `times.py` for all 6 projects;
    - the `audio.build_filter` string for each project (audio-timing V1).
  - If `/private/tmp` was cleared, run `X264_PRESET=veryfast .venv/bin/python pipeline/build.py projects/yocase_2373/script.json --name base_yocase_2373`.
- **Parallel:** no.

### Phase 1: shared plumbing, marina-layer core (S–M)
- **Files:**
  - `common.py`: PATH fix, `low_ram`, `default_procs`, `studio_lock` with hand-down, `keep_awake`, stdout reconfigure, `require_slot`.
  - `beats.py`: import `common`.
  - `build.py`: `--draft`, `--procs`, lock, guard, `renders`.
  - `build_timeline.py:main`: delete meta first, write it last, with `script`, `brand`/`format` = null, `renders`, `checks`.
  - `export_fcpxml.py:main`: procs default, guard before `:265`, lock.
  - `review_frames.py`: the `renders` guard.
  - `prep.py` and `ingest.py`: lock and wake around `main`.
  - `contact_sheet.py`: `--phone`.
- **Deps:** Phase 0.
- **Gate:**
  1. `.venv/bin/python pipeline/build.py projects/yocase_2373/script.json --draft --name p1_2373_draft` gives:
     - `[video] rc=0` and 865 frames;
     - `subme=2`;
     - `ffmpeg -nostdin -i output/base_yocase_2373.mp4 -i output/p1_2373_draft.mp4 -lavfi psnr -f null -` → `average:inf` (or at least 60 dB);
     - `cmp build/timeline.json /private/tmp/claude-501/baseline/timeline_2373.json` identical;
     - `meta.json` equal to `baseline/meta_2373.json` plus the new keys, with `renders` = `["p1_2373_draft"]`.
  2. A second concurrent `--draft --name t2` exits 2 ("studio busy"), and `meta.json`'s mtime is unchanged.
  3. Each of these exits 2 and writes nothing:
     - `build.py projects/yocase_2477/script.json --skip-timeline --skip-overlay --name t2477`;
     - `export_fcpxml.py projects/yocase_2477/script.json --name x` (no `output/x_project` appears);
     - `review_frames.py output/yocase_2477.mp4`.
  4. Crash safety: a scratch copy of 2373 with one 1100-px literal line makes `build_timeline` raise the ValueError (`:253`). `build/meta.json` is then absent, and `build.py <2373> --skip-timeline` refuses with "unknown slot".
  5. Finish by re-running step 1.
- **Parallel:** no.

### Phase 2: brands and formats resolver (M–L)
- **Files:**
  - New: `resolve.py`, `fontcheck.py`, `studio_default.json`.
  - `style_default.json` (`fonts` only).
  - `overlay.html`: remove `:6-8`; FontFace in `init` (`:119-122`); `applyFont` features at `:57`.
  - `build_timeline.main`: `load_script` and the glyph check on tokens. Phase 4a moves the glyph check after the display passes.
  - Switch to `load_script` in `build.py` (`:38`, `:44`), export (`:263`), `lint_edit` (profile; `:162` grade null; `:182`), `times.py:16`, `preview.py:45`.
  - Data: `brands/{tosumi,yocase}/`; `formats/{talking-head,subtitles-only,skit-hoche-a,product-lineup}/`, with the B3–B12 rules applied.
  - Delete `projects/_template`.
  - `learned/` layer loading.
  - Docs: STYLE.md, CONTEXT.md, ADR notes, and the reel-subtitles resolve steps.
- **Deps:** Phase 1.
- **Gate:**
  1. Pure-Python checks: brands-formats V1, V2, V6, V7, V10, V12, plus V9 using `learned/brands/yocase.json`; `git status --porcelain` stays clean.
  2. FontFace identity: before editing `overlay.html`, `overlay_render.py --frames 865 --only 15,90,237,360,600,810 --out $V/ov_css`. After the edit, rebuild the timeline and run the same command with `--out $V/ov_ff`. `cmp` shows the 6 frames identical.
  3. `--draft --name p2_2373_draft`: PSNR against p1 is inf, and the timeline differs from p1 only in `style.fonts`. The brand-migrated copy `$V/yocase_2373_brand.json --draft` also gives inf against p1.
  4. The talking-head variant plus export gives exactly one `name="music"` clip, with `fadeIn` and `fadeOut`.
  5. Finish with the plain 2373 draft.
- **Parallel:** partly. Code (`resolve.py`, `fontcheck.py`, the switch-over) and data (brand and format JSON, FORMAT.md, BRAND.md, templates) are disjoint files and can go to two agents.

### Phase 3: seams, behaviour-neutral (S)
- **Files:**
  - `edl.py`: `VoiceMap.heard_words`, `speech_spans`.
  - `common.py`: `norm` moved from `build_timeline.py:31-32`.
  - `build_timeline.py`: `align_words` extracted unchanged; `face_boxes`; `timeline["sfx"] = []`.
  - New `assets.py`: `find`, `search`, `sfx_peak`, `music_info`, CLI.
  - `build.py`: `sfx_cues(list) -> (cues, missing)`, music through `assets.find`, `report.json` skeleton.
  - `export_fcpxml.py`: `:531` and `:539` use the merged cues and assets.
  - `ingest.py`: the full signature with defaults, the `ffmpeg_cmd()` helper, and the `probe:33` fix.
  - `video_pass.py`: `segment` always loads the timeline; `render_frame` gets layer slots, empty for now.
  - `lint_edit.py`: the three registration hooks and the merged cue list.
  - `times.py`: uses `heard_words`.
- **Deps:** Phase 2.
- **Gate:**
  - Against the Phase-0 golden files: identical filter strings for every project; identical `lint_edit` and `times` output for all 6 projects; identical `ingest.ffmpeg_cmd` strings for the 2373 clip.
  - audio-timing V6 asset checks pass.
  - `--draft --name p3_2373_draft`: PSNR against p2 is inf, and `output/p3_2373_draft.report.json` shows `raw_s` = `out_s` = 28.83 with 0 edits.
- **Parallel:** no. This phase is what makes Phase 4 parallel.

### Phase 4: features, in parallel worktrees
- **4a, text layer** (M+). Applies A4, A5, A9, B1–B4.
  - **Files:**
    - new `text_rules.py`;
    - `build_timeline.py`: `tokenize`, `assign_times`, `build_screens`, the `solve_block` guard and weight, the layout loop, block windows, `front_frames`, checks;
    - `overlay.html`: centring, stroke, ink boxes, `seek(layer)`;
    - `overlay_render.py`;
    - `video_pass.py`: the front slot only;
    - `export_fcpxml.py`: `:472-489` only;
    - `review_frames.py`, `compare_render.py`, `times.py`;
    - studio and talking-head data.
  - **Gate:**
    - text-features V0, re-baselined at p3: 2371, 2373 and 2477 have identical timeline and camera files, identical meta apart from the stamp, and identical PNGs. yocase_line differs only in `front_frames`, and its `checks.fail` lists b6–b10 OUTSIDE.
    - Old scripts' lint output is unchanged, since `cta_check` now comes only from the format.
    - text-features V3 on `/private/tmp/claude-501/design/yocase_2373_text.json --draft`, with `"format": "talking-head"` or `"cta_check": true` added. Expect:
      - about 135 front PNGs;
      - matte AND front-PNG alpha > 0 at frame 720;
      - the CTA card at 21.18–23.18 s, with its chime peaking at 21.18.
    - text-features V4 negatives: U+2217 now FAILs through `fontcheck`; the build exits 2 before `[overlay]`.
    - text-features V5 (FCPXML).
    - Finish with the plain 2373 draft: PSNR against p3 is inf.
- **4b, audio and timing** (M–L).
  - **Files:**
    - new `trim.py`; `assets.py` (extended);
    - `audio.py`: crossfade, `music_chain`, `duck`, `under_lu`, stem;
    - `ingest.py`: speed;
    - `build.py`: audio block `:52-62` and the report sections;
    - `export_fcpxml.py`: audio block `:520-545` only;
    - `grammar.trim` / `speed_max` data, and the brand `under_lu` / `duck`.
  - **Gate:**
    - audio-timing V1–V9;
    - V10 in a scratch directory, deleted afterwards;
    - V11 on `/private/tmp/claude-501/it/script.json --draft`: 855 frames; `report.json` pauses n=2, s=0.333; `missing` = `[no_such_sound]`; the stem is 1,368,000 samples; the FCPXML has 2 music clips and `media/whoosh.wav`;
    - finish with the plain 2373 draft: PSNR against p3 is inf.
- **4c, creator tools** (M).
  - **Files (all new):** `doctor.py` (glyphs through `fontcheck`), `inbox.py` (with the `inserts/` subfolder and `--speed`), `cleanup.py` (G5 patterns), `brief.py` (`parse` only), `selftest.py`, `docs/creator/*`, `learned/README.md` and `PROMOTED.md`, `.claude/settings.json`, `CLAUDE.md`, `INSTALL.md`, `README.uk.md`, `.gitignore`.
  - **Gate:**
    - `selftest.py` passes in under 5 s;
    - doctor shows a WARN for the lock stamp and OK for ffmpeg at `/opt/homebrew/bin`;
    - `doctor.py --script projects/yocase_2373/script.json` is OK;
    - `doctor.py --clips исходники/IMG_2373.MOV` reports SDR, 28.8 s;
    - `cleanup.py plan yocase_2373` matches marina-layer V7;
    - the desktop-session permission checks of marina-layer V8 pass.
- **4d, inserts pure modules** (M). New `inserts.py` (`prepare`, `find_phrase`, `resolve_times`, CLI) and `layers.py`. **Gate:** inserts V1 pure checks except `place_insert`.
- **Parallelisable:**
  - 4c and 4d touch no shared file.
  - 4a and 4b share only `export_fcpxml.py`, in disjoint hunks (`:472-489` and `:520-545`). Merge 4a first and rebase 4b.
  - Gate renders are serialised by the lock.

### Phase 5: inserts integration (L)
- **Files:**
  - `build_timeline.py`: `place_insert`, module-level `window_sum`, copied exclude lists, overlap → `checks.fail`, full-screen skip, `layers`, insert cues into `timeline["sfx"]`.
  - `video_pass.py`: the Compositor fills the full, under and over slots.
  - `export_fcpxml.py`: `write_layer`, `broll`, lanes at `:508`, `clip_xml`.
  - `inserts.lint_inserts`, including insert∩hook as a FAIL.
  - `review_frames.py`, `times.py`.
  - `style_default.json`: `insert` and `layers: []`; the palette insert events; `inserts: []` in the templates; ADR-0009.
- **Deps:** 4a (block windows, front slot, checks, `face_boxes`), 4b (assets), 4d.
- **Gate:**
  - inserts V1 `place_insert` checks;
  - V2 with `--draft`: the disc is intact at frame 609; B-roll frame 441 has PSNR ≥ 38 dB against the converted `.mov`; cue peaks land at f0/30;
  - V3 (lint) and V4 (export, plus the `ru_maxrss` growth under 100 MB);
  - V5: the plain 2373 draft gives PSNR inf against p4, and the timeline differs only in `layers: []`, `style.insert` and `style.layers`.
- **Parallel:** no.

### Phase 6: creator integration and handover (M, plus the visit)
- **Files:**
  - `.claude/skills/reel/{SKILL.md, brief.md, report.uk.md}`: the G1 flow and the D6 template;
  - `brief.check`, wired into `lint_edit.py:180-187`;
  - `reel-subtitles` becomes a reference skill (`disable-model-invocation`), with the merged grammar;
  - `reel-videographer` edits;
  - final versions of CLAUDE.md, README.uk.md and INSTALL (G10);
  - the CONTEXT.md glossary (`:47`) and current state;
  - the push, after open question 1.
- **Deps:** all phases.
- **Gate:**
  1. Create `inbox/t2373/` with:
     - `brief.md`: ХУК, ЦЕНЗУРА: салонний, МУЗИКА: groove, and one ВСТАВКИ line;
     - `inserts/set.jpg`;
     - a `script.json` with `"brand": "yocase"`, `"format": "talking-head"` that points at `build/yocase_2373/*` (no new prep).
  2. Check, in order:
     - `lint_edit.py inbox/t2373/script.json` shows 0 FAIL, including the brief checks;
     - `build.py inbox/t2373/script.json --draft` returns rc 0 with an empty `checks.fail`;
     - `output/t2373_draft.report.json` has every section;
     - `inbox.py archive t2373` moves it to `done/`;
     - `inbox.py reopen t2373 --dry-run` plans no re-ingest;
     - `cleanup.py plan t2373` lists only t2373 items;
     - fresh clone: `py_compile` with `.venv/bin/python`, then `selftest.py`.
  3. Remove the test reel and finish with the plain 2373 draft.
  4. On Marina's Mac: INSTALL steps 1–12, including the smoke reel from `исходники/IMG_2373.MOV` (full flow with trim and reopen). Record the M1 timings and `--procs` 2 vs 4.
- **Parallel:** the docs and skill text can be drafted during Phase 5.

**Effort:** about 14–16 developer-days in sequence, or about 10–12 elapsed days with Phase 4 in parallel, plus the visit.

## Open questions (with defaults)

1. **Public repo contents before pushing `b910950`.**
   - What is already public at `a17cc27`: the 41 licensed WAVs (their licences forbid redistribution), CONTEXT.md:12 family details, and the tosumi_hair copy.
   - What the push would add: the YOCASE subtitle copy.
   - **Default:**
     - Keep the repo public.
     - Untrack `assets/music/*.wav` and `assets/sfx/*.wav`; gitignore them, keep the credits JSON tracked, and copy the WAVs to her Mac in person.
     - Remove the personal details from CONTEXT.md.
     - Keep the YOCASE scripts; that copy is already published as ads.
     - Never track brand logos, photos or licensed fonts (`brands/<b>/local/`).
     - If the WAV history matters, rewrite it now with `filter-repo`, before any clone exists. After that it is not worth doing.
2. **Music in brand talking heads.**
   - **Default:**
     - The brand bed is on, from frame 0. For YOCASE: Gimme that Groove from 18.423 s.
     - Level: 15 LU under the voice, rising 4 dB in gaps of 0.8 s or more. The alternative is the third-party −18 dB with a 2–4 dB dip; one A/B listen on a real YOCASE talking head settles it.
     - `<reel>_no_music.mp4` is rendered with every final, as ADR-0003 says, rather than only on request.
3. **Brand data I cannot infer.**
   - **Default:**
     - YOCASE: the display is lowercase `yocase` in accent `#8A2E92`; product names in Latin lowercase in their product colours; «ти».
     - Hook and CTA in brand fonts: no caps, no stroke, scale 1.5 / 1.25.
     - TOSUMI keeps vignette 0.10 and moves new skits to anchored 1.12 punches.
     - No standing censor list for either brand («ЦЕНЗУРА: стандартна» on request).
   - Each item is a one-line edit in `brand.json`.
4. **How Marina shoots, and speed-up.**
   - Does she reliably say «стоп»? One clip per take, or one long take? Product close-ups as separate clips, or inside talking clips?
   - **Default:**
     - Treat «стоп» as unreliable. Trim proposes; Claude confirms on contact sheets.
     - Keep breaths before phrases.
     - Build speed-up, but it is off. `ШВИДКІСТЬ:` is honoured only in talking-head, with `speed_max` 1.2, and she shoots at 60 fps when she plans to use it.
5. **Inserts on centred talking heads.**
   - **Default:**
     - `m` cards may sit under the chin, with an automatic step-down to `s`. Tall screenshots go full-screen instead of being cropped.
     - Claude crops only when she asks. The third-party skill forbids cropping, and a crop could misrepresent a review.
     - Animation: `snap` (85 ms) at studio SFX levels.
     - Permanent per-brand photos go in `brands/<b>/local/photos/` (untracked, installed in person).
6. **How much Marina's Claude does on its own.**
   - **Default:**
     - Manual mode plus the allowlist; the only routine click is cleanup apply.
     - She may run «онови студію» between reels; doctor guards it.
     - No local-only new brands. A reel for an unknown client is made in the studio look and flagged «Потрібен Влад», as ADR-0002:22-24 says.

The files this critique rests on:
- /Users/vlad/git/reel-studio/pipeline/build_timeline.py
- /Users/vlad/git/reel-studio/pipeline/build.py
- /Users/vlad/git/reel-studio/pipeline/video_pass.py
- /Users/vlad/git/reel-studio/pipeline/export_fcpxml.py
- /Users/vlad/git/reel-studio/pipeline/lint_edit.py
- /Users/vlad/git/reel-studio/pipeline/ingest.py
- /Users/vlad/git/reel-studio/pipeline/overlay.html
- /Users/vlad/git/reel-studio/output/base_yocase_2373.mp4
- /private/tmp/claude-501/baseline/build.log
- /private/tmp/claude-501/baseline/timeline_2373.json
- /private/tmp/claude-501/baseline/meta_2373.json
- /Users/vlad/git/reel-studio/build/meta.json
