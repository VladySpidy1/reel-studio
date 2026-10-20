"""Fast checks of the creator tools and the repository's guards (seconds, no renders, nothing written to the repo).
The developer runs it before every push; a fresh clone runs it after setup.

python selftest.py      one line per failure, then a summary; exit 1 on any failure

- brief: the template parses to the empty defaults, a sample to the exact dict, a free phrase under a label is a
  command and not part of that label's value;
- cmap: the bundled fonts have every probe character, a Latin-only system font does not;
- cleanup: exact names (r never matches r-2), a music stem only with its project, hard links freed only when every
  link is in the plan, apply refuses a plan that no longer matches the disk; a reel named twice is planned once, and
  the files of a reel r_draft never go with r; --temp keeps the render folders while another job holds the lock, and
  apply deletes them under its own lock;
- inbox: transliteration and ids (never one that shares a render name with another reel), archive and reopen never
  overwrite, reopen plans a re-ingest in clips.json order;
- lock: a second job gets exit 2 with the holder's label, the holder's child passes;
- refs: every pipeline/, formats/ and docs/ path named in CLAUDE.md, INSTALL.md, learned/README.md and the skills is
  in the repository (tracked, or new and not ignored);
- tracked: nothing under learned/ (but its README), inbox/, done/, build/ or output/ is tracked (a pull would
  overwrite the creator's file), and no CLAUDE.local.md is in the repository (Claude Code would load it);
- ignore: .gitignore keeps her folders and per-machine files out of git and the docs/creator templates in;
- settings: the tracked .claude/settings.json only allows; the deny and ask rules are in the creator template.
"""
import contextlib
import fcntl
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
import traceback
from datetime import datetime
from pathlib import Path

import brief
import cleanup
import common
import fontcheck
import inbox
from common import PIPE, ROOT, save_json

BRIEF = ROOT / "docs" / "creator" / "brief_template.uk.md"
SAMPLE = """# Бриф рілса
БРЕНД: YOCASE
ІДЕЯ: подарунок подрузі
ХУК:
> дослівно
«Що подарувати подрузі?»
КОДОВЕ СЛОВО: «ПОДАРУНОК»
МУЗИКА: без музики
ЦЕНЗУРА: гроші, знижка
ВСТАВКИ:
- коли кажу «набір» — покажи set.jpg
- коли кажу «ось так виглядає» — покажи box.mov на весь екран
ШВИДКІСТЬ: 1,2
ПРИМІТКИ: зніми ще раз кінець
без правок стилю
"""


def git(*args):
    return subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True, check=True).stdout


def t_brief(tmp):
    empty = {"brand": None, "format": None, "idea": None, "hook": None, "code_word": None, "music": None,
             "censor": [], "inserts": [], "no_style_changes": False, "speed": None, "reference": None, "notes": None}
    assert brief.parse(BRIEF) == empty, brief.parse(BRIEF)
    got = brief.parse_text(SAMPLE)
    want = {**empty, "brand": "YOCASE", "idea": "подарунок подрузі", "hook": "Що подарувати подрузі?",
            "code_word": "ПОДАРУНОК", "music": False, "censor": ["гроші", "знижка"],
            "inserts": [{"when": "набір", "show": "set.jpg", "fullscreen": False},
                        {"when": "ось так виглядає", "show": "box.mov", "fullscreen": True}],
            "no_style_changes": True, "speed": 1.2, "notes": "зніми ще раз кінець\nбез правок стилю"}
    assert got == want, got
    std = brief.parse_text("ЦЕНЗУРА: стандартна\nМУЗИКА: «Gimme That Groove»")
    assert std["censor"] == json.loads((PIPE / "studio_default.json").read_text())["censor_sets"]["standard"], std
    assert std["music"] == "Gimme That Groove", std
    ins = {"when": "набір", "show": "set.jpg", "fullscreen": False}
    for text, part in (                                 # a free phrase under a label is a command, not its value
            ("БРЕНД: YOCASE\nколи кажу «набір» — покажи set.jpg на весь екран",
             {"brand": "YOCASE", "inserts": [{**ins, "fullscreen": True}]}),
            ("МУЗИКА: groove\nбез правок стилю", {"music": "groove", "no_style_changes": True}),
            ("ХУК: Що подарувати?\nколи кажу «набір» — покажи set.jpg\nбез музики",
             {"hook": "Що подарувати?", "inserts": [ins], "music": False}),
            ("ХУК:\n> дослівно\n\nЩо подарувати\nподрузі?\n\nколи кажу «набір» — покажи set.jpg\nзроби яскравіше",
             {"hook": "Що подарувати\nподрузі?", "inserts": [ins]}),
            ("БРЕНД:\nYOCASE\nподарунок подрузі\nЦЕНЗУРА: гроші, знижка\nзроби коротше",
             {"brand": "YOCASE", "censor": ["гроші", "знижка"]}),
            ("ВСТАВКИ:\n- коли кажу «набір» — покажи set.jpg\n\n- фото коробки\nбез музики",
             {"inserts": [ins, {"when": None, "show": "фото коробки", "fullscreen": False}], "music": False})):
        got = brief.parse_text(text)
        assert got == {**empty, **part}, (text, got)


