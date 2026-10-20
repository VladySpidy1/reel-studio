"""Editable project: FCPXML timeline + per-element media for finishing in DaVinci Resolve / Final Cut Pro.

python export_fcpxml.py ../projects/<name>/script.json [--name out] [--freeze baked|png|timemap] [--procs N]
                         [--verbose] [--force]

Run after build.py (it reads build/meta.json, camera.json, timeline.json and the audio mix); it refuses (exit 2)
while the build slot holds another reel (--force: developer only). The terminal gets a short summary; the full output
is in build/<reel>/logs/export_<name>.log. Writes
output/<name>_project/<name>.fcpxml plus media/ (self-contained: source clips, SFX and music are hard-linked in):
  - the picture: the source clips cut like the reel (spine), product holds as freeze clips;
    camera zooms / punch-ins / shakes as transform keyframes on every clip
  - camera freezes (picture stops, voice runs on): a still clip on the lane above the take
  - camera flashes: white ProRes 4444 clips with alpha
  - every subtitle block and doodle: its own ProRes 4444 clip with alpha, text-behind-subject baked in
  - SFX and music: separate audio clips with their levels; one shared gain brings the mix to the
    same loudness as the draft MP4 (no limiter)
Transitions (swipe, spin, zoom-through) are baked clips with their motion blur above the takes; the text moves
with keyframes. Not carried over (yet): zoom blur on cut-ins, motion blur on punch-ins, per-take white balance and the grade, music dropouts and fades
(DaVinci drops FCPXML audio fades), the MP4's limiter.

--freeze picks how holds are written, to test what an editor imports: baked (a ProRes clip of the held
frame, default), png (a still image), timemap (a retimed source clip).
"""
import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
from fractions import Fraction
from multiprocessing import Pool
from pathlib import Path
from xml.sax.saxutils import quoteattr

import cv2
import numpy as np

import build
import camera as cam_mod
import resolve
import video_pass
from common import (BUILD, FPS, H, OUT, PIPE, ROOT, W, default_procs, keep_awake, load_json, reel_id, require_slot,
                    run_log, short, source_path, studio_lock)
from edl import EDL

POS_UNIT = H / 100.0       # FCPXML transform position: percent of the frame height, y up
TAGS = "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv"
ALPHA = "straight"         # Chrome screenshots are straight (unpremultiplied) alpha


# ----------------------------------------------------------------------------- time helpers

def ft(frames):
    """Frame count -> FCPXML rational time string at the sequence rate."""
    f = Fraction(int(frames), FPS)
    return f"{f.numerator}s" if f.denominator == 1 else f"{f.numerator}/{f.denominator}s"


def st(seconds, rate=48000):
    f = Fraction(int(round(seconds * rate)), rate)
    return f"{f.numerator}s" if f.denominator == 1 else f"{f.numerator}/{f.denominator}s"


def fr(t):
    return int(round(t * FPS))


def file_url(p):
    return "file://" + urllib.parse.quote(str(Path(p).resolve()))


# ----------------------------------------------------------------------------- media writers

def encode(frames_iter, out, n, alpha):
    """Write BGR(A) uint8 frames to ProRes (4444 with alpha, else 422 HQ)."""
    pix_in = "bgra" if alpha else "bgr24"
    vf = ("scale=out_color_matrix=bt709:out_range=tv," + ("format=yuva444p10le" if alpha else "format=yuv422p10le")
          + "," + TAGS)
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", pix_in, "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-", "-vf", vf, "-frames:v", str(n), "-c:v", "prores_ks",
           "-profile:v", "4" if alpha else "3", "-vendor", "apl0",
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709"]
    if alpha:
        cmd += ["-alpha_bits", "16"]
    p = subprocess.Popen(cmd + ["-movflags", "+write_colr", str(out)], stdin=subprocess.PIPE)
    for img in frames_iter:
        p.stdin.write(np.ascontiguousarray(img).tobytes())
    p.stdin.close()
    if p.wait():
        raise SystemExit(f"encoding {out} failed")


