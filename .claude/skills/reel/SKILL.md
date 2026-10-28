---
name: reel
description: Make a brand reel (TOSUMI, YOCASE) from the creator's phone footage and her Ukrainian brief, end to end - reel folder, prep, trim, script with hook, CTA and inserts, draft, self-review, Ukrainian report, final, archive. Use when she writes «змонтуй», «зроби рілс», «новий рілс», «рілс для …», «ось бриф» / «ось ТЗ», pastes a brief (БРЕНД:, ХУК:, КОДОВЕ СЛОВО:), says «файли там», corrects a draft, says «фінал», «готово», «правка до рілса …», or types /reel.
argument-hint: "[бриф або назва рілса]"
---

# Reel: the creator flow

Talk to the person at the keyboard as CLAUDE.md "Who is at the keyboard" says (to Marina: Ukrainian, plain words,
no commands or paths). `<reel>`
is the id `inbox.py new` prints (ASCII). Run each command from the repo root exactly as written, on one line: the
permission rules match the text.

Read these only when a step needs them, by section, never twice:
- `.claude/skills/reel/brief.md`: her brief and her corrections -> script keys (step 3.8, corrections).
- `.claude/skills/reel/report.uk.md`: the report (step 4.4, the final).
- `.claude/skills/reel-subtitles/SKILL.md`: subtitle markup, layout, how to fix a lint or build finding.
- `brands/<brand>/BRAND.md`, `formats/<format>/FORMAT.md`; the `reel-videographer` skill for the picture of a reel
  with movement or products.

**Tokens.** One command per stage, the ones below. A step marked (bg) runs with `run_in_background: true`, its output
redirected to `build/<reel>/logs/run_<step>.log`: tell her what is happening, end the turn, and when you are woken
read only `tail -n 20` of that log. Look at each image once; to look closer, make a sheet of just the short stretch in
doubt. No subagents, no workflows, no Monitor, no `sleep`.

## 1. New reel («новий рілс для YOCASE: …», /reel, a pasted brief)
1. `.venv/bin/python pipeline/doctor.py`. A FAIL: CLAUDE.md "Health", stop.
2. The brand from her words; `.venv/bin/python pipeline/resolve.py --list` lists the ids and aliases. None given: ask
   only «Для якого бренду цей рілс — TOSUMI чи YOCASE?». Not in the list: offer to set the brand up first
   (`brands/<id>/brand.json` and `BRAND.md`, like `brands/yocase/`), then continue.
3. `.venv/bin/python pipeline/inbox.py new <brand> <title words>` prints `<reel>`; then `open inbox/<reel>/`.
4. A brief she pasted in chat: write it into `inbox/<reel>/brief.md` as labelled lines (БРЕНД:, ХУК:, …).
5. Say «Перетягни сюди відео з телефона, а картинки й відео для вставок — у папку inserts. Бриф напиши тут або у
   файлі brief.md у цій папці. Коли все там — напиши «файли там».», end the turn.

## 2. Footage («файли там»)
1. `.venv/bin/python pipeline/brief.py inbox/<reel>/brief.md`: the brief as JSON. Keep it; don't re-read brief.md.
2. `.venv/bin/python pipeline/doctor.py --clips inbox/<reel>/` (plus `--speed k` for an allowed ШВИДКІСТЬ,
   brief.md). HDR, no videos, no disk: tell her its hint in plain words, stop.
3. (bg), with the same `--speed k` if any:
   ```
   .venv/bin/python pipeline/inbox.py prep <reel> > build/<reel>/logs/run_prep.log 2>&1
   ```
   Say «Готую відео, це приблизно N хв. Не закривай Claude і не вимикай Мак.», N = 3 x the raw minutes, at least 3.

## 3. Script (woken after prep)
1. `tail -n 20 build/<reel>/logs/run_prep.log`. A failure: CLAUDE.md "Health".
2. Watch the footage once: `<dur>` = `duration` in `build/<reel>/cuts.json`, `<step>` = `<dur>` / 40 rounded up
   to 0.5:
   ```
   .venv/bin/python pipeline/contact_sheet.py build/<reel>/source.ffconcat 0 <dur> <step> --words build/<reel>/words.json
   ```
   Baked-in graphics (logo, insets, chat bubble): format `subtitles-only`, reported. Otherwise the brief's format,
   by default `talking-head`.
3. Learned rules: read `learned/general.md`, `learned/brands/<brand>.md` and `learned/formats/<format>.md` where they
   exist. They win over the defaults below.
4. Skeleton: read `formats/<format>/template.json` and write `inbox/<reel>/script.json` from it: `"brand"`, `NAME` ->
   `<reel>` in the four paths, `"src_duration": <dur>`. Subtitles-only also gets `"takes": [[0, <dur>]]` and
   `"edl": [{"src": [0, <dur>]}]`.
