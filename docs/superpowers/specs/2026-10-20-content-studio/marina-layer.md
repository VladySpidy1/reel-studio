## Creator layer and packaging (Marina's Mac via git)

### Goal

Marina makes brand talking-head reels for TOSUMI and YOCASE on her own M1 8 GB Mac. She works only in the Claude desktop app and only in Ukrainian. The design rests on five points:

- **One entry point.** A `/reel` skill takes a Ukrainian brief, drives the existing pipeline, and ends with a report in Ukrainian.
- **Writes stay in gitignored folders.** Her machine writes only to `inbox/ build/ output/ done/ learned/`, so `git pull --ff-only` keeps working. Her corrections stay visible to the developer without a push, and a selftest guard keeps tracked files out of those folders so a pull can never overwrite her data.
- **Deterministic tools for the mechanics:**
  - `doctor.py` for health and preflight checks;
  - `inbox.py` for the folders, batch prep, archive and reopen;
  - `cleanup.py`, which understands hard links;
  - `brief.py`, which turns the brief into lint checks.
- **Permission rules checked against the current Claude Code docs.** They cover Bash, Edit and the Skill tool. In normal work she sees the one-time workspace-trust dialog and then one approval per reel: cleanup apply, which is an `ask` rule.
- **A developer handover.** INSTALL.md, the commit of the working tree, and a check on a fresh clone.

Feature internals (inserts, CTA, pause cutting, censorship, ducking, the talking-head format, brand.json) belong to the other feature designs. This layer only routes the brief to their keys and checks the result. It depends on `brands/tosumi` and `brands/yocase` existing. Today there is no `brands/` folder, so the brand design must land first (see Effort).

### Creator-facing behaviour

**Session flow.** What Marina says, and what happens:

| Marina | Claude does (the commands are never shown to her) | She sees |
|---|---|---|
| `/reel`, «новий рілс для YOCASE: подарунок подрузі», or a pasted brief | `doctor.py` (silent when OK), then `inbox.py new yocase подарунок подрузі`, then `open inbox/<reel>` | «Перетягни сюди відео з телефона і картинки для вставок. Бриф напиши тут або у файлі brief.md у цій папці.» A Finder window opens. |
| «файли там» | `doctor.py --clips inbox/<reel>` (HDR, length, disk, pictures found). Then `inbox.py prep <reel> > build/<reel>/logs/prep.log 2>&1` with `run_in_background: true`. Claude ends the turn. Claude Code re-invokes it when the background command exits, and it continues (no Monitor, no `sleep`). | «Готую відео, це ~N хв. Не закривай Claude і не вимикай Мак.» |
| (on the completion notice) | Write `inbox/<reel>/script.json`; lint (0 FAIL, including the brief checks); `doctor.py --script`; `build.py … --draft` in the background with a log. Then the review sheets, at most one self-fix, and `open output/<reel>_draft.mp4` | The draft in QuickTime, plus the report (below) |
| «ну що там?» while a job runs | Read tool (or `tail -n 5`, a built-in read-only command) on the newest `build/<reel>/logs/*.log` | One plain sentence about progress |
| corrections in plain words | Re-render. If a correction sounds general, Claude asks «Запам'ятати це для всіх рілсів YOCASE?» and on «так» appends it to `learned/yocase.md` | A new draft |
| «фінал» / «добре» | `build.py` final render (slow preset). If the brief asks for a no-music version: `build.py <script> --skip-timeline --skip-overlay --no-music --name <reel>_no_music`, which is guarded (see build.py). The editable project only on request («для DaVinci»). | Final MP4 and report |
| «готово» / «опублікувала» | `inbox.py archive <reel>` (inbox → done, never deletes), then `cleanup.py plan <reel>`, «Звільнити 0,8 ГБ?», then `cleanup.py apply` | One permission click (the `ask` rule) |
| «бренд просить правку» on an archived reel | `inbox.py reopen <reel>`: done → inbox. If cleanup removed `build/<reel>/media`, it re-ingests the clips in `clips.json` order. Then the normal correction loop. | «Відкрила рілс знову, роблю правку.» |
| «онови студію» | `git pull --ff-only`, then `doctor.py --full`. Only between reels. | «Оновила» or «Потрібен Влад» |
| anything is broken | `doctor.py --report` writes `output/developer_report.txt`, then `open -R` reveals it | «Я не можу це виправити сама. Надішли Владу файл developer_report.txt (я показала його у Finder).» |

**Blocking questions.** Only a missing or unknown brand and "no clips found" stop the work. The format defaults to talking-head and is asked only when the brief names a format that doesn't exist. Everything else is decided and listed under «Сумнівні рішення» in the report. This merges SK:119 with ADR-0002.

**Brief dictionary.** Each command is accepted as a labelled line or as free text in chat:

| Marina writes | Meaning | Maps to (owner) |
|---|---|---|
| `БРЕНД:` TOSUMI / YOCASE | brand preset | `script.brand` → `brands/<brand>/` (brand design). An unknown brand stops the reel: «бренд ще не налаштований — це робить Влад». |
| `ФОРМАТ:` говоряча голова / лінійка / скетч | format | `formats/talking-head` (format design) / `formats/product-lineup` / TOSUMI skit (reel-subtitles reference). **Default: talking-head.** |
| `ХУК:` <фраза> | opening text, word for word; letter case and look follow the brand | A literal line at t≈0 (`build_timeline.py:8-10,112-116`; literal tokens carry no alignment, `:50-51`). Empty → Claude writes one and flags it. |
| `КОДОВЕ СЛОВО:` <слово> | CTA synced to «напиши…» | CTA element (CTA design) |
| «коли кажу X — покажи Y» (list under `ВСТАВКИ:`) | picture insert on phrase X | `inserts[]` (inserts design). Y is a file name or a description; Claude looks at the pictures in `build/<reel>/stills/`. |
| «… на весь екран» | full-screen insert | insert `fullscreen` flag / B-roll EDL (inserts design) |
| `МУЗИКА:` <назва> / «без музики» | named track / none | `audio.music.file`, fuzzy-matched on `title` in `assets/music/credits_music.json`; absent for «без музики» |
| `ЦЕНЗУРА:` слово, слово | asterisk censorship | censor list (censorship design; the asterisk must be escaped from the `*accent*` markup, `build_timeline.py:37`) |
| «без правок стилю» | brand and format defaults only: no style overrides, no doodles or bespoke graphics | Claude-side rule; the brief check warns on `script.style` keys that are not the brand's |
| `ШВИДКІСТЬ:` 1.0–1.3 (optional) | uniform speed-up | only if the format allows it (speed design). Default 1.0; never applied unasked. |
| `РЕФЕРЕНС:`, `ПРИМІТКИ:` | free text | Claude reads it; not checked |

