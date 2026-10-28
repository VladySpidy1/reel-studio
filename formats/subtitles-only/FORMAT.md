# Format: subtitles only («лише субтитри», already edited video)

The brand sends (or she makes) a finished video with its own cut, logo, insets or chat bubbles; the reel gets
subtitles in the brand look and nothing else (the 2026-10-13 rule). Claude picks this format when the contact sheet
shows baked graphics, and says so in the report. Start from `template.json`.

## Rules
- One `src` segment; push 1.00 -> 1.00; no grade, music, SFX or brand layers (`format.json` switches the brand's
  grade, music and `style.layers` off). The brand's subtitle look still applies.
- Exclude baked-in logos and insets: `"style": {"layout": {"exclude+": [[x0, y0, x1, y1]]}}` for the whole video,
  or `place.exclude` per block. A plain `exclude` would drop the IG button rail.
- Never caption a line that is already on screen (e.g. a chat bubble).
- No hook or CTA preset: the video already has its own. Lint does not ask for a CTA block or flag long spans
  without a visible change.

## Worked examples
`projects/yocase_2477` (automatic layout) and `projects/yocase_2371` (brand name and CTA).

## Learned rules
- Corrections from reels go to `learned/formats/subtitles-only.md` (tracked, shared by both Macs); rules that hold are folded into this file.
