"""Shared constants and helpers for the reel pipeline."""
import fcntl
import json
import math
import os
import re
import shutil
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPE = ROOT / "pipeline"
OUT = ROOT / "output"
BUILD = ROOT / "build"

W, H, FPS = 1080, 1920, 30
SHEET_EDGE = 1200          # review images (contact and review sheets): long edge in px, sized for the model


def _tool_path():
    """Homebrew's ffmpeg is not on PATH in every shell (the desktop app sources ~/.zshrc, not ~/.zprofile). Put its
    folder first, so every bare ffmpeg/ffprobe call finds it, spawned workers included (they inherit the environment)."""
    if shutil.which("ffmpeg") is None:
        for d in ("/opt/homebrew/bin", "/usr/local/bin"):
            if os.access(os.path.join(d, "ffmpeg"), os.X_OK):
                os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
                break


_tool_path()
if hasattr(sys.stdout, "reconfigure"):      # Ukrainian lines under a C locale; logs readable while a job runs
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)


def ram_bytes():
    return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")


def low_ram():
    """An 8 GB Mac: whisper int8, 2 render processes."""
    return ram_bytes() < 15e9


def default_procs():
    return 2 if low_ram() else 4


@contextmanager
def studio_lock(label):
    """One heavy job at a time (the single build slot, RAM): exit 2 while another process holds build/.studio.lock.
    The holder's child processes pass (env REEL_STUDIO_LOCK_PID is their parent), so a batch can run its steps as
    children. The fd is not inherited by workers, ffmpeg or Chrome, and the kernel drops the lock when the holder dies.
    Take it only in CLI entry points: build.py calls build_timeline.main in the same process."""
    if os.environ.get("REEL_STUDIO_LOCK_PID") == str(os.getppid()):
        yield
        return
    BUILD.mkdir(exist_ok=True)
    fd = os.open(BUILD / ".studio.lock", os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        holder = os.read(fd, 400).decode("utf-8", "replace").strip() or "another job"
        os.close(fd)
        print(f"studio busy: {holder}", file=sys.stderr)
        sys.exit(2)
    os.ftruncate(fd, 0)
    os.write(fd, f"{label} (pid {os.getpid()})\n".encode())
    prev = os.environ.get("REEL_STUDIO_LOCK_PID")
    os.environ["REEL_STUDIO_LOCK_PID"] = str(os.getpid())
    try:
        yield
    finally:
        if prev is None:
            os.environ.pop("REEL_STUDIO_LOCK_PID", None)
        else:
            os.environ["REEL_STUDIO_LOCK_PID"] = prev
        os.ftruncate(fd, 0)
        os.close(fd)


def keep_awake():
    """Keep the Mac from idle sleep until this process exits (not clamshell sleep: overnight jobs need the lid open)."""
    try:
        subprocess.Popen(["caffeinate", "-i", "-w", str(os.getpid())], stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        pass


def short(path):
    """A path as printed: repo-relative inside the repo, else absolute."""
    p = Path(path).resolve()
    return str(p.relative_to(ROOT)) if p.is_relative_to(ROOT) else str(p)


def reel_id(script_path):
    """A reel's id: the folder of its script (inbox/<id>/script.json, projects/<id>/script.json). Its prep outputs and
    logs live in build/<id>/."""
    return Path(script_path).resolve().parent.name


def require_slot(script=None, need_pass=False, force=False, render=None):
    """The guard of the single build slot (build/meta.json, camera.json, timeline.json, overlay/). Exits 2 unless
    meta.json was written for `script` (and, with `render`, that video was rendered from it); force skips this
    (developer only). need_pass also refuses while the slot's checks FAIL. Returns meta.json."""
    p = BUILD / "meta.json"
    meta = load_json(p) if p.exists() else {}

    def refuse(msg):
        print(msg, file=sys.stderr)
        sys.exit(2)
    if not force:
        if "script" not in meta:
            refuse("unknown slot: build/meta.json is missing or has no script stamp (an older or crashed build); "
                   "rebuild first")
        if script is not None and meta["script"] != str(Path(script).resolve()):
            refuse(f"build/ holds {short(meta['script'])}, not {short(script)}; rebuild first")
        if render is not None and Path(render).stem not in meta.get("renders", []):
            refuse(f"{Path(render).name} was not rendered from the build slot ({short(meta['script'])}, renders "
                   f"{meta.get('renders', [])}); rebuild first")
    fails = meta.get("checks", {}).get("fail", [])
    if need_pass and fails:
        refuse("checks FAIL:\n" + "\n".join(f"  {f}" for f in fails) + "\nfix the script (a deliberate exception: build.py --allow-check-fail)")
    return meta


PROBLEM = re.compile(r"!!|WARN|[Ww]arning|NOT FOUND")       # layout report (no free spot, OUTSIDE), warnings
STAGE = re.compile(r"\[[a-z]+\] ")                           # "[overlay] 13.2s -> build/overlay"


class _Tee:
    """sys.stdout during a run: every line goes to the log (and to the terminal with verbose); problem lines and
    stage lines are kept for the summary."""
    encoding = "utf-8"

    def __init__(self, log, term):
        self.log, self.term, self.part = log, term, ""
        self.problems, self.stages = [], []

    def write(self, s):
        self.log.write(s)
        if self.term:
            self.term.write(s)
        lines = (self.part + s).split("\n")
        self.part = lines.pop()
        for ln in lines:
            if STAGE.match(ln):
                self.stages.append(ln)
            elif PROBLEM.search(ln) and ln not in self.problems:
                self.problems.append(ln)
        return len(s)

    def flush(self):
        self.log.flush()
        if self.term:
            self.term.flush()

    def reconfigure(self, **kw):
        pass

    def isatty(self):
        return False

    def fileno(self):
        return (self.term or self.log).fileno()

    def summary(self, out, path, cap=30):
        if self.part:
            self.write("\n")
        for ln in self.problems[:cap]:
            print(ln, file=out)
        if len(self.problems) > cap:
            print(f"... {len(self.problems) - cap} more problem lines in the log", file=out)
        for ln in self.stages:
            print(ln, file=out)
        print(f"log: {short(path)}", file=out, flush=True)


@contextmanager
def run_log(path, verbose=False):
    """Run with the full output in the log at `path`. The terminal gets all of it with verbose; otherwise only a
    summary at the end, even after a crash: problem lines first, then one line per stage, then the log's path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    term = sys.stdout
    with open(path, "w", encoding="utf-8", buffering=1) as log:
        tee = _Tee(log, term if verbose else None)
        sys.stdout = tee
        try:
            yield
        finally:
            sys.stdout = term
            if verbose:
                tee.flush()
            else:
                tee.summary(term, path)


def sheet_grid(n, tile_w, cols=None, edge=SHEET_EDGE):
    """(cols, tile w, tile h) for n 9:16 tiles at most tile_w wide on a sheet whose long edge is <= edge; unless cols
    is given, the column count that gives the biggest tiles (of equal sizes, the one with the fewest rows)."""
    best = None
    for c in [cols] if cols else range(1, max(n, 1) + 1):
        rows = -(-n // c)
        tw = min(tile_w, edge // c, edge * 9 // (16 * rows))
        tw -= tw % 2
        if best is None or tw >= best[1]:
            best = (c, tw)
    return best[0], best[1], best[1] * 16 // 9


def norm(w):
    """A word as the transcript and the script are matched: lowercase, punctuation dropped (hyphens and
    apostrophes stay inside the word)."""
    return re.sub(r"[^\w\-ʼ'’]", "", w.lower()).strip("-")


def source_path(script):
    """The reel's source video (repo-relative in script.json): a 1080x1920 30 fps file, usually the
    source.ffconcat written by ingest.py."""
    return ROOT / script["source"]


def torch_device():
    import torch
    return "mps" if torch.backends.mps.is_available() else "cuda" if torch.cuda.is_available() else "cpu"


def load_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_json(obj, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)


def clamp(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def lerp(a, b, t):
    return a + (b - a) * t


def ease_out_cubic(t):
    t = clamp(t)
    return 1 - (1 - t) ** 3


def ease_in_out_cubic(t):
    t = clamp(t)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def ease_out_expo(t):
    t = clamp(t)
    return 1.0 if t >= 1 else 1 - 2 ** (-10 * t)


def ease_in_expo(t):
    t = clamp(t)
    return 0.0 if t <= 0 else 2 ** (10 * t - 10)


def ease_out_back(t, s=1.70158):
    t = clamp(t)
    return 1 + (s + 1) * (t - 1) ** 3 + s * (t - 1) ** 2


def damped_spring(t, freq=4.5, damping=6.0):
    """0 -> 1 with a small overshoot; t in seconds."""
    if t <= 0:
        return 0.0
    return 1 - math.exp(-damping * t) * math.cos(2 * math.pi * freq * t)