**Brief template** (`docs/creator/brief_template.uk.md`, copied to `inbox/<reel>/brief.md` with БРЕНД pre-filled):

```
# Бриф рілса
БРЕНД:
ФОРМАТ: говоряча голова
ІДЕЯ:
ХУК:                (дослівно; порожньо — придумає Claude)
КОДОВЕ СЛОВО:       (якщо в кінці кажу «напиши …»)
МУЗИКА:             (назва треку, «без музики» або порожньо — як у бренду)
ЦЕНЗУРА:            (слова через кому — будуть із зірочкою)
ВСТАВКИ:
- коли кажу «…» — покажи …
- коли кажу «…» — покажи … на весь екран
БЕЗ ПРАВОК СТИЛЮ:   ні
ПРИМІТКИ:
```

**Folders.** All of them live inside the repo at `~/reel-studio`, not on Desktop, in Documents or in Downloads (iCloud and TCC prompts), and all of them are gitignored:

```
inbox/<reel>/      brief.md, raw clips (*.MOV/*.MP4), pictures (jpg/png/heic/webp), script.json (Claude), notes.md
build/<reel>/      ingest/prep outputs, stills/ (pictures converted for Chrome and Claude's Read tool), logs/
output/            <reel>_draft.mp4, <reel>.mp4, <reel>_no_music.mp4, <reel>_project/ (on request), developer_report.txt
done/<reel>/       the whole inbox/<reel>/ after «готово» (sources are never deleted)
learned/           her corrections: general.md, <brand>.md (README.md and PROMOTED.md are tracked)
```

- **Reel ids** are ASCII slugs, `<brand>_<yymmdd>_<translit>`, for example `yocase_261021_podarunok_podruzi`. Marina never types one.
  - ASCII matters for permissions. Rules match the literal command text, and a path with a space, a quote or a glob character either needs quoting, which breaks the `open output/*` match, or forces a prompt (redirect targets with glob characters).
- **The brief lives in `brief.md` next to `script.json`.** That sibling file is the link between brief and script; there is no path key in the script, so the link survives archive and reopen.
- **Creator scripts live in `inbox/<reel>/script.json`**, not in `projects/`, which stays the developer's tracked examples.
- **Nothing downstream needs `projects/`:**
  - `build.py:40` and `export_fcpxml.py:264` derive the name from the script's parent folder;
  - every script path is ROOT-relative (`common.py:14-17`; `build_timeline.py:284,295,316`).

**Final report** (`.claude/skills/reel/report.uk.md`). The template:

```
**<назва> — чернетка / фінал**
- Файл: output/<reel>.mp4 (відкрила в QuickTime)
- Тривалість: сире відео <raw> с → ролик <out> с
- Бренд · формат: YOCASE · говоряча голова
- Хук: «…» (0,0–2,4 с) · Заклик: «напиши ПОДАРУНОК» (24,1–26,3 с)
- Вставки: набір.jpg на «набір» (8,2 с, зі звуком); …
- Музика: Gimme That Groove, тихо під голосом / без музики · Цензура: гр*ші ×2
- Не знайшла / не вийшло: …
- Сумнівні рішення (скажи, якщо інакше): …
- Далі: подивись і напиши правки словами; коли все добре — «готово».
```

