"""Inserts: pictures and clips shown over the picture (a card) or instead of it (full-screen), anchored on what is
heard. This module knows what each file is and when each insert shows; layers.py draws them.

python inserts.py <script>      inventory of the reel's insert files (kind, size, cut-out or not, duration, refused
                                files); writes a viewable JPEG of every file into view/ (videos: 4 frames)

Files: <script dir>/inserts/ (pictures, memes, brand clips; never ingested) and the pictures in <script dir> itself
(videos there are the talking footage). An insert's "file" is a name inside <script dir>/inserts/, a name in
<script dir>, or a repo-relative path. prepare() writes to build/<src>/inserts/ (<src>: the folder of the script's
"source"), names hashed from the inputs:
  inserts.json        the inventory {"v", "dir", "files": {path: entry}}; refused files carry a Ukrainian "refused"
  <stem>_<hash>.png   a picture upright (EXIF orientation), sRGB (ICC converted), RGBA, long side <= 2560
  <stem>_<hash>.mov   the src window of a full-screen video: 1080x1920 30 fps ProRes, no sound (made only for
                      the inserts passed as full_videos)
  view/<stem>.jpg     what Claude looks at (its Read tool cannot open HEIC): long edge <= 1200 px, transparency on a
                      checkerboard; a video's 4 frames with their times
HDR videos are refused (there is no tone-mapping). Nothing here edits the files themselves.

script.json "inserts": [{"file", "at": phrase as heard | output seconds, "occurrence": 1, "offset": 0.0,
  "until": phrase | seconds (auto), "mode": "overlay" | "full", "size": "s" | "m" | "l", "w": px,
  "style": "card" | "cutout" | "plain" (auto), "crop": [x0, y0, x1, y1] (fractions), "focus": [fx, fy],
  "src": [a, b] (full-screen video seconds), "creep": per second, "place": {...}, "sfx": palette event | null,
  "sfx_gain": dB, "why": "..."}]
The look and timing defaults are style.insert (INSERT_STYLE), the size default grammar.insert.size_default, the
sounds the sfx_palette events insert_card / insert_cutout / insert_full.
"""
import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
from difflib import SequenceMatcher
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageCms, ImageOps

import ingest
import resolve
from common import FPS, H, ROOT, SHEET_EDGE, W, load_json, norm, short

