## Brands and formats as data (roadmap step 3, ADR-0002)

### Goal

Marina writes a brief like «YOCASE, говорюча голова». From that, the pipeline applies the brand's look and the format's rules, and no style is copied into `script.json`:
- **Brand (look):** fonts, colours, spacing, grade, music bed (file, gain and offset), SFX palette and bans, spelling and colours of brand and product names, and censor words.
- **Format (structure):** hook and CTA timing, pause-trim thresholds, preset structure, music on or off, and the lint profile.

None of this is data today:
- The style merge is one level deep (`pipeline/build_timeline.py:272-274`). Every YOCASE script therefore repeats the accent and spacing block (`projects/yocase_2373/script.json:21-37`), and 2371 and 2477 repeat the phone rail (`yocase_2371/script.json:33-43`, `yocase_2477:33-43`).
- Fonts are hard-coded in `pipeline/overlay.html:6-8` and `:121`, and the serif features at `:57`.
- Lint's bans and thresholds are global constants: `pipeline/lint_edit.py:19-24`, `:97` and `:162`.
- The only template, `projects/_template/script.json`, is a TOSUMI skit, and it trips lint.

The design adds one resolver module, one small font-check module and some data files. Scripts without a `brand` key (all existing projects) resolve to exactly what they resolve to today.

### Creator-facing behaviour

**What Marina writes** (Ukrainian, in any word form, order or case):

| She writes | Claude puts in `script.json` |
|---|---|
| A brand name in any form: `YOCASE`, «для йокейсу», `ю-кейс`, `тосумі` | `"brand": "yocase"` / `"tosumi"`. Claude picks the id from `resolve.py --list` (ids plus alias hints). Mapping is Claude's job because Ukrainian inflects («говорючу голову»), so no substring matcher is used. The resolver then validates the id. |
| «говорюча голова», «експерт» | `"format": "talking-head"` |
| «лише субтитри», «вже змонтоване», «готове відео» | `"format": "subtitles-only"` |
| «скетч», «хоче … а …» | `"format": "skit-hoche-a"` |
| «лінійка» | `"format": "product-lineup"` |
| `ХУК: <фраза>` | a block with `"preset": "hook"` and a line with `"preset": "hook_line"`; the text is kept verbatim |
| `МУЗИКА: <назва>` / «без музики» | `audio.music.file` (plus `offset` when known) / `"audio": {"music": null}` |
| `ЦЕНЗУРА: слово, слово` | `"censor+": [...]` |
| «без правок стилю» | no `style` keys in the script except `style.layout.exclude+` for baked-in graphics |
| `Запам'ятай для YOCASE: …` / `… для говорючої голови: …` | a dated rule in `brands/yocase/BRAND.local.md` / `formats/talking-head/FORMAT.local.md`. If the rule is mechanical, also the matching `*.local.json`. All of these are gitignored. |
| `Новий бренд: …` | a local-only brand (`brands/<id>/brand.local.json` + `BRAND.local.md`), pending open question 6 |

`КОДОВЕ СЛОВО:`, «коли кажу X — покажи Y» and «на весь екран» belong to the CTA and insert designs. They plug into `presets.cta`, `sfx_palette.insert_*` and `grammar.cta_min_s`, defined below.

**If brand or format is missing** (ADR-0002:20-21), Claude asks only this: «Для якого бренду цей ролик — TOSUMI чи YOCASE? І це говорюча голова чи лише субтитри до вже змонтованого відео?». Everything else is decided and reported.

**What she gets:**
- The reel in the brand's look. YOCASE: purple accents, normal spacing, at most 3 lines per block, and product names in their product colour.
- Brand and product names timed correctly even when whisper heard «U -Case» or «Репейрплекс».
- The format's structure: hook 1-3 s; CTA for at least 2 s; pause trimming once the pause-cut design lands.
- The brand music bed from frame 0 with short fades, unless she says «без музики». Ducking arrives with the ducking design and is not promised before then.
- A report line built from the resolver summary and the build log, for example: «Бренд: YOCASE · Формат: говорюча голова · Музика: Gimme that Groove · Назви: "U -Case" → yocase».
- Her corrections take effect from the next reel. They win over the tracked brand and format files, and they never block `git pull`.

### Schema

#### Resolution order and merge rules (`pipeline/resolve.py: load_script`)

Layers, from lowest to highest priority:
1. **studio:** `pipeline/style_default.json` (as `style`) and the new `pipeline/studio_default.json`
2. `brands/<brand>/brand.json`
3. `formats/<format>/format.json`
4. `brands/<brand>/brand.local.json` (gitignored)
5. `formats/<format>/format.local.json` (gitignored)
6. `script.json`

Local corrections come after every tracked layer, so Marina's correction is never silently shadowed by tracked data. There is no `brand.formats` layer; brand-specific behaviour is expressed through the brand's own keys, such as `lint.slow_push`.

Rules:
- **Merging:**
  - A dict deep-merges into a dict.
  - A list, scalar or `null` replaces the lower value.
  - `"<key>+": [...]` appends to the inherited list without duplicates, at any depth (e.g. `style.layout.exclude+`). It is an error if either side is not a list.
- **Off switches are sticky.** If a format layer sets `grade: null` or `audio.music: null`, a brand-scope layer (including `brand.local.json`) cannot turn it back on. Only the script can.
- **Music track keys:**
  - If a layer sets `audio.music.file`, lower-layer `offset` and `dropouts` are dropped, because they belong to a specific track.
  - If the resolved `audio.music` has no `file`, the resolver sets it to `None`, which means music is off. `build.py:56-58` and `export_fcpxml.py:539-541` then never see a dict without `file`.
- **Ownership (enforced; an error names the key and the file):**
  - A format layer may set only:
    - `name` and `aliases`
    - `camera`
    - `grade`, only as `null`
    - `audio.music`, only as `null` or with `fade_in` / `fade_out` (the ducking design adds `duck` to this list)
    - `presets`, with structure keys only: `literal`, `t`, `until`, `fade`, `behind`, `place`. `free_until` is a `place` key (`build_timeline.py:332`).
    - `lint`
    - `grammar`
  - Formats never set `style`, `colors`, `terms`, a non-null grade, or the music `file`, `gain_db` or `offset`. Gain is a property of the track.
  - Brands own the look. An unknown top-level key in a brand file is a warning (typo guard).
- **Presets:**
  - `"preset": "name"` (or a list of names) on a block or line merges `presets[name]` under the item. The item's own keys win, and the `preset` key is removed.
  - An unknown preset is an error that lists the known ones.
- **Colour references:**
  - A value starting with `@` under a key named `color` is looked up in `colors`; an unknown name is an error.
  - Subtitle text is never touched.
