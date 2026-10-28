"""Is this Mac ready to make reels? Health and preflight checks for the studio.

python doctor.py                     quick checks, no torch and no browser: location, Python and its lock stamp,
                                     macOS, RAM, ffmpeg and its encoders, Playwright's Chromium, model caches, fonts
                                     and brand files, disk, local changes, who is at the keyboard, housekeeping
python doctor.py --full              also torch/MPS and the matting model, a Chromium render of Cyrillic in the studio
                                     font, test encodes, and a real decode plus a 2 s transcription through prep.py's
                                     own code path (about 30 s and 2 GB of RAM; after every update)
python doctor.py --clips <dir|file> ... [--speed k]
                                     a reel's footage (inbox/<reel>): HDR, length, insert files, disk need
python doctor.py --script <script.json>
                                     every character the reel draws is in the font that draws it; build files exist
python doctor.py --report            also writes output/developer_report.txt to send to the other person

Prints "OK|WARN|FAIL <key>: <message>", problems first, and exits 1 on any FAIL. Only the standard library is
imported at start (each check imports what it tests), so it still reports when .venv packages are broken.
"""
import argparse
import contextlib
import copy
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import common
from common import BUILD, OUT, PIPE, ROOT

FFMPEG_TESTED = ("9.",)                         # major versions the pipeline was verified with
ENCODERS = ("prores_ks", "libx264", "aac")
PROBE_TEXT = "Їжак ґанок «№1» — ʼєі’ Ґ*"
RAW_GB_PER_MIN, REEL_GB, EXPORT_GB, INSERT_MB_PER_S = 1.7, 0.5, 1.0, 27   # measured on yocase_2373
UNKNOWN_REEL_GB, SWAP_GB, LOW_DISK_GB = 3.5, 5.0, 15.0
HDR_HINT = ("«Вимкни HDR-відео: Параметри → Камера → Запис відео → HDR-відео — вимкнути, і перезніми або "
            "надішли SDR-версію»")
results = []


def say(level, key, msg):
    results.append((level, key, msg))


def sh(cmd, timeout=120):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def gb(n):
    return f"{n / 1e9:.1f} GB"


def check_location():
    home, git = Path.home(), ROOT / ".git"
    synced = [d for d in ("Desktop", "Documents", "Downloads", "Library/Mobile Documents")
              if ROOT.is_relative_to(home / d)]
    if git.is_file():
        say("FAIL", "location", f"{ROOT} is a git worktree: work in the main folder ~/reel-studio "
                                "(«відкрий нову сесію в папці reel-studio»)")
    elif not git.is_dir():
        say("FAIL", "location", f"{ROOT} is not a git checkout (clone it again, see INSTALL.md)")
    elif synced:
        say("FAIL", "location", f"{ROOT} is under ~/{synced[0]} (iCloud and privacy prompts): clone to ~/reel-studio")
    elif "'" in str(ROOT):
        say("FAIL", "location", f"{ROOT} has a ' in it, which breaks ffmpeg's concat files")
    else:
        say("OK", "location", str(ROOT))


def check_python():
    venv, v = ROOT / ".venv", sys.version_info
    if Path(sys.prefix).resolve() != venv.resolve():
        say("FAIL", "python", f"run with .venv/bin/python, not {sys.executable}")
    elif v[:2] != (3, 12):
        say("FAIL", "python", f"3.12 expected, .venv has {platform.python_version()}: re-run zsh pipeline/setup_mac.sh")
    else:
        say("OK", "python", f"{platform.python_version()} in .venv")
    stamp = venv / "reel-studio.lock.sha256"
    want = hashlib.sha256((PIPE / "requirements.lock.txt").read_bytes()).hexdigest()
    if not stamp.exists():
        say("WARN", "lock stamp", ".venv has no stamp of requirements.lock.txt (installed before stamps; "
                                  "setup_mac.sh writes it)")
    elif stamp.read_text().split()[:1] != [want]:
        say("FAIL", "lock stamp", ".venv was installed from another requirements.lock.txt: re-run "
                                  "zsh pipeline/setup_mac.sh")
    else:
        say("OK", "lock stamp", ".venv matches requirements.lock.txt")