def t_cmap(tmp):
    for f in sorted((ROOT / "assets" / "fonts").glob("*.ttf")):
        cps = fontcheck.cmap_codepoints(str(f))
        assert all(ord(c) in cps for c in fontcheck.PROBE), f.name
    chalk = Path("/System/Library/Fonts/Supplemental/Chalkduster.ttf")
    if chalk.exists():
        cps = fontcheck.cmap_codepoints(str(chalk))
        assert not any(ord(c) in cps for c in "іїєґІЇЄҐ№" + fontcheck.UA), "Chalkduster has Cyrillic?"
        assert all(ord(c) in cps for c in fontcheck.LATIN), "Chalkduster lacks Latin?"


def touch(p, size=10):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(b"x" * size)
    return p


def t_cleanup(tmp):
    root = tmp / "c"
    orig = touch(root / "inbox" / "r" / "A.MOV", 5)
    media = touch(root / "build" / "r" / "media" / "A.mov", 1000)
    (root / "output" / "r_project" / "media").mkdir(parents=True)
    os.link(media, root / "output" / "r_project" / "media" / "A.mov")
    touch(root / "output" / "r_project" / "b0.mov", 100)
    save_json({"fps": 30, "clips": [{"name": "A", "orig": str(orig), "file": "media/A.mov", "n_frames": 3}]},
              root / "build" / "r" / "clips.json")
    for f, n in (("output/r_draft.mp4", 10), ("output/r.mp4", 10), ("build/r_mix_raw.wav", 10),
                 ("build/r_draft_mix.wav", 10), ("build/r-2_mix_raw.wav", 10), ("output/r-2_draft.mp4", 10),
                 ("build/r/masks.npy", 10), ("build/r_music.wav", 10), ("build/r_draft_music.wav", 10)):
        touch(root / f, n)
    plan, _ = cleanup.make_plan(root, ["r"])
    paths = sorted(it["path"] for it in plan["items"])
    assert paths == sorted(["output/r_project", "output/r_draft.mp4", "build/r_mix_raw.wav", "build/r_draft_mix.wav",
                            "build/r_music.wav", "build/r/media"]), paths    # r_draft_music: no r_draft_project
    assert any(k.startswith("build/r_draft_music.wav") for k in plan["kept"]), plan["kept"]
    assert plan["frees_bytes"] == 1000 + 100 + 10 * 4, plan["frees_bytes"]

    def without_time(*reels):
        p, _ = cleanup.make_plan(root, list(reels))
        return {k: v for k, v in p.items() if k != "created"}
    assert without_time("r", "r") == without_time("r")            # a reel named twice: the plan for one
    both = [it["path"] for it in without_time("r", "r_draft")["items"]]     # r_draft named too: its final stays
    assert len(both) == len(set(both)) and "output/r_draft.mp4" not in both, both
    other = tmp / "o"                                   # inbox.new made r and r_draft: r_draft.mp4 is a final
    for f in ("inbox/r/A.MOV", "done/r_draft/A.MOV", "output/r_draft.mp4", "output/r_draft_project/a.mov",
              "build/r_draft_mix.wav", "build/r_draft_music.wav", "build/r_mix.wav"):
        touch(other / f)
    p, _ = cleanup.make_plan(other, ["r"])
    assert [it["path"] for it in p["items"]] == ["build/r_mix.wav"] and any("r_draft" in k for k in p["kept"]), p
    orig.unlink()                                       # the clip is gone: the media stays, its link frees nothing
    plan, _ = cleanup.make_plan(root, ["r"])
    assert "build/r/media" not in [it["path"] for it in plan["items"]], plan["items"]
    assert plan["frees_bytes"] == 100 + 10 * 4, plan["frees_bytes"]
    touch(orig, 5)
    plan, _ = cleanup.make_plan(root, ["r"], all_=True)
    touch(root / "output" / "r_project" / "new.mov", 1)    # changed since the plan: apply deletes nothing
    try:
        cleanup.apply_plan(root, json.loads(json.dumps(plan)))
        raise AssertionError("apply ran on a stale plan")
    except SystemExit as e:
        assert e.code == 2
    assert (root / "build" / "r" / "media" / "A.mov").exists()
    plan, _ = cleanup.make_plan(root, ["r"], all_=True)
    assert cleanup.apply_plan(root, json.loads(json.dumps(plan))) == plan["frees_bytes"]
    left = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
    assert left == ["build/r-2_mix_raw.wav", "build/r/clips.json", "build/r_draft_music.wav", "inbox/r/A.MOV",
                    "output/r-2_draft.mp4", "output/r.mp4"], left
    build = tmp / "t" / "build"                         # --temp: kept while another job runs, applied under the lock
    for f in ("vp_x/a.mov", "overlay/a.png", "vp.txt"):
        touch(build / f)
    saved, common.BUILD = common.BUILD, build
    try:
        fd = os.open(build / ".studio.lock", os.O_RDWR | os.O_CREAT, 0o644)
        fcntl.flock(fd, fcntl.LOCK_EX)
        os.write(fd, b"render (pid 1)\n")
        plan, _ = cleanup.make_plan(build.parent, [], temp=True)
        assert not plan["items"] and plan["kept"] == ["temporary render folders (studio busy: render (pid 1))"], plan
        os.close(fd)
        plan, _ = cleanup.make_plan(build.parent, [], temp=True)
        assert [it["path"] for it in plan["items"]] == ["build/vp_x", "build/overlay"], plan["items"]
        with common.studio_lock("cleanup apply"):       # what main() does: apply must not see its own lock as busy
            cleanup.apply_plan(build.parent, json.loads(json.dumps(plan)))
        assert sorted(p.name for p in build.iterdir()) == [".studio.lock", "vp.txt"], list(build.iterdir())
    finally:
        common.BUILD = saved


