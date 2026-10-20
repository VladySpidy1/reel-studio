# Content studio: decisions (2026-10-20)

Merges the third-party "reels-montage-ua" talking-head skill into Reel Studio and packages the studio for
Marina's Mac. Authority order when files disagree: **this file > `integration.md` > the five section files**
(`marina-layer.md`, `brands-formats.md`, `text-features.md`, `inserts.md`, `audio-timing.md`).

## Developer decisions

- **Delivery:** the GitHub repo stays **public**. Marina's Mac clones it and updates with `git pull --ff-only`.
  No secrets, keys or tokens ever go into the repo. The music/SFX WAVs **stay tracked**: the developer accepted
  the Mixkit licence trade-off (this overrides integration.md open question 1). CONTEXT.md's personal lines stay;
  only its "private repository" wording is corrected to public.
- **Branch:** all work lands on `main` as local commits. Nothing is pushed until the developer says yes.
- **Scope:** everything at once: the pipeline features from all five sections, not only docs.
- **Content:** Marina makes talking-head reels **for brands** (TOSUMI, YOCASE), like `projects/yocase_2371` and
  `yocase_2477`. Code-word CTAs exist but are secondary.
- **Adopted from the third-party skill:** the Ukrainian brief dictionary, talking-head format, image and
  full-screen inserts with SFX, a CTA synced to the spoken phrase, automatic pause cutting with the studio's
  thresholds, asterisk censorship and Latin brand words, first-run and preflight checks, the pre-export checklist,
  a final report in Ukrainian, a `done/` archive that never deletes sources, keyframed music ducking.
- **Not adopted:** safe zone x 60, whisper medium/small, crf 18, a fixed bottom subtitle block, mandatory music,
  "install anything yourself", ×1.3 by default, the lime/handwritten look.

## Open questions: resolved

1. Public repo: see Delivery above. Brand logos, brand photos and licensed brand fonts are never tracked; they live
   in `brands/<b>/local/` and are copied to Marina's Mac in person.
2. Music in brand talking heads: integration.md default (brand bed from frame 0, keyframed ducking, a
   `<reel>_no_music.mp4` with every final).
3. Brand data: integration.md defaults (YOCASE lowercase `yocase` in `#8A2E92`, product names in Latin lowercase
   in their product colours, hook/CTA in brand fonts, no standing censor list).
4. Shooting and speed: integration.md defaults («стоп» treated as unreliable; trim proposes, Claude confirms on
   contact sheets; speed-up built but off; `speed_max` 1.2 in talking-head only).
5. Inserts: integration.md defaults (`snap` 85 ms, no cropping unless asked, tall screenshots go full-screen).
6. Autonomy: integration.md defaults (manual permission mode plus the allowlist).

## Simplifications (override the sections)

- **Learned rules are Markdown only:** `learned/general.md`, `learned/brands/<b>.md`, `learned/formats/<f>.md`
  (gitignored; `learned/README.md` tracked). The `/reel` skill reads them before writing a script; the developer
  promotes rules into tracked files by hand. No JSON patch layers, no `PROMOTED.md` id machinery.
- **Resolver strictness:** unknown keys are a WARN; only type errors on known keys are errors.
- **FCPXML:** every new visual layer (inserts, brand layers, front text) and the music stem with fades must
  export. Music-ducking keyframes in FCPXML are optional; if skipped, say so in the export header and the report.

## Token economy (added after the design)

Measured on the 2026-10-13 session (3 subtitles-only YOCASE reels): 89 model calls, context growing from 81k to
335k tokens, ~6M cache-read tokens per reel. Most growth came from 2000-px review images (often re-read) and
from three reels sharing one session. Requirements:

- **Compact tool output:** pipeline entry points print a short summary by default (problems first); full detail
  goes to `build/<id>/logs/*.log` or `--verbose`.
- **Model-sized images:** `review_frames.py` and `contact_sheet.py` default to a long edge of at most 1200 px; a
  flag gives full size; the skill zooms into crops instead of re-reading full sheets.
- **Few calls per reel:** one command per stage (`inbox.py prep`, `build.py --draft`, review), not chains of
  small commands.
- **Creator `CLAUDE.md` rules:** one reel per session (new session or `/clear` between reels); never re-read the
  same image; long steps run in the background with a log and only the log tail is read; no subagents or
  workflows in creator sessions; skills stay short and the playbook is read by section only.
- **Verification:** Phase 6 measures one creator-flow reel's tokens against the baseline above.

## Implementation order

`docs/superpowers/plans/2026-10-20-content-studio.md`.
