"""Free disk space after a reel is done: delete what can be made again, never the reel itself.

python cleanup.py plan <reel> [<reel> ...] [--all] [--temp]   shows what would go, writes build/cleanup_plan.json
python cleanup.py plan --temp                                 only the temporary render folders
python cleanup.py apply                                       deletes exactly that plan (an ask rule on her Mac)

The plan names files exactly, never by prefix, so <reel> never matches <reel>-2:
  output/<reel>_draft.mp4 and output/<reel>[_draft|_no_music]_project/;
  build/<reel>[_draft|_no_music]_mix[_raw].wav;
  build/<reel>[_draft|_no_music]_music.wav, only together with that render's project (the export reads it);
  build/<reel>/media/, only when every clip in clips.json is still found by name in done/<reel>/ or inbox/<reel>/ or
    at its original path (ingest makes it again; clips that are gone make the media irreplaceable);
  build/<reel>/inserts/, only while done/<reel>/inserts/ or inbox/<reel>/inserts/ holds the originals;
  --all: build/<reel>/masks.npy too (a fix render needs it; reopen runs prep again);
  --temp: build/vp_*, build/overlay, build/preview, build/review and build/look, only while no other job holds the
    lock.
<reel>_draft and <reel>_no_music are also the names of another reel's final (inbox.new can make r and r_draft): when
a reel of that name exists (a folder in inbox/, done/, build/ or projects/, or named in the same plan), those files
are its own and stay out of <reel>'s plan. A reel named twice is planned once; no path is listed twice.
Kept always: final MP4s, <reel>_no_music.mp4, report.json, the prep JSONs, sheet.jpg, logs/, inbox/, done/,
projects/, assets/, learned/. Freed bytes count an inode once, and only when all its hard links are in the plan: the
editable project hard-links the clips, SFX and music, so build/<reel>/media frees space only together with
output/<reel>_project. apply recomputes the plan and deletes nothing if anything differs (a changed or new file, a
symlink, a path outside build/ or output/).
"""
import argparse
import fcntl
import os
import re
import shutil
import sys
import time
from pathlib import Path

from common import ROOT, load_json, save_json, studio_lock

VARIANTS = ("_draft", "_no_music")
TEMP_DIRS = ("overlay", "preview", "review", "look")
REEL_DIRS = ("inbox", "done", "build", "projects")


def lock_holder(root=ROOT):
    """The label of the job holding the studio lock, or None when it is free or held by this process (apply holds
    it while it recomputes the plan)."""
    p = Path(root) / "build" / ".studio.lock"
    if not p.exists():
        return None
    fd = os.open(p, os.O_RDONLY)
    try:
        fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
    except BlockingIOError:
        label = os.read(fd, 400).decode("utf-8", "replace").strip() or "another job"
        return None if label.endswith(f"(pid {os.getpid()})") else label     # common.studio_lock's label
    finally:
        os.close(fd)
    return None


def regenerable(root, reel, sub):
    """Can build/<reel>/<sub> be made again from the originals? (ok, why not)."""
    root = Path(root)
    if sub == "media":
        cj = root / "build" / reel / "clips.json"
        if not cj.exists():
            return False, "no clips.json"
        lost = []
        for c in load_json(cj)["clips"]:
            name = Path(c["orig"]).name
            where = (root / "done" / reel / name, root / "inbox" / reel / name, Path(c["orig"]))
            if not any(p.is_file() for p in where):
                lost.append(name)
        return not lost, f"clips not found: {', '.join(lost)}" if lost else ""
    ok = any((root / d / reel / "inserts").is_dir() for d in ("done", "inbox"))
    return ok, "" if ok else "the originals are not in done/ or inbox/"


