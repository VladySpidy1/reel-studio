## Text layer: censorship, Latin words, hook, CTA and pre-export text checks

### Goal

This adds five features from the third-party skill to the subtitle and graphics layer. They reuse the line markup, the layout solver, SFX peak placement, the EDL and the per-block FCPXML layers.

1. **Censorship.** Subtitle display text gets an ASCII `*` (`гр*ші`) after alignment, so two censored words in one line work. The words come from ЦЕНЗУРА: and the brand list. The universal list is empty.
2. **Latin words.** Brand and platform words (`yocase`, `reels`, `tiktok`, `claude`, `repair plex`) show as typed but align to the Cyrillic or mangled transcript (`U -Case`, «рілс»). One `terms` map (`heard_as`) is canonicalised on both sides of the alignment.
3. **Hook.** The ХУК: text appears verbatim in the brand fonts and colours. It is centred, shown from frame 0 for 2–3 s, sits in y 270–700 off the face, can have a real stroke, and is drawn in front of her.
4. **CTA block.** The subtitle block of the spoken CTA phrase becomes a card. It pops on its first word with the chime and stays to the phrase end and at least 2 s (to the reel end when it is the last phrase). It respects the safe zone. Lint fails a spoken CTA that has no card.
5. **Pre-export text checks.** A FAIL blocks the final render and the FCPXML export:
   - a glyph that is not in the brand fonts;
   - a block outside the safe area, on the rail, or bigger than the safe area;
   - two visible blocks overlapping;
   - letters of different lines colliding;
   - a hook or CTA over the face.

**Compatibility contract.**
- For 2371, 2373 and 2477, `timeline.json`, `camera.json`, `meta.json` and the overlay PNGs stay byte-identical.
- yocase_line changes only through the intended fix of its one mixed screen. Its `*поїхали*` block is `behind: false` inside a behind screen, so today the matte cuts a hole in it.
- tosumi_hair and `_template` also have mixed screens, but they cannot be rebuilt on this Mac.

### Creator-facing behaviour

Marina writes the brief in Ukrainian in the Claude app. Claude turns it into `script.json` fields.

| Marina writes | What happens |
|---|---|
| `ХУК: Чому волосся ламається восени?` | A hook block with the text verbatim, in the brand fonts and colours. Claude splits it into lines that fit 824 px. It is centred near the top, shown from frame 0 to 2.5 s, and drawn in front of her but never over her face. No CTA or insert appears while it is up. |
| `КОДОВЕ СЛОВО: ПЛЕКС` | Her spoken CTA phrase («напиши ПЛЕКС у коментарях») becomes the CTA card, with the code word in the brand accent style. The card pops on the phrase's first word with a soft chime and stays to the end of the phrase, at least 2 s. |
| *(no keyword: she just says «напишіть нам…», «пиши в дірект», «посилання в шапці профілю»)* | The phrase is found in the transcript. Claude makes that block the CTA card, or lint blocks delivery. |
| `ЦЕНЗУРА: гроші, знижка` | These words and the brand's list appear in subtitles as `гр*ші`, `зн*жка`, in every form (грошей → гр*шей). `ЦЕНЗУРА: стандартна` adds the skill's money list (гроші, безкоштовн…, заробіток, підписка). Titles she typed, such as the hook, are censored only if she asks. Nothing is censored by default. |
| «пиши Repair Plex латиницею» | Claude adds the word to the reel's `terms`. A brand-wide request goes to the brand's local override (learned-rules design), never into the tracked `brand.json`. |
| `без правок стилю` | The hook and CTA use the brand presets unchanged. |

She gets a "Текст" section in the final report. Claude writes it in Ukrainian from `build/text_checks.json`:

```
Текст:
• Хук «Чому волосся ламається восени?» — 0,0–2,5 с, угорі по центру.
• Заклик «напишіть нам ПЛЕКС» — 31,3–33,3 с, з дзвіночком.
• Цензура: гр*ші (2), зн*жка (1).
• Латиницею: yocase (3), repair plex (2).
• Перевірка: усі літери є у шрифтах бренду, текст у безпечній зоні, нічого не накладається.
```

Claude fixes FAILs before any render, because the timeline step is cheap: it splits a too-wide hook, moves a CTA or drops an emoji. Only judgement calls go into the report, for example: «емодзі 🔥 немає у шрифті бренду — прибрала».

### Schema

#### Where the keys live

The brand/format resolver (other area) merges, in order: universal defaults, format, brand, brand-local override, script. It hands one resolved script to build_timeline, lint_edit and times.py.

This section defines the meaning of five top-level keys in that chain: `terms`, `censor`, `cta_phrases`, `cta_check` and `presets`. These are the names the brand design already uses (`terms.*.heard_as`, `censor: []`).
- There is no `text_default.json`, no `text.spell` and no `style.presets`. The universal values below go into the resolver's universal file.
- The CTA chime lives only in `presets.cta.sfx`. A `sfx_palette.cta` must not become a second source.
- The talking-head template's line preset `hook_line` becomes `presets.hook.lines`.
- Until the resolver lands, `text_rules.load_rules` reads the universal file plus the script's own keys.

