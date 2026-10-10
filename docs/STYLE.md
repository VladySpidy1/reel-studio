# House subtitle style (from the reference investigation, Oct 2026)

Client brief (UA, paraphrased): previous subtitles had an untrendy font and were too big. Liked references:
ref2 (DZmz4VRMULC) and ref3 (DXOmJP5jWid). From ref3 take the font for the main text, the animation and
the "interesting" placement, but the main text is WHITE and accent words are PINK. Letter spacing and line
spacing must be tight.

## Typography (pipeline/style_default.json)
| element | font | size @1080w | tracking | colour |
|---|---|---|---|---|
| main text | Roboto Condensed 420 (≈ Arial Narrow of ref3) | 58 px | -0.03 em | #FFFFFF |
| fail / punch words `*…*` | Playfair Display Italic 500, in (parentheses) | same | -0.015 em | #FF3D96 (TOSUMI-bag pink) |
| dream / setup words `_…_` | Playfair Display Italic 500, no brackets | same | -0.015 em | white |
| take label `№N` | Playfair Display 400, "( №N )" | 0.95× | 0 | pink |
| ornament `//` | main font | same | | pink |
- Leading 0.62 for plain white lines (ref3-tight); lines with serif accents/labels get +0.16 em, the line
  after them +0.2 em, so pink never sits on white.
- Lowercase, punctuation dropped (except `?` in literal titles).
- Outline: soft drop-shadow ring (1 px 62% black + 7 px 26% black). Needed: white on a bright beige wall.
- Size rule: text is SMALL (cap ≈ 41 px). Only two things get big: an interjection gag (`ой`, ×3, pop)
  and the final punchline header (×1.55).

## Animation
- Per-letter elastic typewriter (ref3): each glyph 0.13 s, scaleY 0.12 → 1.32 → 1, slight skew; 40 chars/s,
  never earlier than its spoken word. Accent words overshoot ×1.15.
- Labels and big gag words pop as whole words (scale 0.2 → 1.28 → 1 with a little rotation).
- Screens cut hard at take cuts; titles/hero fade 0.2–0.25 s.

## Layout (automatic solver, pipeline/build_timeline.py)
- Blocks float beside the person ("editorial" placement), never a bottom bar.
- Person matte (Robust Video Matting) per frame; a block must stay clear of her until it has been read
  (`read_time` 0.9 s after its last word); afterwards she may walk IN FRONT of it (text-behind-subject).
- IG safe zone: x 56–1024, y 250–1480, right button column (x>960, y>1050) excluded.
- Video-specific exclusions (bright lamps etc.) go into the script's `style.layout.exclude`.

## Comedy structure that worked ("Хоче X, а Y" skits)
- One screen per take, two blocks: setup `№N / хоче … _dream_` near her at chest height, punch
  `// а … *(fail)*` elsewhere (often top-left). Both halves visible together until the cut.
- Pink = the fail/punch word only (consistent → viewers anticipate it). Dream words = white serif.
- Hook title for the first ~1.6 s (literal text, e.g. "у якому № / _впізнала себе?_").
- Interjection gag: video-only freeze on the silent beat + record scratch + music dropout, then a big pink
  pop word next to her face + punch-in + shake + thump.
- Product payoff: after the last word, a 1.2 s freeze on the best product frame (flash + shutter + sparkle
  SFX, hand-drawn pink circle around the product), then let her walk out so the end frame (empty hallway)
  loops into frame 0. No text on the last 0.6 s.

## Edit & sound
- Per-take white-balance gains (match takes), light grade (lift .01, contrast 1.04, sat 1.04, vignette .10).
- Slow push 1.00→1.04 per take, cut-in zoom 1.06 with slight zoom blur, punch-ins 1.05–1.07 on fail words.
- Voice: left as recorded (phone/CapCut exports are already cleaned; extra EQ/de-ess/compression sounded
  thin and odd). Only the final mix is normalised to -14 LUFS / -1.5 dBTP. (`voice.process: true` exists.)
- Music bed (Mixkit "Gummies" 120 bpm) static at -17 dB, NO sidechain ducking (it audibly pumps);
  short 40 ms-ramped dropouts for gag freezes.
- SFX (assets/sfx, Mixkit/CC0): whoosh on every cut, boing/punch/scratch/thump on gags, soft pop -23 dB on
  pink words, chime on "salon", shutter+sparkle+shimmer on the product freeze.
