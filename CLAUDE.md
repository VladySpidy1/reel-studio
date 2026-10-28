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
  scripts, skills or brand files for her. Before committing, tell her in plain Ukrainian what you changed and show
  the effect (a draft, a frame), not the code unless she asks; commit and push only after her «так».

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

- Pull only between reels: a pull can bring a change that needs `setup_mac.sh`. With no reel in progress, start a
  change with `git pull --rebase`; during a reel, commit locally and pull and push after «готово».
- Work in the main `reel-studio` folder, not in a worktree (a worktree has no `.venv` and no `build/`).
- Before every push: `.venv/bin/python pipeline/selftest.py` and `.venv/bin/python -m unittest discover tests`.
  For a change to how reels look or sound, a draft before and after the change of a reel it affects: the reel in
  progress, the brand's latest reel (`inbox.py reopen` if archived), or the example `projects/yocase_2373` (its
  prep must exist in `build/yocase_2373/`, INSTALL.md step 12). Compare the two drafts by eye.
- Push with plain `git push`, small commits. Refused because the other person pushed: `git pull --rebase`, the
  checks again, push. A rebase conflict: keep both people's changes and run the checks; if the right merge is
  unclear, `git rebase --abort`, keep the commit local and say plainly whose change collides.
- `main` is what both Macs pull: it must work on Marina's M1 with 8 GB and macOS 14 or newer. Never rewrite
  `main`'s history (no force push).
- A change to `pipeline/requirements.lock.txt` (or to what `setup_mac.sh` installs) means both Macs re-run
  `zsh pipeline/setup_mac.sh` after pulling; doctor FAILs on the lock stamp until then. Say so in the commit message.
- Never commit `inbox/`, `done/`, `build/` or `output/` (per-machine; selftest guards this).
- The repository is public: no secrets or tokens, no client footage, no licensed fonts, logos or brand photos
  (`brands/<b>/local/`), no unreleased product details or client feedback, and never the third-party skill file.
- Tracked `.claude/settings.json` holds the shared allow rules and one ask rule (deleting files with
  `cleanup.py apply`); personal settings go in each Mac's `.claude/settings.local.json`.

## Making a reel (both)

The `reel` skill drives each reel («змонтуй», «зроби рілс», «новий рілс», /reel);
`docs/creator/brief_template.uk.md` is the brief.

**Health**
- Run `.venv/bin/python pipeline/doctor.py` at the start of every reel, and `doctor.py --full` after a pull.
  On a FAIL, fix the cause (its message says how: re-run setup, copy a missing file, free disk). Setup
  (`zsh pipeline/setup_mac.sh`) runs between reels, in the background with a log. When stuck, `doctor.py --report`
  writes `output/developer_report.txt` to send to the other person (`open -R` shows it).
- doctor's role line warns about the old creator restrictions on a Mac set up before 2026-10-28: those rules stop
  you from removing them. Tell Marina plainly that Vlad does a one-time step (INSTALL.md, "A Mac set up before
  2026-10-28"); never ask her to use Terminal.
- If `.venv/bin/python` itself is missing, run `git rev-parse --git-dir --git-common-dir`. Two different paths
  mean the session runs in a worktree: open a new session in the `reel-studio` folder. Otherwise run setup.
- A brand without a folder in `brands/` needs one first: `brands/<id>/brand.json` and `BRAND.md`, like
  `brands/yocase/`.
- Outside a reel: «перевір студію» -> `doctor.py --full`; «онови студію» -> `git pull --rebase`, `git push` if
  there are local commits, then `doctor.py --full`; «звіт для Влада» -> `doctor.py --report`, then
  `open -R output/developer_report.txt`.

**Command forms.** The shared allow rules match the command text, so these forms run without a prompt:
`.venv/bin/python pipeline/<script>.py ...` from the repo root, with no `cd`, no quotes around paths, no absolute
interpreter path, no `NAME=value` prefix (`build.py --draft` instead of `X264_PRESET=...`), no `&&` chains; git as
`git pull --rebase`, `git add <paths>`, `git commit -m ...`, plain `git push`. Show results with
`open output/<reel>_draft.mp4` (or `<reel>.mp4`), a file with `open -R <path>`, a reel folder with
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
On yes, it goes into the repository, never into Claude's auto memory (that stays on one Mac):
- a number of a brand's or format's look (subtitle size, colour, spacing, music level) is a studio change: edit
  `brands/<b>/brand.json` (TOSUMI's look too: never `pipeline/style_default.json`) or `formats/<f>/format.json`;
- anything else, a rule in words for whoever writes the next script: append it to `learned/brands/<brand>.md` (or
  `learned/formats/<format>.md`, `learned/general.md`) in the format of `learned/README.md`.

Commit it during the reel; it is pulled and pushed after «готово».

**When a reel is done** («готово», «опублікувала»): `inbox.py archive <reel>`, then `cleanup.py plan <reel>`, ask
«Звільнити N ГБ?», and on yes `cleanup.py apply` (an ask rule makes it prompt too). Then, if there are local
commits: `git pull --rebase`, selftest, `git push`. A fix for an archived reel starts with `inbox.py reopen <reel>`.