def t_inbox(tmp):
    assert inbox.translit("Юля їжак Згода м'ята") == "yulia yizhak zghoda miata"
    assert inbox.slug("Подарунок подрузі!", 30) == "podarunok_podruzi"
    root = tmp / "i"
    (root / "brands" / "yocase").mkdir(parents=True)
    (root / "brands" / "yocase" / "brand.json").write_text((ROOT / "brands" / "yocase" / "brand.json").read_text())
    (root / "docs" / "creator").mkdir(parents=True)
    (root / "docs" / "creator" / "brief_template.uk.md").write_text(BRIEF.read_text(encoding="utf-8"),
                                                                     encoding="utf-8")
    day = datetime(2026, 10, 21)
    rid = inbox.new("ЙОКЕЙС", "подарунок подрузі", root, day)
    assert rid == "yocase_261021_podarunok_podruzi", rid
    assert inbox.new("yocase", "подарунок подрузі", root, day) == rid + "-2"
    b = brief.parse(root / "inbox" / rid / "brief.md")
    assert (b["brand"], b["idea"]) == ("YOCASE", "подарунок подрузі"), b
    assert (root / "inbox" / rid / "inserts").is_dir() and (root / "build" / rid / "logs").is_dir()
    assert len(inbox.new("yocase", "дуже довга назва рілса про подарунок для найкращої подруги", root, day)) <= 40
    assert inbox.new("yocase", "", root, day) == "yocase_261021"         # its draft render is yocase_261021_draft
    assert inbox.new("yocase", "Драфт", root, day) == "yocase_261021_draft-2"
    assert inbox.archive(rid, root) == root / "done" / rid
    (root / "inbox" / rid).mkdir()
    assert inbox.archive(rid, root) == root / "done" / f"{rid}-2"   # never over the first archive
    (root / "inbox" / rid).mkdir()
    try:
        inbox.reopen_plan(rid, root)
        raise AssertionError("reopen over an open reel")
    except SystemExit:
        pass
    r = root / "done" / "r"                            # archived; cleanup removed its media
    for n in ("B.MOV", "A.MOV"):
        touch(r / n)
    save_json({"fps": 30, "clips": [{"name": n[0], "orig": f"/gone/{n}", "file": f"media/{n[0]}.mov", "n_frames": 9,
                                     "speed": 1.0} for n in ("B.MOV", "A.MOV")]}, root / "build" / "r" / "clips.json")
    touch(root / "build" / "r" / "masks.npy")
    plan = inbox.reopen(r.name, dry_run=True, root=root)
    assert plan["move"] and [p.name for p in plan["reingest"]] == ["B.MOV", "A.MOV"], plan
    assert all(p.parent == root / "inbox" / "r" for p in plan["reingest"]) and plan["frames"] == 18, plan
    assert r.is_dir() and not (root / "inbox" / "r").exists(), "dry run moved the reel"


LOCKER = """import os, subprocess, sys
sys.path.insert(0, {pipe!r})
from pathlib import Path
import common
common.BUILD = Path({tmp!r})
"""


