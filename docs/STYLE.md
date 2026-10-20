# Subtitle system (universal)

How subtitles are written, animated and placed in every reel. **The numbers are data, not prose:** the studio
look is `pipeline/style_default.json` (= the TOSUMI look), a brand changes it in `brands/<brand>/brand.json`, and
`pipeline/resolve.py <script>` shows what a reel resolves to. Brand rules in words are in `brands/<brand>/BRAND.md`,
format structure in `formats/<format>/FORMAT.md`.

Origin (Oct 2026, TOSUMI): the client found the previous subtitles untrendy and too big. From the liked reference
came the condensed main font, the per-letter animation and the "interesting" placement beside the person, with
white main text and the accent words in the brand colour.

## Markup (one script line = one visual line)
| markup | role | drawn with |
|---|---|---|
| plain words | main text | `style.main` (alias `Main`) |
| `*…*` | accent: the punch/fail word, one per half-sentence | `style.accent` (alias `Accent`), accent colour |
| `_…_` | emphasis: the dream/setup words | `style.accent` font, main colour |
| `№N` | take label, drawn "( №N )", pops in | `style.label` (alias `Serif`) |
| `//` | ornament | main font, accent colour |
- Lowercase, punctuation dropped (except `?` in literal titles).
- A line may be a dict: `scale`, `anim` (`pop`/`type`/`none`), `color`, `align`, `indent`, `dy`, `literal` + `t`
  (not spoken, e.g. a hook title). `"preset": "<name>"` on a block or line pulls a named look/structure from the
  studio, brand and format `presets` (hook, cta, interjection, punchline, brand_name, product_label).
- Colours may name a brand colour: `"color": "@repair_plex"`.
- Lines with serif accents or labels get extra room above (`accent_gap`) and the line after them below
  (`accent_gap_after`), so accent letters never sit on the main text.
- Size rule: text is small. Only the big moments (an interjection gag, a final punchline, a hook) get scaled.

## Fonts
`style.fonts` maps the aliases `Main`, `Accent`, `Serif` to font files (one face or a list of static faces, with
`weight`, `style`, `features`). Bundled OFL fonts live in `assets/fonts/`; licensed brand fonts in
`brands/<brand>/local/` (gitignored). The build checks that every character a reel shows exists in its fonts
(`pipeline/fontcheck.py`) and stops otherwise: Chrome would silently draw it in a system font.

## Animation
- Per-letter elastic typewriter (`style.anim`): each glyph scales up from a squashed start with a slight skew,
  typed at a fixed rate and never before its spoken word; accent words overshoot more.
- Labels and big words pop as whole words (scale up with a little rotation).
- Screens cut hard at take cuts; titles fade (`fade`).

## Layout (automatic solver, `pipeline/build_timeline.py`)
- Blocks float beside the person ("editorial" placement), never a bottom bar.
- Person matte per frame; a block stays clear of her until it has been read (`layout.read_time` after its last
  word); afterwards she may walk IN FRONT of it (text-behind-subject). `behind: false` keeps a block in front.
- IG crop-safe area: x 128-952, y 250-1480, and the button rail (x > 850, y > 1050) excluded (`layout.safe`,
  `layout.exclude`). Instagram fills tall phones (19.5:9, 20:9) edge to edge and crops ~100 px off each side; text
  at x 56 was cut off on a real phone (2026-10-13). The solver never leaves this area, the build flags any block
  outside it, and no brand or format may widen it.
- Video-specific exclusions (bright lamps, baked logos) go into `style.layout.exclude+`, which adds rectangles; a
  plain `exclude` replaces the list and drops the rail (the resolver warns).
- A brand may cap the lines per block (`layout.max_lines`); the layout report flags longer blocks.