Merge rules:
- `terms`: a dict by display key; a later layer replaces an entry.
- `censor` and `cta_phrases`: list union.
- `presets`: merged per preset name, key-wise; `place` and `lines` are merged one level deeper.
- `cta_check`: the last value wins.

Nothing in this section goes into `style`, so `timeline.json["style"]` is unchanged. It is serialised at build_timeline.py:313/360.

#### Line grammar (`build_timeline.tokenize`, build_timeline.py:35-54)

Steps 1, 3 and 5 are new; 2, 4 and 6 are today's code.

1. **Escapes.** `\*` and `\_` (JSON `"\\*"`) become U+E000 and U+E001 before run splitting. They come back as `*` and `_` in the display text, and `norm()` drops them.
2. **Runs.** `*…*` is accent and `_…_` is accent-white. The regex at line 37 is unchanged.
3. **Words.** `re.findall(r"[^\s{]*\{[^}]*\}\S*|\S+", part)` replaces `part.split()` at line 45. It is identical for any word without `{`. None of the 224 existing lines contains `{`, `}` or `\`.
4. **`//` and `№N`.** Lines 46-49 stay verbatim; line 49 keeps its U+2009 thin spaces.
5. **`display{heard}`.** The word shows as `display` and matches `norm(heard)`, e.g. `погано{башко}` for a one-off mishear (2477).
   - `heard` may contain spaces and hyphens, but not `* _ { }`.
   - In literal lines the `{…}` part is dropped.
   - An empty display or an empty `{}` is a lint FAIL. There is no "shown but not spoken" form; literal lines already do that.
6. **Everything else** is unchanged.

Inside `assign_times`, before the SequenceMatcher:

7. **T side.** Each `terms` heard variant is matched in the transcript string.
   - Its letters are joined by `-?`. The match starts at a transcript word start and ends at a word end; a trailing `*` makes it a prefix match, for inflections.
   - Variants equal to the display are skipped, because rewriting them collapses «Plex» onto «Repair»'s 8.24 s.
   - The span becomes `squash(display)` and is owned by its first word.
   - Absorbed words count as used in the "not shown" warning (96-101).
8. **S side, per token.** If a token's match word (typed, or its inline `heard`) equals a heard variant, or prefix-matches a `*` variant, the match word becomes `squash(display)`. Typed «рілс» and inline `yocase{юкейс}` therefore still align after T was rewritten.
   - The display text is never rewritten automatically, because some product words are ordinary words (balance ← «баланс»).
   - times.py prints the canonical text, so Claude types the display form, and lint WARNs on a typed heard form.

After `assign_times`, the display passes:

9. **Censor.** It applies to spoken main and accent tokens. It skips term display words, deco and labels. A literal line is censored only when it has `"censor": true`. Matching uses `norm(display)`.
10. **Case.** The block's `case` (`"upper"` or `"lower"`) applies to every token of the block, literal ones included. It skips deco, labels and term display words, so the brand spelling wins.

#### Top-level keys (script.json; also valid in format, brand and brand-local)

| Key | Universal default | Meaning |
|---|---|---|
| `terms` | `{"reels": {"heard_as": ["рілс*", "рілз*"]}, "tiktok": {"heard_as": ["тікток*", "тік ток"]}, "claude": {"heard_as": ["клод*"]}}` | Display form → heard variants. A variant has at least 4 letters, unless it is several words. |
| `censor` | `[]` | ЦЕНЗУРА: words; matched at the word start. The n-th word character of the display becomes an ASCII `*`, since no bundled font has U+2217. See the entry forms below. |
| `cta_phrases` | `["^(на)?пиш(и\|іть)$", "^посилання$", "^переход(ь\|ьте\|и\|іть)$", "^(в\|у)?(дірект\|директ)(і\|у)?$", "^коментар", "^підпиш(ись\|іться)$", "^підписуй(ся\|тесь)$", "^лінк"]` | Trigger regexes over `norm(word)` of the heard words. Hits less than 3 s apart count as one CTA. |
| `cta_check` | `true` | `false` silences the "spoken CTA without a card" FAIL, e.g. for pre-edited subtitles-only reels. |
| `presets` | see below | The block presets `hook` and `cta`. |

A `censor` entry takes one of two forms:
- **A plain word,** e.g. `"гроші"`. The stem is the word with trailing vowels, ь and й stripped, at least 3 letters. The masked letter is the first vowel at index 1 or later.
- **A word with one `*`** at the masked letter, e.g. `"підп*ска"` or `"безкоштовн*"`.

YOCASE example (in the brand file, owned by the brand area):

```json
"terms": {"yocase": {"heard_as": ["u-case", "ю кейс", "юкейс", "ю-кейс"]},
          "repair plex": {"heard_as": ["репейрплекс*", "реперплекс*"]},
          "fix color": {"heard_as": ["фікс-колор", "pixcolor"]}},
"cta_phrases": ["^обирайте$"]
```

