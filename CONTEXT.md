# Reel Studio — project context

## What this is

A Claude Code toolkit that turns raw phone footage into finished Instagram/TikTok reels for a creator who
works for 2–3 brands. It started as a one-off pipeline for a single TOSUMI reel (Oct 2026) and is now being
generalised into a multi-brand, multi-format tool. Design decisions were settled in a debate on 2026-10-10;
see `docs/adr/`.

## People

- **Creator** (the developer's wife): actress and social-media creator. Shoots and edits ~30 reels a month for
  2–3 brands, in sessions of 5–10 reels, 3–5 sessions a month. Edits in CapCut today, is not technical, works
  in Ukrainian. Uses the Claude desktop app, never a terminal. Brands review her videos occasionally. Since
  2026-10-28 she also changes the studio with her own Claude, with the same rights as the developer (ADR-0010).
- **Developer**: built the toolkit and keeps developing it on his own Claude account. Both Macs commit and push to
  `main`; `CLAUDE.md` only switches the language and how much Claude explains.

## Goal

Reels that beat competitors who edit by hand. **Quality first, cost second, speed does not matter** — a batch
rendering overnight is fine. Model effort goes to taste (ideas, hooks, review, graphics), deterministic code
handles mechanics (ADR-0001).

## Glossary

- **Brand** — a client the creator makes reels for. Defines how a reel *looks*: fonts, colours, subtitle
  animation, grade/LUT, music mood, SFX palette, logo and CTA, tone of voice, prohibitions, learned rules.
  Lives in `brands/<brand>/`.
- **Format** — a genre of reel: skit ("хоче X, а Y"), tutorial, before/after, GRWM, review, unboxing, etc.
  Defines how a reel is *cut*: structure, pacing, hook, where freezes and product holds go.
  Lives in `formats/<format>/`.
- **Universal grammar** — editing rules that apply to any talking reel regardless of format: hook, silence
  cleanup, subtitles, accent words, punch-ins, SFX.
- **Brief** — what the creator gives per reel: brand, format, idea, hook, code word, music, censorship, inserts,
  optional reference. A Ukrainian `brief.md` next to the reel's script (template `docs/creator/brief_template.uk.md`);
  `lint_edit.py` checks the script against it (`brief.py`).
- **Take (дубль)** — one attempt at a line. A failed take ends with the creator saying **«стоп»** (shooting
  protocol, ADR-0006); `trim.py` drops attempts that end in «стоп», proposes dropping repeated ones (the last
  complete take stays) and cuts the dead air.
- **Timeline** — the single source of truth for one reel: its script, `inbox/<reel>/script.json` for a creator reel
  (`done/<reel>/` once archived), `projects/<name>/script.json` for the developer's examples. Every export is
  generated from it (ADR-0003).
- **Reel id** — the ASCII name of a creator reel, `<brand>_<yymmdd>_<title in Latin>` (`inbox.py new`), shared by
  its folders in `inbox/` or `done/`, `build/` and its outputs.
- **Screen / block** — subtitle units: one screen per take, blocks of 2–4-word lines inside it.
- **Accent word** — the one punch word per half-sentence, rendered in the brand's accent style.
- **Graphic template** — a parametric, code-drawn motion-graphics element of a brand (product callout, list
  cards, counter, before/after wipe, CTA end card, …). Designed once, filled with text/numbers/timings per reel.
- **Bespoke graphic** — a one-off code-drawn graphic made for a specific idea; promoted to a template if it
  works (ADR-0008).
- **Intermediate media** — colour-normalised video (white balance matched across takes, brand grade), 1080×1920
  ProRes, shared by every export so the MP4 and the editable project look identical. HDR clips are refused at
  ingest (`ingest.py`); there is no HDR→SDR tone-map yet.
- **Draft** — a fast preview render for review (`build.py --draft`: x264 veryfast, `output/<reel>_draft.mp4`).
- **Final** — the reel ready to post (`build.py` without `--draft`: `output/<reel>.mp4`), rendered with its
  no-music variant once the draft is approved.
- **Report** — what the creator reads after each render: the Ukrainian template of the `reel` skill
  (`.claude/skills/reel/report.uk.md`) filled from `output/<name>.report.json` (lengths, removed time, music,
  text, inserts, checks).
- **Build slot** — `build/meta.json`, `timeline.json`, `camera.json` and `overlay/`: one reel's laid-out state at a
  time. Renders, review and export of a reel run against the slot its last build filled, and refuse another reel's.
- **Studio lock** — one heavy job at a time (prep, build, export) across sessions; a second one exits 2
  ("studio busy").
- **Insert** — a picture or clip the creator supplies, shown as a card over the picture or full-screen, on the
  phrase she names (ADR-0009).
- **Editable project** — FCPXML timeline plus per-element media (subtitle blocks and graphics as alpha
  ProRes 4444 clips, SFX, music, zoom keyframes) for finishing in DaVinci Resolve (ADR-0004).
- **No-music variant** — export with SFX but no music bed, so a trending Instagram sound can be added in the
  app at posting time (in-app sounds cannot be baked in).
- **Hook variants** — 2–3 alternative openings rendered from the same timeline, for Instagram trial reels.
- **Session types** — Research & pre-production, Batch edit, Results review (ADR-0007).
- **Learned rules** — corrections from reels, appended to the tracked `learned/` (`general.md`,
  `brands/<brand>.md`, `formats/<format>.md`) and committed, so the next reel on either Mac does not repeat the
  mistake; the `reel` skill reads them before writing a script, and rules that hold are folded into `brands/` or
  `formats/`.
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
| [0009](docs/adr/0009-raster-inserts-outside-the-matte.md) | Raster inserts and brand image layers are Python layers outside the person matte |
| [0010](docs/adr/0010-both-people-develop-the-studio.md) | Both people develop the studio with the same rights; only the language differs |

## Current state (2026-10-21)

- Pipeline in `pipeline/`, ported to macOS / Apple Silicon (roadmap step 1 done; `setup_mac.sh`, locked deps in
  `requirements.lock.txt`, run everything with `.venv/bin/python`):
  - `ingest.py`: raw phone clips (4K HEVC, rotation, VFR) -> 1080×1920 30 fps ProRes 422 HQ intermediates with
    sample-exact audio, joined by `source.ffconcat` (the reel's source; clip boundaries are the cuts).
  - `prep.py`: faster-whisper large-v3 run per Silero-VAD speech chunk (whole-clip decoding silently dropped
    repeated takes and hallucinated «Дякую за перегляд» on noise), float32 with 16 GB RAM / int8 with 8 GB,
    onset snapping; Robust Video Matting resnet50 on MPS (~36 fps); subject track; contact sheet.
  - Subtitles: HTML/CSS overlay (`overlay.html`) rendered to a transparent PNG sequence by headless Chrome
    through Playwright; automatic layout solver with text-behind-subject (`build_timeline.py`).
  - Virtual camera (`camera.py`, `video_pass.py`): creeps, A/B framing, anchored punches, freezes, flashes, and
    gesture transitions - swipe-whip (`push`, two-layer composite with roll), `zoom_through`, `spin` - with a true
    sub-frame motion-blur shutter. `motion.py` finds sweeps and pushes-to-lens in the footage (`motion.json`),
    `beats.py` the music's beat phase and moves cuts onto beats. SFX + music mix normalised to -14 LUFS
    (`audio.py`); voice can be laid independently of the picture (`audio.voice_over`, `audio.mute`); H.264
    1080×1920 output via ffmpeg.
  - Editing craft: `.claude/skills/reel-videographer/` (researched playbook: effects with frame timings, format
    and universal grammar; effect -> script table; learned rules), `lint_edit.py` checks a script against it,
    `contact_sheet.py` makes labelled sheets for watching footage and drafts. First format file:
    `formats/product-lineup/FORMAT.md`.
  - `export_fcpxml.py`: editable project (FCPXML 1.10 + self-contained media folder). Roadmap step 2 done:
    DaVinci Resolve imports it (alpha clips, levels, transform keyframes, baked transitions and holds) and
    renders within ~37 dB median PSNR of ours (`resolve_check.py` + `compare_render.py`); only cut-in zoom blur,
    shakes and the limiter are not reproduced.
- Fixed while porting: picture lagged sound by a frame after most EDL cuts (ffmpeg rawvideo seek), and EDL
  times between frames made the picture repeat/skip frames; both affected the Windows renders too.
- Brands and formats are data (2026-10-20, roadmap step 3): `brands/<brand>/` (`brand.json` + `BRAND.md`) and
  `formats/<format>/` (`format.json` + `FORMAT.md` + `template.json`). `pipeline/resolve.py` resolves every script
  studio → brand → format → script for all entry points; a script without a brand keeps the studio look, which
  is TOSUMI's (`pipeline/style_default.json`). Brands: TOSUMI, YOCASE. Formats: talking-head, subtitles-only,
  skit-hoche-a, product-lineup. `docs/STYLE.md` is the universal subtitle system.
- Content studio (2026-10-21, design in `docs/superpowers/specs/2026-10-20-content-studio/`; roadmap 7 done, the
  «стоп» cutter of roadmap 4 is part of trim; HDR tone-mapping still is not built):
  - Creator flow: the `/reel` skill (`.claude/skills/reel/`: brief -> prep -> template -> trim -> times -> screens,
    inserts, CTA -> lint -> draft -> self-review -> Ukrainian report -> final + no-music -> archive), her brief
    checked by lint, `learned/` for corrections (shared through git since 2026-10-28). `reel-subtitles` is now a reference the model never loads on
    its own. Tools: `doctor.py`, `inbox.py`, `cleanup.py`, `brief.py`, `selftest.py`; one heavy job at a time
    (studio lock); compact terminal output with full logs in `build/<reel>/logs/`; review images at most 1200 px.
  - Text: asterisk censorship, Latin brand words aligned to the transcript (`terms`), hook and CTA presets (the CTA
    card pops with a chime on the spoken phrase), blocks drawn in front of her, pre-render checks (glyphs, safe
    area, overlaps, face, contrast) that FAIL before the render.
  - Audio and timing: `trim.py` (dead air, retakes, «стоп»), keyframed music ducking under the voice, music by
    name (`assets.py`), optional speed-up at ingest, missing sounds skipped and reported.
  - Inserts: pictures and clips as cards or full-screen on a heard phrase, with their sound; brand layers.
  - Every render writes `output/<name>.report.json`, which the Ukrainian report reads.
- Not verified yet: the install on the creator's M1 8 GB Mac (INSTALL.md), and how many tokens a creator-flow reel
  costs against the 2026-10-13 baseline (~6M cache-read tokens per subtitles-only reel).
- Reels: `projects/tosumi_hair/` (finished, Windows; its inputs are gone, it no longer renders) and
  `projects/yocase_line/` — second brand (YOCASE, 4 shampoos), raw iPhone clips; v4 cut with the videographer skill
  (`make_script.py` generates its script; its close-up callouts were moved inside the IG crop-safe area on
  2026-10-21). Its hook (phone mock-up with the creator cut out, from a reference reel) is the next graphic to
  build. Renders, footage and build files are not in git.
- 2026-10-13: three already-edited YOCASE videos got subtitles only (`projects/yocase_2371`, `yocase_2373`,
  `yocase_2477`): comfortable YOCASE spacing, baked graphics excluded, and the IG crop-safe area (x 128-952,
  y 250-1480) after text was cut off on a real phone.
- Reference for the code-drawn graphics style the developer wants available:
  `docs/references/claude_unity_sheet.jpg` — contact sheet of a 103 s fully code-generated explainer
  (kinetic type, timer, UI mock-ups, wireframe 3D, terminal typing, waveform, glitch, phone mock-up, diagrams,
  particles). The original mp4 is not in the repo.

## Environment

- Development: the developer's Mac M2 Pro 16 GB, macOS 26, Homebrew ffmpeg 9.0.2 (no zscale/libplacebo: HDR
  tone-mapping needs another route), Python 3.12.
- Creator: Mac M1 8 GB; the developer's work laptop is available to her as well. Hardware and speed are not
  constraints (ADR-0005).
- Finishing editor: DaVinci Resolve (free). Final Cut Pro is bought only if DaVinci does not work out. The dev
  Mac runs the free 21.0.4 build from the Blackmagic website (the App Store build cannot be scripted). Free
  Resolve refuses external scripting, so `resolve_bridge.lua`, started by hand from Workspace > Scripts, takes
  Lua from `resolve_client.py` through files; `resolve_check.py` imports, renders and compares automatically.
  CapCut desktop re-checked on 2026-10-10: still no timeline import; its brand-work terms are a further reason
  not to target it.
- Creator's Claude plan: decided by measuring real batches; Max is acceptable.
- Distribution: public GitHub repository; the creator's machine pulls updates. No secrets, keys, brand books or
  licensed assets in git: licensed brand fonts, logos and photos live in the gitignored `brands/<brand>/local/`
  and are copied to her Mac in person.

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
