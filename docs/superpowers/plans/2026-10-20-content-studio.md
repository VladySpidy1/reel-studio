# Content studio: implementation plan (2026-10-20)

Spec: `docs/superpowers/specs/2026-10-20-content-studio/` (start with `00-decisions.md`, then `integration.md`).
The phases, files, dependencies and gates are those of `integration.md` § Phases, with the changes listed here.
Every phase ends with local commits on `main` (explicit pathspecs, never `git add -A` while another phase runs)
and with a plain `projects/yocase_2373/script.json` draft so the shared build slot holds 2373 again.

Baselines (from HEAD `b910950`, `X264_PRESET=veryfast`): `output/base_yocase_2373.mp4`,
`output/base_yocase_line.mp4`, `/private/tmp/claude-501/baseline/{timeline_2373.json, meta_2373.json,
timeline_line.json, camera_line.json, build.log}`. Golden lint/times/filter outputs go to
`/private/tmp/claude-501/golden/` at the start of Phase 1. Each phase re-baselines on the previous phase's
accepted outputs (`output/p<N>_2373_draft.mp4`).

| Phase | Content | Depends on | Parallel |
|---|---|---|---|
| 0 | Working tree committed (`b910950`), baselines rendered | none | done |
| 1 | Shared plumbing (integration.md Phase 1) **plus token economy:** compact default output with `--verbose`, logs under `build/<id>/logs/`, `review_frames.py` / `contact_sheet.py` long edge ≤ 1200 px by default | 0 | no |
| 2 | Brands and formats resolver, brand/format data, templates, doc conflict fixes (integration.md Phase 2, learned layer simplified per 00-decisions.md) | 1 | code ∥ data inside the phase |
| 3 | Behaviour-neutral seams (integration.md Phase 3) | 2 | no |
| 4a | Text layer: censorship, terms, hook/CTA presets, front layer, glyph check, checks | 3 | ∥ 4c, 4d |
| 4b | Audio and timing: `trim.py`, ducking, music selection, SFX robustness, speed, report.json sections | 4a (shares `export_fcpxml.py`, `build.py`) | ∥ 4c, 4d |
| 4c | Creator tools: `doctor.py`, `inbox.py`, `cleanup.py`, `brief.py` parse, `selftest.py`, `CLAUDE.md` (with the token rules), `.claude/settings.json`, `INSTALL.md`, `README.uk.md`, `learned/README.md`, `.gitignore` | 3 | ∥ 4a, 4b, 4d |
| 4d | Inserts pure modules: `inserts.py`, `layers.py` | 3 | ∥ 4a, 4b, 4c |
| 5 | Inserts integration: placement, compositor slots, FCPXML lanes, lint | 4a, 4b, 4d | no |
| 6 | `/reel` skill, `brief.check`, skill/doc finalisation, end-to-end creator-flow test on `inbox/t2373`, fresh-clone check, token measurement of one creator-flow reel | all | docs during 5 |

Gate rules (all phases):
- The phase's gate in `integration.md` § Phases passes, run by an independent verifier.
- Old projects (`yocase_2371`, `yocase_2373`, `yocase_2477`, `yocase_line`) render and lint as before except for
  the documented, intended differences.
- No push. No edits to `исходники/`, `assets/**/*.wav`, `output/yocase_*` or `output/base_*`.
- Test renders other than the phase reference are deleted at the end of the phase (disk is ~18 GiB free).