A brand that wants caps and a stroke on the hook adds `"presets": {"hook": {"case": "upper", "stroke": {"px": 3, "color": "#171717"}}}` (open question 3).

#### Universal `presets`

```json
"presets": {
  "hook": {"lines": {"scale": 1.5, "anim": "pop"}, "align": "center", "behind": false, "dur": 2.5, "fade": 0.2,
           "place": {"x": "center", "y": 300, "safe": [128, 270, 952, 700], "avoid": "face"}},
  "cta":  {"lines": {"scale": 1.25, "anim": "pop"}, "align": "center", "behind": false, "hold": 2.0, "tail": 0.2,
           "fade": 0.2, "reveal": "block", "sfx": {"name": "ding_02_soft_chime", "gain_db": -18},
           "place": {"x": "center", "y": 900, "safe": [128, 860, 952, 1248], "avoid": "face"}}
}
```

- The hook scale gives 1.5 × 58 ≈ 87 px; the skill uses 92 px.
- The hook has no SFX, as the skill specifies.
- The CTA zone keeps the paid-profile bottom (y ≤ 1248, playbook.md:587).
- The CTA `y` is 900 so that a block up to about 150 px tall ends above y 1050, where the rail [850,1050,1080,1920] starts. A centred block wider than 620 px cannot sit lower without the solver shifting it left.
- The template's hook is not a preset block, so it keeps its `until: 1.6`.

#### Block keys (new; all optional)

| Key | Default | Meaning |
|---|---|---|
| `preset` | – | `"hook"` or `"cta"`. Merged under the block: block-level keys first, then `lines` into each line spec (a string line becomes `{"text": …}`). Explicit block or line keys win; `place` is merged key-wise. |
| `align` | `left` | New value `"center"`. |
| `stroke` | – | `{"px": ≤4, "color"}`: a real outline, drawn as an SVG filter on the block. |
| `dur` | – | Fixed visible length from t0 (the hook). |
| `hold` | – | Minimum visible time from t0 (the CTA). |
| `tail` | – | Minimum seconds after the end of the block's last spoken word (the CTA). |
| `until` | – | Meaning unchanged: an absolute time after which the block is hidden. It is a clamp. |
| `reveal` | `"word"` | `"block"`: every token takes the block's first time, so the whole card pops at once. |
| `case` | – | `"upper"` or `"lower"`. |
| `sfx` | – | `{"name", "gain_db"}`, peaking at t0. Skipped if `audio.sfx` already has the same name within ±0.1 s. |
| `place.x` | – | New value `"center"`, which targets `540 − w/2`. |
| `place.avoid` | – | `"face"`: avoid the face box instead of the whole person matte. |
| `censor` (on a line) | `false` | Censor a literal line. |

**Block window.** Only blocks with `preset`, `dur`, `hold` or `tail` get one; every other block keeps today's window.

```
t0 = min token time (after reveal)
t1 = min(duration, until, t0 + dur)                                      if dur
t1 = min(duration, until, max(screen t1, t0 + hold, spoken_end + tail))   otherwise
```

- `spoken_end` is the output end of the transcript word that owns the block's last spoken character: `s + e − s_src`, as in times.py:26.
- A missing term drops out of the `min` and `max`.

**The hook** is the first block of the first screen, as in the template. It never gets a screen of its own: that screen's window would be [0, 0.0), because the first word starts at 0.00 (build_timeline.py:136-137).

**Layout numbers** are read in code with defaults, as `left_snap` and `read_time` already are (build_timeline.py:241, 331): `layout.face_margin` = 40 and `layout.ink_overlap_px` = 6. They are not added to style_default.json.

#### Build outputs (single slot)

- **`timeline.json`.** New keys are written only when non-empty:
  - block `t0` and `t1` for windowed blocks;
  - `front_frames`;
  - `sfx`, the auto cues.
- **`build/text_checks.json`** holds `{"script": <resolved path>, "fail": [], "warn": [], "applied": {"censored", "latin", "hook", "cta"}}`. Every `build_timeline.main` deletes it at the start and always writes it at the end.
- **`build/overlay/front/NNNNN.png`** exists only for the `front_frames`.

### Changes by file

#### `pipeline/text_rules.py` (new)

Pure Python, about 140 lines. Used by build_timeline, lint_edit and times.

- **`load_rules(script)`** returns `terms`, `censor`, `cta_phrases`, `cta_check` and `presets` from the resolved script.
- **`heard_words(script, edl)`** is lifted from build_timeline.py:280-289 and adds the output end `s + e − s_src`.
- **`canon_transcript(T, owner, starts, terms)`** and **`canon_word(word, terms)`** implement grammar steps 7 and 8.
- **`censor_index(word, entry)`** and **`mask_letter(text, i)`** implement the censor.
- **`cta_triggers(words, rules)`** returns `[{t, word, end}]`, merging hits less than 3 s apart.

#### `pipeline/build_timeline.py`

