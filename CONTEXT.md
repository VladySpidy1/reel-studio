# Reel Studio — project context

## What this is

A Claude Code toolkit that turns raw phone footage into finished Instagram/TikTok reels for a creator who
works for 2–3 brands. It started as a one-off pipeline for a single TOSUMI reel (Oct 2026) and is now being
generalised into a multi-brand, multi-format tool. Design decisions were settled in a debate on 2026-10-10;
see `docs/adr/`.

## People

- **Creator** (the developer's wife): actress and social-media creator. Shoots and edits ~30 reels a month for
  2–3 brands, in sessions of 5–10 reels, 3–5 sessions a month. Edits in CapCut today, is not technical, works
  in Ukrainian. Uses the Claude desktop app, never a terminal. Brands review her videos occasionally.
- **Developer**: builds and maintains the toolkit on his own Claude account. All R&D, brand and format
  onboarding and graphic-template design happen there; the creator only runs the finished tool.

## Goal

Reels that beat competitors who edit by hand. **Quality first, cost second, speed does not matter** — a batch
rendering overnight is fine. Model effort goes to taste (ideas, hooks, review, graphics), deterministic code
handles mechanics (ADR-0001).

## Glossary

- **Brand** — a client the creator makes reels for. Defines how a reel *looks*: fonts, colours, subtitle
  animation, grade/LUT, music mood, SFX palette, logo and CTA, tone of voice, prohibitions, learned rules.
  Lives in `brands/<brand>/` (planned).
- **Format** — a genre of reel: skit ("хоче X, а Y"), tutorial, before/after, GRWM, review, unboxing, etc.
  Defines how a reel is *cut*: structure, pacing, hook, where freezes and product holds go.
  Lives in `formats/<format>/` (planned).
- **Universal grammar** — editing rules that apply to any talking reel regardless of format: hook, silence
  cleanup, subtitles, accent words, punch-ins, SFX.
- **Brief** — what the creator gives per reel: brand, format, idea, goal, optional reference.
- **Take (дубль)** — one attempt at a line. A failed take ends with the creator saying **«стоп»** (shooting
  protocol, ADR-0006); the pipeline cuts on that marker without model guesswork.
- **Timeline** — the single source of truth for one reel (`projects/<name>/script.json` today). Every export
  is generated from it (ADR-0003).
- **Screen / block** — subtitle units: one screen per take, blocks of 2–4-word lines inside it.
- **Accent word** — the one punch word per half-sentence, rendered in the brand's accent style.
- **Graphic template** — a parametric, code-drawn motion-graphics element of a brand (product callout, list
  cards, counter, before/after wipe, CTA end card, …). Designed once, filled with text/numbers/timings per reel.
- **Bespoke graphic** — a one-off code-drawn graphic made for a specific idea; promoted to a template if it
  works (ADR-0008).
- **Intermediate media** — colour-normalised video (white balance matched across takes, HDR→SDR, brand
  grade), 1080×1920 ProRes, shared by every export so the MP4 and the editable project look identical.
- **Draft MP4** — the rendered reel, ready to post.
- **Editable project** — FCPXML timeline plus per-element media (subtitle blocks and graphics as alpha
  ProRes 4444 clips, SFX, music, zoom keyframes) for finishing in DaVinci Resolve (ADR-0004).
- **No-music variant** — export with SFX but no music bed, so a trending Instagram sound can be added in the
  app at posting time (in-app sounds cannot be baked in).
- **Hook variants** — 2–3 alternative openings rendered from the same timeline, for Instagram trial reels.
- **Session types** — Research & pre-production, Batch edit, Results review (ADR-0007).
- **Learned rules** — corrections the creator makes, appended to the brand or format file so the next reel
  does not repeat the mistake.
- **Research account** — a separate Instagram account (not the creator's working account, not a brand's)
  used for browsing competitors.
- **«реф» collection** — the creator's saved-reels collection of references she likes; an input to research.

## Decisions

| ADR | Decision |
|---|---|
| [0001](docs/adr/0001-quality-first-code-for-mechanics-model-for-taste.md) | Quality first; deterministic code for mechanics, model effort for taste |
| [0002](docs/adr/0002-brand-x-format-model.md) | A reel = Brand × Format + footage + brief |
| [0003](docs/adr/0003-one-timeline-many-exports.md) | One timeline, several exports (MP4, editable project, no-music, hook variants) |
| [0004](docs/adr/0004-davinci-resolve-via-fcpxml.md) | Finish in DaVinci Resolve via FCPXML; Final Cut Pro as fallback; no CapCut import |
| [0005](docs/adr/0005-mac-target-quality-over-speed.md) | Mac is the target platform; full-quality models, overnight batches |
| [0006](docs/adr/0006-shooting-protocol-stop-marker-hdr-off.md) | Shooting protocol: «стоп» after a failed take; iPhone HDR video off |
| [0007](docs/adr/0007-three-session-types-and-competitor-research.md) | Three session types; competitor research; weekly stats loop |
| [0008](docs/adr/0008-code-drawn-graphics-template-library.md) | Code-drawn graphics: per-brand template library plus bespoke graphics |

## Current state (2026-10-10)

- Working pipeline for one brand and one format, built on Windows, in `pipeline/`:
  - `prep.py`: faster-whisper large-v3 (CPU, int8) with onset snapping, take cuts, Robust Video Matting
    (mobilenetv3, CPU) person matte, subject track, 1 fps contact sheet.
  - Subtitles: HTML/CSS overlay (`overlay.html`) rendered to a transparent PNG sequence by headless Chrome
    through Playwright; automatic layout solver with text-behind-subject (`build_timeline.py`).
  - Camera moves, freezes, flashes (`camera.py`, `video_pass.py`); SFX + music mix normalised to -14 LUFS
    (`audio.py`); H.264 1080×1920 output via ffmpeg.
- The TOSUMI style is hard-coded in `docs/STYLE.md` and `pipeline/style_default.json`. The skill
  `.claude/skills/reel-subtitles/` is the TOSUMI-specific v0 and will be generalised.
- One finished reel: `projects/tosumi_hair/` (renders and build files are not in git).
- No hard-coded Windows paths in the code. Requires ffmpeg, Google Chrome and the Python deps in
  `pipeline/requirements.txt`.
- Reference for the code-drawn graphics style the developer wants available:
  `docs/references/claude_unity_sheet.jpg` — contact sheet of a 103 s fully code-generated explainer
  (kinetic type, timer, UI mock-ups, wireframe 3D, terminal typing, waveform, glitch, phone mock-up, diagrams,
  particles). The original mp4 is not in the repo.

## Environment

- Development: the developer's Mac M3 Pro (moving off Windows).
- Creator: Mac M1 8 GB; the developer's work laptop is available to her as well. Hardware and speed are not
  constraints (ADR-0005).
- Finishing editor: DaVinci Resolve (free). Final Cut Pro is bought only if DaVinci does not work out.
- Creator's Claude plan: decided by measuring real batches; Max is acceptable.
- Distribution: private GitHub repository; the creator's machine pulls updates.

## Roadmap (agreed order)

1. Move the repo to the Mac and port the pipeline: Homebrew ffmpeg (VideoToolbox, ProRes), Chrome, Python env.
   Keep whisper large-v3; consider RVM resnet50 on MPS for a cleaner matte — quality over speed.
2. Spike: what DaVinci Resolve imports from FCPXML (alpha ProRes 4444 clips, audio levels, transform
   keyframes, still/freeze clips). Anything it drops gets baked into intermediate media.
3. Refactor: TOSUMI style into `brands/tosumi/brand.json`, the skit into `formats/skit-hoche-a/`, universal
   grammar separated from both. Prove the split by onboarding a second brand.
4. «стоп» take cutter; HDR→SDR tone-mapping as a safety net.
5. Exports: draft MP4, editable project (FCPXML), no-music variant, hook variants.
6. Graphic template library (first 5–6 templates) on the same HTML renderer as subtitles.
7. Brief template and a `/reel` command for the creator; learned-rules loop; draft self-review pass.
8. Research & pre-production session: competitor research, idea bank, hooks, scripts, shot lists.
9. Results review session: weekly insights screenshots → per-brand "what worked" notes.
10. Onboard the remaining brands (brand books collected later) and formats as they appear.

## Open questions

- Brand list and brand books — to be collected later.
- Starter competitor list per brand/niche — the creator provides it, research expands it.
- Which Claude plan the creator needs — measure on real batches.
