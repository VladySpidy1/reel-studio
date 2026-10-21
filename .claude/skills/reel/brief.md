# Her brief and her corrections -> script.json

`brief.py inbox/<reel>/brief.md` gives the brief as JSON (labelled lines plus the free phrases «без музики», «без
правок стилю», «коли кажу … — покажи …»). Anything she writes in chat counts the same; put it into `brief.md` so lint
sees it. Empty fields are yours to decide: decide, and list the judgement calls under «Сумнівні рішення». The only
blocking questions are a missing or unknown brand and "no clips found".

`lint_edit.py` checks the script against `brief.md` (`brief:` lines, from `pipeline/brief.py` `check`).

| She writes | Script | Notes |
|---|---|---|
| `БРЕНД:` | `"brand": "<id>"` | Map her word to an id with `resolve.py --list` (Ukrainian inflects: «для йокейсу» = `yocase`). |
| `ФОРМАТ:` | `"format": "<id>"` | Default `talking-head`; baked-in graphics -> `subtitles-only` (report it). A format that does not exist: ask. |
| `ІДЕЯ:` | — | The report's title; helps with a hook she left empty. |
| `ХУК:` | the first block of screen 1: `{"preset": "hook", "lines": [...]}` | Below. |
| `КОДОВЕ СЛОВО:` | the block of her spoken CTA gets `"preset": "cta"`, the code word as `*accent*` | Below. |
| `ВСТАВКИ:`, «коли кажу X — покажи Y [на весь екран]» | `"inserts": [...]` | Below. |
| `МУЗИКА:` <назва> | `"audio": {"music": {"file": "<exact file>", "asked": "<her words>"}}` | `.venv/bin/python pipeline/assets.py music <her words>` gives the exact file. Several fit: the brand's track if it is among them, else the first; report it. Nothing fits: the brand's track, reported. |
| «без музики» | `"audio": {"music": null}` | |
| МУЗИКА empty | nothing | The brand's bed from frame 0, ducked under her voice. |
| `ЦЕНЗУРА:` слово, слово | `"censor+": ["слово", ...]` | «стандартна» -> `"censor+": ["@standard"]`. Subtitles show `гр*ші` in every form; a hook she typed is censored only if she asks (`"censor": true` on its lines). |
| `БЕЗ ПРАВОК СТИЛЮ: так`, «без правок стилю» | no `style`, `presets` or `doodles` in the script | `style.layout.exclude+` for baked graphics and `place` hints stay allowed. |
| `ШВИДКІСТЬ:` 1,1–1,2 | `--speed k` on `doctor.py --clips` and `inbox.py prep` | talking-head only, up to `grammar.speed_max` (1.2): above it use the maximum, in another format 1.0; report either. Never unasked. It is decided before prep: changing it later means `inbox.py prep <reel> --speed k --force`. |
| `РЕФЕРЕНС:`, `ПРИМІТКИ:` | — | Read and follow; not checked. |

## Hook
- Her `ХУК:` word for word, in her order; only split it into 2-3 lines of at most ~17 characters (824 px),
  lowercase like every subtitle (a `?` may stay; lint compares words, not case or punctuation). No markup unless she
  marked a word. The talking-head format makes the lines literal at t 0 and shows the block
  0-2.5 s, centred near the top, in front of her and off her face.
- Empty: write one of at most 7 words from the idea and the first sentence she says, and list it under «Сумнівні
  рішення» («хук придумала я: …»).
- Nothing else may start while it is up: no CTA, no insert (lint FAILs both).

## CTA
- `times.py` prints `CTA spoken: «напиши…» [t]` for each spoken call to action (напиши/пиши, посилання, дірект,
  коментар, підпишись, the brand's own phrases). Each one needs its phrase's block with `"preset": "cta"`: a card
  that pops on the phrase's first word with the chime and stays at least 2 s (lint FAILs a spoken CTA without one in
  talking-head).
- Keep her words in that block (at most 5); with `КОДОВЕ СЛОВО:` the code word is the `*accent*` and must be a
  spoken word that aligns (typed as she says it; `display{heard}` when whisper wrote it differently).
- No spoken CTA: no CTA block (drop the template's).

## Screens
- One screen per take, blocks of 2-4-word lines in spoken order, lowercase, no punctuation, one accent per
  half-sentence; markup in `reel-subtitles` SKILL.md §2. Brand and product words in the display form
  `brands/<brand>/BRAND.md` gives (`yocase`, `repair plex`); the brand's terms align and colour them.
- Let the layout solver place blocks; add `place` only to fix a review finding, inside x 128-952, y 250-1480 and off
  the rail (x > 850 and y > 1050).

## Inserts
- Open every file's view once (`inserts.py`). Place a picture only when it shows what is being said: the same
  product, a readable number or quote, the same claim. Otherwise it goes under «Не вставлено» with the reason.
  Never place a file you have not looked at.
- `{"file": "<name in inserts/>", "at": "<phrase copied from times.py>", "why": "<what it shows that proves the
  phrase>"}`. Anchor on Ukrainian words near a Latin brand name (whisper garbles those).
- «на весь екран»: `"mode": "full"` (a video always is). Without a phrase: pick the line where it is talked about
  and report which.
- «велике» / «маленьке»: `"size": "l"` / `"s"` (default by format); «довше»: `"until"`; «тільки верх / частину з …»:
  `"crop"` you choose after looking, reported; never crop unasked: a tall screenshot goes full-screen instead.
- Sound: leave `sfx` out (the palette's pop or whoosh). `"sfx": null` only for «без звуку» (`"silent": true`).
- Not in the hook (0-2.5 s), not over her face or a subtitle block: a build FAIL names the problem; fix in this
  order: unpin a nearby block, crop (if she allowed), `"size": "s"`, `"mode": "full"`.

## Corrections (after a draft)
| She says | Change |
|---|---|
| «субтитри вище/нижче», «текст закриває …» | `place` on that block (`y`, or `safe` box), inside the safe area |
| «музика тихіше/голосніше» | `audio.music.under_lu` +3 / −3 when the brand sets it (YOCASE does), else `gain_db` −3 / +3 |
| «без музики» | `"audio": {"music": null}` |
| «прибери вставку N» | remove it from `inserts` |
| «фото більше», «скрін на весь екран» | `"size": "l"`, `"mode": "full"` |
| «вставку N раніше/довше» | `"offset"` (seconds, negative = earlier), `"until"` |
| «залиш паузу після "…"» | `trim.punch` (source time of that word), `trim.py --write` |
| «покажи, як я підношу пляшку» | `trim.keep` (the source range), `trim.py --write` |
| «інший дубль» | `trim.drop` (the source ranges of the take she rejects), `trim.py --write` |
| «пиши X латиницею» | `"terms": {"x": {"heard_as": ["<as times.py prints it>"]}}` |
| «більше руху», «мертве» | the `reel-videographer` skill |

After `trim.py --write` run `times.py` again: output times moved.