def check_machine():
    ver = platform.mac_ver()[0]
    major = int(ver.split(".")[0]) if ver else 0
    say("OK" if major >= 14 else "FAIL", "macos",
        f"{ver or 'not macOS'} {platform.machine()}" + ("" if major >= 14 else " (14 or newer needed)"))
    ram = common.ram_bytes()
    say("OK", "ram", f"{gb(ram)}: {common.default_procs()} render processes, whisper "
                     f"{'int8' if common.low_ram() else 'float32'}")


def check_ffmpeg():
    ff, fp = shutil.which("ffmpeg"), shutil.which("ffprobe")
    if not ff or not fp:
        say("FAIL", "ffmpeg", "ffmpeg/ffprobe not found (setup_mac.sh installs them with Homebrew)")
        return
    line = sh([ff, "-hide_banner", "-version"]).stdout.split("\n")[0]
    ver = (re.search(r"version (\S+)", line) or [None, "?"])[1]
    enc = sh([ff, "-hide_banner", "-encoders"]).stdout
    missing = [e for e in ENCODERS if not re.search(rf"^\s*\S{{6}}\s+{e}\s", enc, re.M)]
    if missing:
        say("FAIL", "ffmpeg", f"{ff} {ver} lacks encoders: {', '.join(missing)}")
    elif not ver.startswith(FFMPEG_TESTED):
        say("WARN", "ffmpeg", f"{ff} {ver} is untested (tested: {', '.join(v + 'x' for v in FFMPEG_TESTED)}); "
                              "run doctor.py --full and a draft before a reel")
    else:
        say("OK", "ffmpeg", f"{ff} {ver}, encoders {', '.join(ENCODERS)}")


def playwright_browsers():
    """(Playwright version, Chromium version, [(name, folder, installed)]) for the Chromium the locked Playwright
    pins, or None when Playwright is not in .venv."""
    found = sorted((ROOT / ".venv" / "lib").glob("python3*/site-packages/playwright/driver/package/browsers.json"))
    if not found:
        return None
    browsers = {b["name"]: b for b in json.loads(found[0].read_text())["browsers"]}
    pw = next(iter(sorted(found[0].parents[3].glob("playwright-*.dist-info"))), None)
    base = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH") or Path.home() / "Library" / "Caches" / "ms-playwright")
    dirs = [(n, base / f"{n.replace('-', '_')}-{browsers[n]['revision']}")
            for n in ("chromium", "chromium-headless-shell")]
    return (pw.name.split("-")[1].removesuffix(".dist") if pw else "?", browsers["chromium"]["browserVersion"],
            [(n, d, (d / "INSTALLATION_COMPLETE").exists()) for n, d in dirs])


def check_chromium():
    pb = playwright_browsers()
    if pb is None:
        say("FAIL", "chromium", "Playwright is not installed in .venv (setup_mac.sh)")
        return
    pw, version, dirs = pb
    missing = [n for n, _, ok in dirs if not ok]
    if missing:
        say("FAIL", "chromium", f"Playwright {pw}'s Chromium {version} is not installed ({', '.join(missing)}; "
                                "setup_mac.sh installs it)")
    else:
        say("OK", "chromium", f"Chromium {version} pinned by Playwright {pw} ({dirs[0][1].parent})")


