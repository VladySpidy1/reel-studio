# Reel Studio

Turns raw phone footage into finished Instagram reels for brands (TOSUMI, YOCASE). `CONTEXT.md` describes the
project and its glossary, `docs/adr/` the decisions, `.claude/skills/` how reels are made, `INSTALL.md` the setup.

## Who is at the keyboard

Two people use this repository, each on their own Mac:

- **Developer mode, the default.** Vladyslav builds and maintains the studio and has full rights here; the creator
  rules below do not apply to him. Reply to him in Russian. Code, comments, docs and commit messages stay in
  English; text shown on screen in a reel is Ukrainian.
- **Creator mode.** Marina makes reels and does not program. It is on only when `CLAUDE.local.md` (loaded after
  this file, never tracked, installed on her Mac only from `docs/creator/CLAUDE.local.template.md`) has the line
  `Mode: creator`. Then follow "Creator mode" below for the whole session and reply in Ukrainian. The language of a
  message never switches the mode.

## Map

- Tracked: `pipeline/` (run every script as `.venv/bin/python pipeline/<script>.py` from the repo root),
  `brands/` and `formats/` (a reel = brand look x format rules, ADR-0002), `projects/` (the developer's example
  reels), `assets/` (fonts, music, SFX), `docs/`, `.claude/`.
- Gitignored, per machine: `inbox/<reel>/` (a creator reel: `brief.md`, her clips, `inserts/`, `script.json`),
  `done/<reel>/` (archived reels, never deleted), `build/` (prep outputs, `build/<reel>/logs/`, the single build
  slot), `output/` (MP4s, `<name>.report.json`), `learned/` (her corrections; only `learned/README.md` is tracked),
  `brands/<b>/local/` and `assets/local/` (licensed or her own files, copied in person), `исходники/`.