- **SFX events:**
  - An `audio.sfx` cue with `"event"` and no `"name"` expands from `sfx_palette[event]`, and needs `peak_at`.
  - Variants rotate by occurrence. A variant is one cue `{name, gain_db, dt?}` or a list of cues (a stack).
  - A cue-level `gain_db` replaces the gain of a single-cue variant. On a stack it is an error, because it would flatten the stack's layered gains.
- **Safe area:**
  - If `style.layout.safe` is wider than the studio's `[128,250,952,1480]`, that is an error in a brand or format layer and a warning in a script.
  - If the resolved `style.layout.exclude` lacks the rail `[850,1050,1080,1920]`, the resolver warns "use exclude+".
- **Errors:** an unknown brand or format lists the known ids, so the template placeholders `BRAND` and `NAME` fail fast.
- **Summary:** lists the layers applied, plus every local file and the keys it set.

#### `script.json`: new keys

| Key | Type | Default | Meaning |
|---|---|---|---|
| `brand` | id (folder under `brands/`) | absent: studio defaults (today's TOSUMI look), plus a warning | brand layer |
| `format` | id (folder under `formats/`) | absent: no format layer | format layer |
| `blocks[].preset`, `lines[].preset` | string or list | — | named preset |
| any `"color": "@name"` | string | — | brand colour reference |
| `audio.sfx[].event` | string | — | palette event instead of `name` |
| `terms`, `censor(+)`, `sfx_palette`, `sfx_banned(+)`, `lint`, `grammar` | as below | — | per-reel overrides |

Everything else stays as today: `style`, `grade`, `camera`, `audio`, `screens`, `edl`, `doodles`.

#### `brands/<brand>/` (folder)

| File | Tracked? | Content |
|---|---|---|
| `brand.json` | yes | machine-readable look and rules |
| `BRAND.md` | yes | prose rules, tone, prohibitions, dated learned rules. **No numbers**: numbers live only in JSON (the STYLE.md:11-14 drift). No brand-book or NDA material, because the repo is public. |
| `brand.local.json`, `BRAND.local.md` | gitignored | Marina's corrections |
| `fonts/` | yes | OFL / free fonts only, with their licence file |
| `local/` | gitignored | licensed brand fonts, logos, product photos. The developer installs them in person. |

`brand.json` keys (all optional):

| Key | Shape | Default if absent | Consumer |
|---|---|---|---|
| `name` | string | folder id | reports |
| `aliases` | [string] | [] | `resolve.py --list` (hints for Claude) |
| `style` | deep-merged over style_default.json, including `style.fonts` and `style.layout.max_lines` | studio | build_timeline, overlay |
| `colors` | {name: "#hex"} | {} | `@name` references |
| `terms` | {canonical lowercase text: {`heard_as`: [phrase…], `color`?: "@x"}} | {} | `apply_terms` and term colouring in build_timeline; times.py |
| `censor` | [word] | [] | censorship design |
| `grade` | Grade params (`video_pass.py:46-75`) or null | no grade | build.py |
| `audio.music` | {file, gain_db, offset?, fade_in?, fade_out?} | no music | build.py, export_fcpxml, lint beat check |
| `sfx_palette` | {event: [variant]} | studio palette | resolver |
| `sfx_banned` | [glob] | [] | lint; added to the profile's ban list, so a brand ban always applies |
| `lint` | {vignette_max?, punch_min?, slow_push?} | studio | lint_edit |
| `presets` | {name: block or line look keys} | studio | resolver |

`style.fonts` is a new key, also added to style_default.json:
- **Shape:** `{alias: face | [face…]}`. A face is `{"file": "<repo-relative or absolute path>", "weight": "100 900", "style": "normal|italic", "features": "<css font-feature-settings>"}`.
- **Aliases** stay `Main`, `Accent` and `Serif` (`overlay.html:41-53`). A brand swaps the files behind them, and a list gives several static faces under one alias.
- **Resolution:** the resolver turns each `file` into an absolute `url` (`Path.as_uri()`).
- **Checks** run only when `check_fonts=True` (build_timeline, build, export_fcpxml, `resolve.py --check`), never in lint, times or preview:
  - The file must exist; if not: "font file missing: <path> (licensed fonts are not in git; copy into brands/<b>/local/)".
  - The file must be TTF or OTF; a `.ttc` is refused with "convert to .ttf/.otf".
  - The glyph check below must pass.

#### `formats/<format>/` (folder)

Contents: `FORMAT.md`, `format.json` and `template.json` (all tracked), plus `format.local.json` / `FORMAT.local.md` (gitignored).

`format.json` keys (only the ones allowed above):

| Key | Meaning |
|---|---|
| `name`, `aliases` | as for brands |
| `camera` | structural defaults, only when they differ from the code defaults (`camera.py:71` push 1.0→1.0, `:144` motion_blur 0.5) |
| `grade: null` | off switch (e.g. subtitles-only) |
| `audio.music` | `null`, or `{fade_in, fade_out}` |
| `presets` | structure keys only |
| `lint` | profile overrides |
| `grammar` | machine-readable knobs that code consumes (below) |

`grammar` keys. There are **no studio defaults**: a key that is absent means the feature is off, i.e. today's behaviour.

| Key | Talking-head value | Read by |
|---|---|---|
| `hook_s` | [1.0, 3.0] | hook / brief design |
| `cta_min_s` | 2.0 | CTA design |
| `trim` | {min_pause 0.45, pad_before 0.13, pad_after 0.10, keep_after_claim 0.40} (PB:220-224: >0.4-0.5 s, 3-5 f, 2-4 f, 8-15 f) | pause-cut design |
| `speed` | absent (= 1.0) | speed option, if built; never above 1.0 by default |
| `insert` | owned by the insert design | — |

Zoom levels are prose in FORMAT.md. Where code must enforce a level, it lives in the lint profile.

**Lint profile** (`lint` key). The studio defaults equal today's behaviour:

| Key | Studio default | Today's source |
|---|---|---|
| `sfx_banned` | ["record_scratch_*", "cartoon_*", "boing_*", "tada_brass", "cha_ching_*"] | `lint_edit.py:23` |
| `whoosh_on_cuts` | false | `:145-149` |
| `punch_min` | 1.10 | `:97` |
| `slow_push` | true (a sub-`punch_min` push held ≥ 1.5 s passes) | `:97` |
| `dead_span` | 4.0 (null = off) | `:21`, `:156-160` |
| `vignette_max` | 0.05 | `:162` |
| `beat_cuts` | true (warn when cuts miss the music beat) | `:165-176` |

#### `pipeline/studio_default.json` (new)

This file holds studio-wide non-style defaults, all inert for existing scripts. `style_default.json` changes only by adding `fonts`.
- `terms`: Latin platform words with their usual mis-hearings: reels ← рілс / рілси / рілз; tiktok ← тікток / тік ток; instagram ← інстаграм; claude ← клод.
- `censor: []`.
- `sfx_palette`: the PB 2.19 events (whip, zoom_rush, zoom_land, name_pop, tick, hero, cta, insert_pop, insert_swish), with today's VS:66-69 gains.
- `sfx_banned: []`.
- `lint`: the profile above.
- `presets` (look defaults): hook_line {anim pop, scale 1.3}, brand_name {anim pop, scale 1.2}, product_label {anim pop, scale 1.3}, interjection_line {anim pop, scale 3}, punchline_line {scale 1.55}.
- No `grammar`.

`style_default.json` gains only `fonts`: the three faces from `overlay.html:6-8`, with `Serif.features` = `"lnum" 1, "case" 1` (`overlay.html:57`).

#### Drafts

**`brands/tosumi/brand.json`**

The TOSUMI look *is* `style_default.json`, which is what keeps every old script identical. It is not copied here: a partial copy (the old draft left out shadow, anim and `accent_gap`, whose default is 0.16 at `overlay.html:151`) would recreate the STYLE.md/JSON drift. BRAND.md says: "TOSUMI's look = pipeline/style_default.json. Before changing that file, move its current values into this brand.json." Gummies is the track used by tosumi_hair and the old template.

```json
{"name": "TOSUMI", "aliases": ["tosumi", "тосумі", "тосуми"],
 "colors": {"accent": "#FF3D96"},
 "terms": {"tosumi": {"heard_as": ["тосумі", "тосуми"]}},
 "grade": {"lift": 0.01, "contrast": 1.04, "saturation": 1.04, "vignette": 0.10},
 "audio": {"music": {"file": "music_01_gummies_120bpm_full.wav", "gain_db": -17, "offset": 16.34}},
 "sfx_palette": {"accent_pop": [{"name": "pop_04_light", "gain_db": -23}],
  "salon": [{"name": "ding_02_soft_chime", "gain_db": -20}],
  "hero": [[{"name": "camera_shutter_01", "gain_db": -8}, {"name": "sparkle_hit_fairy", "gain_db": -11, "dt": 0.06},
            {"name": "shimmer_sparkle_whoosh", "gain_db": -17, "dt": 0.25}]],
  "end": [{"name": "whoosh_quick_03_swish", "gain_db": -15}]},
 "lint": {"vignette_max": 0.10},
 "presets": {"hook_line": {"anim": "type", "scale": 1.25}, "punchline": {"leading": 0.86}}}
```

`brands/tosumi/BRAND.md`:
- **Rules:**
  - Lowercase, no punctuation; small text; white main text.
  - Pink only on the fail/punch word, one per half-sentence; dream words in white serif.
  - Only two big things: the interjection and the final punchline.
  - Voice as recorded; static music bed, no sidechain.
- **Source:** STYLE.md:1-6, 16-21, 52-54.
- **Punchline leading:** 0.86 comes from SS:53. tosumi_hair itself used 0.64 (`:220`); that is noted, not migrated.
- **Not here:** the skit-only exceptions (whoosh on cuts, cartoon gags) live in the skit FORMAT.md.

**`brands/yocase/brand.json`**
- Spacing and colours: the 2026-10-13 rule (SS:99-102).
- Product colours: `projects/yocase_line/make_script.py:25`.
- `heard_as`: from `build/yocase_2371|2373|yocase_line/words.json` («U -Case» at 7.73 and 26.37, «Репейрплекс» 48.76, …).
- Grade and music: from yocase_line, including its downbeat entry offset 18.423 (PB:532). This is one reel of evidence, and BRAND.md says so.

```json
{"name": "YOCASE", "aliases": ["yocase", "йокейс", "йокейз", "ю-кейс", "юкейс", "йо кейс"],
 "style": {"accent": {"color": "@accent", "outline": "0 0 1px rgba(40,0,45,.85), 0 0 1px rgba(40,0,45,.85)", "tracking": 0.0},
  "label": {"color": "@accent"}, "main": {"tracking": -0.005},
  "leading": 1.05, "word_space": 0.03, "accent_gap": 0.06, "accent_gap_after": 0.04, "layout": {"max_lines": 3}},
 "colors": {"accent": "#8A2E92", "energy": "#22A866", "repair_plex": "#C4207F", "balance": "#4A5BD8", "fix_color": "#0FA0DC"},
 "terms": {"yocase": {"heard_as": ["u case", "ю кейс", "юкейс", "йокейс", "йо кейс"]},
  "repair plex": {"heard_as": ["репейрплекс", "реперплекс", "repairplex", "репейр плекс"], "color": "@repair_plex"},
  "energy": {"heard_as": ["енерджі"], "color": "@energy"},
  "balance": {"heard_as": ["баланс"], "color": "@balance"},
  "fix color": {"heard_as": ["фікс колор", "фіксколор", "fixcolor", "pixcolor"], "color": "@fix_color"}},
 "grade": {"lift": 0.01, "contrast": 1.04, "saturation": 1.04, "vignette": 0.04},
 "audio": {"music": {"file": "music_03_gimme_that_groove_112bpm_full.wav", "gain_db": -18, "offset": 18.423, "fade_out": 0.8}},
 "sfx_banned": ["record_scratch_*", "cartoon_*", "boing_*", "tada_brass", "cha_ching_*"],
 "lint": {"slow_push": false},
 "presets": {"brand_name": {"anim": "pop", "scale": 1.2}}}
```

`lint.slow_push: false` enforces the 2026-10-10 rule "moves under 10% read as nothing" (VS:85-87) for every YOCASE format.

`brands/yocase/BRAND.md`:
- Comfortable spacing; 2-3 lines per block; split long screens.
- Brand and product names are spoken lines in Latin lowercase, never literal lines with hand-set times. The glossary times them, and product names in accent take their product colour.
- One way of styling the brand name, replacing the three ways in 2371 (`:309-324`, `:429-434`, `:456-459`).
- Check which bottle is in her hand (product-lineup FORMAT.md:33-34).
- No cartoon SFX; no moves under 10%; no filler made from between-take fragments (VS:88-91).
- Register is still open: «ти» in yocase_line and 2373, «ви» in 2371 and 2477.
- Learned rules dated 2026-10-10 and 2026-10-13.

#### Format files

**`formats/talking-head/`** (new; brand talking heads like yocase_2371 / 2477, but from raw footage)

`format.json`:

```json
{"name": "Talking head for a brand", "aliases": ["говорюча голова", "розмовне", "експерт", "експертне", "talking head"],
 "audio": {"music": {"fade_in": 0.1, "fade_out": 0.8}},
 "presets": {"hook": {"behind": false, "fade": 0.2, "until": 2.5, "place": {"y": 270}},
  "hook_line": {"literal": true, "t": 0.0}, "cta": {"behind": false, "fade": 0.25}},
 "lint": {"beat_cuts": false},
 "grammar": {"hook_s": [1.0, 3.0], "cta_min_s": 2.0,
  "trim": {"min_pause": 0.45, "pad_before": 0.13, "pad_after": 0.10, "keep_after_claim": 0.40}}}
```

`beat_cuts: false`: speech cuts follow words, not beats (PB:581). Without it, every talking head with a 112 bpm bed would get "cuts miss the beat" warnings that invite moving speech cuts.

`FORMAT.md`:
- **Structure:**
  - Hook 1-3 s from frame 0. Use her `ХУК` verbatim; otherwise write one of 7 words or fewer, at y 270-700, not over the face. Brand and main message within 5 s (PB:530-531).
  - Body: one screen per thought; one accent per half-sentence, on the word that carries the meaning.
  - Product moments: the name pops in its product colour. Use an insert or product shot only when the image proves what is being said.
  - CTA spoken and on screen for at least 2 s, synced to the phrase (±0.2 s, held to the end of the phrase).
  - End with no logo card; the last frame close to frame 0.
- **Pause trimming:** `grammar.trim`. Pauses over 0.45 s are cut, with pads of 4 f / 3 f, and 12 f are kept after a key claim. Never strip every breath (PB:220-239). The third-party 0.2 s and its "strip head and tail" are rejected.
- **Zooms by meaning** (prose; lint enforces the floors):

| Move | Rule | TOSUMI | YOCASE |
|---|---|---|---|
| A/B step on a same-setup jump cut | A 1.00 / B 1.12-1.18, a hard step at the cut, switching every 2nd-3rd cut (PB:226-227) | same | same |
| Fast punch on a stressed word (`in` ≤ 0.15 s) | ≥ 1.12, `anchor: true`, held to the end of the thought (PB:201-210) | 1.12 (open question 1) | ≥ 1.12 |
| Slow "meaning push" (the third-party levels) | 1.05-1.08, `{"in": 0.45, "ease": "inout", "anchor": true}`, held ≥ 1.5 s, only on uncut takes over 4 s | allowed (`slow_push` true; `lint_edit.py:97` passes it) | not allowed (`lint.slow_push: false` warns) |
| Back out to 1.00 | only at a cut (A framing), never an animated zoom-out (PB:43) | | |

  Aim for 3-6 changes per 30 s.
- **Music:**
  - On by default with the brand bed: its file, gain and offset come from brand.json, with 0.1 s / 0.8 s fades.
  - «без музики» turns it off, and the no-music export always exists (`build.py --no-music`, ADR-0003).
  - Keyframed ducking comes from the ducking design; until then the bed is static.
  - The third-party "mandatory music" is rejected.
- **Inserts** (the inserts design owns the mechanics): only when the image directly confirms the phrase; never over the face or the subtitles; inside x 128-952, y 250-1480.
- **Contributed by the third-party skill:** verbatim hook; code-word CTA; image inserts with pop-in and SFX; full-screen inserts; pause cutting (with studio thresholds); asterisk censorship plus Latin platform words; glyph and disk preflight; pre-export checklist; Ukrainian report; `done/` archive; keyframed ducking; "don't ask about trifles".
- **Rejected from it:** the x 60 safe zone, whisper medium/small, crf 18, the fixed bottom block, mandatory music, self-install, ×1.3 by default, and its lime/handwritten look.
- **Learned rules:**
  - 2026-10-13: spacing is brand data.
  - Brand names mis-heard by whisper are fixed by `terms`, not by literal lines (2371:309-324, 2373:153-160).
  - Prefer automatic layout (2477) over hand-placed blocks (2373).
  - Baked-in graphics go in `style.layout.exclude+` (screen-wide) or `place.exclude` (per block).
  - `behind: false` protects a block only when no other block of its screen is behind (see Interactions).

**`formats/subtitles-only/`** (new; the 2026-10-13 rule at SS:103-105)

`format.json`:

```json
{"name": "Subtitles only (already edited video)", "aliases": ["лише субтитри", "тільки субтитри", "вже змонтоване", "готове відео"],
 "grade": null, "audio": {"music": null}, "lint": {"dead_span": null}}
```

`FORMAT.md`:
- One `src` segment; no grade, music or SFX; the brand look still applies.
- Exclude baked-in logos and insets with `exclude+`.
- Never caption a line that is already on screen (e.g. a chat bubble).
- Worked examples: yocase_2477 (automatic layout) and yocase_2371 (brand name and CTA).

**`formats/skit-hoche-a/`** (new; content moved from STYLE.md:38-57 and SS:54-65)

`format.json`:

```json
{"name": "Skit: хоче X, а Y", "aliases": ["скетч", "хоче а", "хоче-а"],
 "camera": {"push": {"from": 1.0, "to": 1.04, "ease": "linear"}},
 "presets": {"hook": {"behind": false, "fade": 0.2, "until": 1.6, "place": {"y": 270}}, "hook_line": {"literal": true, "t": 0.0},
  "interjection": {"behind": false}, "punchline": {"behind": false, "fade": 0.25, "place": {"y": 300}}},
 "lint": {"sfx_banned": ["tada_brass", "cha_ching_*"], "whoosh_on_cuts": true}}
```

`FORMAT.md`:
- One screen per take: setup `№N / хоче … _мрія_` plus punch `// а … *(провал)*`.
- Interjection gag: freeze + record scratch + music dropout + ×3 pop.
- A 1.2 s product hold with flash, shutter stack and circle; a walk-out loop; no text in the last 0.6 s.
- Cartoon SFX and a whoosh on every take cut are **allowed only here** (lint profile above); brand bans still apply.
- Silent beats are the comedy, so there is no `trim`.
- Changes recorded against tosumi_hair: a linear creep replaces in-out + `cut_in`, because in-out stops at both cuts and `cut_in` pumps (lint_edit.py:103-109, PB:258-269).

**`formats/product-lineup/`** (exists):
- Add a `format.json` with only `name` and `aliases`. Its camera values equal the code defaults, so they are not repeated.
- Align FORMAT.md:27 (hero freeze) and :28 (budget) with PB:314 / PB:543.
- Note that `make_script.py`'s placement hints predate the 2026-10-13 safe area (projects report §4): x 60, safe x 56, y 110 and similar. Fix them before it is shown as the worked example.

#### Templates (they replace `projects/_template/script.json`)

The templates contain no style, no grade and no placeholder effects; recipes live in FORMAT.md. Every effect list starts empty, because effects with `t: 0` placeholders fire at frame 0 if left unfilled (`_template:134-173`, `:202-208`, `:230-256`).

`formats/talking-head/template.json`:

```json
{"brand": "BRAND", "format": "talking-head",
 "source": "build/NAME/source.ffconcat", "words": "build/NAME/words.json", "masks": "build/NAME/masks.npy", "track": "build/NAME/track.json",
 "src_duration": 0.0, "takes": [[0.0, 0.0]], "edl": [{"src": [0.0, 0.0]}],
 "screens": [{"take": 1, "blocks": [
   {"preset": "hook", "lines": [{"preset": "hook_line", "text": "хук дослівно з брифу"}]},
   {"lines": ["перша думка", "з *акцентом* по змісту"]}]},
  {"take": 1, "blocks": [{"preset": "cta", "lines": ["заклик", "*словами спікера*"]}]}],
 "doodles": [], "camera": {"punches": []}, "audio": {"sfx": []}}
```

The other templates:
- **subtitles-only:** no presets (the video already has its own hook), `"style": {"layout": {"exclude+": []}}`, and no camera or audio.
- **skit-hoche-a:** the old skeleton (hook via presets, №1 setup/punch blocks, a 1.2 s hold in the edl). It drops:
  - `cut_in` (`_template:186-190`)
  - the whole-take in-out push (`:176-179`)
  - the unanchored 1.06 punch (`:193-199`)
  - the vignette 0.1 (`:211-216`), now brand data
  - `LAST_TAKE` (`:181`)
  - the hook `place.x 70`, which is outside x ≥ 128 (`:65-68`)
- **product-lineup:** hook preset only, with empty `push_takes`, `transitions`, `punches` and `flashes`.

### Changes by file

**New `pipeline/resolve.py`** (~170 lines; a plain module plus CLI, run with `.venv/bin/python`). Functions:
- `load_script(path, check_fonts=False) -> dict`: the layers and rules above.
- `merge(base, over)`.
- `apply_presets(script)`.
- `resolve_colors(obj, colors)`.
- `expand_sfx(cues, palette)`.
- `font_urls(style)`.
- `summary(script) -> str`.
- `apply_terms(words, terms, spoken_tokens) -> (words, hits)`:
  - For each `heard_as` phrase (compared as `build_timeline.norm` tokens, longest first) that occurs as consecutive transcript words, it rewrites the first word's `w` to the canonical text and blanks the others. Times are kept.
  - A rule fires **only for terms whose canonical token sequence occurs in the script's non-literal lines**, so «баланс» stays intact in reels that don't name the product.
  - Only matching is affected, never the displayed text. `hits` is returned for the build log.

CLI:
- `resolve.py <script>`: layers, warnings, local files and keys, and key settings (fonts, accent, music, grade, lint profile, grammar).
- `--json`: the full resolved script.
- `--list`: brands and formats with aliases; local-only ones are marked.
- `--check`: font files and glyphs; exit code 1 on failure.

**New `pipeline/fontcheck.py`** (~50 lines; shared with the preflight design, whose prototype is `/private/tmp/claude-501/design/cmap_proto.py`):
- `cmap_codepoints(path)` reads the sfnt cmap (formats 4 and 12) in pure Python, with no Chrome and no reference fonts.
- `check_glyphs(script)`:
  - Per alias it collects the characters of the resolved tokens by kind: main and deco → Main; accent and accent-white → Accent; label `( №N )` → Serif.
  - It adds the probe «ІЇЄҐіїєґʼ’№«»–» for every alias.
  - Every face of the alias must contain every character. Otherwise: `font <alias> (<file>) has no glyph for: …`.
- All five existing scripts pass with the bundled fonts (checked against the cmaps).

**`pipeline/build_timeline.py`:**
- `main` `:269-274`:
  - Signature becomes `main(script_path, script=None)`, with `script = script or resolve.load_script(script_path, check_fonts=True)` and `style = script["style"]`. This deletes the one-level merge at `:272-274`. The glyph check therefore runs before Chrome starts.
  - After words are loaded (`:283-289`): `words, hits = resolve.apply_terms(...)`, and each hit is printed as `terms: 'U -Case' → yocase @7.73`.
  - `meta.json` (`:304-305`) gains `"script"` (the absolute resolved path), `"brand"` and `"format"`: the build-slot stamp.
- `assign_times` `:96-101`: skip empty `w` in the "not shown" list.
- `build_screens` `:113-120`: after `tokenize`, if the line has no explicit `color`, a run of consecutive accent tokens whose norms equal a coloured term gets `tok["color"]`. The overlay honours `tok.color` on accent, deco and label kinds (`overlay.html:37`).
- Layout loop `:319-356`:
  - Warn when `len(lines) > style.layout.max_lines`.
  - Warn when a `behind: false` block sits in a screen that has a behind block **and** its `solve_block` result carries "no free spot": "front block overlaps her and will be cut by the matte". Occlusion is per frame (`:357-359`).

**`pipeline/overlay.html`:**
- Delete `:6-8`.
- `init` `:119-122`:
  - Read `TL.style.fonts`, and for each face `await new FontFace(alias, \`url("${url}")\`, {weight, style}).load()`, then `document.fonts.add`.
  - A rejected load throws `font <alias> failed: <url>`, instead of today's silent fallback.
  - A timeline without `style.fonts` throws "timeline.json predates brand fonts: rerun build_timeline".
- `applyFont` `:57`: `fontFeatureSettings = (faces(st.family)[0].features) || 'normal'`.

**`pipeline/style_default.json`:** add `fonts` only.

**New `pipeline/studio_default.json`:** as in the schema.

**`pipeline/build.py`:**
- `:38`: `script = resolve.load_script(a.script, check_fonts=not a.skip_timeline)`; print `resolve.summary`.
- `:44`: `build_timeline.main(a.script, script)`.
- After `:46`: with `--skip-timeline`, stop if `meta["script"]` is not this script.
- `sfx_cues` `:18-25` is unchanged, because cue names are already resolved.

**`pipeline/export_fcpxml.py`:**
- `:263`: `resolve.load_script(a.script)`.
- Move `meta = load_json(BUILD / "meta.json")` (`:269`) above the `proj` / `media` creation (`:265-267`), and stop there with "build/ holds <x>; run build.py for this script first" if the stamp differs. No empty project folder is left behind.
- Music `:539-545` then carries the brand track, gain, offset and fades.

**`pipeline/lint_edit.py`:**
- `:19-24`: keep `E_HELD`, `E_MOVING`, `MIN_GAP`, `WHOOSH` and `DESIGNED`; the rest comes from `P = script["lint"]`.
- `:95-98`:
  - Use `P["punch_min"]`.
  - With `P["slow_push"]` false, warn on any punch below `punch_min` whatever its hold: "moves under 10% read as nothing (<brand>)".
- `:142-149`:
  - Ban list = `fnmatch` over `P["sfx_banned"] ∪ script["sfx_banned"]`, with the message `"banned for <brand>/<format>"`.
  - Skip the plain-cut whoosh check when `whoosh_on_cuts` is true.
- `:156-160`: skip when `dead_span` is null.
- `:162`: `(script.get("grade") or {})`. Today this raises `AttributeError` on `"grade": null`.
- `:165-176`: skip when `beat_cuts` is false.
- `:182`: `lint(resolve.load_script(path))`.

**`pipeline/times.py`:**
- `:16`: `resolve.load_script`.
- `:21-26`: show every term match for display, e.g. `yocase(U -Case)[7.73]`, so Claude writes the canonical spelling.

**`pipeline/preview.py`:** `:45`: `resolve.load_script`.

**`pipeline/audio.py`:** the `:1` docstring says "ducked under the voice". It should say "static bed; optional `sidechain` (`:108-112`), off by default". There is no logic change in this piece.

**Data and template files:**
- `brands/tosumi/{brand.json, BRAND.md}` and `brands/yocase/{brand.json, BRAND.md}`.
- `formats/{talking-head, subtitles-only, skit-hoche-a}/{FORMAT.md, format.json, template.json}`.
- `formats/product-lineup/{format.json, template.json}`, plus the FORMAT.md edits.
- Delete `projects/_template/`.

**`.gitignore`:** add `*.local.json`, `*.local.md` and `brands/*/local/`.

**Docs (conflict fixes):**
- **`docs/STYLE.md`** becomes the universal subtitle system: markup, animation mechanics, solver and safe zone.
  - The typography table `:8-21` (stale 420/-0.03, 500/-0.015, 0.95×) is replaced by "numbers: style_default.json / brand.json".
  - `:36` becomes "`style.layout.exclude+` adds; a plain `exclude` replaces the rail".
  - `:38-57` moves to `formats/skit-hoche-a/FORMAT.md` and `brands/tosumi/BRAND.md`.
- **True peak:** stays at -1.5 dBTP. `PB:447` changes "-1 dBTP" to -1.5, matching `audio.py:136-138` and `export_fcpxml.py:221-231`.
- **Cartoon SFX:** `VS:62-64` and `PB:440` change "never in brand reels" to "never outside skit-hoche-a; lint enforces per format, brands may ban more".
- **`.claude/skills/reel-subtitles/SKILL.md`:**
  - `:3` and `:10`: brand-neutral wording.
  - New step before writing the script:
    - Run `resolve.py --list`.
    - Read `brands/<b>/BRAND.md` + `BRAND.local.md` and `formats/<f>/FORMAT.md` + `FORMAT.local.md`.
    - Run `resolve.py <script>` after setting `brand` / `format`.
  - `:35`: copy `formats/<format>/template.json`.
  - `:54-65` moves to the skit FORMAT.md.
  - `:98-111` moves to BRAND.md / FORMAT.md / STYLE.md; new learned rules go to `*.local.md` first.
- **`CONTEXT.md`:**
  - `:28` and `:31`: drop "(planned)".
  - `:35-36`: the «стоп» cutter is planned (roadmap 4), not existing.
  - `:45`: HDR clips are refused at ingest (`ingest.py:57-59`); there is no tone-map yet.
  - `:100-101`: point to `brands/` and `formats/`.
  - `:124`: the repo is public; no secrets, brand books or licensed assets; `*.local.*` and `local/` are gitignored.
  - "Current state": add 2026-10-13, yocase_2371/2373/2477, and the resolver.
- **ADRs** (only factual or status notes; decisions are not rewritten):
  - `ADR-0005:8,13`: M3 Pro → M2 Pro 16 GB.
  - Append "status: not built yet" notes to `ADR-0006:12-15` (stop marker, tone-map) and to `ADR-0001:18` / `ADR-0003:23` (HDR→SDR).
  - `ADR-0008:18`: "glitch accent word" is limited to at most one, for a deliberate error beat (PB:458).

### Interactions

**Person matte:**
- `behind` still defaults from `style.layout.behind` (`build_timeline.py:327`). The hook, CTA, interjection and punchline presets set `behind: false`.
- **Limitation (existing code, unchanged):**
  - Occlusion is per frame, not per block. A screen enters `occlude_frames` if *any* of its blocks is behind (`build_timeline.py:357-359`).
  - On those frames the whole overlay PNG is multiplied by (1 − matte) (`video_pass.py:216-217`), and each FCPXML layer is matted the same way (`export_fcpxml.py:128-132`).
  - So in the talking-head template, the hook shares screen 1 with a behind block and is cut wherever it overlaps her.
  - `behind: false` still makes the solver keep the block clear of her for its whole window (`:331`), so this matters only on "no free spot". The new layout warning flags exactly that case.
- Brand fonts change only measured sizes; the occlusion masks (`:331-334`) are unaffected.
- Future brand graphics (logo, strip) must be a separate layer, never part of the text PNG, for the same reason.

**Safe zone and layout solver:**
- The global safe area and rail stay studio data. A brand or format cannot widen the safe area (error); a script can, with a warning.
- Dropping the rail warns; the resolver flags tosumi_hair's `[960,…]` rail.
- The solver (`:193-255`) is unchanged: `:205` already combines global and per-block exclusions.
- `max_lines` only warns.

**Subtitle timing:**
- `apply_terms` gives mis-heard brand names the right start time. Measured on the real transcripts:
  - 2373 `yocase`: fuzzy 7.86 s → 7.73 s.
  - 2371 `repair plex`: NOT FOUND (interpolated to 48.93 s) → 48.76 s.
- In 2373, «Repair» (8.24) and «Plex» (8.60) are already separate correct words.
- The typewriter rule (`overlay.html:182-190`) is unchanged.
- The censor design must keep the canonical word for matching.

**FCPXML export:**
- Text layers render through the same `overlay.html` + `timeline.json` (`export_fcpxml.py:116-121`), so brand fonts and colours carry over.
- Brand music and palette SFX come in through `load_script`.
- Grade is still not exported (`:14-16`).
- The stamp check, placed before any folder is created, prevents exporting another reel's subtitles.

**lint_edit:**
- Becomes brand- and format-aware through the profile.
- Templates are lint-clean by construction. The old template, filled in, raises cut_in, in-out push, vignette, twitch and unanchored-punch warnings, plus a whoosh on a plain cut.
- `grade: null` no longer crashes it.
- Talking heads no longer get beat-sync warnings for speech cuts.

**Audio mix:**
- `audio.py` is unchanged. `music: null` and file-less music resolve to `None`, which `build.py:56` and `export_fcpxml.py:539` already handle.
- Gain and offset come only from the track's owner, the brand (or the script).
- Ducking is not part of this piece; TOSUMI's skit keeps a static bed (STYLE.md:54).
- True peak stays at -1.5 dBTP.
- Palette expansion reproduces tosumi_hair's hero stack exactly: 21.60 / 21.66 / 21.85 s at -8 / -11 / -17 dB.

**Shared build state:**
- The resolver writes nothing.
- `timeline.json` carries absolute font URLs; this is machine-local, which is fine for `build/`.
- `meta.json` carries the script stamp, which `export_fcpxml.py` and `build.py --skip-timeline` check.
- Builds still run strictly one at a time.

**8 GB RAM:** nothing new is held in memory. The glyph check is a pure-Python cmap read, and FontFace loads the same font bytes the CSS did.

**Other designs:**
- CTA: `presets.cta`, `grammar.cta_min_s`, `sfx_palette.cta`.
- Inserts: `sfx_palette.insert_*`, `grammar.insert`; a brand `layers` key is added by that design when built.
- Pause cutter: `grammar.trim`, present only in talking-head, so old scripts are never trimmed.
- Speed: `grammar.speed`.
- Censorship: `censor`.
- Ducking: adds `audio.music.duck` to the format allow-list.
- Preflight: `fontcheck.check_glyphs`.
- Ukrainian report: `resolve.summary` plus the `terms:` lines from the build log.

### Verification

All on the dev Mac. `V=/private/tmp/claude-501/design/v`; prefix Python with `PYTHONDONTWRITEBYTECODE=1`. Renders run one at a time; build/ currently holds yocase_2373.

1. **Old scripts unchanged (pure Python).** For tosumi_hair, 2371, 2373, 2477 and yocase_line, compare `resolve.load_script(...)["style"]` minus `fonts` with today's merge (`build_timeline.py:272-274`), and compare `camera`, `grade`, `audio`, `screens` and `edl` with the raw script.
   - Expect `True` for all five.
   - Expect no `grammar` key.
   - Expect the rail warning for tosumi_hair only.
2. **Brand migration equivalence (pure Python).** Write `$V/yocase_{2371,2373,2477}_brand.json`: drop `style`, `camera` and `audio`, and add `"brand": "yocase", "format": "subtitles-only"`. For 2371 and 2477, add `"style": {"layout": {"exclude+": [[620,0,1080,650]]}}` / `[[645,0,1080,430]]`.
   - Expect the resolved style to equal today's, apart from `layout.max_lines`.
   - Expect camera equal, music `None` and grade `None`.
3. **FontFace identity.**
   - Before editing overlay.html: `.venv/bin/python pipeline/overlay_render.py --frames 865 --only 15,90,237,360,600,810 --out $V/ov_css`.
   - After the change: `.venv/bin/python pipeline/build_timeline.py projects/yocase_2373/script.json`, then the same command with `--out $V/ov_ff`.
   - Expect `cmp` identical for all 6 frames.
4. **Integration draft, migration.**
   - `X264_PRESET=veryfast .venv/bin/python pipeline/build.py projects/yocase_2373/script.json --name rs2373_ref_draft`
   - `cp -R build/overlay $V/ov_ref && cp build/timeline.json $V/tl_ref.json`
   - `X264_PRESET=veryfast .venv/bin/python pipeline/build.py $V/yocase_2373_brand.json --name rs2373_brand_draft`
   - Expect the summary "studio → brand yocase → format subtitles-only → script".
   - Expect `timeline.json` to differ from `$V/tl_ref.json` only in `style.layout.max_lines`.
   - Expect 0 PNGs differing from `$V/ov_ref`.
   - Expect `ffmpeg -nostdin -i output/rs2373_ref_draft.mp4 -i output/rs2373_brand_draft.mp4 -lavfi psnr -f null -` to report `average:inf`, or ≥ 60 dB.
5. **Glossary and term colours.**
   - Variant `$V/yocase_2373_terms.json`: the literal line at 2373 `:153-160` becomes the spoken `{"text": "*yocase repair plex*", "anim": "pop", "scale": 1.2}`. Build the draft.
   - Expect the log line `terms: 'U -Case' → yocase @7.73`.
   - Expect no `'yocase' ~ '-Case'` fuzzy line, and neither `'U'` nor `''` in "transcript words not shown".
   - Expect timeline tokens `yocase` t=7.73 (colour unset, so accent #8A2E92), and `repair` t=8.24 and `plex` t=8.60, both `#C4207F`.
   - Pure Python on 2371 words: `repair plex` → 48.76 for both tokens.
6. **Glyph check (pure Python).** Scratch script with `"style": {"fonts": {"Main": {"file": "/System/Library/Fonts/Supplemental/Chalkduster.ttf"}}}`:
   - `resolve.py <it> --check` exits 1, naming the Cyrillic letters, № and ʼ.
   - `build_timeline.py <it>` stops before Chrome launches.
   - A nonexistent path prints "font file missing".
   - `resolve.py projects/yocase_2373/script.json --check` exits 0.
   - `lint_edit.py` on the Chalkduster script still runs (it does not check fonts).
7. **Lint profiles (pure Python, no render).** Fill each `formats/*/template.json` with the `build/yocase_2373/*` paths, `src_duration 28.8333`, takes `[[0,14],[14,28.8333]]` and `edl [{"src":[0,28.8333]}]`.
   - Expect 0 FAIL, and none of cut_in, in-out, anchor, twitch, vignette or whoosh.
   - Expect no "no visible change" for subtitles-only.
   - Add `{"name": "boing_01_spring", "peak_at": 5}` plus `whoosh_soft_01_air_sweep` at 14.0:
     - skit + tosumi: silent;
     - skit + yocase: boing warns;
     - talking-head + either brand: both warn.
   - Add the punch `{"t": 3, "scale": 1.06, "in": 0.45, "ease": "inout", "until": 6, "target": "face", "anchor": true}`:
     - talking-head + tosumi: silent;
     - talking-head + yocase: warns "under 10%".
   - talking-head + yocase (112 bpm bed): no "miss the beat" warning. product-lineup + yocase still checks beats.
   - `"grade": null` does not crash.
8. **Talking-head render.** `$V/yocase_2373_th.json` = the 2373 brand copy with `"format": "talking-head"`. Build the draft, then `export_fcpxml.py $V/yocase_2373_th.json --name rs2373_th`.
   - Expect the summary to show music `music_03_gimme_that_groove…`, -18 dB, offset 18.423, fades 0.1 / 0.8, and grade vignette 0.04.
   - Expect `grep -c 'name="music"' output/rs2373_th_project/rs2373_th.fcpxml` = 1, with a `fadeIn` and `fadeOut`. The subtitles-only export of step 4 would have 0.
9. **Local overrides and precedence.**
   - Create a temporary `brands/yocase/brand.local.json` with `{"audio": {"music": {"gain_db": -24, "file": "music_02_one_more_dance_110bpm_full.wav"}}, "presets": {"hook": {"until": 3.0}}}`.
   - `resolve.py $V/yocase_2373_th.json --json` shows gain -24, the One More Dance file with no offset, and hook `until` 3.0: the local file beats the talking-head format.
   - The summary lists the local file and its keys.
   - `resolve.py $V/yocase_2373_brand.json --json` still shows music `None` (the sticky subtitles-only off switch).
   - `git status --porcelain brands` prints nothing. Delete the file.
10. **No raw loads left.** `grep -nE 'load_json\((a\.script|script_path|path)\)|json\.loads\(path\.read_text' pipeline/*.py` returns nothing.
11. **Build-slot guard.** After step 8, `export_fcpxml.py projects/yocase_2477/script.json --name x` exits with "build/ holds …", and `ls output/x_project` fails because no folder was created.
12. **Ids.**
    - `resolve.py --list` prints tosumi and yocase, and the four formats with aliases.
    - A scratch script with `"brand": "yokeis"` exits "unknown brand 'yokeis'; known: tosumi, yocase".
    - The template copied unfilled exits on `BRAND`.

Scratch evidence already in hand:
- Scripts: `/private/tmp/claude-501/design/{proto_resolve.py, proto_glossary.py, font_identity.py, cmap_proto.py}`.
- Draft data: `/private/tmp/claude-501/design/tree/` (to be updated to this section: no `brand.formats`, no `grammar.zoom`, no studio `grammar`).

### Risks

- **List-replace trap.** A plain `exclude` silently drops the phone rail. The resolver warns; templates and skills use `exclude+`.
- **Stale local overrides.** `*.local.*` keeps winning after you change the tracked file. Every build prints the local files and keys; promoting a rule means deleting its local copy.
- **Local brand vs tracked brand.** A brand made on Marina's Mac lives only in `brand.local.json`. A later tracked `brand.json` with the same id never conflicts on pull, but her local keys keep winning until deleted.
- **Glossary false positives.**
  - A coloured term whose `heard_as` is a common word (YOCASE «баланс»): once `balance` appears in a spoken line, every «баланс» in that reel's transcript is rewritten. A Cyrillic «баланс» elsewhere in the subtitles then shows as NOT FOUND and is interpolated.
  - Limited by the "term written in the script" guard. The build log prints each rewrite and each NOT FOUND.
- **Matte cuts a front block** in a screen that mixes front and behind blocks (existing behaviour). Only the "no free spot" case is visible, and the new warning flags it.
- **Public repo.** A licensed font, logo, product photo or brand-book text committed by mistake would be published. Mitigations: the gitignored `local/` folders, the "OFL only in `fonts/`" rule, the "no brand books" rule in BRAND.md, and the developer's setup checklist.
- **Missing licensed font on a fresh Mac** stops the build with a clear message. This is intended; the old behaviour was a silent fallback. Lint, times and preview still work.
- **TOSUMI look changes in new skits** (linear creep, no `cut_in`, 1.12 punches) differ from the approved tosumi_hair. They are recorded in the skit FORMAT.md, and tosumi_hair stays as an untouched archive.
- **The TOSUMI look lives in `style_default.json`.** Changing the studio default changes TOSUMI unless its values are moved into `brands/tosumi/brand.json` first; BRAND.md and STYLE.md say so.
- **A missed entry point** (a new tool calling `load_json` on a script) would ignore the brand. Check 10 catches it.

### Effort

| Piece | Size |
|---|---|
| `resolve.py` (merge, layers, ownership, sticky offs, presets, colours, palette, terms, summary, CLI) | M |
| `fontcheck.py` (cmap reader + per-alias check; shared with preflight) | S |
| build_timeline integration (resolver, terms, term colours, max_lines and front-block warnings, meta stamp) | S-M |
| overlay.html FontFace loading | S |
| build.py / export_fcpxml / lint_edit (profile incl. slow_push, beat_cuts) / times / preview switched to `load_script` | S |
| `studio_default.json`, `style_default.json` fonts, `.gitignore` | S |
| TOSUMI and YOCASE brand.json + BRAND.md | S |
| 4 × format.json, 3 new FORMAT.md, product-lineup edits | M |
| 4 templates, delete `projects/_template` | S |
| Doc conflict fixes (STYLE, CONTEXT, ADR notes, playbook, both skills) | S |
| Verification (pure-Python checks plus 3-4 draft renders of 28.8 s and one export) | S |

### Open questions for the developer

1. **TOSUMI vs the playbook.**
   - The design keeps TOSUMI's client-approved vignette 0.10 as brand data with a brand lint threshold.
   - It moves new TOSUMI skits from 1.05-1.07 fail-word punches to anchored 1.12, which the playbook says read as deliberate (PB:201-210).
   - Should either go the other way? Each is a one-line change in `brands/tosumi/brand.json` or the skit FORMAT.md.
2. **YOCASE brand-name colour.** `yocase` was shown in #C4207F, the Repair Plex colour, in 2371 and 2373. Should the brand name use that colour, the accent #8A2E92, or white? The draft leaves it uncoloured, so it shows as an accent run in #8A2E92.
3. **Music in brand talking heads.**
   - The default is on: the brand bed with 0.1 / 0.8 s fades; «без музики» turns it off; the no-music export always exists.
   - Is Gimme that Groove (from yocase_line, entering at 18.423 s) the right YOCASE bed?
4. **How Marina's local corrections reach you.** They are gitignored `*.local.*` files on her Mac. Design default: her Claude lists any new local rules at the end of each report so she can forward them, and you promote them on your account. Or do you prefer to copy them during visits?
5. **Censorship default.** The censor list stays empty unless `ЦЕНЗУРА:` or the brand sets it. Should brand talking heads censor money and sales words by default, as the third-party skill does?
6. **New brands on Marina's Mac.** ADR-0002:22-24 and CONTEXT.md:15-16 put brand onboarding on your account. Should her Claude be allowed to create a local-only brand (accent colour, music, rules in `brand.local.json`) when a new client appears before you onboard it? The alternative is to make that reel in the studio (TOSUMI) look and flag it for you.