def check_models():
    hub = Path(os.environ.get("HF_HUB_CACHE") or
               Path(os.environ.get("HF_HOME") or Path.home() / ".cache" / "huggingface") / "hub")
    bins = [p for p in hub.glob("models--Systran--faster-whisper-large-v3/snapshots/*/model.bin") if p.exists()]
    size = max((p.stat().st_size for p in bins), default=0)
    say("OK" if size > 2.5e9 else "FAIL", "whisper",
        f"large-v3 {gb(size)} in {hub}" if size > 2.5e9 else f"large-v3 is not downloaded to {hub} (setup_mac.sh)")
    th = Path(os.environ.get("TORCH_HOME") or Path.home() / ".cache" / "torch") / "hub"
    need = [th / "PeterL1n_RobustVideoMatting_master" / "hubconf.py", th / "checkpoints" / "rvm_resnet50.pth"]
    lost = [str(p) for p in need if not p.exists()]
    say("FAIL" if lost else "OK", "matting",
        f"missing {', '.join(lost)} (setup_mac.sh)" if lost else f"RVM resnet50 cached in {th}")


def brand_looks():
    """[(look name, resolved style)]: the studio look and every brand's, fonts as absolute files."""
    import resolve
    studio = common.load_json(PIPE / "style_default.json")
    looks = [("studio", copy.deepcopy(studio))]
    for p in sorted((ROOT / "brands").glob("*/brand.json")):
        looks.append((p.parent.name, resolve.merge(copy.deepcopy(studio), common.load_json(p).get("style", {}))))
    for _, style in looks:
        resolve.font_urls(style)
    return looks


def check_fonts():
    """G8/G10: every font of the studio and the brands exists, is TTF/OTF and has the probe set; every brand file
    (brands/<b>/local/, copied in person) and the brand music exist."""
    import fontcheck
    problems, files, looks = [], set(), brand_looks()
    for name, style in looks:
        bad = []
        for alias, faces in style.get("fonts", {}).items():
            for f in faces:
                p = Path(f["file"])
                if not p.is_file():
                    bad.append(f"{name}: font {alias} missing: {common.short(p)} (licensed fonts are copied "
                               "into brands/<brand>/local/ in person)")
                    continue
                with open(p, "rb") as fh:
                    if fh.read(4) not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
                        bad.append(f"{name}: font {alias}: {common.short(p)} is not a TTF/OTF font")
                        continue
                files.add(p)
        problems += bad or [f"{name}: {x}" for x in fontcheck.check_glyphs(style, [])]
    for p in sorted((ROOT / "brands").glob("*/brand.json")):
        refs = re.findall(r'"(brands/[^"]+)"', p.read_text(encoding="utf-8"))
        problems += [f"{p.parent.name}: {r} is missing (copied in person)" for r in refs if not (ROOT / r).exists()]
        music = ((common.load_json(p).get("audio") or {}).get("music") or {}).get("file")
        if music:
            import assets
            if assets.find("music", music) is None:
                problems.append(f"{p.parent.name}: music {music} not found in assets/")
    if problems:
        for x in problems:
            say("FAIL", "fonts", x + " (copy the brand's local/ folder, INSTALL.md step 7)")
    else:
        say("OK", "fonts", f"{len(files)} font files of the studio and {len(looks) - 1} brands draw "
                           "Ukrainian and Latin in both cases, digits and ʼ’№«»–—*; brand files present")


def check_disk(need):
    free = shutil.disk_usage(ROOT).free
    msg = f"{gb(free)} free, a reel needs ~{gb(need)} plus {SWAP_GB:.0f} GB headroom"
    if free - need < SWAP_GB * 1e9:
        say("FAIL", "disk", msg + ": free space first (cleanup.py plan of archived reels)")
    elif free < LOW_DISK_GB * 1e9:
        say("WARN", "disk", msg + f"; under {LOW_DISK_GB:.0f} GB free")
    else:
        say("OK", "disk", msg)


def check_git():
    r = sh(["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no"])
    if r.returncode:
        say("WARN", "local changes", f"git status failed: {r.stderr.strip()[:200]}")
        return
    changed = [ln[3:] for ln in r.stdout.splitlines() if ln.strip()]
    if changed:
        say("WARN", "local changes", f"{len(changed)} tracked files changed here ({', '.join(changed[:4])}"
                                     f"{', ...' if len(changed) > 4 else ''}): commit or discard them before the next pull")
    else:
        say("OK", "local changes", "none in tracked files")