def candidates(root, reels, all_=False, temp=False):
    """(paths to delete, notes on what is kept)."""
    root = Path(root)
    build, out = root / "build", root / "output"
    paths, kept = [], []
    for r in reels:
        # <r>_draft named as a reel (a folder, or in this plan) owns <r>_draft.mp4 and the rest: its final, not r's draft
        theirs = [v for v in VARIANTS if r + v in reels or any((root / d / (r + v)).is_dir() for d in REEL_DIRS)]
        kept += [f"output/{r}{v}*, build/{r}{v}_*.wav (they belong to reel {r}{v})" for v in theirs
                 if r + v not in reels]
        rx = re.escape(r) + "(" + "|".join(v for v in VARIANTS if v not in theirs) + ")?"
        projects = {m.group(1) or "": out / m.group(0) for p in sorted(out.glob("*_project"))
                    if (m := re.fullmatch(rx + "_project", p.name)) and p.is_dir()}
        paths += sorted(projects.values())
        draft = out / f"{r}_draft.mp4"
        if draft.is_file() and "_draft" not in theirs:
            paths.append(draft)
        for p in sorted(build.glob("*.wav")):
            if re.fullmatch(rx + r"_mix(_raw)?\.wav", p.name):
                paths.append(p)
            elif m := re.fullmatch(rx + r"_music\.wav", p.name):
                if (m.group(1) or "") in projects:      # the plan takes that project too
                    paths.append(p)
                else:
                    kept.append(f"build/{p.name} (no {r}{m.group(1) or ''}_project: a later export reads it)")
        for sub in ("media", "inserts"):
            d = build / r / sub
            if d.is_dir():
                ok, why = regenerable(root, r, sub)
                (paths.append(d) if ok else kept.append(f"build/{r}/{sub} ({why})"))
        masks = build / r / "masks.npy"
        if masks.is_file():
            (paths.append(masks) if all_ else kept.append(f"build/{r}/masks.npy (--all deletes it)"))
        kept += [f"output/{p.name}" for p in (out / f"{r}.mp4", out / f"{r}_no_music.mp4") if p.is_file()]
    if temp:
        holder = lock_holder(root)
        if holder:
            kept.append(f"temporary render folders (studio busy: {holder})")
        else:
            paths += sorted(p for p in build.glob("vp_*") if p.is_dir())
            paths += [build / d for d in TEMP_DIRS if (build / d).is_dir()]
    paths = list(dict.fromkeys(paths))                  # each path once, and never inside another one of the plan
    return [p for p in paths if not any(q in p.parents for q in paths)], list(dict.fromkeys(kept))


def stat_files(path):
    """[(path, lstat)] of every file under path (the path itself for a file); symlinks are reported, not followed."""
    st = os.lstat(path)
    if not os.path.isdir(path) or os.path.islink(path):
        return [(str(path), st)]
    out = []
    for d, dirs, files in os.walk(path):
        for n in dirs + files:
            p = os.path.join(d, n)
            s = os.lstat(p)
            if n in files or os.path.islink(p):
                out.append((p, s))
    return out


def make_plan(root, reels, all_=False, temp=False):
    root = Path(root)
    reels = list(dict.fromkeys(reels))
    paths, kept = candidates(root, reels, all_, temp)
    items, inodes = [], {}
    for p in paths:
        files = stat_files(p)
        for f, s in files:
            ino = inodes.setdefault((s.st_dev, s.st_ino), {"size": s.st_size, "nlink": s.st_nlink, "paths": []})
            ino["paths"].append(f)
        st = os.lstat(p)
        items.append({"path": str(p.relative_to(root)), "dir": p.is_dir() and not p.is_symlink(),
                      "dev": st.st_dev, "ino": st.st_ino, "nlink": st.st_nlink,
                      "size": sum(s.st_size for _, s in files), "files": len(files),
                      "mtime_ns": max([s.st_mtime_ns for _, s in files] + [st.st_mtime_ns]),
                      "symlinks": sum(os.path.islink(f) for f, _ in files)})
    frees = sum(v["size"] for v in inodes.values() if len(v["paths"]) >= v["nlink"])
    return {"created": time.strftime("%Y-%m-%d %H:%M:%S"), "reels": list(reels), "all": all_, "temp": temp,
            "items": items, "kept": kept, "frees_bytes": frees}, inodes