- **`tokenize`** (35-54): grammar steps 1, 3 and 5.
- **`assign_times`** (57-101):
  - records the word starts and calls `canon_transcript` after 63-67;
  - applies `canon_word` to each token before 69-72;
  - returns `{fuzzy, not_found, last_owner}`, and still prints as today.
- **`build_screens`** (104-153) takes `rules` and returns `(screens, info)`. main (294) is its only caller.
  - Preset merge at 111-121.
  - After 127: `reveal`, censor and case.
  - After the screen windows (128-153): the block windows and the auto SFX cues.
- **`solve_block`** (193-255):
  - **Guard.** If the block is wider or taller than its safe box, return `(x, y, "TOO BIG …")` without solving. Today a block wider than 1080 px crashes: the grid built at 208-212 is empty, and line 253 calls `.min()` on an empty array (ValueError, reproduced with bw=1100).
  - **Text weight.** Cells occupied by other blocks get the value 8 instead of 1 (337). With no free spot, the fallback then overlaps her rather than text; `feasible` is unchanged.
- **`face_occupancy`** (new, next to `occupancy` at 168-179):
  - takes the per-coordinate median of the `track.json` face boxes over the window;
  - interpolates them by source time, as `cam.face_track` does (camera.py:37-45), and maps them with `cam.matrix`;
  - the median rejects 2373's 810 px false boxes;
  - with no face sample in the window, it falls back to `occupancy`.
- **`measure`** (258-266) also calls `textChecks()` and `glyphProbe()` in the same Chrome session, then `text_checks.glyphs(pg)`.
- **`main`** (269-362):
  - deletes `build/text_checks.json` first, then loads the rules;
  - resolves `place.x == "center"` to `540 − w/2` before the solve;
  - places preset blocks first within a screen;
  - hoists `placed` out of the screen loop (320). This is placement-identical for 2371, 2373, 2477 and yocase_line: none of them has block windows overlapping across screens (checked);
  - sets the window with `t_end = b.get("t1", min(...))` (326);
  - uses `face_occupancy` when `place.avoid == "face"` (334);
  - makes OUTSIDE (352-354) a FAIL on the same layout bbox ± Q, as today's check. Crossing a global `layout.exclude` rectangle and TOO BIG are also FAILs. Ink that overshoots the layout bbox by more than Q is a WARN;
  - sets `front_frames` to the frames in `occl` (357-359) where a `behind: false` block is visible;
  - runs `text_checks.geometry` and writes `text_checks.json`.

#### `pipeline/text_checks.py` (new)

About 100 lines. It decides FAIL or WARN; Claude reports.

- **`glyphs(pg)`** makes one CDP `CSS.getPlatformFontsForNode` call per probe span.
  - Any font with `isCustomFont: false` is a FAIL, e.g. `glyph U+2217 '∗' (Main 380) rendered by Apple Symbols`.
  - This also catches a brand @font-face that never loaded.
  - If CDP errors, the result is a WARN "glyph check unavailable", never a crash.
- **`geometry`**:
  - FAIL: two blocks visible at the same time with intersecting layout bboxes.
  - FAIL: a preset block intersecting the window's median face box grown by `face_margin`. This is skipped when the window has no face.
  - FAIL: cross-line ink collisions of at least `ink_overlap_px` pixels.
  - WARN: "no free spot", as today.
- **`gate(allow_fail, script_path)`** exits 2 in any of these cases, unless `allow_fail` is set:
  - the file is missing;
  - its `script` differs from `Path(script_path).resolve()`;
  - it has any FAIL.

There is no `--fonts` mode. Static font coverage belongs to the preflight design's cmap reader.

#### `pipeline/overlay.html`

- **Centre alignment** (142-144):
  - `x0 = right ? … : center ? (bw − ln.width)/2 + indentPx : indentPx`;
  - the hanging-bracket rule at 144 becomes `lineAlign === 'left'`, which is equivalent for today's values.
- **Stroke** (131): when `blk.stroke` is set, add an `<svg><filter>` once per (px, color): `feMorphology` dilate on SourceAlpha, then `feFlood`, then `feComposite in`, then `feMerge` with SourceGraphic. Then set `el.style.filter = 'url(#…) ' + S.shadow`.
- **Ink boxes.** For each glyph, canvas `measureText` (`actualBoundingBox*`) with the glyph's font, plus `stroke.px`.
  - They are stored next to `bbox` (195) and never used for placement.
  - Serif labels are skipped in collision counting, because canvas ignores their `"lnum","case"` features (57).
- **`textChecks()`**:
  - per block, draws each line's glyphs at rest on an OffscreenCanvas;
  - for line pairs whose ink rectangles meet, counts the pixels where both alphas are at least 128;
  - returns the collisions and the ink bboxes.
- **`glyphProbe()`** builds a `visibility: hidden` `#gc` div with one span per unique (family, weight, italic, char). It is called only from the measure session, never while frames are rendered.
- **`seek(t, layer)`** (348-368):
  - the window becomes `t0 = blk.t0 ?? screen.t0` and `t1 = blk.t1 ?? min(screen.t1, until)`;
  - `layer === 'back'` hides `behind === false` blocks;
  - `'front'` shows only those blocks and hides `#doodles`;
  - with no layer, it behaves exactly as today.