def bake_hold(clip, f, n, out):
    """ProRes clip of frame f of a source clip held for n frames, straight from the 10-bit intermediate (no 8-bit RGB
    round trip, so it matches the neighbouring clips exactly)."""
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{max(0, (f - 0.5) / FPS):.4f}", "-i", str(clip),
                    "-an", "-vf", f"trim=end_frame=1,loop=loop={n - 1}:size=1:start=0,setpts=N/({FPS}*TB),"
                                  f"format=yuv422p10le,{TAGS}",
                    "-r", str(FPS), "-frames:v", str(n), "-c:v", "prores_ks", "-profile:v", "3", "-vendor", "apl0",
                    "-movflags", "+write_colr", str(out)], check=True)


def source_frame(src, f):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{max(0, (f - 0.5) / FPS):.4f}", "-i", str(src),
                          "-frames:v", "1", "-vf", "scale=in_color_matrix=bt709:in_range=tv",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W, 3)


def render_layer(job):
    """Render one overlay element (block or doodle) alone in headless Chrome, bake text-behind-subject,
    trim to its visible frames and encode. Returns (first_frame, n_frames) or None if never visible."""
    from playwright.sync_api import sync_playwright
    name, tl, frames, out, occl, masks_path, cam_path = job
    cam = load_json(cam_path)["frames"]
    masks = np.load(masks_path, mmap_mode="r") if masks_path else None
    imgs = {}
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", args=["--font-render-hinting=none", "--disable-lcd-text"])
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        pg.goto((PIPE / "overlay.html").as_uri())
        pg.evaluate("tl => init(tl)", tl)
        pg.evaluate("window.ready")
        for i in frames:
            pg.evaluate(f"seek({i / FPS:.6f})")
            png = pg.screenshot(omit_background=True, type="png")
            bgra = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED)
            if bgra[:, :, 3].max() == 0:
                continue
            if i in occl and masks is not None:
                fr_ = cam[i]
                a = bgra[:, :, 3].astype(np.float32) / 255
                a *= 1 - video_pass.person_alpha(masks, fr_.get("src_f", i), cam_mod.matrix(fr_))
                bgra[:, :, 3] = np.round(a * 255).astype(np.uint8)
            imgs[i] = bgra
        b.close()
    if not imgs:
        return name, None
    f0, f1 = min(imgs), max(imgs)
    empty = np.zeros((H, W, 4), np.uint8)

    def gen():
        for i in range(f0, f1 + 1):
            im = imgs.get(i, empty)
            if ALPHA == "premultiplied":
                im = im.copy()
                im[:, :, :3] = (im[:, :, :3].astype(np.float32) * (im[:, :, 3:4] / 255.0)).round().astype(np.uint8)
            yield im
    encode(gen(), out, f1 - f0 + 1, alpha=True)
    return name, (f0, f1 - f0 + 1)


# ----------------------------------------------------------------------------- camera -> transform keyframes

def matrix_vals(m):
    """2x3 screen affine (uniform scale + rotation + shift) -> FCPXML [scale, pos x, pos y, rotation]: the clip is
    scaled/rotated about the frame centre, then moved; position in percent of frame height, y up."""
    m = np.asarray(m, np.float64)       # rotation sign matches Resolve 21 (checked with resolve_check.py)
    cx, cy = m @ np.array([W / 2, H / 2, 1.0])
    return np.array([np.hypot(m[0, 0], m[0, 1]), (cx - W / 2) / POS_UNIT, -(cy - H / 2) / POS_UNIT,
                     np.degrees(np.arctan2(m[0, 1], m[0, 0]))])


def transform_at(fr_):
    return matrix_vals(cam_mod.matrix(fr_))


def overlay_at(fr_):
    """Text/graphics move only inside transitions (camera "ovm"), otherwise they stay put."""
    return matrix_vals(fr_.get("ovm", [[1, 0, 0], [0, 1, 0]]))


TOL = np.array([0.0005, 0.02, 0.02, 0.02])     # scale, position (% of height ~ 0.4 px), rotation (deg)


