# Installing the studio on Marina's Mac

The checklist for her Mac (M1, 8 GB), done in person. Every command runs in Terminal on her Mac unless it says
"dev Mac". Allow about half a day, most of it the smoke reel. Afterwards Marina has the same rights as Vlad
(ADR-0010): she makes reels and changes the studio with her own Claude, commits and pushes.

## Before the visit (dev Mac)

1. `main` is pushed and its commit passed `.venv/bin/python pipeline/selftest.py`.
2. A fresh clone works: `git clone https://github.com/VladySpidy1/reel-studio.git /private/tmp/rs-clone`, then
   `.venv/bin/python -m py_compile /private/tmp/rs-clone/pipeline/*.py` (the 3.12 interpreter, not
   `/usr/bin/python3`) and `.venv/bin/python /private/tmp/rs-clone/pipeline/selftest.py`. Delete the clone
   afterwards.
3. GitHub: Marina needs a GitHub account; invite it on github.com/VladySpidy1/reel-studio, Settings ->
   Collaborators, and let her accept the e-mail invitation (that is what lets her push).
4. Pack on a USB stick or for AirDrop:
   - `brands/*/local/` for every brand (licensed fonts, layers, permanent brand photos: never in git);
   - `исходники/IMG_2373.MOV` (40 MB) for the smoke reel;
   - optionally the model caches, which saves a 3 GB download: `~/.cache/huggingface/hub` (with `blobs/` and the
     symlinks: copy with `rsync -a`) and `~/.cache/torch/hub`.

## On her Mac

1. **macOS 14 or newer** (`sw_vers -productVersion`); update first if older, the locked wheels are
   `macosx_14_0_arm64`. At least 50 GB free (`df -h ~`).
2. **Command line tools:** `xcode-select --install` (brings git).
3. **Homebrew:** the installer from https://brew.sh (needs her admin password), then the two "Next steps" lines it
   prints, which add `brew shellenv` to `~/.zprofile`. Open a new Terminal window.
4. **The studio:** `git clone https://github.com/VladySpidy1/reel-studio.git ~/reel-studio`. Never move or rename
   the folder afterwards: the editable project uses absolute file paths.
5. **Model caches (optional):** `rsync -a <stick>/huggingface/hub/ ~/.cache/huggingface/hub/` and the same for
   `~/.cache/torch/hub/`.
6. **Setup:** `cd ~/reel-studio && zsh pipeline/setup_mac.sh`. It installs ffmpeg and uv with Homebrew, the locked
   Python packages into `.venv`, the Chromium that Playwright pins (the subtitle renderer; Google Chrome is not
   needed), and downloads the models. Safe to re-run.
7. **Files that are not in git:** copy each brand's `local/` folder to `~/reel-studio/brands/<brand>/local/`, and
   `IMG_2373.MOV` to `~/reel-studio/исходники/`.
8. **Who is at the keyboard:** `cp docs/creator/CLAUDE.local.template.md CLAUDE.local.md`. Its `Person: Marina`
   line makes Claude reply in Ukrainian, in plain words, and run every command itself (`CLAUDE.md`). It is
   gitignored. The template has another name on purpose: Claude Code loads any `CLAUDE.local.md` in a folder it
   touches, so a template under that name would switch Vlad's sessions to Ukrainian.
9. **Git and GitHub:** `brew install gh`, then `gh auth login` (GitHub.com, HTTPS, log in with a browser: Marina
   signs in to her own account) and `gh auth setup-git`. Then `git config --global user.name "Marina ..."` and
   `git config --global user.email <her GitHub e-mail>`.
10. **Claude desktop app:** install it from https://claude.ai/download and let Marina sign in to her own account.
    Code tab, choose the folder `~/reel-studio`:
    - accept the workspace-trust dialog (the shared allow rules apply only after it);
    - sessions must run in the folder itself, not in a worktree;
    - the permission mode is hers to choose, as on Vlad's Mac (Auto asks the least).
11. **Health check:** in her app write «перевір студію». Claude runs `.venv/bin/python pipeline/doctor.py --full`:
    no FAIL; every line OK except at most a disk WARN (it warns under 15 GB free); ffmpeg at
    `/opt/homebrew/bin/ffmpeg`; the role line "Marina's Mac (CLAUDE.local.md)".
12. **Smoke reel:** with Marina at the keyboard, «новий рілс для YOCASE: тест». Drag `исходники/IMG_2373.MOV` into
    the reel folder that opens, write «файли там», and go through the whole flow: draft, one correction, «фінал»
    (the final and the no-music version), «готово» (cleanup asks before it deletes), then «правка до рілса …»
    (reopen re-ingests the media) and «готово» again. Time each step and watch Memory Pressure in Activity Monitor.
    Note the M1 timings, and whether 2 render processes (the 8 GB default) or 4 are better; put the prep estimate
    into `.claude/skills/reel/SKILL.md` step 2.3 (now «3 x the raw minutes», measured on the M2 Pro).
13. **A first change of her own:** let her ask her Claude for something small (for example one learned rule from
    the smoke reel). Claude changes it, runs selftest, commits and pushes; pull on the dev Mac and see her commit.
14. **Comfort:** add `~/reel-studio/inbox` and `~/reel-studio/output` to the Finder sidebar. System Settings,
    Energy (Battery on a laptop): prevent automatic sleeping on power adapter when the display is off. Long steps
    need Claude open, the Mac on power and the lid open.

## Updates and working together

- Both Macs push to `main` (CLAUDE.md "Changing the studio"): `git pull --rebase` before a change, selftest and
  the unit tests before a push, small commits, never a force push. Between reels, «онови студію» pulls and runs
  `doctor.py --full`.
- A change to `pipeline/requirements.lock.txt`, the Playwright version or anything `setup_mac.sh` installs: each
  Mac re-runs `zsh pipeline/setup_mac.sh` after pulling (her Claude can run it); doctor FAILs on the lock stamp
  until then.
- Rules learned from reels live in the tracked `learned/` and reach the other Mac with the next pull.
- To help from afar: «звіт для Влада» writes `output/developer_report.txt` (doctor, machine, git state, the last
  logs).

### A Mac set up before 2026-10-28

The first setup locked Marina out of changing the studio (deny rules, `Mode: creator`). After pulling this change,
run once in Terminal on her Mac (her old rules do not let her Claude do it):

```
cd ~/reel-studio && rm .claude/settings.local.json && cp docs/creator/CLAUDE.local.template.md CLAUDE.local.md
```

then do step 9 (git and GitHub) and start a new session; `doctor.py` shows the role line OK.