def marina_machine():
    p = ROOT / "CLAUDE.local.md"
    text = p.read_text(encoding="utf-8") if p.is_file() else ""
    return re.search(r"(?mi)^(person:\s*marina|mode:\s*creator)\b", text) is not None, \
        re.search(r"(?mi)^mode:\s*creator\b", text) is not None


# rules of the old creator template (before 2026-10-28) that kept Marina from changing the studio
OLD_LOCKS = ("Bash(git push *)", "Bash(git commit *)", "Edit(/pipeline/**)", "Bash(zsh pipeline/setup_mac.sh *)")


def check_role():
    marina, legacy = marina_machine()
    lp = ROOT / ".claude" / "settings.local.json"
    deny = (common.load_json(lp).get("permissions") or {}).get("deny", []) if lp.exists() else []
    if any(r in deny for r in OLD_LOCKS):
        say("WARN", "role", ".claude/settings.local.json still has the old creator restrictions (no commits, no "
                            "code edits): delete that file (INSTALL.md, Updates)")
    elif legacy:
        say("WARN", "role", "CLAUDE.local.md has the old 'Mode: creator' line: copy "
                            "docs/creator/CLAUDE.local.template.md again (INSTALL.md, Updates)")
    else:
        say("OK", "role", "Marina's Mac (CLAUDE.local.md)" if marina else "Vlad's Mac (no 'Person: Marina' in "
                                                                          "CLAUDE.local.md)")


def check_housekeeping():
    import cleanup
    holder = cleanup.lock_holder()
    if holder:
        say("WARN", "studio lock", f"busy: {holder}")
    vp = [p for p in BUILD.glob("vp_*") if p.is_dir()]
    if vp and not holder:                               # while a job runs, its vp_* folders are live
        size = sum(f.stat().st_size for d in vp for f in d.rglob("*") if f.is_file())
        say("WARN", "leftovers", f"{len(vp)} build/vp_* folders from a stopped render, {gb(size)} "
                                 "(cleanup.py plan --temp)")
    done = [d.name for d in (ROOT / "done").glob("*") if (BUILD / d.name / "media").is_dir()]
    if done:
        size = sum(f.stat().st_size for r in done for f in (BUILD / r / "media").rglob("*") if f.is_file())
        say("OK", "reclaimable", f"{gb(size)} of media in {len(done)} archived reels (cleanup.py plan <reel>)")


