# Reel Studio

Turns raw phone footage into finished Instagram reels for brands (TOSUMI, YOCASE). `CONTEXT.md` describes the
project and its glossary, `docs/adr/` the decisions, `.claude/skills/` how reels are made, `INSTALL.md` the setup.

## Who is at the keyboard

Two people build and use this studio, each on their own Mac, with the same rights (ADR-0010): both make reels,
change any file, commit and push to `main`.

- **Vladyslav**, the default: reply in Russian.
- **Marina**, when `CLAUDE.local.md` (never tracked; on her Mac, installed from
  `docs/creator/CLAUDE.local.template.md`) has the line `Person: Marina` (an older file with `Mode: creator` means
  the same). Reply in Ukrainian and in plain words. She does not program and does not use Terminal: run every
  command yourself, never ask her to type one. When she wants the studio to work differently, change the code,
  scripts, skills or brand files for her; before committing, tell her in plain Ukrainian what you changed and show
  the effect (a draft, a frame), not the code, unless she asks for it.

Code, comments, docs and commit messages stay in English for both; text shown on screen in a reel is Ukrainian.

## Map

- Tracked: `pipeline/` (run every script as `.venv/bin/python pipeline/<script>.py` from the repo root),
  `brands/` and `formats/` (a reel = brand look x format rules, ADR-0002), `projects/` (example reels), `assets/`
  (fonts, music, SFX), `learned/` (rules learned from reels, shared by both Macs), `docs/`, `tests/`, `.claude/`.
- Gitignored, per machine: `inbox/<reel>/` (a reel in progress: `brief.md`, clips, `inserts/`, `script.json`),
  `done/<reel>/` (archived reels, never deleted), `build/` (prep outputs, `build/<reel>/logs/`, the single build
  slot), `output/` (MP4s, `<name>.report.json`), `brands/<b>/local/` and `assets/local/` (licensed or own files,
  copied in person), `исходники/`, `CLAUDE.local.md`, `.claude/settings.local.json`.
- Reel tools: `pipeline/doctor.py` (health and preflight), `pipeline/inbox.py` (reel folders: new, prep, archive,
  reopen), `pipeline/cleanup.py` (frees disk after a reel), `pipeline/brief.py` (reads `brief.md`; `lint_edit.py`
  checks a reel's script against the brief next to it).
- Skills: `reel` (a reel from brief to final, with `brief.md` and the Ukrainian `report.uk.md`; the report reads
  `output/<name>.report.json`), `reel-videographer` (the picture), `reel-subtitles` (a reference for commands,
  markup and fixes; only `/reel-subtitles` loads it, the model never does).
- One heavy job at a time: renders, prep and export hold the studio lock; "studio busy" (exit 2) means wait and
  retry. Checks render with `build.py --draft`.

## Changing the studio (both)

- Before a change: `git pull --rebase`. Work in the main `reel-studio` folder, not in a worktree (a worktree has
  no `.venv` and no `build/`).
- Before every push: `.venv/bin/python pipeline/selftest.py` and `.venv/bin/python -m unittest discover tests`; for
  a change to rendering, a draft of an example reel (`build.py projects/yocase_2373/script.json --draft --name
  check_2373`) looked at against the last good one. Push small commits; if the push is refused because the other
  person pushed, `git pull --rebase`, check again, push.
- `main` is what both Macs pull: it must work on Marina's M1 with 8 GB and macOS 14 or newer. Never rewrite
  `main`'s history (no force push).
- A change to `pipeline/requirements.lock.txt` (or to what `setup_mac.sh` installs) means both Macs re-run
  `zsh pipeline/setup_mac.sh` after pulling; doctor FAILs on the lock stamp until then. Say so in the commit message.
- Never commit `inbox/`, `done/`, `build/` or `output/` (per-machine; selftest guards this).
- The repository is public: no secrets or tokens, no client footage, no licensed fonts, logos or brand photos
  (`brands/<b>/local/`), and never the third-party skill file.
- Tracked `.claude/settings.json` holds shared allow rules only; personal settings go in each Mac's
  `.claude/settings.local.json`.

## Making a reel (both)

The `reel` skill drives each reel («змонтуй», «зроби рілс», «новий рілс», /reel);
`docs/creator/brief_template.uk.md` is the brief.

**Health**
- Run `.venv/bin/python pipeline/doctor.py` at the start of every reel, and `doctor.py --full` after a pull.
  On a FAIL, fix the cause (its message says how: re-run setup, copy a missing file, free disk). When stuck,
  `doctor.py --report` writes `output/developer_report.txt` to send to the other person (`open -R` shows it).
- If `.venv/bin/python` itself is missing, run `git rev-parse --git-dir --git-common-dir`. Two different paths
  mean the session runs in a worktree: open a new session in the `reel-studio` folder. Otherwise run
  `zsh pipeline/setup_mac.sh`.
- A brand without a folder in `brands/` needs one first: `brands/<id>/brand.json` and `BRAND.md`, like
  `brands/yocase/`.
- Outside a reel: «перевір студію» -> `doctor.py --full`; «звіт для Влада» -> `doctor.py --report`, then
  `open -R output/developer_report.txt`.

**Command forms.** The shared allow rules match the command text, so these forms run without a prompt:
`.venv/bin/python pipeline/<script>.py ...` from the repo root, with no `cd`, no quotes around paths, no absolute
interpreter path, no `NAME=value` prefix (`build.py --draft` instead of `X264_PRESET=...`), no `&&` chains. Show
results with `open output/<reel>_draft.mp4` (or `<reel>.mp4`), a file with `open -R <path>`, a reel folder with
`open inbox/<reel>/`. Reel ids are ASCII (`inbox.py new` makes them), so paths never need quotes. A reel's script is
JSON (`inbox/<reel>/script.json`); what a reel needs and the pipeline cannot do yet is a change to the studio
(above), not a one-off script.

**Tokens and long steps** (a reel costs tokens on every call, so keep each reel lean)
- One reel per session: a new session (or `/clear`) between reels.
- Prep, builds and exports run with `run_in_background: true` and their output redirected to
  `build/<reel>/logs/run_<step>.log` (the scripts keep their own full log next to it). End the turn; you are woken
  when the command exits. Never Monitor or `sleep` for them. Read only the last lines of a log (`tail -n 20`);
  «ну що там?» is answered from `tail -n 5`.
- Look at each image once: never read the same sheet or frame again in a session; to look closer, make a crop.
- No subagents and no workflows while making a reel.
- Read long skill files by section (find the heading, read those lines), never whole; the videographer playbook
  only by section.
- During long steps: Claude stays open, the Mac on power, the lid open.

**Corrections.** When a correction sounds general, ask («Запам'ятати це для всіх рілсів <бренду>?» to Marina).
On yes, append it to `learned/brands/<brand>.md` (or `learned/formats/<format>.md`, `learned/general.md`) in the
format of `learned/README.md` and commit it; it reaches the other Mac with the next push.

**When a reel is done** («готово», «опублікувала»): `inbox.py archive <reel>`, then `cleanup.py plan <reel>`, ask
«Звільнити N ГБ?», and on yes `cleanup.py apply` (it deletes files, so it is deliberately not in the allow rules). A
fix for an archived reel starts with `inbox.py reopen <reel>`.