STILLS = {".heic", ".heif", ".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEOS = {".mov", ".mp4", ".m4v"}
MAX_SIDE = 2560          # prepared pictures: long side
CUTOUT = 0.02            # a picture with more of its pixels transparent than this is a cut-out
MIN_RATIO = 0.8          # phrase match: SequenceMatcher ratio of the normalised letters
VERSION = 1              # of prepare's outputs: entries of another version are made again
SRGB_ICC = "/System/Library/ColorSync/Profiles/sRGB Profile.icc"
WHOOSH = re.compile(r"whoosh|swish|swoosh")
INSERT_STYLE = {          # style.insert defaults (a script's or brand's style.insert overrides them key by key)
    "widths": {"s": 315, "m": 430, "l": 580}, "max_w": 700, "max_h": 900,
    "min_dur": 1.5, "hold": 0.5, "full_min_dur": 1.0, "full_creep": 0.015,
    "anim": "snap", "exit": 0.13,
    "radius": 12, "border_px": 1, "border": "#111111",
    "shadow": {"dy": 6, "blur": 22, "alpha": 0.30}, "outline": "#111111",
    "margin_text": 20, "min_face_px": 120, "person_cost": 600, "prefer_y": 260}
SFX_EVENTS = {            # the insert events where the resolved sfx_palette has none
    "insert_card": [{"name": "whoosh_quick_03_swish", "gain_db": -14},
                    {"name": "whoosh_soft_02_wind_swoosh", "gain_db": -14}],
    "insert_cutout": [{"name": "pop_04_light", "gain_db": -20}, {"name": "pop_02_bubble_a", "gain_db": -20},
                      {"name": "pop_03_bubble_b", "gain_db": -20}],
    "insert_full": [{"name": "whoosh_soft_01_air_sweep", "gain_db": -12},
                    {"name": "whoosh_quick_03_swish", "gain_db": -12}]}
REFUSED = {   # creator-facing reasons (Ukrainian, gender-neutral) for the report
    "hdr": "відео зняте в HDR, його поки не вдається вставити. Надішли версію без HDR.",
    "unreadable": "файл не відкривається: можливо, він пошкоджений. Надішли його ще раз.",
    "convert": "відео не вдалося перетворити. Надішли його ще раз або в іншому форматі.",
    "format": "такий формат не підтримується; підходять HEIC, JPG, PNG, WebP, MOV, MP4."}


# ----------------------------------------------------------------------------- files

def insert_style(style):
    return {**INSERT_STYLE, **(style.get("insert") or {})}


def script_dir(script):
    """The folder of a resolved script (resolve.load_script records its path)."""
    return Path(script["_resolve"]["script"]).parent


def inserts_dir(script):
    """build/<src>/inserts/: prepared pictures, converted videos, views, inserts.json."""
    return (ROOT / script["source"]).parent / "inserts"


def locate(name, sdir):
    """The file an insert names: inside <sdir>/inserts/, else in <sdir>, else repo-relative (or absolute)."""
    for p in (sdir / "inserts" / name, sdir / name, ROOT / name):
        if p.is_file():
            return p.resolve()
    return None


def files_of(script, sdir):
    """[(path, name)]: every file in <sdir>/inserts/, the pictures in <sdir>, then the other files the inserts name;
    name is what an insert's "file" says to reach it."""
    out, seen = [], set()

    def add(p, name):
        p = p.resolve()
        if p not in seen:
            seen.add(p)
            out.append((p, name))
    box = sdir / "inserts"
    if box.is_dir():
        for p in sorted(box.rglob("*")):
            rel = p.relative_to(box)
            if p.is_file() and not any(part.startswith(".") for part in rel.parts):
                add(p, str(rel))
    for p in sorted(sdir.iterdir()):
        if p.is_file() and p.suffix.lower() in STILLS and not p.name.startswith("."):
            add(p, p.name if locate(p.name, sdir) == p.resolve() else short(p))
    for ins in script.get("inserts", []):
        p = locate(ins.get("file", ""), sdir) if ins.get("file") else None
        if p:
            add(p, short(p))
    return out


def _fresh(entry, st):
    return bool(entry) and entry.get("size") == st.st_size and entry.get("mtime") == st.st_mtime_ns


def _read_inventory(path):
    try:
        inv = load_json(path)
    except (OSError, ValueError):
        return {}
    return inv.get("files", {}) if inv.get("v") == VERSION else {}


# ----------------------------------------------------------------------------- probing (read-only)

def _rotation(sides):
    rot = next((sd["rotation"] for sd in sides or [] if "rotation" in sd), 0)
    return abs(int(round(float(rot)))) % 180 == 90


def _rate(r):
    a, _, b = str(r or "0/1").partition("/")
    return round(float(a) / float(b or 1), 3) if float(b or 1) else 0.0      # "0/0": unknown


def probe_video(path):
    """{kind, w, h (upright), duration, fps, hdr} by ffprobe."""
    v, a, fmt_dur = ingest.probe(path)
    w, h = int(v["width"]), int(v["height"])
    if _rotation(v.get("side_data_list")) or str(v.get("tags", {}).get("rotate", "0")) in ("90", "270", "-90"):
        w, h = h, w
    return {"kind": "video", "w": w, "h": h, "duration": round(ingest.video_duration(v, fmt_dur), 4),
            "fps": _rate(v.get("avg_frame_rate") or v.get("r_frame_rate")),
            "hdr": v.get("color_transfer") in ingest.HDR_TRC}


def probe_heic(path):
    """{kind, w, h (upright)} of a HEIC/HEIF by ffprobe (Pillow cannot open them): an iPhone photo is a grid of
    tiles, whose size and rotation are on the tile-grid group."""
    d = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_stream_groups", "-of", "json",
                                   str(path)], capture_output=True, text=True, check=True).stdout)
    grid = next((g["components"][0] for g in d.get("stream_groups", []) if g.get("type") == "Tile Grid"
                 and g.get("components")), None)
    src = grid or next(s for s in d["streams"] if s.get("codec_type") == "video")
    w, h = int(src["width"]), int(src["height"])
    if _rotation(src.get("side_data_list")):
        w, h = h, w
    return {"kind": "still", "w": w, "h": h, "transparent": 0.0, "cutout": False, "animated": False}