- Creator tools: `pipeline/doctor.py` (health and preflight), `pipeline/inbox.py` (reel folders: new, prep,
  archive, reopen), `pipeline/cleanup.py` (frees disk after a reel), `pipeline/brief.py` (reads `brief.md`;
  `lint_edit.py` checks a reel's script against the brief next to it).
- Skills: `reel` (the creator flow from brief to final, with `brief.md` and the Ukrainian `report.uk.md`; the
  report reads `output/<name>.report.json`), `reel-videographer` (the picture), `reel-subtitles` (a reference for
  commands, markup and fixes; only `/reel-subtitles` loads it, the model never does).
- One heavy job at a time: renders, prep and export hold the studio lock; "studio busy" (exit 2) means wait and
  retry. Checks render with `build.py --draft`.

## Creator mode

Talk to Marina in Ukrainian and in plain words: no paths, commands, script names or jargon. Never ask her to run a
command or to open Terminal. The `reel` skill drives each reel («змонтуй», «зроби рілс», «новий рілс», /reel);
`docs/creator/brief_template.uk.md` is her brief.

**Health**
- Run `.venv/bin/python pipeline/doctor.py` at the start of every reel, and `doctor.py --full` after an update.
  On a FAIL: tell her in one plain sentence what is wrong, run `doctor.py --report`, show the file with
  `open -R output/developer_report.txt`, and stop: «Я не можу це виправити сама. Надішли Владу файл
  developer_report.txt (я показала його у Finder).»
- If `.venv/bin/python` itself is missing, run `git rev-parse --git-dir --git-common-dir`. Two different paths
  mean the session runs in a worktree: «Відкрий нову сесію в папці reel-studio». Otherwise setup is missing: Vlad.
- A brand without a folder in `brands/` stops the reel: «Цей бренд ще не налаштований — це робить Влад».
- Outside a reel: «перевір студію» -> `doctor.py --full`; «звіт для Влада» -> `doctor.py --report`, then
  `open -R output/developer_report.txt`.

**What you may change**
- Write only into `inbox/`, `build/`, `output/` and `learned/`, by hand or through the pipeline scripts. Never edit
  a tracked file (`pipeline/`, `brands/`, `formats/`, `projects/`, `docs/`, `assets/`, `.claude/`, this file). If a
  fix needs code, say so plainly and stop: that is Vlad's work.
- A reel's script is JSON (`inbox/<reel>/script.json`). Never write Python, shell scripts or HTML for a reel.
- Never run brew, sudo, `setup_mac.sh`, pip, uv, curl, rm, or git other than `git pull --ff-only`. Update only when
  she asks («онови студію») and never in the middle of a reel: `git pull --ff-only`, then `doctor.py --full`.
- Work in the main `reel-studio` folder, never in a worktree.

**Exact command forms.** The permission rules match the command text; any other form makes her approve a prompt
she cannot judge.
- `.venv/bin/python pipeline/<script>.py ...` from the repo root: no `cd`, no quotes around paths, no absolute
  interpreter path, no `NAME=value` prefix (`build.py --draft` instead of `X264_PRESET=...`), no `python -c`, no
  raw `ffmpeg`/`ffprobe`, no `&&` chains.
- Show results with `open output/<reel>_draft.mp4` (or `<reel>.mp4`), a file with `open -R <path>`, a reel folder
  with `open inbox/<reel>/` (with the trailing slash).
- Reel ids are ASCII (`inbox.py new` makes them), so paths never need quotes.

**Tokens and long steps**
- One reel per session: between reels she opens a new session (or `/clear`).
- Prep, builds and exports run with `run_in_background: true` and their output redirected to
  `build/<reel>/logs/run_<step>.log` (the scripts keep their own full log next to it). End the turn; you are woken
  when the command exits. Never Monitor or `sleep` for them. Read only the last lines of a log (`tail -n 20`);
  «ну що там?» is answered from `tail -n 5`.
- Look at each image once: never read the same sheet or frame again in a session; to look closer, make a crop.
- No subagents and no workflows (her settings deny them).
- Read long skill files by section (find the heading, read those lines), never whole; the videographer playbook
  only by section.
- During long steps: Claude stays open, the Mac on power, the lid open.

**Corrections.** When a correction sounds general, ask «Запам'ятати це для всіх рілсів <бренду>?». On «так»,
append it to `learned/brands/<brand>.md` (or `learned/formats/<format>.md`, `learned/general.md`) in the format of
`learned/README.md`. Auto memory is off on her Mac; `learned/` is the only memory.

**When a reel is done** («готово», «опублікувала»): `inbox.py archive <reel>`, then `cleanup.py plan <reel>`, ask
«Звільнити N ГБ?», and on «так» `cleanup.py apply` (her one approval click). A fix for an archived reel starts with
`inbox.py reopen <reel>`.

## Developer mode

- `main` is what Marina pulls: everything on `main` must work on her M1 with 8 GB and macOS 14 or newer. Never
  rewrite `main`'s history.
- Run `.venv/bin/python pipeline/selftest.py` before every push.
- A change to `pipeline/requirements.lock.txt` needs setup on her Mac in person; her doctor FAILs on the lock stamp
  until then.
- Never commit anything under `learned/` (except its README), `inbox/`, `done/`, `build/` or `output/`: her next
  pull would silently replace her ignored file with the committed one. selftest guards this.
- Her learned rules reach you in `output/developer_report.txt` (`doctor.py --report`) or on a visit. Promote a rule
  by hand into the brand's or format's tracked files, then delete the entry from her `learned/` file.
- The repository is public: no secrets or tokens, no client footage, no licensed fonts, logos or brand photos
  (`brands/<b>/local/`), and never the third-party skill file.
- Tracked `.claude/settings.json` holds allow rules only, safe for both machines; her deny and ask rules live in
  `docs/creator/claude-settings.local.json`, which `INSTALL.md` copies to `.claude/settings.local.json` on her Mac.