def simplify(vals):
    """Indices of the keyframes needed to reproduce vals (n, 4) with linear interpolation within TOL."""
    keep = {0, len(vals) - 1}
    stack = [(0, len(vals) - 1)]
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        t = (np.arange(a + 1, b) - a) / (b - a)
        interp = vals[a] + (vals[b] - vals[a]) * t[:, None]
        err = (np.abs(vals[a + 1:b] - interp) / TOL).max(axis=1)
        k = int(np.argmax(err))
        if err[k] > 1:
            keep.add(a + 1 + k)
            stack += [(a, a + 1 + k), (a + 1 + k, b)]
    return sorted(keep)


def transform_xml(cam, o0, n, local0, ind, at=transform_at):
    """adjust-transform for output frames o0..o0+n-1 of a clip whose local time starts at local0 frames."""
    vals = np.array([at(cam[min(i, len(cam) - 1)]) for i in range(o0, o0 + n)])
    if np.all(np.abs(vals - [1, 0, 0, 0]) < TOL):
        return ""
    keys = simplify(vals)
    if len(keys) == 2 and np.all(np.abs(vals[0] - vals[-1]) < TOL):
        keys = [0]
    pad = " " * ind

    def param(name, fmt, cols):
        if len(keys) == 1 or np.all(np.abs(vals[:, cols] - vals[0, cols]) < TOL[cols]):
            return ""           # constant: the attribute on adjust-transform carries it
        ks = "".join(f'{pad}      <keyframe time="{ft(local0 + k)}" value="{fmt(vals[k])}" interp="linear" curve="linear"/>\n'
                     for k in keys)
        return f'{pad}  <param name="{name}">\n{pad}    <keyframeAnimation>\n{ks}{pad}    </keyframeAnimation>\n{pad}  </param>\n'

    v0 = vals[keys[0]]
    z = lambda x: 0.0 if abs(x) < 5e-5 else x
    pos = lambda v: f"{z(v[1]):.4f} {z(v[2]):.4f}"
    scl = lambda v: f"{v[0]:.5f} {v[0]:.5f}"
    rot = lambda v: f"{z(v[3]):.4f}"
    body = param("position", pos, [1, 2]) + param("scale", scl, [0]) + param("rotation", rot, [3])
    return (f'{pad}<adjust-transform position="{pos(v0)}" scale="{scl(v0)}" rotation="{rot(v0)}">\n'
            f'{body}{pad}</adjust-transform>\n')


# ----------------------------------------------------------------------------- main

def loudness_gain(raw_mix):
    """dB toward the MP4's -14 LUFS, capped so the true peak stays at -1.5 dBTP: the editor applies no limiter."""
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(raw_mix), "-af",
                        "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True)
    m = json.loads(re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)[-1])
    want, room = -14.0 - float(m["input_i"]), -1.5 - float(m["input_tp"])
    if want > room:
        print(f"loudness: {want:+.2f} dB would clip; using {room:+.2f} dB, the project plays "
              f"{want - room:.1f} dB quieter than the MP4 (add a limiter on the main bus to match)")
    return min(want, room)