Where the numbers come from:
- raw length: `build/<reel>/clips.json`;
- output length: `build/meta.json` (read right after this reel's build; the slot is single);
- placements: `script.json` plus the build log;
- warnings: the build log (`NOT FOUND`, `!! no free spot`, `OUTSIDE`) and lint.

**Pre-export checklist.** The skill blocks "final" until all of these hold (merges SK:123 with the studio's own checks):
1. `lint_edit` shows 0 FAIL. This includes the brief checks and the feature designs' insert, CTA and pause checks.
2. The build log has no `!! no free spot` and no `OUTSIDE the IG crop-safe area` (`build_timeline.py:352-356`). No spoken CTA phrase or brand word appears in the `NOT FOUND` list (`build_timeline.py:85-87`). The hook is a literal line with no alignment; `brief.check` verifies it instead.
3. `doctor.py --script` passes: every character drawn is in the font that draws it.
4. The review sheet and the 0.3 s contact sheet with the `--phone` crop lines are clean: no overlaps, nothing clipped, no junk frames.

### Schema

**script.json.** No new keys from this layer. `brand`, `format`, `inserts`, `cta`, the censor list, music ducking and speed belong to the brand, format and feature designs; this layer only fills them from the brief. Lint finds the brief by convention: `Path(script).with_name("brief.md")`. Existing `projects/*/script.json` have no `brief.md`, so they lint and render unchanged.

**build/meta.json** (internal; written at `build_timeline.py:304-305`):
- `"script"`: `os.path.relpath(script_path, ROOT)`. Both paths are made absolute first, so it is the same whether the developer runs from `pipeline/` with `../projects/…` (the `build.py:3` docstring) or from the root.
- `"renders"`: `[]` when the timeline is written; `build.py` appends the render name after `rc==0`.
- **A meta.json without `"script"`** (written before this change) counts as "unknown slot". Export, review and `build.py --skip-*` refuse with "build/ holds an unknown reel; rebuild first". `--force` overrides this for the developer.

**Machine and config files:**

| File | Tracked | Content |
|---|---|---|
| `.venv/reel-studio.lock.sha256` | no | `shasum -a 256 pipeline/requirements.lock.txt`, written by `setup_mac.sh` |
| `build/.studio.lock` | no | `flock` target: label and pid of the running heavy job |
| env `REEL_STUDIO_LOCK_PID` | — | Set by a lock holder for its child processes. `studio_lock()` is a no-op when it equals `os.getppid()`. |
| `build/cleanup_plan.json` | no | `{"created", "reels", "items":[{"path","dev","ino","size","nlink"}], "frees_bytes"}` |
| `learned/<brand>.md`, `learned/general.md` | no | Entries: `- [2026-10-21a] (рілс <reel>) «<her words>» → <concrete rule, English>` |
| `learned/PROMOTED.md` | yes | `[id] promoted to <file>` / `[id] rejected: <why>`. The skill skips these ids. |

**`.claude/settings.json`** (tracked and shared by both machines, so it holds only rules that are safe for both):

```json
{
  "permissions": {
    "allow": [
      "Bash(.venv/bin/python pipeline/*)",
      "Bash(.venv/bin/python projects/*/make_script.py*)",
      "Bash(git pull --ff-only)",
      "Bash(open output/*)", "Bash(open -R output/*)",
      "Bash(open inbox/*)",  "Bash(open -R inbox/*)", "Bash(open done/*)",
      "Skill(reel *)", "Skill(reel-videographer *)",
      "Edit(/inbox/**)", "Edit(/learned/**)", "Edit(/build/**)", "Edit(/output/**)"
    ],
    "ask":  ["Bash(.venv/bin/python pipeline/cleanup.py apply*)"],
    "deny": ["Bash(sudo *)"]
  }
}
```

There is deliberately no allow rule for Python under `inbox/`. Her session can write there, so such a rule would run Claude-written code without a prompt and bypass every deny below. Talking-head scripts are written as JSON. Generators stay in tracked `projects/`, which only the developer edits.

**`docs/creator/claude-settings.local.json`** (a tracked template; INSTALL copies it to her untracked `.claude/settings.local.json`):

```json
{
  "autoMemoryEnabled": false,
  "permissions": {
    "defaultMode": "default",
    "deny": [
      "Bash(brew *)", "Bash(sudo *)", "Bash(uv *)", "Bash(pip *)", "Bash(pip3 *)",
      "Bash(.venv/bin/pip *)", "Bash(.venv/bin/python -m pip *)", "Bash(curl *)", "Bash(wget *)",
      "Bash(zsh pipeline/setup_mac.sh*)", "Bash(bash pipeline/setup_mac.sh*)", "Bash(sh pipeline/setup_mac.sh*)",
      "Bash(pipeline/setup_mac.sh*)", "Bash(./pipeline/setup_mac.sh*)",
      "Bash(git push *)", "Bash(git commit *)", "Bash(git reset *)", "Bash(git checkout *)", "Bash(git restore *)",
      "Bash(git clean *)", "Bash(git stash *)", "Bash(git rebase *)", "Bash(git merge *)", "Bash(git rm *)",
      "Bash(rm *)", "Bash(rmdir *)",
      "Edit(/pipeline/**)", "Edit(/projects/**)", "Edit(/docs/**)", "Edit(/formats/**)", "Edit(/brands/**)",
      "Edit(/assets/**)", "Edit(/done/**)", "Edit(/.claude/**)", "Edit(/.venv/**)",
      "Edit(/CLAUDE.md)", "Edit(/CLAUDE.local.md)", "Edit(/CONTEXT.md)", "Edit(/INSTALL.md)",
      "Edit(/README.md)", "Edit(/README.uk.md)", "Edit(/.gitignore)",
      "Edit(/learned/README.md)", "Edit(/learned/PROMOTED.md)"
    ]
  }
}
```

The memory doc says to turn auto memory off for one project by setting `autoMemoryEnabled` in that project's settings; this local file is where her machine sets it. With auto memory off, her corrections can only land in `learned/`, which `--report` collects; it never reads `~/.claude`.

**Permission behaviour these files rely on.** Checked on 2026-10-20 against https://code.claude.com/docs/en/permissions, /permission-modes, /tools-reference, /memory and /skills:
- **Env-var prefixes.** An allow rule "won't match past an assignment of any other variable"; only certain known-safe variables are stripped. So `X264_PRESET=veryfast .venv/bin/python …` always prompts. It is replaced by `build.py --draft`.
- **Deny wins.** Rules are evaluated deny, then ask, then allow, and deny or ask rules match past any leading assignment. Her local denies apply in every mode.
- **Deny rules are not a security boundary.** They match the command text Claude writes: `/bin/rm`, `bash -c '…'` and file writes made by a script are not matched. The allowlist therefore runs only tracked code her session cannot edit.
- **Path anchors.** `Edit(/x/**)` in project and local settings is anchored at the primary working directory. Path rules for `Write` are never consulted, and `Edit` covers Write.
- **Redirects.** Output redirects (`> file`, `2> file`) are checked against `Edit` rules, protected paths and the working directories. That is why `Edit(/build/**)` covers the logs. A target containing a glob character prompts, which is one more reason for ASCII slugs.
- **Read-only commands** (`ls`, `cat`, `head`, `tail`, `du`, `stat`, read-only `git`) run without a prompt in every mode.
- **Skill tool.** The tools reference lists it as permission-required, so `Skill(name *)` allow rules are needed. `disable-model-invocation: true` removes a skill's description from context; the user can still type `/name`.
- **Protected paths.** `.claude/` and `.git` writes are prompted in Manual and acceptEdits, and allow rules don't change that. So learned rules must not live in `.claude/skills/…`: the current loop at `reel-subtitles/SKILL.md:98` would prompt, and local edits there can make a pull fail.
- **acceptEdits is out for her.** It auto-approves `mkdir`, `touch`, `rm`, `rmdir`, `mv`, `cp` and `sed` inside the working directory. She uses Manual mode, which the mode selector remembers per folder.
- **Workspace trust.** Project `permissions.allow` rules apply only after the workspace-trust dialog is accepted; deny and ask rules apply always. An untracked `settings.local.json` is applied once git confirms it is untracked.
- **Timeouts.** Bash defaults to 2 min, with a 10-min maximum per foreground command. A foreground command that times out is moved to the background, not killed. Local desktop-app sessions have no time limit on background commands, and Claude is re-invoked when one exits. Monitor expires after 5 min by default (30 max), so it is not used for prep.
- **Shell environment.** The Bash tool sources `~/.zshrc` (not `~/.zprofile`) and captures aliases, functions and options. PATH from Homebrew's `~/.zprofile` line is therefore not guaranteed.
- **`env.PATH` in the desktop app.** Third-party reports say the Code tab ignores `env.PATH` from settings.json (claudeissues.com #43579, #42602; not official, unverified). So PATH is fixed in code instead (`common.py`).

### Changes by file

**Existing files** (path:line → change):

- `pipeline/common.py:1-11`. Add:
  - **`_tool_path()`**, run at import. If `shutil.which("ffmpeg")` is None, it prepends whichever of `/opt/homebrew/bin` and `/usr/local/bin` holds ffmpeg to `os.environ["PATH"]`. Every bare `ffmpeg`/`ffprobe` call inherits it, including spawned workers, which inherit the environment. Examples: `ingest.py:28,67`, `prep.py:30,229`, `video_pass.py:230,266`.
  - **`ram_bytes()`**, moved from `prep.py:245`.
  - **`default_procs()`**: 2 when RAM is under 12e9, else 4.
  - **`studio_lock(label)`**, a context manager:
    - creates `BUILD`, then takes `fcntl.flock(LOCK_EX|LOCK_NB)` on `build/.studio.lock` and writes its label and pid;
    - on contention it prints "studio busy: <holder label> (pid N)" and exits 2;
    - it is a no-op when `os.environ.get("REEL_STUDIO_LOCK_PID") == str(os.getppid())`;
    - the holder sets that variable for its children;
    - Python fds are non-inheritable, so spawned workers, ffmpeg and Chrome never hold it. The kernel releases it when the process dies.
  - **`keep_awake()`**: `Popen(["caffeinate","-i","-w",str(os.getpid())])`, ignored if caffeinate is absent.
  - **Output**: `sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)`, so Ukrainian log lines are safe under a C locale and logs are readable while a job runs. `build_timeline.py:361` stays harmless.
- `pipeline/beats.py:12-16`: `import common  # noqa: F401` for PATH. It calls ffmpeg at `:23` and is imported without `common` by `projects/yocase_line/make_script.py:19-20`.
- `pipeline/prep.py:233-271` `main`: `common.ram_bytes()` at `:245`. Wrap the body in `studio_lock("prep "+out)` + `keep_awake()`.
- `pipeline/ingest.py:94-120` `main`: wrap in `studio_lock` + `keep_awake()`.
- `pipeline/video_pass.py`:
  - `:23` keeps the env default;
  - `segment` (`:222`) and `main` (`:248-257`) gain a `preset=None` parameter passed through the `Process` args; `:233` uses `preset or PRESET`.

  This is needed because macOS multiprocessing uses `spawn`: workers re-import the module, so a module global changed in the parent never reaches them. `main` already has `procs` (`:249`).
- `pipeline/build.py:28-68` `main`:
  - **Lock first.** `studio_lock("build "+name)` and `keep_awake()` right after argument parsing, before `build_timeline.main` (`:44`) or any slot read or write.
  - **`--draft`**: passes `preset="veryfast"`; the default name becomes `<parent>_draft`.
  - **`--procs`**, default `common.default_procs()`: 4 on the 16 GB dev Mac (unchanged there), 2 on 8 GB. It is passed to `overlay_render.render` (`:50`) and `video_pass.main` (`:64`). The M1 smoke test confirms the choice.
  - **Slot guard.** With `--skip-timeline` or `--skip-overlay`, it refuses (exit 2) unless `meta.get("script") == relpath(a.script, ROOT)`. Otherwise those flags render this script's audio and source under another reel's camera, timeline and overlay (`:46-50,64-65`).
  - **Slot record**: after `rc==0`, append the name to `meta["renders"]` and save.
- `pipeline/build_timeline.py:304-305`: meta gets `"script": os.path.relpath(script_path, ROOT)` and `"renders": []`.
- `pipeline/export_fcpxml.py:255-267`:
  - `--procs` default `default_procs()` (`:260`), giving 2 on 8 GB. The peak per worker is bounded by the visible frames of one layer (`:133`).
  - Before `media.mkdir` (`:267`), refuse when `meta["script"]` is missing or differs from the script given ("build/ holds X; rebuild first"); `--force` overrides.
  - `studio_lock` + `keep_awake`.

  The raw mix it reads is `build/<name>_mix_raw.wav` (`:361`).
- `pipeline/review_frames.py:23-29` `main`: refuse unless `Path(video).stem` is in `meta.json["renders"]`; `--force` overrides for the developer.
- `pipeline/contact_sheet.py:22,47-57`: a `--phone` flag draws the Instagram crop lines on each tile. The crop is 97 px per side at 1080 wide, which is 16 px on a 180-px tile. This replaces the raw `ffmpeg … crop=886:1920:97:0` step at `reel-subtitles/SKILL.md:110-111`, which would prompt.
- `pipeline/lint_edit.py:180-187` `main`: if `path.with_name("brief.md")` exists, extend `fails`/`warns` with `brief.check(brief.parse(that), script)`. It returns lists of `(t, msg)` tuples in the format `lint()` uses (`:182-185`), with `t=0.0` for script-level findings.
- `pipeline/setup_mac.sh:22-23`: after `uv pip install`, write the lock stamp. Chrome must also be opened once (no code change).
- `.claude/skills/reel-subtitles/SKILL.md`:
  - **`:1-4`**: the description becomes "Reference: pipeline commands, subtitle markup, TOSUMI skit style. Read by the `reel` skill; not an entry point." Add `disable-model-invocation: true`. This removes the «змонтуй»/«зроби рілс» collision; the developer can still type `/reel-subtitles`.
  - **`:17-22` §0**: becomes "run `doctor.py`; on FAIL stop. Never run setup."
  - **`:34-37`, `:67-88`**: paths become "the reel's script"; the draft command becomes `build.py … --draft`.
  - **`:98`**: creator corrections go to `learned/`; only the developer promotes them here.
  - **`:110-111`**: use `contact_sheet.py --phone`.
- `.claude/skills/reel-videographer/SKILL.md`:
  - `:75` → `--draft`;
  - `:84`: the same learned-rules note;
  - `:14-15`: generators only for developer reels in `projects/`.

  It stays model-invocable (allowed by `Skill(reel-videographer *)`). Its triggers («мертве», «більше руху») are feedback on a draft inside a reel session, not entry phrases.
- `.gitignore`. Add:

  ```
  inbox/
  done/
  learned/*
  !learned/README.md
  !learned/PROMOTED.md
  исходники/
  *.log
  .claude/settings.local.json
  CLAUDE.local.md
  ```

**New files:**
- **`CLAUDE.md`** (English, under 200 lines):
  1. *Map*: tracked vs gitignored folders.
  2. *Two users*:
     - developer Vladyslav: reply in Russian, full dev rights;
     - creator Marina: reply in Ukrainian, plain words, no paths or jargon.

     `CLAUDE.local.md` is the per-machine marker. Message language is the secondary cue.
  3. *Creator-mode rules*:
     - never ask her to run commands or open Terminal;
     - doctor at the start of every reel and after an update; on FAIL, one plain sentence plus `doctor.py --report`, then "call Vlad";
     - if `.venv/bin/python` itself is missing, run `git rev-parse --git-dir --git-common-dir` (read-only):
       - if the two differ, the session is in a worktree: «відкрий нову сесію в папці reel-studio»;
       - otherwise setup is missing: call Vlad;
     - never brew/sudo/setup/pip/uv/git commit/push/reset; only `git pull --ff-only`, only when she asks and never mid-reel;
     - write only to the gitignored folders, via the scripts; never edit tracked files (if a fix needs code, say so and stop);
     - one reel at a time (the lock);
     - long steps with `run_in_background: true` and output redirected to `build/<reel>/logs/<step>.log`; end the turn and continue when re-invoked on exit; never Monitor or `sleep` for these;
     - exact command forms, because the allow rules match the text:
       - `.venv/bin/python pipeline/…` from the repo root;
       - no `cd`, no quotes around paths, no absolute interpreter path;
       - no `python -c`, no raw ffmpeg;
     - keep the app open, the Mac on power, the lid open;
     - cleanup policy (below);
     - corrections go to `learned/` (auto memory is off on her Mac);
     - work in the main folder.
  4. *Developer-mode rules*:
     - main is what Marina pulls, so anything on main must work on 8 GB / macOS 14+;
     - never rewrite main;
     - a lock-file change needs an in-person re-sync on her Mac (her doctor FAILs until then);
     - never commit anything under `learned/` (except README and PROMOTED), `inbox/`, `done/`, `build/` or `output/`: git silently overwrites her ignored files with the committed version on pull;
     - run `selftest.py` before every push;
     - promote her rules and log the ids in `PROMOTED.md`;
     - the repo is public: no secrets, no client footage, don't commit the third-party skill file (licence unknown);
     - files in English, on-screen text in Ukrainian.
- **`.claude/skills/reel/SKILL.md`** (`name: reel`, `argument-hint: [бриф або назва рілса]`). The description puts the use case first, then the triggers: «змонтуй», «зроби рілс», «новий рілс», «рілс для …», «ось бриф/ТЗ», `ХУК:`/`КОДОВЕ СЛОВО:`, /reel. The steps follow the session-flow table:
  - load learned rules (`learned/general.md`, `learned/<brand>.md` minus ids in `PROMOTED.md`);
  - load `brands/<brand>/`, `formats/<format>/FORMAT.md` and the format template;
  - read `reel-subtitles/SKILL.md` §1-5 as reference; load `reel-videographer` for the picture;
  - pre-export checklist; at most one self-fix loop before Marina sees a draft.

  Supporting files: `brief.md` (the dictionary table above, with parsing notes) and `report.uk.md` (the template above). The third-party skill is never installed; its content lives here and in the feature designs.
- **`pipeline/doctor.py`** (`[--full] [--clips <dir|files>] [--script <script.json>] [--report]`). Stdlib-only at import, so it reports even when `.venv` packages are broken. It prints `OK/WARN/FAIL <key>: <msg>` in English and exits 1 on any FAIL. Default checks, all quick (no torch, no Chrome):
  - **Location**: repo root is a main checkout (`.git` is a dir) and not under Desktop/Documents/Downloads/iCloud; no `'` in the path (`video_pass.py:265`).
  - **Python**: 3.12 from `.venv`; the lock stamp matches (missing → WARN, mismatch → FAIL).
  - **macOS** ≥ 14 (`platform.mac_ver`).
  - **RAM**, with the procs that will be used.
  - **ffmpeg/ffprobe**: resolved path and version; `-encoders` contains `prores_ks` and `libx264` (full output captured, no pipe).
  - **Chrome**: `/Applications/Google Chrome.app`.
  - **Model caches**:
    - `${HF_HUB_CACHE:-${HF_HOME:-~/.cache/huggingface}/hub}/models--Systran--faster-whisper-large-v3/snapshots/*/model.bin` resolves (over 2.5 GB);
    - `~/.cache/torch/hub/PeterL1n_RobustVideoMatting_master/hubconf.py` and `checkpoints/rvm_resnet50.pth`. With these cached, `torch.hub` falls back to the cache when offline.
  - **Glyphs**: every `@font-face url(...)` in `overlay.html:6-8` plus brand fonts must contain `іїєґІЇЄҐʼ’№«»–—*`, the full Ukrainian and Latin alphabets in both cases, and digits. A pure-`struct` cmap reader (formats 4/12; `.ttc`/`.woff2` → WARN unsupported) does this with no new dependency.
  - **Disk** (rule below).
  - **Local changes to tracked files** → WARN "a pull that touches them will fail" (creator mode treats it as stop).
  - **Creator machine** (`CLAUDE.local.md` present): `.claude/settings.local.json` must contain every deny rule of `docs/creator/claude-settings.local.json` and `autoMemoryEnabled: false`, else WARN (template drift after a pull).
  - **Housekeeping**: studio lock holder; leftover `build/vp_*`; reclaimable GB (done reels whose build media still exist).

  The modes:

  | Mode | What it does |
  |---|---|
  | `--full` | Also imports torch and reports MPS. Launches Playwright `channel="chrome"`, loads `overlay.html` and renders a Cyrillic probe, which catches Chrome/Playwright drift (R10). |
  | `--clips` | ffprobe each video: HDR → FAIL with the Ukrainian fix hint (ADR-0006). Totals the duration. Lists pictures (HEIC noted). Disk need is per reel. |
  | `--script` | Every drawn character is in its font. The font per token kind comes from the merged style (`style_default.json` + brand + `script.style`), the way `overlay.html:40-51` `styleForKind` picks it: plain words and `//` → `main.family`; `*…*` and `_…_` → `accent.family`; `№N` labels → `label.family`. Family → file via the `@font-face` rules. Markup characters are stripped first. All referenced build files exist; a missing `media/` after cleanup → "reopen". |
  | `--report` | Writes `output/developer_report.txt`: doctor results, macOS/RAM/chip, `git log -1`, dirty tracked files, the tails of the 3 newest `build/*/logs/*.log`, full `learned/*.md`, inbox and done reel lists with sizes. It never reads `~/.claude` or the environment. |

  **Disk rule.** Need = 1.7 GB × raw minutes + 0.5 GB (+1.0 GB if an export is requested); 3.5 GB per reel when the clips are unknown. FAIL if free − need < 5 GB (swap headroom on 8 GB); WARN if under 15 GB. The figures were measured on yocase_2373:
  - ProRes media: 680 MB (648 MiB) for 28.8 s, i.e. 1.35 GB per minute (`ingest.py:76`);
  - masks: 112 MB, i.e. 0.23 GB per minute;
  - mix WAVs: 19 MB per render name;
  - MP4: 43 MB.
- **`pipeline/inbox.py`**. Every function takes a `root` parameter (default `ROOT`) so selftest can drive it in a temp dir.
  - **`new <brand> <title…>`**: makes the slug (Ukrainian national transliteration table, `[a-z0-9_]`, at most 40 chars, `-2` on collision), creates `inbox/<id>/brief.md` from the template and `build/<id>/logs/`, and prints the id and absolute path.
  - **`list`**: per reel, the clip count and duration, pictures, brief/script present, prepped (`words.json`), and outputs.
  - **`prep <id> [<id>…] [--force] [--dry-run]`**:
    1. Holds `studio_lock("prep batch …")` and `keep_awake()` for the whole batch and sets `REEL_STUDIO_LOCK_PID` for its children, so no other build can slip in between two steps and kill an overnight batch.
    2. For each reel in sequence:
       - order the videos by ffprobe `creation_time` (then mtime, then name);
       - run `ingest.py build/<id> <clips>`, then `prep.py build/<id>/source.ffconcat build/<id>`, as child processes logged to `build/<id>/logs/prep.log`;
       - convert pictures into `build/<id>/stills/`: HEIC → JPEG with macOS `sips` (Claude's Read tool refuses `.heic`), the rest copied;
       - skip reels that already have `words.json` and `masks.npy`, unless `--force`.
    3. A child failure stops the batch with the reel and log named. `--dry-run` prints the planned commands and clip order only.
  - **`archive <id>`**: moves `inbox/<id>` → `done/<id>` (`-2` if it exists); never deletes.
  - **`reopen <id> [--dry-run]`**:
    - moves `done/<id>` → `inbox/<id>`, refusing if `inbox/<id>` exists;
    - if `build/<id>/media` is missing, re-runs `ingest.py` on the clips in `clips.json` order, each found by the basename of `orig` in `inbox/<id>/` or at `orig`;
    - then checks every `n_frames` against the old `clips.json` and that `masks.npy` has that many frames (`prep.py:168`);
    - on a mismatch, or when `masks.npy` is gone (cleanup `--all`), it runs full prep.
- **`pipeline/cleanup.py`**:
  - **`plan <id>… [--all] [--temp]`**. The deletion set uses exact names, never prefixes, so `<id>` cannot match `<id>-2`:
    - `output/<id>_draft.mp4`;
    - `output/<id>_project/`;
    - `build/` files matching `^<id>(_draft|_no_music)?_mix(_raw)?\.wav$` (`build.py:53`, `audio.py:131`);
    - `build/<id>/media/`, **only** if every clip in `clips.json` is found by basename in `done/<id>/` or `inbox/<id>/`, or at its `orig` path (`ingest.py:85`). Otherwise it refuses, because yocase_line-style media can't be regenerated.
    - `--all` adds `masks.npy`.
    - `--temp` covers `build/vp_*` (`video_pass.py:253,262-263`) and `build/overlay|preview|review|look`, only when the lock is free.
    - **Kept always**: final MP4s, `<id>_no_music.mp4`, the `*.json` prep outputs, `sheet.jpg`, `logs/`, `inbox/`, `done/`, `projects/`, `assets/`, `learned/`.
    - **Freed bytes** are summed per `(st_dev, st_ino)`, counting an inode only when all `st_nlink` links are in the set. The project hard-links clips, SFX and music (`export_fcpxml.py:302-321`), so the links into `assets/` free nothing, and `build/<id>/media` frees space only together with `output/<id>_project`.
    - It writes `build/cleanup_plan.json`.
  - **`apply`**: re-stats every item and refuses on any change, on symlinks, or on any path outside `build/` or `output/`. Then it deletes and prints the GB freed. It sits behind the `ask` rule, so it is the only approval click.
- **`pipeline/brief.py`**:
  - **`parse(path) -> dict`**: `{brand, format, idea, hook, code_word, music: str|None|False, censor: [..], inserts: [{when, show, fullscreen}], no_style_changes, speed, notes}`. It accepts labelled lines and the free phrases «без музики», «без правок стилю», «коли кажу … — покажи … [на весь екран]».
  - **`check(brief, script) -> (fails, warns)`** as `(t, msg)` lists:
    - the hook matches a literal line case-insensitively, with markup stripped;
    - the music matches, or is absent for «без музики»;
    - «без правок стилю» → no non-brand `style` keys;
    - code word, censorship and insert checks call into keys owned by the other designs, and skip with one WARN while those keys don't exist.
- **`pipeline/selftest.py`**: plain asserts in temporary dirs, no repo writes:
  - brief parsing;
  - cmap pass/fail;
  - hard-link accounting and the exact-name patterns (`r` vs `r-2`);
  - slug and translit; archive and reopen without overwrite, including the reopen re-ingest plan in `--dry-run`;
  - the lock between two processes and the `REEL_STUDIO_LOCK_PID` hand-down;
  - **refs**: every `pipeline/*.py`, `formats/…` and `docs/…` path mentioned in CLAUDE.md and the skills is in `git ls-files`;
  - **tracked-path guard**: `git ls-files learned inbox done build output` ⊆ {`learned/README.md`, `learned/PROMOTED.md`}.
- **`docs/creator/`**: `brief_template.uk.md`, `claude-settings.local.json`, and `CLAUDE.local.md`. The last is the creator marker: «Ця машина — Марини. Режим creator: дотримуйся розділу Creator у CLAUDE.md.»
- **`learned/README.md`** (format and flow) and **`learned/PROMOTED.md`** (empty).
- **`README.uk.md`** (one page for Marina):
  - what the studio does;
  - how to start (Claude → Code → папка reel-studio → «новий рілс для …» або `/reel`);
  - where to drop files (the Finder sidebar «Рілси»; from the iPhone via AirDrop, then drag into the reel folder);
  - the brief template;
  - shooting rules: HDR Video off; say «стоп» after a failed take;
  - «готово», «правка до рілса …», «онови студію», «звіт для Влада»;
  - keep Claude open and the Mac on power for long steps.
- **`INSTALL.md`** (developer-run, in person on her Mac):
  1. macOS ≥ 14 (update first if older; locked wheels are `macosx_14_0_arm64`). At least 50 GB free.
  2. `xcode-select --install`, which brings git.
  3. Homebrew installer with an admin password, then its "Next steps" `brew shellenv` line into `~/.zprofile`.
  4. Google Chrome into /Applications; open it once.
  5. `git clone https://github.com/VladySpidy1/reel-studio.git ~/reel-studio`. The repo is public, so no auth and no `gh`. Never move the folder: the FCPXML uses absolute `file://` URLs (`export_fcpxml.py:66-67`).
  6. Optionally `rsync -a` `~/.cache/huggingface/hub` (symlinks and `blobs/` included) and `~/.cache/torch/hub` from the dev Mac. This saves a 3 GB download and pins RVM (R7).
  7. `zsh pipeline/setup_mac.sh`.
  8. `cp docs/creator/CLAUDE.local.md CLAUDE.local.md` and `cp docs/creator/claude-settings.local.json .claude/settings.local.json`.
  9. Claude app, signed in to her account → Code → folder `~/reel-studio`:
     - accept workspace trust;
     - make sure sessions run in the folder itself, not a worktree;
     - set the mode selector to Manual, which is remembered per folder.
  10. In her app, «перевір студію» → `doctor.py --full` all OK. The ffmpeg line must show `/opt/homebrew/bin/ffmpeg`, and no command may prompt.
  11. Smoke reel with `исходники/IMG_2373.MOV` (40 MB): full flow including «готово» and «правка» (reopen), timing each step and watching memory pressure. Write the M1 timings and the chosen `--procs` into the reel skill's estimates.
  12. Add `inbox/` and `output/` to the Finder sidebar. Set Energy to "prevent sleeping on power adapter".

  It also lists, **before handover on the dev Mac**: commit all 17 modified and 20 untracked files (B2), except anything under `исходники/` (the third-party file lives outside the repo; never copy it in). Then run `selftest.py`, `git clone` into a scratch dir, and run `.venv/bin/python -m py_compile` on the clone's `pipeline/*.py` (the 3.12 interpreter, not `/usr/bin/python3` 3.9).

### Interactions

- **Person matte.**
  - Doctor checks the RVM cache, so prep runs offline (the torch hub cache fallback).
  - Cleanup keeps `masks.npy` unless `--all`, because a fix render needs it (`video_pass.py:227`, `export_fcpxml.py:114`).
  - `reopen` re-ingests media and verifies frame counts against `clips.json` and `masks.npy` before reusing the masks.
  - The `studio_lock` serialises RVM on MPS with every other heavy job on 8 GB.
- **Safe zone and layout solver.** No change. The pre-export gate relies on the solver's stable log strings (`build_timeline.py:352-356`). «без правок стилю» still allows `place` hints (layout, not style). `contact_sheet --phone` replaces the raw-ffmpeg crop check.
- **Subtitle timing.**
  - The hook is a literal line (exact time, no alignment; `build_timeline.py:50-51,114-116`), checked by `brief.check`.
  - `NOT FOUND` alignments (`build_timeline.py:85-87`) of spoken CTA phrases or brand words are listed in the report and block delivery. The display/match split for Latin and censored words belongs to the censorship design.
  - The glyph check uses the same family per token kind as `overlay.html:40-51`.
- **FCPXML export.** Only on request:
  - `--procs` comes from RAM (2 on 8 GB);
  - it refuses before touching `output/` when the slot holds another reel or an unknown one, guarding the "last reel's subtitles" trap (`reel-subtitles/SKILL.md:94-96`);
  - cleanup treats the project and `build/<id>/media` as one unit because of the hard links;
  - the folder must not move (absolute URLs).
- **lint_edit.** It gains the sibling-brief check, in its own `(t, msg)` format. It stays the single "0 FAIL before render" gate. The feature designs add their insert, CTA and pause checks there; this layer only routes the brief.
- **Audio mix.**
  - МУЗИКА resolves to a file in `assets/music` by credits title; «без музики» drops `audio.music`.
  - The no-music variant reuses the slot: `build.py --skip-timeline --skip-overlay --no-music --name <id>_no_music` (`build.py:34`). The slot guard refuses it unless meta matches this script.
  - Mix WAVs are cleaned per reel by exact name. The raw mix is read by the export (`export_fcpxml.py:361`), so cleanup deletes it only together with the project.
- **Shared build state.**
  - `build/camera.json`, `meta.json`, `timeline.json` and `overlay/` are single-slot (`build_timeline.py:303-305`, `build.py:49-50`).
  - The flock gives one heavy job at a time across sessions, and the batch lock hand-down keeps an overnight `inbox.py prep a b c` atomic.
  - `meta.script` and `renders` stop export, review and `build.py --skip-*` against the wrong reel.
  - A batch is `inbox.py prep a b c` (sequential), then one interactive build per reel.

### Verification

All of these run on the dev Mac. The renders write into `build/` and `output/` under new names; the slot ends up holding yocase_2373 again, as it does today.

1. `.venv/bin/python pipeline/selftest.py`. Expect all PASS in under 5 s, including:
   - brief: the template parses to all-empty defaults; a sample with ХУК / КОДОВЕ СЛОВО / «без музики» / ЦЕНЗУРА: гроші, знижка / two inserts (one «на весь екран») gives the exact dict;
   - cmap: the 4 bundled TTFs pass, and `/System/Library/Fonts/Supplemental/Chalkduster.ttf` fails on `іїєґІЇЄҐ№` and the Cyrillic alphabet. The existing prototype `/private/tmp/claude-501/design/cmap_proto.py` reproduces this today;
   - link accounting: a file hard-linked into `build/r/media` and `output/r_project/media` counts as freed only when both are in the plan, and `r` never matches `r-2_mix_raw.wav`;
   - a second `studio_lock` exits 2 with the first holder's label; a child with `REEL_STUDIO_LOCK_PID` = parent pid passes;
   - reopen `--dry-run` on a temp `done/r` with no `build/r/media` plans an ingest in `clips.json` order;
   - refs and tracked-path guard pass.
2. `.venv/bin/python pipeline/doctor.py`. Expect:
   - OK lines with the ffmpeg path `/opt/homebrew/bin/ffmpeg`;
   - WARN for the lock stamp (this `.venv` predates the stamp);
   - WARN "local changes to tracked files" (the dev tree is dirty);
   - disk OK (18 GiB free vs 3.5 + 5).

   Then:
   - `doctor.py --script projects/yocase_2373/script.json` → glyph OK;
   - `doctor.py --clips исходники/IMG_2373.MOV` → SDR OK at 28.8 s with a need of about 1.3 GB.
3. **Brief through lint** (scratch only):
   - copy `projects/yocase_2373/script.json` to `/private/tmp/claude-501/design/v/script.json`, plus a `brief.md` next to it with `ХУК: тест хук` and `МУЗИКА: без музики`;
   - `.venv/bin/python pipeline/lint_edit.py /private/tmp/claude-501/design/v/script.json` → expect a FAIL for the hook (no matching literal line), a FAIL or WARN for the music if the script has `audio.music`, the feature-key WARNs, and exit code 1;
   - the same lint on `projects/yocase_2373/script.json` → output identical to today's.
4. **Integration test.** Run in the background with a log:
   ```
   .venv/bin/python pipeline/build.py projects/yocase_2373/script.json --draft --name t2373_draft > build/yocase_2373/logs/t_draft.log 2>&1
   ```
   Expected:
   - the log ends with `[video] rc=0`;
   - `ffprobe -v error -show_entries format=duration -of csv=p=0 output/t2373_draft.mp4` → about 28.83;
   - `strings output/t2373_draft.mp4 | grep -m1 -o 'subme=[0-9]*'` → `subme=2` (veryfast), while `output/yocase_2373.mp4` gives `subme=8` (slow). This proves the preset reached the spawned encoders;
   - `.venv/bin/python pipeline/compare_render.py output/yocase_2373.mp4 output/t2373_draft.mp4 --out /private/tmp/claude-501/design/cmp` → no "differs" runs below the default 32 dB threshold; the median is expected well above it (estimate). Do not compare against `output/yocase_2373_draft.mp4`: it was rendered at 10:24 on Oct 13, before `style_default.json` (11:38) and `build_timeline.py` (11:47) changed the safe area. `output/yocase_2373.mp4` (11:49) has the current layout;
   - `build/meta.json` has `"script": "projects/yocase_2373/script.json"` and `"renders": ["t2373_draft"]`.
5. While step 4 runs, start a second `build.py … --draft --name t2`. It should exit at once with code 2 ("studio busy: build t2373_draft (pid …)") without touching `build/meta.json` (its mtime is unchanged).
6. After step 4, these must refuse with exit 2 and write nothing:
   - `export_fcpxml.py projects/yocase_2477/script.json --skip-layers` ("build/ holds projects/yocase_2373/script.json");
   - `build.py projects/yocase_2477/script.json --skip-timeline --skip-overlay --name t2477`;
   - `review_frames.py output/yocase_2477.mp4`.

   `review_frames.py output/t2373_draft.mp4` works.
7. `.venv/bin/python pipeline/cleanup.py plan t2373 yocase_2373`. Expect:
   - `build/yocase_2373/media/IMG_2373.mov` 680 MB (648 MiB), "2 links, both in plan";
   - `output/yocase_2373_project` 727 MB, of which about 82 MB is its own data;
   - `output/yocase_2373_draft.mp4`, `output/t2373_draft.mp4` and the matching mix WAVs;
   - `output/yocase_2373.mp4` and `masks.npy` kept;
   - total around 0.9 GB;
   - the clips are regenerable from `исходники/IMG_2373.MOV` (the `orig` in `clips.json`).

   Only `build/cleanup_plan.json` is written; `du -sh build output` is unchanged. Do not run apply here.
8. **Permissions**, in a desktop session on the dev Mac with the new settings.json:
   - `.venv/bin/python pipeline/doctor.py` → no prompt;
   - «новий рілс для YOCASE: тест» → the `reel` skill loads with no Skill prompt (then stop before `inbox.py new`, or delete the scratch reel by hand);
   - `X264_PRESET=veryfast .venv/bin/python pipeline/build.py --help` → prompts (confirms the env-prefix rule);
   - `.venv/bin/python pipeline/cleanup.py apply` → prompts (ask);
   - `/permissions` lists the rules with no invalid-rule warnings.

   With the creator `settings.local.json` and `CLAUDE.local.md` in a trusted scratch clone:
   - `rm x`, an Edit to `pipeline/common.py` and an Edit to `.claude/settings.json` are denied;
   - `/memory` shows auto memory off.
9. **Fresh clone** after the commit:
   - `git clone` into `/private/tmp/claude-501/design/clone`;
   - `.venv/bin/python -m py_compile` on its `pipeline/*.py` passes;
   - `.venv/bin/python /private/tmp/claude-501/design/clone/pipeline/selftest.py` → refs and tracked-path guard pass;
   - `git status --porcelain` in the dev tree is clean.
10. **Her Mac** (INSTALL step 11): the smoke reel end to end, including reopen, with no prompts except cleanup apply. Record the M1 timings and peak memory pressure for `--procs` 2 vs 4.

### Risks

| Risk | Mitigation |
|---|---|
| Desktop-app environment (PATH, the trust dialog, worktree default, which mode new sessions start in, Skill prompts) is not verified on her machine. | The PATH fix in code, doctor, the Skill allow rules, and INSTALL steps 9-11. |
| Claude writes a command in a form the allow rules don't match (quoted or absolute paths, `cd`, `python -c`, raw ffmpeg, `git pull` with extra args). Marina then sees prompts she can't judge. | CLAUDE.md fixes the exact forms; ASCII slugs need no quoting; the smoke test surfaces the rest. |
| Deny rules match command text only and are not a security boundary. | Her allowlist runs only tracked code she can't edit; no allow rule for Python under `inbox/`; Manual mode. |
| A pull brings a lock-file change, so imports break until the developer re-syncs. | The doctor stamp FAIL turns this into "call Vlad". Developer rule: no lock changes on main without an in-person visit. |
| Learned rules never reach the developer. | `--report` bundles them; auto memory is off, so they can't go elsewhere; `PROMOTED.md` keeps promoted or rejected ids out of her sessions. |
| The developer commits a file at a path she keeps ignored (e.g. `learned/yocase.md`). Git then **silently overwrites** her file on pull: tested in a scratch repo, `git pull --ff-only` exits 0 and her text is replaced. | CLAUDE.md developer rule plus the selftest tracked-path guard run before every push. |
| 8 GB RAM: whisper int8 plus RVM plus Claude plus her browser leads to swap. Export or build with 4 workers could reach 5-6 GB (estimate). | Procs come from RAM for build and export, the lock makes the single slot explicit, the disk headroom covers swap, and the skill asks her to close heavy apps during prep. |
| `caffeinate -i` can't stop clamshell sleep. | Overnight batches need the lid open on power (README / INSTALL). |
| HEIC pictures. | Converted with `sips` in `inbox.py prep`. Inserts must read from `build/<id>/stills/`, not `inbox/` (coordination with the inserts design). |
| The brief check depends on key names the other designs haven't settled. | It skips with a WARN until they exist; the names are agreed when merging. |
| `brands/` doesn't exist yet, so every reel stops on «бренд ще не налаштований». | The brand design lands before this layer is handed over (Effort order). |
| The re-ingest in `reopen` depends on unchanged clips and a compatible ffmpeg. | The frame-count check against `clips.json` and `masks.npy`; full prep on any mismatch. |
| Public repo. | Nothing from her machine is ever pushed. But CONTEXT.md family details, the client copy in `projects/yocase_*` and the licensed WAVs stay public (B1). |

### Effort

| Piece | Size |
|---|---|
| Commit the working tree and check a fresh clone (must come first) | S |
| Brand presets `brands/tosumi`, `brands/yocase` (brand design; prerequisite for handover) | — (other design) |
| `common.py` (PATH, RAM/procs, lock with hand-down, wake, stdout) + `beats.py` import | S |
| `build.py --draft/--procs` + `video_pass` preset param + export procs default + slot guards (meta, review, export, `build --skip-*`) | S |
| `contact_sheet --phone`, setup stamp, `.gitignore` | S |
| `doctor.py` (incl. cmap reader, style-aware `--script`, `--clips`, `--report`, settings drift) | M |
| `inbox.py` (new, list, prep with batch lock, ordering and stills, archive, reopen) | M |
| `cleanup.py` (two-phase, inode accounting, exact names, regenerability check) | S-M |
| `brief.py` + lint hook | S-M |
| `selftest.py` (incl. tracked-path guard) | S |
| `reel` skill (SKILL.md, brief.md, report.uk.md) + edits to the two existing skills | M |
| CLAUDE.md, `CLAUDE.local.md` / settings templates, `.claude/settings.json` | S |
| INSTALL.md, README.uk.md, `learned/` README and PROMOTED | S |
| In-person install and smoke reel on her Mac | S (half a day) |

Overall this area is M-L: about 2.5-3 dev days plus the visit, after the brand design.

### Open questions for the developer

1. **Permission mode for Marina.** I recommend Manual plus the allowlist: deterministic, and one click per reel. The alternative is Auto mode with the same deny list: fewer prompts for incidental commands, but a classifier decides. Which do you want?
2. **Deliverables per reel.** Should every final also render `<reel>_no_music.mp4` by default (for trending in-app sounds), or only when the brief asks? It reuses the slot, so it costs one audio mix and one video pass.
3. **Public repo contents.** The YOCASE example scripts carry client subtitle copy, and CONTEXT.md describes your wife. Both become public with the commit B2 requires. Keep them public, or strip or move them before that commit?
4. **Who triggers updates.** The design lets Marina run `git pull --ff-only` on «онови студію», never in the middle of a reel. Do you prefer that updates happen only when you're there?
