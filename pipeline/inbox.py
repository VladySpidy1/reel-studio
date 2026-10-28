"""The creator's reels as folders: make one, prepare its footage, archive it when posted, reopen it for a fix.

python inbox.py new <brand> <title ...>     inbox/<reel>/ with brief.md (БРЕНД and ІДЕЯ filled in) and inserts/, plus
                                            build/<reel>/logs/; prints the reel id and the folder
python inbox.py list                        reels in inbox/ and done/: clips, pictures, brief, script, prep, outputs
python inbox.py prep <reel> [<reel> ...] [--speed k] [--force] [--dry-run]
                                            ingest + prep for each reel in turn, all under one studio lock (an
                                            overnight batch cannot be interrupted by another job); --speed k
                                            (1.0-1.3) speeds the footage up at ingest; --dry-run prints the clip
                                            order and the commands
python inbox.py archive <reel>              inbox/<reel> -> done/<reel> (-2 if taken); never deletes anything
python inbox.py reopen <reel> [--dry-run]   done/<reel> -> inbox/<reel>; media that cleanup removed is ingested again
                                            from the clips (clips.json order and speed), and prep runs again only when
                                            the frame counts no longer match masks.npy

A reel id is an ASCII slug, <brand>_<yymmdd>_<title in Latin>, so commands and permission rules never need quoting.
The videos in the reel folder itself are her talking footage, ingested in shooting order (creation_time, then mtime,
then name); pictures and clips for inserts go in inserts/ and are never ingested (inserts.py prepares them).
"""
import argparse
import ast
import json
import re
import shutil
import struct
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

from common import ROOT, keep_awake, load_json, studio_lock

VIDEO = {".mov", ".mp4", ".m4v"}
PICTURE = {".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}
SPEED = (1.0, 1.3)
RENDER_VARIANTS = ("_draft", "_no_music")                 # build.py names: <reel>_draft, <reel>_no_music
TR = {"а": "a", "б": "b", "в": "v", "г": "h", "ґ": "g", "д": "d", "е": "e", "є": "ie", "ж": "zh", "з": "z", "и": "y",
      "і": "i", "ї": "i", "й": "i", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o", "п": "p", "р": "r", "с": "s",
      "т": "t", "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ь": "", "ю": "iu",
      "я": "ia", "'": "", "ʼ": "", "’": "", "ы": "y", "э": "e", "ё": "io", "ъ": ""}
WORD_START = {"є": "ye", "ї": "yi", "й": "y", "ю": "yu", "я": "ya"}      # Ukrainian national transliteration (2010)
APOSTROPHES = {"'", "ʼ", "’"}


def count(items, word):
    return f"{len(items)} {word}{'' if len(items) == 1 else 's'}"


def translit(text):
    out, prev = [], ""
    for ch in text.lower():
        if ch == "г" and prev == "з":
            out.append("gh")                            # зг -> zgh, not zh
        elif ch in WORD_START and not prev.isalpha() and prev not in APOSTROPHES:     # м'ята -> miata
            out.append(WORD_START[ch])
        else:
            out.append(TR.get(ch, ch))
        prev = ch
    return "".join(out)


def slug(text, limit):
    s = re.sub(r"[^a-z0-9]+", "_", translit(text)).strip("_")
    if len(s) > limit:
        s = s[:limit]
        s = s[:s.rfind("_")] if "_" in s[limit // 2:] else s
    return s.strip("_")


def brand_id(name, root=ROOT):
    """The brand folder for an id, a display name or an alias (any case), or None."""
    n = name.strip().lower()
    for p in sorted((Path(root) / "brands").glob("*/brand.json")):
        d = load_json(p)
        if n in [p.parent.name, d.get("name", "").lower()] + [x.lower() for x in d.get("aliases", [])]:
            return p.parent.name
    return None


def taken(root, rid):
    """The id or a render name it shares with another reel is in use: r's draft is output/r_draft.mp4, the final of a
    reel r_draft (the title «драфт»)."""
    names = {rid} | {rid + v for v in RENDER_VARIANTS} | {rid[:-len(v)] for v in RENDER_VARIANTS if rid.endswith(v)}
    return any((Path(root) / d / n).exists() for d in ("inbox", "done", "build") for n in names)


def new(brand, title, root=ROOT, today=None):
    """Make inbox/<id>/ (brief.md, inserts/) and build/<id>/logs/; returns the id."""
    root = Path(root)
    b = brand_id(brand, root)
    if b is None:
        known = ", ".join(p.parent.name for p in sorted((root / "brands").glob("*/brand.json")))
        raise SystemExit(f"unknown brand {brand!r} (known: {known}); add brands/<id>/ first, like brands/yocase/")
    head = f"{b}_{(today or datetime.now()).strftime('%y%m%d')}"
    rid = "_".join(x for x in (head, slug(title, 40 - len(head) - 3)) if x)
    base, k = rid, 2
    while taken(root, rid):
        rid, k = f"{base}-{k}", k + 1
    folder = root / "inbox" / rid
    (folder / "inserts").mkdir(parents=True)
    (root / "build" / rid / "logs").mkdir(parents=True, exist_ok=True)
    name = load_json(root / "brands" / b / "brand.json").get("name", b)
    brief = (root / "docs" / "creator" / "brief_template.uk.md").read_text(encoding="utf-8")
    brief = re.sub(r"(?m)^БРЕНД:.*$", f"БРЕНД: {name}", brief, count=1)
    brief = re.sub(r"(?m)^ІДЕЯ:.*$", f"ІДЕЯ: {title.strip()}", brief, count=1) if title.strip() else brief
    (folder / "brief.md").write_text(brief, encoding="utf-8")
    return rid


def creation_time(path):
    """Seconds since the epoch when the clip was shot: the iPhone's capture date, else the container's or a stream's
    creation_time (an edited file may list several: the first), else the file's mtime."""
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags:stream_tags=creation_time", "-of",
                        "json", str(path)], capture_output=True, text=True)
    d = json.loads(r.stdout or "{}")
    fmt = d.get("format", {}).get("tags", {})
    for v in [fmt.get("com.apple.quicktime.creationdate"), fmt.get("creation_time")] + \
             [s.get("tags", {}).get("creation_time") for s in d.get("streams", [])]:
        try:
            return datetime.fromisoformat(v.split(";")[0].strip()).timestamp()
        except (AttributeError, ValueError):
            pass
    return path.stat().st_mtime


