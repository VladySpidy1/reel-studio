# Brand: YOCASE

Hair care, purple accent. The look (spacing, colours, product colours, grade, music bed, bans) is in `brand.json`;
numbers live only there. Evidence so far: `projects/yocase_line` (product lineup, raw clips) and
`projects/yocase_2371`, `yocase_2373`, `yocase_2477` (already-edited videos, subtitles only).

## Rules
- Comfortable spacing, never the TOSUMI tightness; 2-3 lines per block, split long screens (the layout report flags
  a block over the brand's line limit).
- The brand display is lowercase `yocase` in the accent colour. Brand and product names are spoken lines in Latin
  lowercase (`yocase`, `repair plex`, `energy`, `balance`, `fix color`), never literal lines with hand-set times:
  `terms` maps what whisper hears («U -Case», «Репейрплекс») to them. A product name in accent takes its product
  colour.
- One way of styling the brand name per reel (2371 used three).
- Check which bottle is in her hand before using a shot (`formats/product-lineup/FORMAT.md`, shooting notes).
- No cartoon SFX in any format; no camera moves under 10 % (they read as nothing; lint warns); no filler made from
  between-take fragments.
- Register: «ти» (yocase_line and 2373; 2371 and 2477 used «ви»). Ask the developer before switching.
- Music: Gimme that Groove from its groove section. One reel of evidence (yocase_line); the developer may change it.
- No standing censor list; «ЦЕНЗУРА:» in the brief adds words per reel.

## Notes
- Licensed fonts, logos and product photos go in `brands/yocase/local/` (gitignored, installed in person). The repo
  is public: no brand book or NDA material here.
- Corrections from reels go to `learned/brands/yocase.md` (gitignored); the developer promotes them into this file.

## Learned rules
- 2026-10-10: «видео мертвое» - every visible gesture is an edit point; moves under 10 % and in-out blips read as
  nothing.
- 2026-10-10: a block stitched from between-take fragments to cover a voice-over is worse than a shorter block.
- 2026-10-13: «между текстом должны быть хорошие отступы» - the comfortable spacing is brand data (`brand.json`
  style), not per-script style.
- 2026-10-13: already-edited videos with a baked logo, insets or a chat bubble get subtitles only (format
  `subtitles-only`).