#### `pipeline/overlay_render.py`

- **`worker`** (17-28) parses `front_frames` from the timeline text it already reads.
  - For those frames, `seek(t,'back')` goes to `NNNNN.png` and `seek(t,'front')` goes to `front/NNNNN.png`.
  - All other frames use `seek(t)` as today.
- **`render`** (31-43) clears `out_dir/front` first. The CLI path never clears its output folder.

#### `pipeline/video_pass.py`

- **`segment`** (222-227) already loads the timeline for `occlude_frames`; it also reads `front_frames`.
- **`render_frame`** (201-219), after the masked composite at 216-217, composites `front/NNNNN.png` for frames in that set only.
  - It uses the same `ovm` warp (211-213) and no person matte.
  - The trigger is never the file's existence, so stale PNGs are harmless.

#### `pipeline/build.py`

- New flag `--allow-text-fail`. The name is not `--draft`, because CONTEXT.md:47 defines "Draft MP4" as the deliverable.
- `text_checks.gate(a.allow_text_fail, a.script)` runs right after the timeline step (44-45), before the overlay render (48-50).
- Audio (61) becomes `sfx_cues({"sfx": au.get("sfx", []) + load_json(BUILD / "timeline.json").get("sfx", [])})`. 2373 has no `audio.sfx`.

#### `pipeline/export_fcpxml.py`

- `gate(False, a.script)` runs at the start of `main` (255).
- In the per-block jobs (476-483):
  - `f0`/`f1` come from `b.get("t0", sc["t0"])` and `b.get("t1", sc["t1"])`;
  - occlusion is `set() if b.get("behind") is False else occl` (473/482).
- Audio cues (531) use the same merged `sfx_cues` call.
- The stroke and censorship are baked into each block's alpha clip, because Chrome draws them.

#### `pipeline/lint_edit.py`

A new `lint_text(script, fail, warn)` is called at the end of `lint` (40-177). It uses `text_rules.heard_words`, `takes_out` (27-30) and `build_timeline.build_screens`; no Chrome is involved.

| Check | Level |
|---|---|
| For each `cta_triggers` hit (unless `cta_check: false`): the trigger word's token must be inside a preset-cta block whose first spoken word is at most 1.0 s before the trigger. For a literal-only CTA block, t0 must be within ±0.2 s of the trigger. | FAIL |
| CTA visible less than 2.0 s, i.e. cut by the reel end. Fix: extend the last EDL segment or add an end `{"hold", "dur"}`. | FAIL |
| CTA longer than 5 words (playbook.md:537) | WARN |
| A CTA (later: insert) window intersecting a hook window | FAIL |
| Hook visible time outside 2.0–3.0 s, or not starting at 0 | WARN |
| Hook longer than 7 words (playbook.md:530) | WARN |
| `not_found` for a token with `{heard}`, a term word, or a token in a preset block | FAIL |
| Empty display or empty `{}` | FAIL |
| Any other `not_found` | WARN |
| A typed heard form of a term (e.g. «рілс» where `reels` is the display) | WARN |
| A literal line showing a censor word uncensored | WARN |

#### Other files

- **`pipeline/review_frames.py`** (32-36): use the block window, and add a frame at `t0 + 0.3` for each preset block.
- **`pipeline/compare_render.py`** (74): use the block window.
- **`pipeline/times.py`** (30-33): print `CTA spoken: «напишіть…» [31.25]` and the term rewrites (`U -Case → yocase [7.73]`).
- **Docs** (English, with the Ukrainian brief keywords):
  - `.claude/skills/reel-subtitles/SKILL.md` §2: the grammar, the presets, the ЦЕНЗУРА / ХУК / КОДОВЕ СЛОВО rows and the «Текст» report template;
  - the same file, §3-4: the text gate, `--allow-text-fail`, and how to fix each FAIL (split lines, extend the end);
  - the talking-head `FORMAT.md` (other area) points at the presets.

### Interactions

**Person matte.**
- Today occlusion is per screen (build_timeline.py:357-358, video_pass.py:216-217). A `behind: false` block in a screen that also has behind blocks gets a person-shaped hole: the template hook and yocase_line's `*поїхали*` do today.
- The front layer makes `behind: false` exact in the MP4, and per-block occlusion makes it exact in each FCPXML layer.
- It costs one extra screenshot per front frame: 75 for a hook, plus the CTA frames that overlap a behind screen.
- 2371, 2373 and 2477 have no mixed screens, so their `front_frames` stays empty.
- Inserts (other area) reuse this layer.

**Safe zone and layout solver.**
- A preset's `place.safe` is intersected with the global safe box, as today (199-202).
- Face-avoid lets big centred text sit over her hair or torso, but not her face.
- The global `placed` list keeps subtitles off a CTA that outlives its screen.
- OUTSIDE, the rail and TOO BIG are FAILs on the layout bbox; ink overshoot is a WARN.
- A centred block wider than 620 px cannot stay centred below y 1050, because of the rail.