def videos(folder):
    """Her talking footage in a reel folder (not inserts/), in shooting order."""
    vs = [p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in VIDEO and not p.name.startswith(".")]
    return sorted(vs, key=lambda p: (creation_time(p), p.stat().st_mtime, p.name))


def pictures(folder):
    d = Path(folder) / "inserts"
    return sorted(p for p in d.iterdir() if p.is_file() and not p.name.startswith(".")) if d.is_dir() else []


def rel(p, root):
    p = Path(p)
    return str(p.relative_to(root)) if p.is_relative_to(root) else str(p)


def py(script, *args):
    return [".venv/bin/python", f"pipeline/{script}", *map(str, args)]


def prep_cmds(rid, clips, speed, root):
    out, k = f"build/{rid}", ["--speed", f"{speed:g}"] if speed != 1.0 else []
    return [py("ingest.py", out, *[rel(c, root) for c in clips], *k), py("prep.py", f"{out}/source.ffconcat", out)]


def run(cmds, root, what):
    for cmd in cmds:
        print("$ " + " ".join(cmd), flush=True)
        if subprocess.run([sys.executable, *cmd[1:]], cwd=root).returncode:
            log = f"build/{what}/logs/prep.log" if cmd[1].endswith("prep.py") else "the output above"
            raise SystemExit(f"stopped: {what} failed at {Path(cmd[1]).name} (see {log})")


def prep(ids, speed=1.0, force=False, dry_run=False, root=ROOT):
    root = Path(root)
    if not SPEED[0] <= speed <= SPEED[1]:
        raise SystemExit(f"--speed {speed:g}: allowed {SPEED[0]}-{SPEED[1]}")
    plan = []
    for rid in ids:
        folder = root / "inbox" / rid
        if not folder.is_dir():
            raise SystemExit(f"no reel {rid} in inbox/")
        clips = videos(folder)
        if not clips:
            raise SystemExit(f"{rid}: no videos in inbox/{rid}/ (pictures and insert clips go in inserts/)")
        b = root / "build" / rid
        if not force and (b / "words.json").exists() and (b / "masks.npy").exists():
            print(f"{rid}: already prepared (--force to redo)")
            continue
        plan.append((rid, clips))
    for rid, clips in plan:
        print(f"{rid}: {count(clips, 'clip')} in shooting order: " + ", ".join(c.name for c in clips))
        cmds = prep_cmds(rid, clips, speed, root)
        if dry_run:
            print("\n".join("  " + " ".join(c) for c in cmds))
            continue
        t = time.time()
        run(cmds, root, rid)
        print(f"{rid}: prepared in {(time.time() - t) / 60:.1f} min", flush=True)


