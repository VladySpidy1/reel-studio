# Format: talking head for a brand («говорюча голова»)

She talks to the camera about a brand's product, shot raw on the phone (like `projects/yocase_2371` / `yocase_2477`,
but from raw footage). The default format: when the brief names no format, it is this one. When the contact sheet
shows baked graphics (a logo, insets, a chat bubble), the video is already edited: use `subtitles-only` and say so
in the report. Machine-readable rules: `format.json` (presets, lint profile, `grammar`); the studio presets are in
`pipeline/studio_default.json`. Start from `template.json`.

## Structure
- **Hook** 2-3 s from frame 0 (`"preset": "hook"`, lint checks 2.0-3.0 s). Her `ХУК` verbatim; otherwise one of
  7 words or fewer, at y 270-700, never over her face. No CTA and no insert while the hook is up. Brand and main
  message within 5 s (playbook 3.5).
- **Body:** one screen per thought; one accent per half-sentence, on the word that carries the meaning.
- **Product moments:** the product name pops in its product colour (`brand_name` / `product_label` line presets).
  An insert or a product shot only when the picture proves what she says.
- **CTA** spoken and on screen for at least 2 s (`"preset": "cta"`), synced to the phrase (±0.2 s) and held to its
  end. A spoken CTA without a CTA block is a lint FAIL in this format (`cta_check`).
- **End:** no logo card; the last frame close to frame 0.

## Pause trimming
`grammar.trim` holds the thresholds `trim.py` uses: inner pauses over 0.45 s are cut, with 4 f before the voice
onset and 3 f after its end, and 10 f are kept after a sentence end or a key claim. Never strip every breath
(playbook 2.7). The third-party 0.2 s threshold and its "strip head and tail" are rejected.
Speed-up is built but off: `ШВИДКІСТЬ:` is honoured only here, up to `grammar.speed_max`, on footage shot at 60 fps.

## Zooms by meaning (lint enforces the floors)
| Move | Rule | TOSUMI | YOCASE |
|---|---|---|---|
| A/B step on a same-setup jump cut | A 1.00 / B 1.12-1.18, a hard step at the cut, switching every 2nd-3rd cut (playbook 2.7) | same | same |
| Fast punch on a stressed word (`in` <= 0.15 s) | >= 1.12, `anchor: true`, held to the end of the thought (playbook 2.6) | 1.12 | >= 1.12 |
| Slow "meaning push" | 1.05-1.08, `{"in": 0.45, "ease": "inout", "anchor": true}`, held >= 1.5 s, only on uncut takes over 4 s | allowed | not allowed (lint warns: under 10 %) |
| Back out to 1.00 | only at a cut (A framing), never an animated zoom-out | | |

Aim for 3-6 changes per 30 s.

## Music
- On by default with the brand bed from frame 0: file, level and offset come from `brand.json`, the short fades
  from this format.
- «без музики» writes `"audio": {"music": null}` in the script; the no-music export always exists (ADR-0003).
- Speech cuts follow words, not beats, so lint skips the beat check here (`lint.beat_cuts`).
- Keyframed ducking, never a sidechain: the bed sits `under_lu` (15) LU under the voice and rises `duck.rise_db`
  (4 dB) in gaps of at least `duck.min_gap` (0.8 s); the brand sets these in `brand.json` `audio.music`. The
  third-party "mandatory music" is rejected.

## Inserts
Only when the image directly confirms the phrase; never over her face or the subtitles; inside x 128-952,
y 250-1480 (the inserts work owns the mechanics).

## Contributed by the third-party skill
Verbatim hook; code-word CTA; image inserts with pop-in and SFX; full-screen inserts; pause cutting (with the studio
thresholds); asterisk censorship plus Latin platform words; glyph and disk preflight; pre-export checklist; a
Ukrainian report; the `done/` archive; keyframed ducking; "don't ask about trifles".
**Rejected:** the x 60 safe zone, whisper medium/small, crf 18, the fixed bottom block, mandatory music,
self-install, ×1.3 by default, and its lime/handwritten look.

## Learned rules
- 2026-10-13: spacing is brand data (`brand.json`), never per-script style.
- Brand names misheard by whisper are fixed by `terms`, not by literal lines (2371, 2373).
- Prefer automatic layout (2477) over hand-placed blocks (2373).
- Baked-in graphics go in `style.layout.exclude+` (screen-wide) or `place.exclude` (per block).
- Corrections from reels go to `learned/formats/talking-head.md` (tracked, shared by both Macs); rules that hold are folded into this file.