def check_clips(args, speed):
    """--clips: her talking videos (a reel folder's own videos, or files), the insert files, the disk need."""
    import inbox
    import ingest
    talk, inserts = [], []
    for a in args:
        p = Path(a)
        if p.is_dir():
            talk += inbox.videos(p)
            inserts += inbox.pictures(p)
        elif p.is_file():
            talk.append(p)
        else:
            say("FAIL", "clips", f"{a} not found")
    if not talk:
        say("FAIL", "clips", f"no talking videos in {', '.join(args)} (pictures and insert clips go in inserts/)")
    total = ins_s = 0.0
    for v in talk:
        try:
            vs, au, fmt = ingest.probe(v)
        except (subprocess.CalledProcessError, StopIteration):
            say("FAIL", "clip", f"{v.name}: not a video ffprobe can read")
            continue
        dur = ingest.video_duration(vs, fmt)
        total += dur
        if vs.get("color_transfer") in ingest.HDR_TRC:
            say("FAIL", "clip", f"{v.name}: HDR video ({vs['color_transfer']}), {dur:.1f} s: {HDR_HINT}")
        else:
            say("OK", "clip", f"{v.name}: SDR, {dur:.1f} s, {vs.get('codec_name')} {vs.get('width')}x"
                              f"{vs.get('height')}" + ("" if au else ", no sound"))
    vids = [p for p in inserts if p.suffix.lower() in inbox.VIDEO]
    for v in vids:
        try:
            vs, _, fmt = ingest.probe(v)
            ins_s += ingest.video_duration(vs, fmt)
            if vs.get("color_transfer") in ingest.HDR_TRC:
                say("WARN", "insert", f"{v.name}: HDR video, will be refused: ask for an SDR copy")
        except (subprocess.CalledProcessError, StopIteration):
            say("WARN", "insert", f"{v.name}: not a video ffprobe can read")
    pics = [p for p in inserts if p.suffix.lower() in inbox.PICTURE]
    other = [p.name for p in inserts if p not in vids and p not in pics]
    if inserts:
        heic = sum(p.suffix.lower() in (".heic", ".heif") for p in pics)
        say("WARN" if other else "OK", "inserts", f"{len(pics)} pictures" + (f" ({heic} HEIC)" if heic else "")
            + f", {len(vids)} videos ({ins_s:.1f} s)"
            + (f"; not a picture or video: {', '.join(other)}" if other else ""))
    need = RAW_GB_PER_MIN * 1e9 * total / 60 / speed + REEL_GB * 1e9 + INSERT_MB_PER_S * 1e6 * ins_s
    if talk:
        say("OK", "clips", f"{len(talk)} video{'s' if len(talk) > 1 else ''}, {total:.1f} s"
            + (f" at speed {speed:g}" if speed != 1 else "")
            + f": a reel needs ~{gb(need)} (+{EXPORT_GB:.0f} GB with the editable project)")
    return need, talk


def check_script(path):
    """--script: every drawn character is in the font that draws it; the build files the script names exist."""
    import fontcheck
    import resolve
    try:
        script = resolve.load_script(path, check_fonts=True)
    except SystemExit as e:
        say("FAIL", "script", str(e.code))
        return
    try:
        import text_rules
        display_tokens = text_rules.display_tokens
    except (ImportError, AttributeError):
        display_tokens = resolve.display_tokens
    lines = display_tokens(script)
    problems = fontcheck.check_glyphs(script["style"], lines)
    for x in problems:
        say("FAIL", "glyphs", x)
    if not problems:
        fams = sorted({Path(f["file"]).name for fs in script["style"]["fonts"].values() for f in fs})
        say("OK", "glyphs", f"{len(lines)} lines: every character is in its font ({', '.join(fams)})")
    raw = common.load_json(path)
    lost = [f"{k} {raw[k]}" for k in ("source", "words", "masks", "track")
            if raw.get(k) and not (ROOT / raw[k]).exists()]
    src = ROOT / raw["source"] if raw.get("source") else None
    if src and src.suffix == ".ffconcat" and src.exists():
        media = re.findall(r"(?m)^file '([^']+)'", src.read_text(encoding="utf-8"))
        lost += [f"media {m}" for m in media if not (src.parent / m).exists()]
    reel = Path(path).resolve().parent.name
    if lost:
        say("FAIL", "build files", f"missing: {', '.join(lost[:4])}: after a cleanup, inbox.py reopen {reel} "
                                   "brings the media back")
    else:
        say("OK", "build files", "the source, words, masks and track the script names exist")


def check_full(clip):
    """--full: the heavy imports and real runs a broken update would break; the decode uses her first clip when
    --clips names one, else the test clip."""
    t = time.time()
    try:
        import torch
        say("OK", "torch", f"{torch.__version__}, MPS {'yes' if torch.backends.mps.is_available() else 'no'}")
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            torch.hub.load("PeterL1n/RobustVideoMatting", "resnet50", trust_repo=True)      # as prep.matte loads it
        say("OK", "matting load", "RVM resnet50 loads through torch.hub")
    except Exception as e:                              # noqa: BLE001 - report any breakage as a FAIL line
        say("FAIL", "torch", f"{type(e).__name__}: {e}"[:300])
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        try:
            probe_chromium(td)
        except Exception as e:                          # noqa: BLE001
            say("FAIL", "chromium render", f"{type(e).__name__}: {e}"[:300])
        try:
            test = synth_clip(td)
            decode_and_transcribe(clip or test, td)
        except Exception as e:                          # noqa: BLE001
            say("FAIL", "decode", f"{type(e).__name__}: {e}"[:300])
    say("OK", "full", f"heavy checks took {time.time() - t:.0f} s")


