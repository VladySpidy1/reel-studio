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
3. GitHub, on github.com/VladySpidy1/reel-studio:
   - Settings -> Collaborators: invite Marina's GitHub account and let her accept the e-mail invitation (that is
     what lets her push);
   - Settings -> Rules -> Rulesets: a ruleset for `main` with "Block force pushes" and "Restrict deletions", so a
     bad push from either Mac can never erase the other's commits.
4. Pack on a USB stick or for AirDrop:
   - `brands/*/local/` for every brand (licensed fonts, layers, permanent brand photos: never in git);
   - `исходники/IMG_2373.MOV` (40 MB) for the smoke reel and the example reel;
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
   `git config --global user.email <id>+<login>@users.noreply.github.com`: her noreply address from GitHub,
   Settings -> Emails. Never her real e-mail: every commit in this public repository shows it.
10. **Claude desktop app:** install it from https://claude.ai/download and let Marina sign in to her own account.
    Code tab, choose the folder `~/reel-studio`:
    - accept the workspace-trust dialog (the shared allow rules apply only after it);
    - sessions must run in the folder itself, not in a worktree;
    - permission mode: Auto, as on Vlad's Mac. The shared allow rules already cover reels, commits and pushes;
      deleting files with `cleanup.py apply` always asks.
11. **Health check:** in her app write «перевір студію». Claude runs `.venv/bin/python pipeline/doctor.py --full`:
    no FAIL; every line OK except at most a disk WARN (it warns under 15 GB free); ffmpeg at
    `/opt/homebrew/bin/ffmpeg`; the role line "Marina's Mac (CLAUDE.local.md)".
12. **The example reel**, so her Claude can make check drafts (CLAUDE.md "Changing the studio"): prepare it once
    and render the reference draft:
    ```
    .venv/bin/python pipeline/ingest.py build/yocase_2373 исходники/IMG_2373.MOV
    .venv/bin/python pipeline/prep.py build/yocase_2373/source.ffconcat build/yocase_2373
    .venv/bin/python pipeline/build.py projects/yocase_2373/script.json --draft --name check_2373_base
    ```
13. **Smoke reel:** with Marina at the keyboard, «новий рілс для YOCASE: тест». Drag `исходники/IMG_2373.MOV` into
    the reel folder that opens, write «файли там», and go through the whole flow: draft, one correction, «фінал»
    (the final and the no-music version), «готово» (cleanup asks before it deletes), then «правка до рілса …»
    (reopen re-ingests the media) and «готово» again. Time each step and watch Memory Pressure in Activity Monitor.
    Note the M1 timings, and whether 2 render processes (the 8 GB default) or 4 are better; put the prep estimate
    into `.claude/skills/reel/SKILL.md` step 2.3 (now «3 x the raw minutes», measured on the M2 Pro).
14. **A first change of her own:** let her ask her Claude for something small (for example one learned rule from
    the smoke reel). Claude changes it, runs selftest, commits and pushes; pull on the dev Mac and see her commit.
15. **Comfort:** add `~/reel-studio/inbox` and `~/reel-studio/output` to the Finder sidebar. System Settings,
    Energy (Battery on a laptop): prevent automatic sleeping on power adapter when the display is off. Long steps
    need Claude open, the Mac on power and the lid open.

## Updates and working together

- Both Macs push to `main` (CLAUDE.md "Changing the studio"): pull only between reels, `git pull --rebase` before a
  change, selftest and the unit tests before a push, small commits, never a force push (the ruleset of "Before the
  visit" step 3 enforces it). Between reels, «онови студію» pulls, pushes local commits and runs `doctor.py --full`.
- A change to `pipeline/requirements.lock.txt`, the Playwright version or anything `setup_mac.sh` installs: each
  Mac re-runs `zsh pipeline/setup_mac.sh` after pulling (her Claude can run it); doctor FAILs on the lock stamp
  until then.
- Rules learned from reels live in the tracked `learned/` (or straight in a brand's or format's JSON) and reach the
  other Mac with the next pull.
- To help from afar: «звіт для Влада» writes `output/developer_report.txt` (doctor, machine, git state, the last
  logs).

### A Mac set up before 2026-10-28 (Vlad, in person)

The first setup locked Marina out of changing the studio (deny rules, `Mode: creator`, auto memory off), and those
rules also stop her Claude from removing them. Once, in Terminal on her Mac:

```
cd ~/reel-studio && git pull --ff-only && rm -f .claude/settings.local.json && cp docs/creator/CLAUDE.local.template.md CLAUDE.local.md
```

Then:
- "Before the visit" step 3 and "On her Mac" step 9 (GitHub access and her git identity), and step 12 (the example
  reel) if `build/yocase_2373/` is missing;
- in a new Claude session in `~/reel-studio`: her old corrections were gitignored and are now untracked files in
  `learned/`; have Claude commit them (`git add learned`, commit, `git pull --rebase`, `git push`) before Vlad
  commits a file at the same path, or her next pull stops on "untracked working tree files would be overwritten";
- auto memory is on again with the old settings gone; corrections still go into the repository
  (CLAUDE.md "Corrections"), not into memory.

`doctor.py` then shows the role line "Marina's Mac (CLAUDE.local.md)".