**Subtitle timing.**
- Term canonicalisation pins brand words to their real onset: yocase at 7.73 s instead of a fuzzy 7.86 s in 2373.
- Censorship and case never touch `tok.word`.
- CTA and hook windows come from the transcript, so EDL and pause-cutting changes (other area) move the card, its chime and the hook together.

**FCPXML export.**
- Text clips get their lanes from `lanes_for`, so a CTA that overlaps the next block lands on its own lane.
- The chime is one more SFX clip. Nothing new is dropped by Resolve.

**`lint_edit`.**
- Existing checks are untouched.
- These reels start failing lint until their CTA blocks get `preset: "cta"` or `cta_check: false`:
  - 2477 («напишіть» 31.25);
  - 2371 («посилання» 47.29);
  - yocase_line («пиши» 26.60 + «дірект» 27.30).
- The auto chime is not in `audio.sfx`; the whoosh and cartoon rules do not concern it.

**Audio mix.**
- One chime at −18 dB is added through the existing peak alignment (build.py:22-23).
- Loudness (audio.py:129-143) and ducking (other area) are unaffected.
- `presets.cta.sfx: null` turns the chime off.

**Shared build state.**
- `text_checks.json` and `overlay/front/` share the single slot with `timeline.json`.
- `text_checks.json` is deleted at the start of each timeline build and always rewritten, so a crashed run or another reel cannot leave a passing file behind.
- `gate` compares resolved script paths.
- video_pass reads front PNGs only for the frames listed in `front_frames`.

**Memory (8 GB).**
- Nothing new loads `masks.npy`; face avoidance uses `track.json`.
- The Chrome checks run in the existing measure session.
- `overlay_render` keeps 4 processes.

**Brand/format design.** This layer consumes the resolver's merged `terms`, `censor`, `cta_phrases`, `cta_check` and `presets`. The brand area drops its own glossary rewrite (`apply_glossary`). Any style deep-merge stays in that area.

### Verification

**Design-time checks already run** (read-only; scratch in `/private/tmp/claude-501/design/`):

- **`proto_text.py`.** The new tokenizer matches the current one on all 224 existing lines.
  - The old code splits «гр*ші і підп*ска» into `['гр','ші','і','підп','ска']`.
  - The censor rules give гроші→гр*ші, грошей→гр*шей and підписку→підп*ску; груші is not matched.
- **`proto_spell.py`.** With terms, 2373's yocase aligns at 7.73 s with 6 of 6 characters matched; without terms, at 7.86 s with 4 of 6. yocase_line's spelling variants canonicalise to `repairplex` and `fixcolor`.
- **`review_text/win_line.py` and `review_text/scan.py`:**
  - no block windows overlap across screens in 2371, 2373, 2477 or yocase_line;
  - no transcript or script contains a universal term or a money word;
  - the only heard CTA triggers are 2371 at 47.29, 2477 at 31.25 and yocase_line at 26.60/27.30.
- **`probe.py` and `probe2.py`** (Chrome via Playwright):
  - CDP flags `∗` (Apple Symbols) and CJK as non-custom fonts; 132 spans take 0.16 s;
  - `feMorphology` draws a clean 3 px outline;
  - canvas ink boxes work with the variable weights.
- **2373 facts the plan relies on:**
  - the matte is empty for frames 0–90; the first person pixels are at frame 120;
  - `track.json` has no face before 3.1 s;
  - between 21.5 and 25 s the matte covers 27–49 % of the y 270–700 band.

**V0 – golden snapshot before coding, identity after** (on the dev Mac).

```
G=/private/tmp/claude-501/golden; mkdir -p $G
for P in yocase_2371 yocase_2477 yocase_line yocase_2373; do
  .venv/bin/python pipeline/build_timeline.py projects/$P/script.json > $G/$P.log
  mkdir -p $G/$P && cp build/timeline.json build/camera.json build/meta.json $G/$P/; done
.venv/bin/python pipeline/overlay_render.py --frames 865 --only 0,60,231,400,640,860 --out $G/yocase_2373/png
```