5. Trim (talking-head only): `.venv/bin/python pipeline/trim.py inbox/<reel>/script.json`. It prints the attempts,
   a contact-sheet command per group of repeated takes, and the product moments the cut would lose: run each sheet
   command it printed and look once. It keeps the last complete take; change that only when a frame shows an earlier
   one is better (`trim.drop`, reported). Save a product moment with `trim.keep`, a deliberate pause with
   `trim.punch`. Then `.venv/bin/python pipeline/trim.py inbox/<reel>/script.json --write`. "constant bed" (music
   or noise under her voice, or an edited video): no trim; `takes` and `edl` cover the whole source as for
   subtitles-only, and the report says so.
6. `.venv/bin/python pipeline/times.py inbox/<reel>/script.json`: what is heard in output time (brand words as
   whisper heard them until a screen types them), `CTA spoken`, gestures. From here every time in the script is
   an output time; copy phrases from this transcript.
7. Inserts (files in `inbox/<reel>/inserts/`): `.venv/bin/python pipeline/inserts.py inbox/<reel>/script.json`, then
   open every `view/*.jpg` it lists, once each.
8. Write the rest by brief.md: screens with the hook, the CTA, inserts, music, censorship; camera and sfx by
   `reel-videographer` when the footage moves or shows products.
9. `.venv/bin/python pipeline/lint_edit.py inbox/<reel>/script.json`: 0 FAIL (its `brief:` lines check the script
   against her brief). Then `.venv/bin/python pipeline/doctor.py --script inbox/<reel>/script.json`: no FAIL.

## 4. Draft
1. (bg) «Роблю чернетку, це кілька хвилин.»
   ```
   .venv/bin/python pipeline/build.py inbox/<reel>/script.json --draft > build/<reel>/logs/run_draft.log 2>&1
   ```
2. Woken: `tail -n 20 build/<reel>/logs/run_draft.log`; problems come first, `[video] rc=0` is the line before the
   last (`log: …`). A check FAIL stops the build before the render: fix the script, lint, draft again.
3. Review, each image once: `.venv/bin/python pipeline/review_frames.py output/<reel>_draft.mp4` (a tile per screen
   and insert), then `.venv/bin/python pipeline/contact_sheet.py output/<reel>_draft.mp4 0 <out_s> 0.3 --phone`
   (`out_s` from `output/<reel>_draft.report.json`, which the report reads anyway). Look for text over her face or a
   label, clipped or overlapping text, text past the phone lines, junk frames, an insert that does not prove its
   phrase, and each `no free spot` block.
4. At most one self-fix (edit, lint, (bg) draft, review). Then `open output/<reel>_draft.mp4` and the report
   (report.uk.md) from `output/<reel>_draft.report.json` (read it again only after a new render).

## 5. After the draft
- **Correction** in her words: edit the script (brief.md "Corrections"), lint, (bg) draft, review, report. When it
  sounds general, ask «Запам'ятати це для всіх рілсів <бренду>?»; on «так» append it to `learned/brands/<brand>.md`
  (or `learned/formats/<format>.md`, `learned/general.md`) as `learned/README.md` shows, and commit it.
- **«фінал» / «добре»**: the checklist below holds, then (bg) the final, and when woken (bg) the no-music version:
  ```
  .venv/bin/python pipeline/build.py inbox/<reel>/script.json > build/<reel>/logs/run_final.log 2>&1
  .venv/bin/python pipeline/build.py inbox/<reel>/script.json --skip-timeline --skip-overlay --no-music --name <reel>_no_music > build/<reel>/logs/run_no_music.log 2>&1
  ```
  Woken: `open output/<reel>.mp4` and the final report from `output/<reel>.report.json`.
- **«для DaVinci»** (only when asked, after the final of this reel and before any other build): (bg)
  ```
  .venv/bin/python pipeline/export_fcpxml.py inbox/<reel>/script.json > build/<reel>/logs/run_export.log 2>&1
  ```
  Woken: `open -R output/<reel>_project`.
- **«готово» / «опублікувала»**: `.venv/bin/python pipeline/inbox.py archive <reel>`, then
  `.venv/bin/python pipeline/cleanup.py plan <reel>`; ask «Звільнити N ГБ?»; on «так»
  `.venv/bin/python pipeline/cleanup.py apply` (her one approval click).
- **«правка до рілса …»**: `.venv/bin/python pipeline/inbox.py list` finds it; then (bg)
  `.venv/bin/python pipeline/inbox.py reopen <reel> > build/<reel>/logs/run_reopen.log 2>&1` («Відкрила рілс знову,
  роблю правку.»); woken, the correction loop.
- **«ну що там?»**: `tail -n 5` of the newest log in `build/<reel>/logs/`, one plain sentence.

## Before «фінал» (all must hold)
1. lint: 0 FAIL, the `brief:` lines included.
2. The draft's report: `checks.fail` is empty; each `no free spot` in `checks.warn` was seen on its review tile and
   goes under «Сумнівні рішення»; no brand word or spoken CTA is NOT FOUND (lint FAILs those).
3. `doctor.py --script`: no FAIL.
4. The review sheet and the 0.3 s `--phone` sheet are clean.
5. Every insert sounds unless she wrote «без звуку»; the music starts at frame 0 (lint warns otherwise).