def _alpha_share(im):
    """The share of pixels under half opacity (0 for pictures without alpha)."""
    if im.mode not in ("RGBA", "LA", "PA") and "transparency" not in im.info:
        return 0.0
    return float((np.asarray(im.convert("RGBA").getchannel("A")) < 128).mean())


def probe_still(path):
    """{kind, w, h (upright), transparent, cutout, animated} by Pillow (HEIC: probe_heic)."""
    if path.suffix.lower() in (".heic", ".heif"):
        return probe_heic(path)
    with Image.open(path) as im:
        w, h = im.size
        if im.getexif().get(0x0112) in (5, 6, 7, 8):
            w, h = h, w
        share = _alpha_share(im)
        return {"kind": "still", "w": w, "h": h, "transparent": round(share, 4), "cutout": share > CUTOUT,
                "animated": getattr(im, "n_frames", 1) > 1}


def probe(path):
    """What a file is, without writing anything (lint and times.py read this when inserts.json is missing)."""
    ext = path.suffix.lower()
    if ext not in STILLS | VIDEOS:
        return {"kind": "other", "refused": REFUSED["format"]}
    try:
        e = probe_video(path) if ext in VIDEOS else probe_still(path)
    except Exception:            # ffprobe/Pillow failures of every kind: the file is unusable either way
        return {"kind": "video" if ext in VIDEOS else "still", "refused": REFUSED["unreadable"]}
    if e.get("hdr"):
        e["refused"] = REFUSED["hdr"]
    return e


def load_inventory(script):
    """The inventory without writing anything: inserts.json's entries where the file is unchanged, else a probe."""
    sdir = script_dir(script)
    old = _read_inventory(inserts_dir(script) / "inserts.json")
    files = {}
    for p, name in files_of(script, sdir):
        st, key = p.stat(), short(p)
        e = old[key] if _fresh(old.get(key), st) else probe(p)
        files[key] = {**e, "name": name, "path": key, "size": st.st_size, "mtime": st.st_mtime_ns}
    return {"v": VERSION, "dir": short(sdir), "files": files}


# ----------------------------------------------------------------------------- prepare (writes build/<src>/inserts)

def _digest(*parts):
    return hashlib.sha1(json.dumps(parts, sort_keys=True).encode()).hexdigest()[:10]


def _stem(p):
    """A file name stem safe in paths and URLs (Ukrainian letters stay)."""
    return re.sub(r"[^\w\-]", "_", p.stem).strip("_") or "file"


def _view_name(p, taken):
    name, k = f"{_stem(p)}.jpg", 2
    while name in taken:
        name, k = f"{_stem(p)}_{k}.jpg", k + 1
    taken.add(name)
    return name


def _upright_srgb(im):
    """RGBA, upright (EXIF orientation), in sRGB: an embedded non-sRGB ICC profile (Display P3, Adobe RGB, CMYK)
    is converted. Animated pictures give their first frame."""
    im = ImageOps.exif_transpose(im)
    icc = im.info.get("icc_profile")
    alpha = im.convert("RGBA").getchannel("A") if im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info \
        else None
    rgb = im if im.mode == "CMYK" else im.convert("RGB")
    if icc:
        try:
            prof = ImageCms.ImageCmsProfile(io.BytesIO(icc))
            if "srgb" not in ImageCms.getProfileDescription(prof).lower():
                rgb = ImageCms.profileToProfile(rgb, prof, ImageCms.createProfile("sRGB"), outputMode="RGB")
        except (ImageCms.PyCMSError, OSError, ValueError):
            pass                 # an unusable profile: the pixels as they are
    out = rgb.convert("RGB").convert("RGBA")
    if alpha is not None:
        out.putalpha(alpha)
    return out