def t_lock(tmp):
    env = {k: v for k, v in os.environ.items() if k != "REEL_STUDIO_LOCK_PID"}
    head = LOCKER.format(pipe=str(PIPE), tmp=str(tmp))
    child = head + "with common.studio_lock('child'):\n    print('in', flush=True)\n"
    holder = head + ("with common.studio_lock('holder A'):\n"
                     f"    c = subprocess.run([sys.executable, '-c', {child!r}], capture_output=True, text=True)\n"
                     "    print(c.returncode, c.stdout.strip(), flush=True)\n"
                     "    sys.stdin.readline()\n")
    a = subprocess.Popen([sys.executable, "-c", holder], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
                         env=env)
    try:
        assert a.stdout.readline().split() == ["0", "in"], "the holder's child was refused"
        b = subprocess.run([sys.executable, "-c", head + "with common.studio_lock('B'):\n    pass\n"],
                           capture_output=True, text=True, env=env)
        assert b.returncode == 2 and "holder A" in b.stderr, (b.returncode, b.stderr)
    finally:
        a.communicate("\n", timeout=10)


def repo_files():
    return set(git("ls-files", "--cached", "--others", "--exclude-standard").splitlines())


def t_refs(tmp):
    files = repo_files()
    docs = [ROOT / "CLAUDE.md", ROOT / "INSTALL.md", ROOT / "learned" / "README.md",
            *sorted((ROOT / ".claude" / "skills").rglob("*.md"))]
    bad = []
    for d in docs:
        for ref in re.findall(r"(?<![\w./:-])(pipeline/[\w.-]+\.py|(?:formats|docs)/[\w./-]*[\w/])",
                              d.read_text(encoding="utf-8")):
            if not (ref in files or any(f.startswith(ref.rstrip("/") + "/") for f in files)):
                bad.append(f"{d.relative_to(ROOT)}: {ref}")
    assert not bad, "not in the repository: " + ", ".join(bad)


def t_tracked(tmp):
    tracked = set(git("ls-files", "learned", "inbox", "done", "build", "output").splitlines())
    assert tracked <= {"learned/README.md"}, f"tracked creator files: {sorted(tracked)}"
    local = [f for f in repo_files() if Path(f).name == "CLAUDE.local.md"]
    assert not local, f"Claude Code loads these into every session that touches their folder: {local}"


def t_ignore(tmp):
    ignored = ["inbox/r/brief.md", "done/r/a.MOV", "learned/general.md", "learned/brands/yocase.md",
               "assets/local/music/a.wav", "brands/yocase/local/font.ttf", "CLAUDE.local.md",
               ".claude/settings.local.json", "build/r/logs/run_prep.log"]
    kept = ["learned/README.md", "docs/creator/CLAUDE.local.template.md", "docs/creator/claude-settings.local.json",
            "docs/creator/brief_template.uk.md", ".claude/settings.json", "CLAUDE.md"]
    r = subprocess.run(["git", "-C", str(ROOT), "check-ignore", "--no-index", *ignored, *kept],
                       capture_output=True, text=True)
    got = set(r.stdout.splitlines())
    assert got == set(ignored), f"should be ignored: {sorted(set(ignored) - got)}; " \
                                f"should be kept: {sorted(got - set(ignored))}"


def t_settings(tmp):
    shared = json.loads((ROOT / ".claude" / "settings.json").read_text())
    assert set(shared) == {"permissions"} and set(shared["permissions"]) == {"allow"}, \
        "the tracked settings may only allow (every session of both machines loads them)"
    creator = json.loads((ROOT / "docs" / "creator" / "claude-settings.local.json").read_text())
    assert creator["autoMemoryEnabled"] is False and creator["permissions"]["defaultMode"] == "default"
    assert "Bash(.venv/bin/python pipeline/cleanup.py apply *)" in creator["permissions"]["ask"]
    assert not any("cleanup.py apply" in r for r in shared["permissions"]["allow"])
    rules = shared["permissions"]["allow"] + creator["permissions"]["deny"] + creator["permissions"]["ask"]
    assert all(re.fullmatch(r"[A-Z]\w*(\(.+\))?", r) for r in rules), "malformed rule"


TESTS = [t_brief, t_cmap, t_cleanup, t_inbox, t_lock, t_refs, t_tracked, t_ignore, t_settings]


def main():
    t0, failed = time.time(), []
    for t in TESTS:
        with tempfile.TemporaryDirectory() as tmp, contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()):
            try:
                t(Path(tmp))
            except (Exception, SystemExit) as e:        # noqa: BLE001 - every failure is reported, then exit 1
                where = traceback.extract_tb(e.__traceback__)[-1]
                failed.append(f"FAIL {t.__name__[2:]}: {type(e).__name__}: {e} ({Path(where.filename).name}:"
                              f"{where.lineno})")
    for f in failed:
        print(f)
    names = ", ".join(t.__name__[2:] for t in TESTS)
    print(f"selftest: {len(TESTS) - len(failed)}/{len(TESTS)} passed in {time.time() - t0:.1f} s ({names})")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