def notes(root, item, inodes):
    """What a plan line says about hard links: own bytes of a folder, links of a shared file."""
    base = str(Path(root) / item["path"])

    def inside(f):
        return f == base or f.startswith(base + os.sep)
    shared = [(k, v) for k, v in inodes.items() if any(inside(f) for f in v["paths"]) and v["nlink"] > 1]
    out = []
    for _, v in shared:
        name = Path(next(f for f in v["paths"] if inside(f))).name
        rest = v["nlink"] - len(v["paths"])
        out.append(f"{name}: {v['nlink']} links, " + ("all in the plan" if rest <= 0 else
                                                       f"{rest} outside the plan (frees nothing)"))
    if item["dir"] and shared:
        own = sum(v["size"] for v in inodes.values() if all(inside(f) for f in v["paths"]) and v["nlink"] <= 1)
        out.insert(0, f"own {own / 1e6:.1f} MB")
    return "; ".join(out[:3]) + (f"; +{len(out) - 3} more" if len(out) > 3 else "")


def show(root, plan, inodes):
    for it in plan["items"]:
        name = it["path"] + ("/" if it["dir"] else "")
        n = notes(root, it, inodes)
        print(f"  {name:48} {it['size'] / 1e6:9.1f} MB" + (f"  {n}" if n else ""))
    for k in plan["kept"]:
        print(f"  kept: {k}")
    print(f"frees {plan['frees_bytes'] / 1e9:.2f} GB (hard-linked files counted once)")


def outside(root, rel):
    p = (Path(root) / rel).resolve(strict=False)
    return not any(p.is_relative_to((Path(root) / d).resolve()) for d in ("build", "output")) or ".." in Path(rel).parts


def apply_plan(root, plan):
    """Delete the plan's items if a fresh plan for the same reels is identical (else exit 2, nothing deleted).
    Returns the bytes freed."""
    root = Path(root)
    fresh, _ = make_plan(root, plan["reels"], plan.get("all", False), plan.get("temp", False))
    problems = [f"{it['path']}: outside build/ and output/" for it in plan["items"] if outside(root, it["path"])]
    problems += [f"{it['path']}: a symlink" for it in plan["items"] if it.get("symlinks") or
                 (root / it["path"]).is_symlink()]
    if fresh["items"] != plan["items"]:
        old = {i["path"]: i for i in plan["items"]}
        new = {i["path"]: i for i in fresh["items"]}
        problems += [f"{p}: changed since the plan" for p in sorted(set(old) | set(new)) if old.get(p) != new.get(p)]
    if problems:
        print("cleanup refused, nothing deleted:\n" + "\n".join(f"  {p}" for p in problems), file=sys.stderr)
        sys.exit(2)
    for it in plan["items"]:
        p = root / it["path"]
        shutil.rmtree(p) if it["dir"] else p.unlink()
    return plan["frees_bytes"]


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    pl = sub.add_parser("plan")
    pl.add_argument("reels", nargs="*")
    pl.add_argument("--all", action="store_true", help="also masks.npy")
    pl.add_argument("--temp", action="store_true", help="also the temporary render folders")
    sub.add_parser("apply")
    a = ap.parse_args()
    plan_path = ROOT / "build" / "cleanup_plan.json"
    if a.cmd == "plan":
        if not a.reels and not a.temp:
            ap.error("name a reel, or --temp")
        bad = [r for r in a.reels if not re.fullmatch(r"[A-Za-z0-9_.-]+", r) or r in (".", "..")]
        if bad:
            ap.error(f"not a reel id: {', '.join(bad)}")
        plan, inodes = make_plan(ROOT, a.reels, a.all, a.temp)
        save_json(plan, plan_path)
        show(ROOT, plan, inodes)
        print("plan: build/cleanup_plan.json; delete with: .venv/bin/python pipeline/cleanup.py apply")
        return 0
    if not plan_path.exists():
        sys.exit("no plan: run cleanup.py plan <reel> first")
    with studio_lock("cleanup apply"):
        freed = apply_plan(ROOT, load_json(plan_path))
    plan_path.unlink()
    print(f"freed {freed / 1e9:.2f} GB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