def probe_chromium(td):
    """The studio's main font loaded into the pinned Chromium and Cyrillic drawn with it."""
    from playwright.sync_api import sync_playwright
    style = brand_looks()[0][1]
    font = Path(style["fonts"][style["main"]["family"]][0]["file"])
    page = td / "probe.html"
    page.write_text("""<!doctype html><meta charset="utf-8"><canvas id="c" width="1080" height="200"></canvas><script>
window.probe = async (url, text) => {
  const f = new FontFace("Probe", `url(${url})`); await f.load(); document.fonts.add(f);
  const c = document.getElementById("c").getContext("2d");
  c.font = "64px monospace"; const w0 = c.measureText(text).width;
  c.font = "64px Probe"; const w = c.measureText(text).width;
  c.fillStyle = "#fff"; c.fillText(text, 10, 100);
  const d = c.getImageData(0, 0, 1080, 200).data; let ink = 0;
  for (let i = 3; i < d.length; i += 4) if (d[i]) ink++;
  return {w, w0, ink, ok: document.fonts.check("64px Probe", text)};
};</script>""", encoding="utf-8")
    with sync_playwright() as p:                        # launched the way overlay_render.worker launches it
        b = p.chromium.launch(args=["--font-render-hinting=none", "--disable-lcd-text"])
        pg = b.new_page()
        pg.goto(page.as_uri())
        r = pg.evaluate("([u, t]) => probe(u, t)", [font.as_uri(), PROBE_TEXT])
        version = b.version
        b.close()
    good = r["ok"] and r["ink"] > 2000 and abs(r["w"] - r["w0"]) > 1
    say("OK" if good else "FAIL", "chromium render",
        f"Chromium {version} drew «{PROBE_TEXT}» in {font.name}" if good else f"probe failed: {r}")


def synth_clip(td):
    """A 2 s test clip with sound, made with the encoders the pipeline uses (also a ProRes test encode)."""
    out = td / "probe.mov"
    base = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30",
            "-f", "lavfi", "-i", "sine=frequency=330:sample_rate=48000", "-t", "2"]
    for args, what in ((["-c:v", "libx264", "-preset", "veryfast", "-c:a", "aac", str(out)], "libx264/aac"),
                       (["-c:v", "prores_ks", "-profile:v", "3", "-an", "-f", "null", "-"], "prores_ks")):
        r = sh(base + args)
        if r.returncode:
            raise RuntimeError(f"{what} encode failed: {r.stderr.strip()[:200]}")
    say("OK", "encode", "libx264, aac and prores_ks encode a test clip")
    return out


def decode_and_transcribe(clip, td):
    """prep.py's path: ffmpeg decodes the clip's sound to 16 kHz mono, prep.read_wav makes samples, Silero VAD and
    faster-whisper large-v3 (int8, as on 8 GB) run on them through prep.transcribe_chunks and model.transcribe."""
    import prep
    wav = td / "audio16k.wav"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-t", "2", "-i", str(clip), "-vn", "-ac", "1", "-ar",
                    str(prep.SR), str(wav)], check=True)
    x = prep.read_wav(wav)
    if len(x) < prep.SR:
        raise RuntimeError(f"decoded only {len(x)} samples from {Path(clip).name}")
    say("OK", "decode", f"{Path(clip).name}: {len(x) / prep.SR:.1f} s of sound -> {len(x)} samples (prep.read_wav)")
    from faster_whisper import WhisperModel
    import faster_whisper
    t = time.time()
    m = WhisperModel("large-v3", device="cpu", compute_type="int8")
    with contextlib.redirect_stdout(io.StringIO()):
        prep.transcribe_chunks(m, x, "uk")
        segs = list(m.transcribe(x, language="uk", word_timestamps=True, beam_size=5,
                                 condition_on_previous_text=False)[0])
    import av
    import ctranslate2
    say("OK", "whisper run", f"large-v3 int8 loads and transcribes 2 s ({len(segs)} segments) in "
                             f"{time.time() - t:.0f} s (faster-whisper {faster_whisper.__version__}, "
                             f"av {av.__version__}, ctranslate2 {ctranslate2.__version__})")