def probe_audio_seconds(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def lanes_for(items, first_lane):
    """Greedy lane assignment so clips on one lane never overlap. items: [(start, n, ...)] sorted by start."""
    ends, out = [], []
    for it in items:
        for k, e in enumerate(ends):
            if e <= it[0]:
                ends[k] = it[0] + it[1]
                out.append(first_lane + k)
                break
        else:
            ends.append(it[0] + it[1])
            out.append(first_lane + len(ends) - 1)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--name", default="")
    ap.add_argument("--freeze", default="baked", choices=["baked", "png", "timemap"])
    ap.add_argument("--procs", type=int, default=default_procs(), help="render processes (default: 2 on 8 GB RAM, else 4)")
    ap.add_argument("--skip-layers", action="store_true", help="reuse rendered block/doodle clips")
    ap.add_argument("--force", action="store_true", help="developer only: export although build/ holds another reel")
    ap.add_argument("--verbose", action="store_true", help="the full output on the terminal (it is always in the log)")
    a = ap.parse_args()
    name = a.name or reel_id(a.script)
    with studio_lock("export " + name):
        keep_awake()
        require_slot(a.script, force=a.force)          # before anything is written: build/ must hold this script
        with run_log(BUILD / reel_id(a.script) / "logs" / f"export_{name}.log", a.verbose):
            export(a, name)


def export(a, name):
    T = time.time()
    script = resolve.load_script(a.script, check_fonts=True)
    proj = OUT / f"{name}_project"
    media = proj / "media"
    media.mkdir(parents=True, exist_ok=True)
    src = source_path(script)
    meta = load_json(BUILD / "meta.json")
    camj = load_json(BUILD / "camera.json")
    cam = camj["frames"]
    tl = load_json(BUILD / "timeline.json")
    n_out = meta["n_frames"]
    n_src = int(round(meta["src_duration"] * FPS))
    edl = EDL(meta["edl"], meta["src_duration"])

    # source clips (ingest.py) or the single source file
    clips_json = src.parent / "clips.json"
    if src.suffix == ".ffconcat" and clips_json.exists():
        clips = [{**c, "path": src.parent / c["file"], "f0": fr(c["offset"])} for c in load_json(clips_json)["clips"]]
    else:
        clips = [{"name": src.stem, "path": src, "f0": 0, "n_frames": n_src}]

    def clip_of(f):
        for k, c in enumerate(clips):
            if c["f0"] <= f < c["f0"] + c["n_frames"]:
                return k
        return len(clips) - 1

    resources, rid = [], [0]

    def new_id(prefix="r"):
        rid[0] += 1
        return f"{prefix}{rid[0]}"

    fmt_id = new_id()
    resources.append(f'<format id="{fmt_id}" name="FFVideoFormat1080x1920p30" frameDuration="{ft(1)}" '
                     f'width="{W}" height="{H}" colorSpace="1-1-1 (Rec. 709)"/>')
    still_fmt = None
    assets, collected = {}, {}

    def collect(path):
        """Hard-link (or copy) outside media into the project's media/ folder, so the project is one
        self-contained folder: the App Store build of Resolve is sandboxed to folders the user picks."""
        path = Path(path).resolve()
        if path.parent == media.resolve():
            return path
        dest = media / path.name
        owner = collected.setdefault(dest.name, path)
        if owner != path:                         # two sources share a name: keep both
            dest = media / f"{path.stem}_{abs(hash(str(path))) % 10 ** 6}{path.suffix}"
        if dest.exists():
            st_s, st_d = path.stat(), dest.stat()
            if os.path.samefile(path, dest) or (st_s.st_size, int(st_s.st_mtime)) == (st_d.st_size, int(st_d.st_mtime)):
                return dest
            dest.unlink()                         # the source changed since the last export
        try:
            os.link(path, dest)
        except OSError:
            shutil.copy2(path, dest)
        return dest

    def video_asset(path, n, has_audio, label):
        path = collect(path)
        key = str(path)
        if key not in assets:
            i = new_id()
            aud = ' hasAudio="1" audioSources="1" audioChannels="2" audioRate="48000"' if has_audio else ""
            resources.append(f'<asset id="{i}" name={quoteattr(label)} start="0s" duration="{ft(n)}" hasVideo="1" '
                             f'format="{fmt_id}"{aud}>\n    <media-rep kind="original-media" src={quoteattr(file_url(path))}/>\n  </asset>')
            assets[key] = i
        return assets[key]

    def still_asset(path, label):
        nonlocal still_fmt
        if still_fmt is None:
            still_fmt = new_id()
            resources.append(f'<format id="{still_fmt}" name="FFVideoFormatRateUndefined" width="{W}" height="{H}" '
                             f'colorSpace="1-1-1 (Rec. 709)"/>')
        key = str(path)
        if key not in assets:
            i = new_id()
            resources.append(f'<asset id="{i}" name={quoteattr(label)} start="0s" duration="0s" hasVideo="1" '
                             f'format="{still_fmt}">\n    <media-rep kind="original-media" src={quoteattr(file_url(path))}/>\n  </asset>')
            assets[key] = i
        return assets[key]

    def audio_asset(path, label):
        path = collect(path)
        key = str(path)
        if key not in assets:
            i = new_id()
            d = probe_audio_seconds(path)
            resources.append(f'<asset id="{i}" name={quoteattr(label)} start="0s" duration="{st(d)}" hasAudio="1" '
                             f'audioSources="1" audioChannels="2" audioRate="48000">\n'
                             f'    <media-rep kind="original-media" src={quoteattr(file_url(path))}/>\n  </asset>')
            assets[key] = (i, d)
        return assets[key]

    # ---- loudness: one shared gain on every clip
    raw_mix = BUILD / f"{name}_mix_raw.wav"
    norm = loudness_gain(raw_mix) if raw_mix.exists() else 0.0
    au = script.get("audio", {})
    voice_db = au.get("voice", {}).get("gain_db", 0) + norm
    print(f"loudness gain {norm:+.2f} dB (from {raw_mix.name if raw_mix.exists() else 'no mix'})")

    # ---- holds / freezes media
    def freeze_media(src_f, n, label):
        """(kind, asset id, local start frame) for a held source frame."""
        if a.freeze == "timemap":
            k = clip_of(src_f)
            return "timemap", video_asset(clips[k]["path"], clips[k]["n_frames"], True, clips[k]["name"]), src_f - clips[k]["f0"]
        if a.freeze == "png":
            p = media / f"{label}.png"
            cv2.imwrite(str(p), source_frame(src, src_f))
            return "png", still_asset(p, label), 0
        p = media / f"{label}.mov"
        k = clip_of(src_f)
        bake_hold(clips[k]["path"], src_f - clips[k]["f0"], n, p)
        return "baked", video_asset(p, n, False, label), 0

    # ---- spine: EDL items
    spine = []      # dicts: o0, n, kind, ref, start(local frames), name
    sf = lambda i: edl.src_frame(i, n_src)
    for o0, o1, seg in edl.items:
        f_o0, f_o1 = fr(o0), fr(o1)
        i = f_o0
        while i < f_o1:
            f = sf(i)
            if "src" not in seg or (i > f_o0 and f == sf(i - 1)):      # a hold, or a segment's clamped last frame
                j = i
                while j + 1 < f_o1 and sf(j + 1) == f:
                    j += 1
                label = f"hold_{len(spine):02d}"
                kind, ref, start = freeze_media(f, j - i + 1, label)
                spine.append({"o0": i, "n": j - i + 1, "kind": kind, "ref": ref, "start": start, "name": label})
            else:                                  # the source advances one frame per output frame inside one clip
                c = clips[clip_of(f)]
                j = i
                while j + 1 < f_o1 and sf(j + 1) == sf(j) + 1 and sf(j + 1) < c["f0"] + c["n_frames"]:
                    j += 1
                spine.append({"o0": i, "n": j - i + 1, "kind": "clip", "start": f - c["f0"], "name": c["name"],
                              "ref": video_asset(c["path"], c["n_frames"], True, c["name"])})
            i = j + 1

    # ---- audio.mute: split spine clips at the mute edges and silence the muted pieces
    mutes = [(fr(m0), fr(m1)) for m0, m1 in au.get("mute", [])]
    split = []
    for s_ in spine:
        cuts_ = sorted({e for m in mutes for e in m if s_["kind"] == "clip" and s_["o0"] < e < s_["o0"] + s_["n"]})
        edges = [s_["o0"]] + cuts_ + [s_["o0"] + s_["n"]]
        for e0, e1 in zip(edges[:-1], edges[1:]):
            piece = {**s_, "o0": e0, "n": e1 - e0, "start": s_["start"] + (e0 - s_["o0"])}
            piece["muted"] = s_["kind"] == "clip" and any(m0 <= e0 and e1 <= m1 for m0, m1 in mutes)
            split.append(piece)
    spine = split

    # ---- camera freezes (picture held, audio runs): runs where camera src_f differs from the EDL
    connected = []  # dicts: o0, n, lane, xml (without offset) builder
    i = 0
    while i < n_out:
        e = edl.src_frame(i, n_src)
        if cam[i]["src_f"] != e:
            j = i
            while j + 1 < n_out and cam[j + 1]["src_f"] == cam[i]["src_f"] and cam[j + 1]["src_f"] != edl.src_frame(j + 1, n_src):
                j += 1
            n = j - i + 1
            label = f"freeze_{i:05d}"
            kind, ref, start = freeze_media(cam[i]["src_f"], n, label)
            connected.append({"o0": i, "n": n, "cat": "freeze", "kind": kind, "ref": ref, "start": start, "name": label,
                              "hold_src": cam[i]["src_f"]})
            i = j + 1
        else:
            i += 1

    # ---- transitions (swipe, spin, zoom-through): baked with their motion blur; the takes underneath keep the voice
    runs = {}
    for i, fr_ in enumerate(cam):
        if "tr" in fr_:
            runs.setdefault(fr_["tr"], []).append(i)
    if runs:
        sources = [video_pass.FrameSource(src), video_pass.FrameSource(src)]
        shutter = camj.get("motion_blur", 0.0)
        for k_tr, idx in sorted(runs.items()):
            f0, n = idx[0], idx[-1] - idx[0] + 1
            label = f"transition_{k_tr + 1:02d}"
            p = media / f"{label}.mov"
            encode((video_pass.picture(cam, i, sources, shutter) for i in range(f0, f0 + n)), p, n, alpha=False)
            connected.append({"o0": f0, "n": n, "cat": "transition", "kind": "overlay",
                              "ref": video_asset(p, n, False, label), "start": 0, "name": label})
        for s_ in sources:
            s_.close()

    # ---- flashes
    i = 0
    while i < n_out:
        if cam[i].get("flash", 0) > 0:
            j = i
            while j + 1 < n_out and cam[j + 1].get("flash", 0) > 0:
                j += 1
            label = f"flash_{i:05d}"
            p = media / f"{label}.mov"
            fl = [cam[k]["flash"] for k in range(i, j + 1)]
            encode((np.dstack([np.full((H, W, 3), 255, np.uint8), np.full((H, W), int(round(x * 255)), np.uint8)]) for x in fl),
                   p, len(fl), alpha=True)
            connected.append({"o0": i, "n": len(fl), "cat": "flash", "kind": "overlay",
                              "ref": video_asset(p, len(fl), False, label), "start": 0, "name": label})
            i = j + 1
        else:
            i += 1

    # ---- subtitle blocks and doodles, one clip each
    occl = set(tl.get("occlude_frames", []))
    masks_path = str(ROOT / script["masks"]) if script.get("masks") else None
    jobs = []
    for sc in tl["screens"]:
        for b in sc["blocks"]:
            one = {**tl, "screens": [{**sc, "blocks": [b]}], "doodles": []}
            f0 = max(0, int(sc["t0"] * FPS) - 1)
            f1 = min(n_out, int(np.ceil((sc["t1"] + sc.get("fade", 0.3) + 0.1) * FPS)) + 1)
            text = " ".join(t["text"] for l in b["lines"] for t in l["tokens"])
            jobs.append((f"{b['id']}", one, list(range(f0, f1)), str(media / f"{b['id']}.mov"), occl, masks_path,
                         str(BUILD / "camera.json"), text))
    for k, d in enumerate(tl.get("doodles", [])):
        one = {**tl, "screens": [], "doodles": [d]}
        f0 = max(0, int(d["t"] * FPS) - 1)
        f1 = min(n_out, int(np.ceil(d["t1"] * FPS)) + 1) if "t1" in d else n_out     # no t1: to the end
        jobs.append((f"doodle{k}", one, list(range(f0, f1)), str(media / f"doodle{k}.mov"), occl, masks_path,
                     str(BUILD / "camera.json"), d["type"]))
    layer_meta = proj / "layers.json"
    if a.skip_layers and layer_meta.exists():
        placed = {k: tuple(v) if v else None for k, v in load_json(layer_meta).items()}
    else:
        with Pool(a.procs) as pool:
            placed = dict(pool.map(render_layer, [j[:7] for j in jobs]))
        layer_meta.write_text(json.dumps(placed), encoding="utf-8")
    for nm, _, _, path, _, _, _, text in jobs:
        if placed.get(nm):
            f0, n = placed[nm]
            connected.append({"o0": f0, "n": n, "cat": "doodle" if nm.startswith("doodle") else "text",
                              "kind": "overlay", "ref": video_asset(path, n, False, nm), "start": 0,
                              "name": f"{nm} {text}"[:60]})
        else:
            print(f"warning: {nm} is never visible")

    # lanes, bottom to top as the MP4 composites them: freeze stills, flashes, text, doodles
    lane = 1
    for cat in ("freeze", "transition", "flash", "text", "doodle"):
        items = sorted([c for c in connected if c["cat"] == cat], key=lambda c: c["o0"])
        if not items:
            continue
        ls = lanes_for([(c["o0"], c["n"]) for c in items], lane)
        for c, l in zip(items, ls):
            c["lane"] = l
        lane = max(ls) + 1

    # ---- audio: voice-overs (own wav files: a video asset on an audio lane would bring its picture), sfx, music
    audio_items = []
    for k, v in enumerate(au.get("voice_over", [])):
        a0, a1 = v["src"]
        wav = media / f"voice_over_{k:02d}.wav"
        d, nfr = a1 - a0, math.ceil((a1 - a0) * FPS - 1e-6)
        subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-ss", f"{a0:.6f}", "-i", str(src), "-t", f"{d:.6f}",
                        "-vn", "-af", f"aresample=48000,afade=t=in:d=0.006,afade=t=out:st={max(0, d - 0.006):.6f}:d=0.006,"
                                      f"apad,atrim=end_sample={nfr * 48000 // FPS}",
                        "-ac", "2", "-c:a", "pcm_s24le", str(wav)], check=True)
        aid, _ = audio_asset(wav, f"voice over {k + 1}")
        o0 = fr(v["at"])
        audio_items.append({"o0": o0, "n": min(nfr, n_out - o0), "ref": aid, "start_s": 0.0,
                            "name": f"voice over {k + 1}", "db": voice_db + v.get("gain_db", 0)})
    for cue in build.sfx_cues(au):
        aid, d = audio_asset(Path(cue["file"]), Path(cue["file"]).stem)
        o0, head = max(0, fr(cue["t"])), max(0.0, -cue["t"])      # a cue before 0 starts inside the file
        n = min(int((d - head) * FPS), n_out - o0)
        if n <= 0:
            continue
        audio_items.append({"o0": o0, "n": n, "ref": aid, "start_s": head, "name": Path(cue["file"]).stem,
                            "db": cue.get("gain_db", -12) + norm})
    if au.get("music"):
        m = au["music"]
        mp = ROOT / "assets/music" / m["file"]
        aid, d = audio_asset(mp, mp.stem)
        n = min(n_out, int((d - m.get("offset", 0)) * FPS))
        audio_items.append({"o0": 0, "n": n, "ref": aid, "start_s": m.get("offset", 0), "name": "music",
                            "db": m.get("gain_db", -20) + norm, "fade_in": m.get("fade_in", 0), "fade_out": m.get("fade_out", 0)})
    audio_items.sort(key=lambda x: x["o0"])
    for x, l in zip(audio_items, lanes_for([(x["o0"], x["n"]) for x in audio_items], -1)):
        x["lane"] = l
    # negative lanes count downwards
    neg = sorted({x["lane"] for x in audio_items})
    remap = {l: -(k + 1) for k, l in enumerate(neg)}
    for x in audio_items:
        x["lane"] = remap[x["lane"]]

    # ---- attach every connected item to the spine element under its start
    def parent_of(o):
        for k, s in enumerate(spine):
            if s["o0"] <= o < s["o0"] + s["n"]:
                return k
        return len(spine) - 1

    children = {k: [] for k in range(len(spine))}

    def vol(db, ind, fade_in=0, fade_out=0):
        pad = " " * ind
        fades = ""
        if fade_in or fade_out:
            fades = (f"{pad}  <param name=\"amount\">\n"
                     + (f'{pad}    <fadeIn type="easeIn" duration="{ft(fr(fade_in))}"/>\n' if fade_in else "")
                     + (f'{pad}    <fadeOut type="easeOut" duration="{ft(fr(fade_out))}"/>\n' if fade_out else "")
                     + f"{pad}  </param>\n")
            return f'{pad}<adjust-volume amount="{db:+.2f}dB">\n{fades}{pad}</adjust-volume>\n'
        return f'{pad}<adjust-volume amount="{db:+.2f}dB"/>\n'

    def clip_xml(c, offset, ind, lane=None, with_transform=True, audio_db=None):
        pad = " " * ind
        lane_attr = f' lane="{lane}"' if lane is not None else ""
        if c["kind"] == "png":
            head = (f'{pad}<video ref="{c["ref"]}"{lane_attr} offset="{ft(offset)}" name={quoteattr(c["name"])} '
                    f'start="0s" duration="{ft(c["n"])}">\n')
            tail = f"{pad}</video>\n"
            local0 = 0
        else:
            start = c["start"] if c["kind"] != "timemap" else 0
            head = (f'{pad}<asset-clip ref="{c["ref"]}"{lane_attr} offset="{ft(offset)}" name={quoteattr(c["name"])} '
                    f'start="{ft(start)}" duration="{ft(c["n"])}" format="{fmt_id}" tcFormat="NDF">\n')
            tail = f"{pad}</asset-clip>\n"
            local0 = start
        body = ""
        if c["kind"] == "timemap":
            body += (f'{pad}  <timeMap>\n{pad}    <timept time="0s" value="{ft(c["start"])}" interp="linear"/>\n'
                     f'{pad}    <timept time="{ft(c["n"])}" value="{ft(c["start"])}" interp="linear"/>\n{pad}  </timeMap>\n')
        if with_transform and c.get("cat") in ("doodle", "text"):
            body += transform_xml(cam, c["o0"], c["n"], local0, ind + 2, at=overlay_at)
        elif with_transform and c.get("cat") not in ("flash", "transition"):
            body += transform_xml(cam, c["o0"], c["n"], local0, ind + 2)
        if audio_db is not None:
            body += vol(audio_db, ind + 2)
        return head, body, tail

    out_lines = []
    for k, s in enumerate(spine):
        # spine offsets are sequence times; a connected clip's offset is in its parent's local time
        audio_db = (-96.0 if s.get("muted") else voice_db) if s["kind"] == "clip" else -96.0 if s["kind"] == "timemap" else None
        head, body, tail = clip_xml(s, s["o0"], 6, audio_db=audio_db)
        local0 = s["start"] if s["kind"] == "clip" else 0
        kids = ""
        for c in sorted([c for c in connected if parent_of(c["o0"]) == k], key=lambda c: (c["lane"], c["o0"])):
            off = local0 + (c["o0"] - s["o0"])
            h, b_, t = clip_xml(c, off, 8, lane=c["lane"],
                                audio_db=-96.0 if c["kind"] == "timemap" else None)
            kids += h + b_ + t
        for x in [x for x in audio_items if parent_of(x["o0"]) == k]:
            off = local0 + (x["o0"] - s["o0"])
            kids += (f'        <asset-clip ref="{x["ref"]}" lane="{x["lane"]}" offset="{ft(off)}" name={quoteattr(x["name"])} '
                     f'start="{st(x["start_s"])}" duration="{ft(x["n"])}">\n'
                     + vol(x["db"], 10, x.get("fade_in", 0), x.get("fade_out", 0))
                     + "        </asset-clip>\n")
        out_lines.append(head + body + kids + tail)

    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n<fcpxml version="1.10">\n<resources>\n  '
           + "\n  ".join(resources) + "\n</resources>\n<library>\n"
           f'  <event name={quoteattr(name)}>\n  <project name={quoteattr(f"{name} ({a.freeze})")}>\n'
           f'    <sequence format="{fmt_id}" duration="{ft(n_out)}" tcStart="0s" tcFormat="NDF" audioLayout="stereo" audioRate="48k">\n'
           "     <spine>\n" + "".join(out_lines) + "     </spine>\n    </sequence>\n  </project>\n  </event>\n</library>\n</fcpxml>\n")
    out = proj / f"{name}.fcpxml" if a.freeze == "baked" else proj / f"{name}_{a.freeze}.fcpxml"
    out.write_text(xml, encoding="utf-8")
    n_text = sum(1 for c in connected if c["cat"] == "text")
    print(f"[export] {time.time() - T:.1f}s -> {short(out)}: {len(spine)} spine clips, {n_text} text clips, "
          f"{sum(1 for c in connected if c['cat'] == 'doodle')} doodles, {sum(1 for c in connected if c['cat'] == 'freeze')} freezes, "
          f"{sum(1 for c in connected if c['cat'] == 'flash')} flashes, {len(audio_items)} audio clips")


if __name__ == "__main__":
    sys.exit(main())