def _checker(size, cell=16):
    w, h = size
    yy, xx = np.mgrid[0:h, 0:w]
    g = np.where((yy // cell + xx // cell) % 2, 200, 154).astype(np.uint8)
    return Image.fromarray(np.dstack([g, g, g, np.full_like(g, 255)]), "RGBA")


def _view_still(im, path):
    v = im.copy()
    v.thumbnail((SHEET_EDGE, SHEET_EDGE), Image.Resampling.LANCZOS)
    bg = _checker(v.size)
    bg.alpha_composite(v)
    bg.convert("RGB").save(path, quality=85)


def _grab(path, t, tw, th):
    """One frame of a video at t seconds, upright, scaled to tw x th, as BGR."""
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.3f}", "-i", str(path), "-frames:v", "1",
                          "-vf", f"scale={tw}:{th}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         capture_output=True, check=True).stdout
    if len(raw) < tw * th * 3:
        return np.zeros((th, tw, 3), np.uint8)
    return np.frombuffer(raw[:tw * th * 3], np.uint8).reshape(th, tw, 3).copy()


def _view_video(path, e, out):
    """4 frames at 1/8, 3/8, 5/8, 7/8 of the clip, labelled with their times: side by side for a vertical video,
    stacked for a horizontal one, long edge <= 1200 px."""
    vertical = e["h"] >= e["w"]
    if vertical:
        tw = SHEET_EDGE // 4
        th = int(round(tw * e["h"] / e["w"] / 2)) * 2
    else:
        th = SHEET_EDGE // 4
        tw = int(round(th * e["w"] / e["h"] / 2)) * 2
    tiles = []
    for k in range(4):
        t = e["duration"] * (2 * k + 1) / 8
        img = _grab(path, t, tw, th)
        for col, thick in (((0, 0, 0), 4), ((255, 255, 255), 1)):
            cv2.putText(img, f"{t:.1f}s", (8, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, col, thick, cv2.LINE_AA)
        tiles.append(img)
    cv2.imwrite(str(out), np.hstack(tiles) if vertical else np.vstack(tiles), [cv2.IMWRITE_JPEG_QUALITY, 85])


def _prepare_file(p, key, st, out, view):
    """The entry of one file, writing its upright sRGB PNG (pictures) and its view."""
    e = probe(p)
    if e["kind"] == "other" or (e.get("refused") == REFUSED["unreadable"]):
        return e
    try:
        if e["kind"] == "video":
            _view_video(p, e, out / view)
        else:
            png = out / f"{_stem(p)}_{_digest(key, st.st_size, st.st_mtime_ns, VERSION)}.png"
            src = p
            if p.suffix.lower() in (".heic", ".heif"):         # sips keeps the EXIF orientation tag
                src = out / f"tmp_{png.name}"
                subprocess.run(["sips", "-s", "format", "png", "--matchTo", SRGB_ICC, str(p), "--out", str(src)],
                               capture_output=True, check=True)
            try:
                with Image.open(src) as im:
                    animated = getattr(im, "n_frames", 1) > 1
                    img = _upright_srgb(im)
            finally:
                if src != p:
                    src.unlink(missing_ok=True)
            e.update(w=img.width, h=img.height, animated=animated)
            share = _alpha_share(img)
            e.update(transparent=round(share, 4), cutout=share > CUTOUT)
            if max(img.size) > MAX_SIDE:
                img.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
            img.save(png, compress_level=3)
            _view_still(img, out / view)
            e["png"] = short(png)
    except Exception:            # sips, Pillow or ffmpeg could not read it
        return {"kind": e["kind"], "refused": REFUSED["unreadable"]}
    e["view"] = short(out / view)
    return e


def _outputs(e):
    return [e[k] for k in ("png", "view") if e.get(k)] + [c["file"] for c in e.get("converted", [])]


def _remove(e):
    for f in _outputs(e):
        (ROOT / f).unlink(missing_ok=True)


def video_window(ins, e):
    """[a, b]: the seconds of a full-screen video an insert plays (its src, inside the clip)."""
    a, b = ins.get("src") or [0.0, e["duration"]]
    return [round(max(0.0, float(a)), 4), round(min(float(b), e["duration"]), 4)]


def _convert(p, e, ins, out):
    """The converted src window of a full-screen video (made once, then reused); None for an empty window (which
    resolve_times reports)."""
    src, focus = video_window(ins, e), [float(v) for v in ins.get("focus", [0.5, 0.5])]
    if src[1] - src[0] < 1 / FPS:
        return None
    for c in e.setdefault("converted", []):
        if c["src"] == src and c["focus"] == focus:
            return c
    name = f"{_stem(p)}_{_digest(e['path'], e['size'], e['mtime'], src, focus, VERSION)}"
    info = ingest.ingest(p, out, name, audio=False, focus=focus, trim=src)
    c = {"src": src, "focus": focus, "file": short(out / f"{name}.mov"), "n_frames": info["n_frames"]}
    e["converted"] = [x for x in e["converted"] if x["file"] != c["file"]] + [c]
    return c


def prepare(script, script_path, full_videos=()):
    """Inventory the reel's insert files into build/<src>/inserts/inserts.json, making the upright sRGB PNG and the
    view of each new or changed file; full_videos (insert dicts with mode "full") get their video's src window
    converted. Unchanged files are reused; the outputs of changed or deleted files are removed. A file that cannot
    be used is listed with a Ukrainian "refused" reason, never raised. Returns the inventory."""
    sdir = Path(script_path).resolve().parent
    out = inserts_dir(script)
    (out / "view").mkdir(parents=True, exist_ok=True)
    old = _read_inventory(out / "inserts.json")
    found = [(p, name, p.stat(), short(p)) for p, name in files_of(script, sdir)]
    kept, views = {}, set()
    for p, _, st, key in found:      # an unchanged file keeps its outputs and its view's name across runs
        e = old.get(key)
        if _fresh(e, st):
            if e.get("view"):
                views.add(Path(e["view"]).name)
            if all((ROOT / e[k]).is_file() for k in ("png", "view") if e.get(k)):
                kept[key] = e
    listed = {key for *_, key in found}
    for key, e in old.items():       # stale outputs go before any new one is written: their view names are free
        if key not in kept and (key in listed or not (ROOT / key).exists()):
            _remove(e)
    files = {}
    for p, name, st, key in found:
        e = kept.get(key)
        if e:
            if "converted" in e:         # a deleted window is made again when it is asked for
                e = {**e, "converted": [c for c in e["converted"] if (ROOT / c["file"]).is_file()]}
        else:
            e = old.get(key)
            view = Path(e["view"]).name if _fresh(e, st) and e.get("view") else _view_name(p, views)
            e = _prepare_file(p, key, st, out, f"view/{view}")
        files[key] = {**e, "name": name, "path": key, "size": st.st_size, "mtime": st.st_mtime_ns}
    for ins in full_videos:
        p = locate(ins["file"], sdir)
        e = files.get(short(p)) if p else None
        if e and e["kind"] == "video" and not e.get("refused"):
            try:
                _convert(p, e, ins, out)
            except (SystemExit, subprocess.CalledProcessError):
                e["refused"] = REFUSED["hdr"] if e.get("hdr") else REFUSED["convert"]
    inv = {"v": VERSION, "dir": short(sdir), "files": files}
    tmp = out / "inserts.json.tmp"
    tmp.write_text(json.dumps(inv, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, out / "inserts.json")
    return inv


# ----------------------------------------------------------------------------- when

def find_phrase(words, phrase, occurrence=1, after=0.0):
    """The occurrence-th place the phrase is heard at or after `after` (output seconds): {t0, t1, ratio, heard}, or
    None. words: VoiceMap.heard_words (output start/end o, oe). Windows of n-1..n+1 heard words are compared with
    the phrase's n words as normalised letters (SequenceMatcher ratio >= 0.8); matches do not overlap, and of two
    overlapping windows the better one counts."""
    target = "".join(norm(x) for x in phrase.split())
    n = sum(1 for x in phrase.split() if norm(x))
    if not target:
        return None
    keys = [norm(w["w"]) for w in words]
    best = []                      # (start, length, ratio): the best window starting at each word
    for i, w in enumerate(words):
        if w["o"] < after - 1e-6:
            continue
        cand = None
        for ln in (n - 1, n, n + 1):
            if ln < 1 or i + ln > len(words):
                continue
            r = SequenceMatcher(None, target, "".join(keys[i:i + ln]), autojunk=False).ratio()
            if r >= MIN_RATIO and (cand is None or r > cand[2]):
                cand = (i, ln, r)
        if cand:
            best.append(cand)
    hits = []
    for c in best:
        if hits and c[0] < hits[-1][0] + hits[-1][1]:
            if c[2] > hits[-1][2]:
                hits[-1] = c
            continue
        hits.append(c)
    if not 1 <= occurrence <= len(hits):
        return None
    i, ln, r = hits[occurrence - 1]
    return {"t0": words[i]["o"], "t1": words[i + ln - 1]["oe"], "ratio": round(r, 3),
            "heard": " ".join(w["w"].strip() for w in words[i:i + ln])}


def fit(aspect, width, ist):
    """(w, h) on screen of a picture with h/w = aspect, `width` px wide, shrunk to max_w and max_h."""
    w = min(float(width), ist["max_w"])
    if w * aspect > ist["max_h"]:
        w = ist["max_h"] / aspect
    return int(round(w)), int(round(w * aspect))


def _pick_sfx(ev, variants, peak, cues, ptr):
    """The variant of an insert event at `peak`: rotated by occurrence, and not the same whoosh as the whooshes
    before and after it on the cue list."""
    def near(side):
        ws = [c for c in cues if WHOOSH.search(c["name"]) and (c["peak_at"] < peak if side < 0 else
                                                                 c["peak_at"] > peak)]
        return (max(ws, key=lambda c: c["peak_at"]) if side < 0 else min(ws, key=lambda c: c["peak_at"]))["name"] \
            if ws else None
    prev, nxt = near(-1), near(1)
    p = ptr.get(ev, 0)
    order = [variants[(p + k) % len(variants)] for k in range(len(variants))]
    order = [v[0] if isinstance(v, list) else v for v in order]           # a stack plays its first sound
    clash = lambda v, others: WHOOSH.search(v["name"]) and v["name"] in others
    pick = next((k for k, v in enumerate(order) if not clash(v, (prev, nxt))), None)
    if pick is None:
        pick = next((k for k, v in enumerate(order) if not clash(v, (prev,))), 0)
    ptr[ev] = p + pick + 1
    return order[pick]


def resolve_times(script, words, duration, style, inventory=None):
    """When and how each of script["inserts"] shows, without image work: (items, fails, warns), the problems as
    (t, msg) lists like lint's. words: VoiceMap.heard_words; duration: the output length; inventory: prepare()'s or
    load_inventory()'s (default: load_inventory, which never writes).
    items, in time order: {id, cat "insert", file, path, name, label, mode, kind, style, z, rides, t0, t1, f0,
    f1 (exclusive; the exit fade is inside it), phrase, size, w, h, aspect, crop, place, anim, exit, focus, creep,
    src, n_media, media, event, sfx, sfx_gain, why}.
    Only one insert shows at a time: a later one ends the previous one 1 f before it starts. Fails: a missing,
    refused or unusable file or key. Warns: a phrase not heard (the insert is left out) or heard only roughly,
    an insert shorter than its minimum, a cut-short video, an animated picture, a silent insert (sfx null)."""
    ist = insert_style(style)
    size_default = ((script.get("grammar") or {}).get("insert") or {}).get("size_default", "m")
    palette = {**SFX_EVENTS, **(script.get("sfx_palette") or {})}
    sdir = script_dir(script)
    inv = inventory if inventory is not None else load_inventory(script)
    n_frames = int(round(duration * FPS))
    fails, warns, items = [], [], []
    for k, ins in enumerate(script.get("inserts", [])):
        iid = f"i{k}"
        fname = ins.get("file", "")
        at, offset = ins.get("at"), float(ins.get("offset", 0.0))
        phrase = None
        if isinstance(at, str):
            occ = int(ins.get("occurrence", 1))
            phrase = find_phrase(words, at, occ)
            if phrase is None:
                warns.append((0.0, f"{iid} {fname}: «{at}» (occurrence {occ}) is not heard; copy the words from "
                                   f"times.py. Left out"))
                continue
            if phrase["ratio"] < 1:
                warns.append((phrase["t0"], f"{iid} {fname}: «{at}» heard as «{phrase['heard']}» "
                                            f"(ratio {phrase['ratio']:.2f})"))
            t0 = phrase["t0"] + offset
        elif isinstance(at, (int, float)) and not isinstance(at, bool):
            t0 = float(at) + offset
        else:
            fails.append((0.0, f"{iid} {fname}: \"at\" must be a phrase as heard or output seconds"))
            continue
        t0 = max(0.0, t0)
        path = locate(fname, sdir) if fname else None
        if path is None:
            fails.append((t0, f"{iid}: file {fname!r} not found in {short(sdir / 'inserts')}/, "
                              f"{short(sdir)}/ or the repo"))
            continue
        e = inv["files"].get(short(path)) or probe(path)
        if e.get("refused"):
            fails.append((t0, f"{iid} {fname}: refused: {e['refused']}"))
            continue
        mode = ins.get("mode", "overlay")
        if mode not in ("overlay", "full"):
            fails.append((t0, f"{iid} {fname}: mode {mode!r}; use \"overlay\" or \"full\""))
            continue
        if e["kind"] == "video" and mode != "full":
            fails.append((t0, f"{iid} {fname}: a video shows full-screen only (\"mode\": \"full\")"))
            continue
        if e.get("animated"):
            warns.append((t0, f"{iid} {fname}: animated picture; only its first frame shows"))
        src = video_window(ins, e) if e["kind"] == "video" else None
        if src and src[1] - src[0] < 1 / FPS:
            fails.append((t0, f"{iid} {fname}: src {ins.get('src')} is outside the {e['duration']:.2f} s clip"))
            continue
        # until: auto, a phrase (its last word's end) or seconds
        u = ins.get("until")
        p_end = phrase["t1"] if phrase else t0
        auto = max(t0 + ist["min_dur"], p_end + ist["hold"]) if mode == "overlay" else \
            max(t0 + ist["full_min_dur"], p_end + 0.2)
        t1 = auto
        if isinstance(u, str):
            pu = find_phrase(words, u, 1, after=t0)
            if pu is None:
                warns.append((t0, f"{iid} {fname}: until «{u}» is not heard after {t0:.2f} s; auto until"))
            else:
                t1 = pu["t1"]
                if pu["ratio"] < 1:
                    warns.append((pu["t0"], f"{iid} {fname}: until «{u}» heard as «{pu['heard']}» "
                                            f"(ratio {pu['ratio']:.2f})"))
        elif isinstance(u, (int, float)) and not isinstance(u, bool):
            t1 = float(u)
        if src and t1 - t0 > src[1] - src[0] + 1e-6:
            if u is not None:
                warns.append((t0, f"{iid} {fname}: the video window is {src[1] - src[0]:.2f} s; ends at "
                                  f"{t0 + src[1] - src[0]:.2f} s, not {t1:.2f} s"))
            t1 = t0 + src[1] - src[0]
        t1 = min(t1, duration)
        f0, f1 = int(round(t0 * FPS)), int(round(t1 * FPS))
        if f0 >= n_frames or f1 <= f0:
            warns.append((t0, f"{iid} {fname}: {t0:.2f}-{t1:.2f} s shows nothing (after the end, or until before "
                              f"at). Left out"))
            continue
        # look
        st = ins.get("style") or ("cutout" if e.get("cutout") else "card")
        if mode == "overlay" and st not in ("card", "cutout", "plain"):
            fails.append((t0, f"{iid} {fname}: style {st!r}; use card, cutout or plain"))
            continue
        crop = ins.get("crop")
        if crop is not None and not (len(crop) == 4 and 0 <= crop[0] < crop[2] <= 1 and 0 <= crop[1] < crop[3] <= 1):
            fails.append((t0, f"{iid} {fname}: crop {crop} must be [x0, y0, x1, y1] fractions, x0 < x1, y0 < y1"))
            continue
        size = ins.get("size", size_default)
        if mode == "overlay" and "w" not in ins and size not in ist["widths"]:
            fails.append((t0, f"{iid} {fname}: size {size!r}; use {', '.join(ist['widths'])} or \"w\""))
            continue
        cx = (crop[2] - crop[0], crop[3] - crop[1]) if crop else (1.0, 1.0)
        aspect = e["h"] * cx[1] / (e["w"] * cx[0])
        if mode == "overlay":
            w, h = fit(aspect, ins.get("w", ist["widths"].get(size, 0)), ist)
        else:
            w, h = W, H
        conv = next((c for c in e.get("converted", []) if src and c["src"] == src
                     and c["focus"] == [float(v) for v in ins.get("focus", [0.5, 0.5])]), None)
        items.append({
            "id": iid, "cat": "insert", "file": fname, "path": short(path), "name": e.get("name", fname),
            "label": f"{iid} {Path(fname).stem}", "mode": mode, "kind": e["kind"],
            "style": st if mode == "overlay" else None, "z": "under", "rides": mode == "overlay",
            "t0": round(t0, 4), "t1": round(t1, 4), "f0": f0, "f1": f1,
            "phrase": {"text": at, "heard": phrase["heard"], "ratio": phrase["ratio"]} if phrase else None,
            "size": size if mode == "overlay" and "w" not in ins else None, "w": w, "h": h,
            "aspect": round(aspect, 5), "crop": crop, "place": ins.get("place", {}),
            "anim": ist["anim"] if mode == "overlay" else None, "exit": ist["exit"] if mode == "overlay" else 0,
            "focus": ins.get("focus", [0.5, 0.5]), "creep": ins.get("creep", ist["full_creep"])
            if mode == "full" and e["kind"] == "still" else 0, "src": src,
            "n_media": int(round((src[1] - src[0]) * FPS)) if src else None,
            "media": (conv["file"] if conv else None) if src else e.get("png") if mode == "full" else None,
            "why": ins.get("why"), "_ins": ins})
    # one at a time: a later insert ends the previous one 1 f before its start
    items.sort(key=lambda it: it["f0"])
    kept = []
    for it in items:
        if kept and kept[-1]["f1"] > it["f0"] - 1:
            prev = kept[-1]
            prev["f1"] = it["f0"] - 1
            prev["t1"] = round(prev["f1"] / FPS, 4)
            if prev["f1"] <= prev["f0"]:
                warns.append((prev["t0"], f"{prev['id']} {prev['file']}: starts with {it['id']} or later; "
                                          f"left out"))
                kept.pop()
        kept.append(it)
    for it in kept:
        least = ist["min_dur"] if it["mode"] == "overlay" else ist["full_min_dur"]
        if it["t1"] - it["t0"] < least - 1e-6:
            warns.append((it["t0"], f"{it['id']} {it['file']}: {it['t1'] - it['t0']:.2f} s < {least} s on screen"))
    # sound: palette events, one sample after another, never the same whoosh twice in a row
    cues = [c for c in (script.get("audio") or {}).get("sfx", []) if "name" in c and "peak_at" in c]
    ptr = {}
    for it in kept:
        ins = it.pop("_ins")
        ev = ins["sfx"] if "sfx" in ins else "insert_full" if it["mode"] == "full" else \
            "insert_cutout" if it["style"] == "cutout" else "insert_card"
        it.update(event=ev, sfx=None, sfx_gain=None)
        if ev is None:
            warns.append((it["t0"], f"{it['id']} {it['file']}: silent (\"sfx\": null)"))
            continue
        if not palette.get(ev):
            fails.append((it["t0"], f"{it['id']} {it['file']}: sfx {ev!r} is not an sfx_palette event "
                                    f"({', '.join(sorted(palette))})"))
            continue
        peak = round(it["f0"] / FPS, 4)
        v = _pick_sfx(ev, palette[ev], peak, cues, ptr)
        it.update(sfx=v["name"], sfx_gain=ins.get("sfx_gain", v.get("gain_db", 0)))
        cues.append({"name": v["name"], "peak_at": peak})
    return kept, fails, warns


# ----------------------------------------------------------------------------- CLI

def summary(inv, out):
    """The inventory as printed: refused files first, then one line per file."""
    files = sorted(inv["files"].values(), key=lambda e: e["name"].lower())
    lines = [f"refused: {e['name']} — {e['refused']}" for e in files if e.get("refused")]
    lines.append(f"{len(files)} files ({inv['dir']}) -> {short(out / 'inserts.json')}; views in {short(out / 'view')}/")
    width = max([len(e["name"]) for e in files] + [4])
    for e in files:
        if e.get("refused"):
            what = f"{e['kind']} REFUSED"
        elif e["kind"] == "video":
            what = f"video {e['w']}x{e['h']} {e['duration']:.2f} s {e['fps']:g} fps"
        else:
            what = f"still {e['w']}x{e['h']} " + (f"cutout ({e['transparent']:.0%} transparent)" if e["cutout"]
                                                  else "card")
            what += " animated: first frame only" if e["animated"] else ""
        lines.append(f"  {e['name']:{width}}  {what}" + (f"  {Path(e['view']).name}" if e.get("view") else ""))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    a = ap.parse_args()
    script = resolve.load_script(a.script)
    inv = prepare(script, a.script)
    print(summary(inv, inserts_dir(script)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