def move_free(src, dst_dir, rid):
    """src -> dst_dir/<rid>, or <rid>-2, -3 ... when taken; returns the new path."""
    dst, k = dst_dir / rid, 2
    while dst.exists():
        dst, k = dst_dir / f"{rid}-{k}", k + 1
    dst_dir.mkdir(exist_ok=True)
    shutil.move(str(src), str(dst))
    return dst


def archive(rid, root=ROOT):
    root = Path(root)
    src = root / "inbox" / rid
    if not src.is_dir():
        raise SystemExit(f"no reel {rid} in inbox/")
    return move_free(src, root / "done", rid)


def npy_frames(path):
    """The first dimension of a .npy array, read from its header (no numpy)."""
    with open(path, "rb") as f:
        major = f.read(8)[6]
        n = struct.unpack("<H" if major == 1 else "<I", f.read(2 if major == 1 else 4))[0]
        return ast.literal_eval(f.read(n).decode("latin1"))["shape"][0]


def reopen_plan(rid, root=ROOT):
    """What reopen does: {"move", "folder", "src", "reingest": [clip paths], "speed", "frames", "prep", "why"}."""
    root = Path(root)
    done, inbox = root / "done" / rid, root / "inbox" / rid
    if done.is_dir() and inbox.exists():
        raise SystemExit(f"inbox/{rid} exists already; nothing moved")
    if not done.is_dir() and not inbox.is_dir():
        raise SystemExit(f"no reel {rid} in done/ or inbox/")
    folder = done if done.is_dir() else inbox
    sp = folder / "script.json"
    source = load_json(sp).get("source") if sp.exists() else None
    src = (root / source).parent if source else root / "build" / rid
    plan = {"move": folder == done, "folder": folder, "src": src, "reingest": [], "speed": 1.0, "frames": None,
            "prep": False, "why": ""}
    cj = src / "clips.json"
    if not cj.exists():
        if not videos(folder):
            raise SystemExit(f"{rid}: {rel(cj, root)} is missing and {rel(folder, root)}/ has no videos to prepare")
        plan.update(prep=True, why=f"{rel(cj, root)} is missing: full prep from the reel's videos")
        return plan
    clips = load_json(cj)["clips"]
    plan["frames"] = sum(c["n_frames"] for c in clips)
    if all((src / c["file"]).is_file() for c in clips):
        if not (src / "masks.npy").exists():
            plan.update(prep=True, why="masks.npy is missing: prep again")
        return plan
    speeds = {c.get("speed", 1.0) for c in clips}
    if len(speeds) > 1:
        raise SystemExit(f"{rid}: clips were ingested at different speeds {sorted(speeds)}; re-ingest by hand")
    for c in clips:
        name = Path(c["orig"]).name
        found = next((p for p in (folder / name, Path(c["orig"])) if p.is_file()), None)
        if found is None:
            raise SystemExit(f"{rid}: clip {name} is gone (not in {rel(folder, root)}/ or at {c['orig']}); "
                             "the media cannot be made again")
        plan["reingest"].append(inbox / name if found.parent == folder else found)
    plan["speed"] = speeds.pop()
    if not (src / "masks.npy").exists():
        plan.update(prep=True, why="masks.npy is missing: prep again")
    return plan


