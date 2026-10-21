# Installing the studio on Marina's Mac

The developer's checklist, done in person on her Mac (M1, 8 GB). Every command runs in Terminal on her Mac unless
it says "dev Mac". Allow about half a day, most of it the smoke reel.

## Before the visit (dev Mac)

1. `main` is pushed and its commit passed `.venv/bin/python pipeline/selftest.py`.
2. A fresh clone works: `git clone https://github.com/VladySpidy1/reel-studio.git /private/tmp/rs-clone`, then
   `.venv/bin/python -m py_compile /private/tmp/rs-clone/pipeline/*.py` (the 3.12 interpreter, not
   `/usr/bin/python3`) and `.venv/bin/python /private/tmp/rs-clone/pipeline/selftest.py`. Delete the clone
   afterwards.
3. Pack on a USB stick or for AirDrop:
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
4. **The studio:** `git clone https://github.com/VladySpidy1/reel-studio.git ~/reel-studio`. The repository is
   public, so no login. Never move or rename the folder afterwards: the editable project uses absolute file paths.
5. **Model caches (optional):** `rsync -a <stick>/huggingface/hub/ ~/.cache/huggingface/hub/` and the same for
   `~/.cache/torch/hub/`.
6. **Setup:** `cd ~/reel-studio && zsh pipeline/setup_mac.sh`. It installs ffmpeg and uv with Homebrew, the locked
   Python packages into `.venv`, the Chromium that Playwright pins (the subtitle renderer; Google Chrome is not
   needed), and downloads the models. Safe to re-run.
7. **Files that are not in git:** copy each brand's `local/` folder to `~/reel-studio/brands/<brand>/local/`, and
   `IMG_2373.MOV` to `~/reel-studio/исходники/`.
8. **Creator settings:**
   ```
   cp docs/creator/CLAUDE.local.template.md CLAUDE.local.md
   cp docs/creator/claude-settings.local.json .claude/settings.local.json
   ```
   `CLAUDE.local.md` switches Claude to creator mode (Ukrainian, plain words, the creator rules in `CLAUDE.md`);
   the local settings add her deny and ask rules, Manual mode and auto memory off. Both copies are gitignored. The
   template has another name on purpose: Claude Code loads any `CLAUDE.local.md` in a folder it touches, so a
   template under that name would switch the developer's sessions to creator mode.
9. **Claude desktop app:** install it from https://claude.ai/download and let Marina sign in to her own account.
   Code tab, choose the folder `~/reel-studio`:
   - accept the workspace-trust dialog (the shared allow rules apply only after it);
   - sessions must run in the folder itself, not in a worktree;
   - set the mode selector to Manual (it is remembered per folder).
10. **Health check:** in her app write «перевір студію». Claude runs `.venv/bin/python pipeline/doctor.py --full`:
    no FAIL; every line OK except at most a disk WARN (it warns under 15 GB free); ffmpeg at
    `/opt/homebrew/bin/ffmpeg`; the
    role line "creator machine, creator settings in place"; and no permission prompt.
11. **Smoke reel:** with Marina at the keyboard, «новий рілс для YOCASE: тест». Drag `исходники/IMG_2373.MOV` into
    the reel folder that opens, write «файли там», and go through the whole flow: draft, one correction, «фінал»
    (the final and the no-music version), «готово» (the cleanup click), then «правка до рілса …» (reopen re-ingests
    the media) and «готово» again. Time each step and watch Memory Pressure in Activity Monitor. Note the M1
    timings, and whether 2 render processes (the 8 GB default) or 4 are better; put the prep estimate into
    `.claude/skills/reel/SKILL.md` step 2.3 (now «3 x the raw minutes», measured on the M2 Pro). The only permission
    prompt allowed in the whole flow is the cleanup.
12. **Comfort:** add `~/reel-studio/inbox` and `~/reel-studio/output` to the Finder sidebar. System Settings,
    Energy (Battery on a laptop): prevent automatic sleeping on power adapter when the display is off. Long steps
    need Claude open, the Mac on power and the lid open.

## Updates

- The developer pushes tested commits to `main` (selftest first). Marina never commits or pushes.
- Between reels she writes «онови студію»: Claude runs `git pull --ff-only` and then `doctor.py --full`, and
  answers «Оновила» or «Потрібен Влад».
- A change to `pipeline/requirements.lock.txt`, the Playwright version or anything `setup_mac.sh` installs needs a
  visit: doctor FAILs on the lock stamp until `zsh pipeline/setup_mac.sh` runs again on her Mac.
- If a pull fails because a tracked file changed on her Mac, doctor shows it under "local changes"; fix it in
  person.
- Her corrections stay in her gitignored `learned/`. Read them in `output/developer_report.txt` (she sends it on
  «звіт для Влада») and promote them by hand.