def report(lines):
    """output/developer_report.txt: what the other person needs to help from afar (never ~/.claude or the env)."""
    import inbox
    out = ["Reel Studio developer report " + time.strftime("%Y-%m-%d %H:%M"), "", "== doctor =="] + lines
    chip = sh(["sysctl", "-n", "machdep.cpu.brand_string"]).stdout.strip()
    out += ["", "== machine ==", f"macOS {platform.mac_ver()[0]}, {chip}, RAM {gb(common.ram_bytes())}",
            "", "== git =="]
    out += [sh(["git", "-C", str(ROOT), "log", "-1", "--format=%h %ad %s", "--date=short"]).stdout.strip(),
            sh(["git", "-C", str(ROOT), "status", "--porcelain", "--untracked-files=no"]).stdout.rstrip() or
            "(no local changes)"]
    logs = sorted(BUILD.glob("*/logs/*.log"), key=lambda p: p.stat().st_mtime, reverse=True)[:3]
    for p in logs:
        tail = p.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
        out += ["", f"== {common.short(p)} (last {len(tail)} lines) =="] + tail
    for p in sorted((ROOT / "learned").rglob("*.md")):
        if p.name != "README.md":
            out += ["", f"== {common.short(p)} ==", p.read_text(encoding="utf-8", errors="replace").rstrip()]
    out += ["", "== reels =="] + (inbox.listing() or ["(none)"])
    dest = OUT / "developer_report.txt"
    OUT.mkdir(exist_ok=True)
    dest.write_text("\n".join(out) + "\n", encoding="utf-8")
    return dest


def guarded(check, *args):
    """Run one check; a crash becomes a FAIL line instead of ending doctor."""
    try:
        return check(*args)
    except Exception as e:                              # noqa: BLE001
        say("FAIL", check.__name__.removeprefix("check_"), f"crashed: {type(e).__name__}: {e}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="also the heavy checks (torch, Chromium render, whisper)")
    ap.add_argument("--clips", nargs="+", metavar="DIR_OR_FILE", help="check a reel's footage")
    ap.add_argument("--speed", type=float, default=1.0, help="the speed-up the reel will be ingested at")
    ap.add_argument("--script", help="check a script's glyphs and build files")
    ap.add_argument("--report", action="store_true", help="write output/developer_report.txt")
    a = ap.parse_args()
    for c in (check_location, check_python, check_machine, check_ffmpeg, check_chromium, check_models, check_fonts,
              check_git, check_role, check_housekeeping):
        guarded(c)
    need, talk = (guarded(check_clips, a.clips, a.speed) if a.clips else None) or (UNKNOWN_REEL_GB * 1e9, [])
    if a.script:
        guarded(check_script, a.script)
    check_disk(need)
    if a.full:
        check_full(talk[0] if talk else None)
    lines = [f"{lv} {k}: {m}" for order in ("FAIL", "WARN", "OK") for lv, k, m in results if lv == order]
    n = {lv: sum(r[0] == lv for r in results) for lv in ("OK", "WARN", "FAIL")}
    lines.append(f"doctor: {n['OK']} OK, {n['WARN']} WARN, {n['FAIL']} FAIL")
    print("\n".join(lines))
    if a.report:
        print(f"report: {common.short(report(lines))}")
    return 1 if n["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