def reopen(rid, dry_run=False, root=ROOT):
    root = Path(root)
    plan = reopen_plan(rid, root)
    src = rel(plan["src"], root)
    lines = [f"move done/{rid} -> inbox/{rid}"] if plan["move"] else [f"inbox/{rid} is open already"]
    if plan["reingest"]:
        lines.append(f"ingest {count(plan['reingest'], 'clip')} again into {src}/ in clips.json order at speed "
                     f"{plan['speed']:g}: " + ", ".join(p.name for p in plan["reingest"]))
        lines.append(f"then check {plan['frames']} frames against the old clips.json and masks.npy")
    elif not plan["prep"]:
        lines.append(f"media in {src}/ is there: nothing to ingest")
    if plan["prep"]:
        lines.append(plan["why"])
    print("\n".join(lines))
    if dry_run:
        return plan
    if plan["move"]:
        shutil.move(str(root / "done" / rid), str(root / "inbox" / rid))
    if plan["reingest"]:
        old = {c["name"]: c["n_frames"] for c in load_json(plan["src"] / "clips.json")["clips"]}
        speed = ["--speed", f"{plan['speed']:g}"] if plan["speed"] != 1.0 else []
        run([py("ingest.py", src, *[rel(p, root) for p in plan["reingest"]], *speed)], root, rid)
        new_ = {c["name"]: c["n_frames"] for c in load_json(plan["src"] / "clips.json")["clips"]}
        masks = plan["src"] / "masks.npy"
        if new_ != old or not masks.exists() or npy_frames(masks) != sum(new_.values()):
            print("frame counts changed: prep again")
            plan["prep"] = True
    if plan["prep"]:
        clips = videos(root / "inbox" / rid) if not (plan["src"] / "clips.json").exists() else []
        cmds = prep_cmds(rid, clips, 1.0, root) if clips else [py("prep.py", f"{src}/source.ffconcat", src)]
        run(cmds, root, rid)
    return plan


def size_gb(p):
    return sum(f.stat().st_size for f in Path(p).rglob("*") if f.is_file()) / 1e9 if Path(p).exists() else 0.0


def listing(root=ROOT):
    root = Path(root)
    rows = []
    for where in ("inbox", "done"):
        for folder in sorted(p for p in (root / where).glob("*") if p.is_dir()):
            rid, b = folder.name, root / "build" / folder.name
            cj = b / "clips.json"
            vs = [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in VIDEO]
            dur = sum(c["duration"] for c in load_json(cj)["clips"]) if cj.exists() else None
            pics = pictures(folder)
            outs = [s for s in ("_draft", "", "_no_music") if (root / "output" / f"{rid}{s}.mp4").exists()]
            rows.append(f"{where}/{rid}: {count(vs, 'video')}" + (f" {dur:.1f} s" if dur else "")
                        + f", {count(pics, 'insert')}" + (" (HEIC)" if any(p.suffix.lower() in (".heic", ".heif")
                                                                          for p in pics) else "")
                        + f", brief {'yes' if (folder / 'brief.md').exists() else 'no'}"
                        + f", script {'yes' if (folder / 'script.json').exists() else 'no'}"
                        + f", prep {'yes' if (b / 'words.json').exists() and (b / 'masks.npy').exists() else 'no'}"
                        + f", media {size_gb(b / 'media'):.1f} GB"
                        + (", out " + " ".join(f"{rid}{s}.mp4" for s in outs) if outs else ""))
    return rows


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("new")
    p.add_argument("brand")
    p.add_argument("title", nargs="*")
    sub.add_parser("list")
    p = sub.add_parser("prep")
    p.add_argument("reels", nargs="+")
    p.add_argument("--speed", type=float, default=1.0, help="uniform speed-up at ingest, 1.0-1.3 (default 1.0)")
    p.add_argument("--force", action="store_true", help="prepare again although words.json and masks.npy exist")
    p.add_argument("--dry-run", action="store_true", help="print the clip order and the commands only")
    p = sub.add_parser("archive")
    p.add_argument("reel")
    p = sub.add_parser("reopen")
    p.add_argument("reel")
    p.add_argument("--dry-run", action="store_true", help="print what would happen only")
    a = ap.parse_args()
    for r in getattr(a, "reels", []) + ([a.reel] if getattr(a, "reel", None) else []):
        if not re.fullmatch(r"[a-z0-9_-]+", r):
            ap.error(f"not a reel id: {r}")
    if a.cmd == "new":
        rid = new(a.brand, " ".join(a.title))
        print(f"{rid}\n{ROOT / 'inbox' / rid}")
        return 0
    if a.cmd == "list":
        print("\n".join(listing()) or "no reels in inbox/ or done/")
        return 0
    if getattr(a, "dry_run", False):
        prep(a.reels, a.speed, a.force, True) if a.cmd == "prep" else reopen(a.reel, True)
        return 0
    label = "prep batch " + " ".join(a.reels) if a.cmd == "prep" else f"{a.cmd} {a.reel}"
    with studio_lock(label):                      # children (ingest, prep) pass: they inherit REEL_STUDIO_LOCK_PID
        keep_awake()
        if a.cmd == "prep":
            prep(a.reels, a.speed, a.force)
        elif a.cmd == "archive":
            print(f"archived: {rel(archive(a.reel), ROOT)}")
        else:
            reopen(a.reel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