Repeat into `/private/tmp/claude-501/after/` and `cmp`. Expected:
- **2371, 2477 and 2373:** `timeline.json`, `camera.json` and `meta.json` are identical, and the 6 PNGs are identical.
- **yocase_line:** `camera.json` and `meta.json` are identical. `timeline.json` differs only by the added `front_frames` (screen 2's `*поїхали*`); compare after deleting that key.
- **`text_checks.json`:** `fail: []` for all four.
- **Ink collisions:** yocase_line exercises the check on the tight default leading 0.62. Any hit there sets the default `ink_overlap_px` before shipping.
- **Logs:** the layout-report lines are identical; new check lines may be added.

**V1 – pure-Python logic.** Rerun `proto_text.py` and `proto_spell.py` against the real `text_rules`, plus:
- typed «рілс» and inline `yocase{юкейс}` still align after T is canonicalised, with the display unchanged;
- `cta_triggers` on the heard words gives:
  - 2477: «напишіть» at 31.25;
  - 2371: «посилання» at 47.29, and «обирайте» at 44.76 only with the YOCASE regex;
  - yocase_line: one merged CTA at 26.60;
  - 2373: none;
- «директор» does not trigger.

**V2 – lint, no render.**
- `lint_edit.py projects/yocase_2477/script.json` gives `FAIL 31.25s spoken CTA «напишіть» has no CTA block`. 2371 and yocase_line FAIL the same way.
- On a scratch copy of 2477 where the «напишіть нам / яке у вас волосся» block has `"preset": "cta"`, the text FAILs are gone and lint prints `CTA 31.25–33.25`.

**V3 – integration draft on 2373** (28.8 s, about 2 min). Make `/private/tmp/claude-501/design/yocase_2373_text.json` from `projects/yocase_2373/script.json` with these edits:

- **Top level:** `"terms": {"yocase": {"heard_as": ["u-case"]}}`, `"censor": ["салонний", "догляд"]` and `"cta_phrases": ["^отримуєш$"]`.
- **`screens[0]`:** insert as `blocks[0]` the hook `{"preset": "hook", "lines": [{"text": "салонний догляд", "literal": true, "t": 0}, {"text": "_вдома_", "literal": true, "t": 0}]}`. The existing block loses its `place` and gets `"behind": true`.
- **`screens[5]`:** the line becomes spoken: `{"text": "*yocase repair plex*", "anim": "pop", "scale": 1.2, "color": "#C4207F"}`.
- **`screens[14]`** («і отримуєш / волосся»): add `"preset": "cta"` and remove `place`.
- **`screens[15]`** («яке виглядає / _здоровим_ доглянутим»): remove `place` and set `"behind": true`. Append a front-layer test block. Its `free_until` (an existing key, build_timeline.py:332) empties its occupancy, so it deliberately lands on her:

  ```json
  {"lines": [{"text": "*тест поверх*", "literal": true, "t": 23.3, "scale": 1.5}], "behind": false, "dur": 1.4,
   "align": "center", "place": {"x": "center", "y": 420, "safe": [128, 270, 952, 700], "free_until": 23.0}}
  ```

```
.venv/bin/python pipeline/lint_edit.py /private/tmp/claude-501/design/yocase_2373_text.json
X264_PRESET=veryfast .venv/bin/python pipeline/build.py /private/tmp/claude-501/design/yocase_2373_text.json --name yocase_2373_text
ls build/overlay/front | wc -l
.venv/bin/python pipeline/review_frames.py output/yocase_2373_text.mp4
.venv/bin/python pipeline/contact_sheet.py output/yocase_2373_text.mp4 0 3 0.1
.venv/bin/python pipeline/contact_sheet.py output/yocase_2373_text.mp4 21 24.8 0.1
.venv/bin/python -c "import numpy as np,cv2; m=np.load('build/yocase_2373/masks.npy',mmap_mode='r'); a=cv2.imread('build/overlay/front/00720.png',-1)[:,:,3]; print(int(((cv2.resize(m[720],(1080,1920))>127)&(a>128)).sum()))"
ffmpeg -i output/yocase_2373_text.mp4 -vf crop=886:1920:97:0 -an /private/tmp/claude-501/design/phone.mp4
```

Expected:
- **Lint:** 0 text FAILs. One WARN: the hook literal shows «салонний догляд» uncensored.
- **Timeline log:** no NOT FOUND, and «U -Case Repair Plex» is no longer listed as "not shown".
- **`text_checks.json`:**
  - `fail: []`;
  - `applied.censored` = с*лонний ×1 and д*гляд ×2 («_с*лонний_ д*гляд», «*д*гляд*»);
  - `latin: {"yocase": 1}`;
  - `hook: {t0: 0, t1: 2.5}`, at x ≈ 540 − w/2 with its top in y 270–700;
  - `cta: [{t0: 21.18, t1: 23.18, trigger: 21.48}]`.
- **Chime:** `timeline.json` `sfx[0]` peaks at 21.18.
- **Front layer:** about 135 front PNGs:
  - frames 0–74 (the hook);
  - about 678–695 (the CTA tail over the behind screen);
  - about 699–740 (the test block).
- **Matte overlap:** the one-liner prints a number above 0, which proves the test block really covers her.
- **Sheet 0–3 s:** the hook pops at frame 0 and fades between 2.3 and 2.5 s. There is no person in these frames, so this sheet checks timing and centring only.
- **Sheet 21–24.8 s:**
  - the whole CTA card pops at 21.2 s, centred and under her face, with the chime audible;
  - it stays to 23.2 s;
  - from 23.3 to 24.7 s, «тест поверх» is drawn uncut across her hair and shoulders.
- **Phone crop:** all text is inside.

**V4 – negative tests.** Use copies of the V3 script and run only the timeline step and the gate.
- A literal `"∗ тест"` gives `FAIL glyph U+2217 … Apple Symbols`, and `build.py` exits 2 before `[overlay]`.
- A literal line whose layout-report width is 850–1050 px gives FAIL OUTSIDE.
- A line wider than 1080 px gives FAIL "TOO BIG, split the line"; today it crashes with a ValueError.
- `style.leading: 0.3` gives FAIL "letters collide".
- Splitting `screens[14]` so that the CTA block starts at «волосся» (22.02) gives the lint FAIL "trigger 21.48 not in a CTA block".
- After rebuilding the timeline for another project, `export_fcpxml.py` with the V3 script is refused (script mismatch).

**V5 – FCPXML.** Run right after V3:

```
.venv/bin/python pipeline/export_fcpxml.py /private/tmp/claude-501/design/yocase_2373_text.json --name yocase_2373_text
```

Expected:
- `layers.json` has `b0` (the hook) as `[0, 75]`, the test block as about `[699, 42]` and the CTA as about `[636, 60]`.
- The test block's clip alpha at output frame 720 shows no matte hole. Extract it with `ffmpeg … select=eq(n\,21),alphaextract`; ANDed with the matte as in V3, it is above 0.
- `grep -c '<asset-clip[^>]*name="ding_02_soft_chime"' output/yocase_2373_text_project/*.fcpxml` gives 1. A plain grep for the name also hits the asset and media-rep lines.
- With a V4 FAIL in `text_checks.json`, the export exits 2.

### Risks

- **Term over-matching.** A short heard variant could capture an ordinary word.
  - Variants need 4 or more letters (or several words) and match whole words unless they end in `*`.
  - times.py prints every rewrite, and the report lists them.
  - The display is never rewritten automatically.
- **Censor stems** can hit related words (гроші → грошовий). Every censored word is listed in the report, and the per-reel `censor` can be edited.
- **Ink-collision FAIL on tight leading.** TOSUMI's leading of 0.62 interleaves descenders by design, and tosumi_hair cannot be rebuilt. yocase_line in V0 uses the same leading; tune `ink_overlap_px` per brand from it.
- **OUTSIDE and TOO BIG as FAILs** block final renders of stale scripts, such as yocase_line's x 56–60 hints. This is intended; `--allow-text-fail` still renders for inspection.
- **The hook zone vs medium shots.**
  - With the eye line at y 630–770 (playbook.md:589), the face box starts at about y 470–520. A hook then has about 200–250 px, which is 2–3 lines of 87 px, so Claude splits or shortens it.
  - The face tracks of pre-edited videos are noisy: 2373's face x jumps from 49 to 1024. The median damps this, but false face FAILs are still possible.
- **A wide CTA** (over 620 px) is shifted left of centre below y 1050 by the rail. Measured: a 700 px block targeted at x 190 lands at x 148. Keep CTA lines short; `applied.cta` reports the x offset.
- **`feMorphology`** gives square-ish corners above 4 px, so `stroke.px` is capped at 4.
- **`CSS.getPlatformFontsForNode`** is a DevTools-protocol method, and Chrome is unpinned on Marina's Mac. If it fails, the check degrades to a WARN.
- **Dependency on the brand/format design.** The resolved `terms` and `presets` come from it, so both areas must use the key names in this section.

### Effort

| Piece | Effort |
|---|---|
| Line grammar (escapes, `display{heard}`) | S |
| `text_rules.py` (rules, two-sided canonicalisation, censor, CTA triggers, heard words) | S |
| Presets, block windows (`dur`/`hold`/`tail`), `reveal`, `case`, centre alignment, `place.x` center | M |
| `solve_block` TOO BIG guard | S |
| SVG stroke filter | S |
| Front layer (overlay `seek(layer)`, `overlay_render`, `video_pass`, export per-block occlusion) | M |
| Face-avoid occupancy and the face check | S |
| CTA auto chime (timeline `sfx`, build, export) | S |
| `lint_text` | S–M |
| Glyph check (CDP) | S |
| Ink-collision check | S–M |
| Geometry FAILs, the `text_checks.json` lifecycle, `gate`, `--allow-text-fail` | S |
| `review_frames`, `compare_render`, `times.py`, SKILL.md, report template | S |

**Total:** about M+, roughly 2–3 dev days including V0–V5.

### Open questions for the developer

1. **Censorship in brand reels.** It is off by default; only ЦЕНЗУРА: or a brand list turns it on. Should TOSUMI or YOCASE have a standing list? Brand ads may legitimately say «безкоштовна доставка» or «знижка».
2. **YOCASE spelling.**
   - Is the canonical display `yocase` or `YOCASE`?
   - Are product names shown in Latin (`repair plex`, `fix color`) or in Cyrillic?
   - Does the brand name get a fixed colour? 2371 styles it three ways today.
3. **Hook and CTA look per brand.** TOSUMI is small lowercase text with a text-shadow; the skill uses caps with a 3 px stroke at about 90 px. Which `case`, `stroke` and `scale` should each brand use?
4. **CTA trigger scope.**
   - Should any spoken call to action (посилання, дірект, напишіть нам) require a card and chime, or only «напиши СЛОВО» as in the third-party skill?
   - Should pre-edited, subtitles-only reels like 2371 and 2477 default to `cta_check: false` with no chime?
