"""One review sheet per render: a frame for every subtitle screen at the moment it is fully typed and for every
insert once it has popped in, plus the layout report. Cheap to look at (one image, long edge <= 1200 px; --full:
360x640 tiles).

python review_frames.py output/<name>.mp4 [--out build/review/<name>_screens.jpg] [--cols N] [--full] [--force]
python review_frames.py output/<name>.mp4 --cuts [--out build/review/<name>_cuts.jpg]

--cuts: instead, the last frame before and the first frame after every cut of the slot's edl (output time), side by
side, labelled with the cut's time and the words heard around it: does a head jump, does a word get clipped.
It reads the build slot's timeline, so it refuses (exit 2) a video the slot did not render (--force: debugging only).
"""
import argparse
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import layers
from common import BUILD, FPS, H, ROOT, SHEET_EDGE, W, load_json, require_slot, sheet_grid
from edl import EDL

LABEL_FONT = ROOT / "assets" / "fonts" / "RobotoCondensed-VF.ttf"       # Cyrillic labels (cv2 draws ASCII only)


def grab(video, t):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W, 3).copy()


def frame(video, f):
    """Output frame f of a video (seeking to its middle; seeking to f/30 can land on the next frame)."""
    return grab(video, max(0.0, (f - 0.5) / FPS))


def cuts(meta):
    """[(cut frame, kind, words before, words after)] for every boundary of the slot's edl."""
    edl = EDL(meta["edl"], meta["src_duration"])
    words = sorted(meta["words"], key=lambda w: w["s"])
    out = []
    for (o0, o1, a), (p0, p1, b) in zip(edl.items, edl.items[1:]):
        f = round(p0 * FPS)
        kind = "hold" if "hold" in a or "hold" in b else "cut"
        before = " ".join(w["w"].strip() for w in words if w["s"] < f / FPS)
        after = " ".join(w["w"].strip() for w in words if w["s"] >= f / FPS)
        out.append((f, kind, before[-28:], after[:28]))
    return out


def cut_sheet(a, meta):
    """Pairs of tiles (last frame before, first frame after) per cut, an even column count, long edge <= 1200 px."""
    cs = cuts(meta)
    if not cs:
        print("no cuts in the slot's edl")
        return 0
    n = 2 * len(cs)
    cols, tw, th = max((sheet_grid(n, 360, c) for c in range(2, n + 1, 2)), key=lambda g: (g[1], -g[0]))
    font = ImageFont.truetype(str(LABEL_FONT), max(10, tw // 13))
    lh = font.size + 3
    tiles = []
    for k, (f, kind, before, after) in enumerate(cs):
        for side, g, text in ((0, f - 1, f"#{k + 1} {f / FPS:.2f}s {kind}"), (1, f, "")):
            im = Image.fromarray(cv2.cvtColor(cv2.resize(frame(a.video, g), (tw, th), interpolation=cv2.INTER_AREA),
                                              cv2.COLOR_BGR2RGB))
            d = ImageDraw.Draw(im)
            lines = [text, f"…{before}" if before else "(start)"] if side == 0 else ["after", f"{after}…" if after else "(end)"]
            d.rectangle((0, th - 2 * lh - 4, tw, th), fill=(0, 0, 0))
            for i, ln in enumerate(lines):
                d.text((4, th - 2 * lh - 2 + i * lh), ln, font=font, fill=(0, 255, 0) if i == 0 else (255, 255, 255))
            if side:                                  # the cut: a bar on the after tile's left edge
                d.rectangle((0, 0, 2, th), fill=(255, 64, 64))
            tiles.append(cv2.cvtColor(np.asarray(im), cv2.COLOR_RGB2BGR))
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    sheet = np.vstack([np.hstack(tiles[k:k + cols]) for k in range(0, len(tiles), cols)])
    assert max(sheet.shape[:2]) <= SHEET_EDGE
    out = Path(a.out) if a.out else BUILD / "review" / f"{Path(a.video).stem}_cuts.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(f"{out}  ({len(cs)} cuts)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", default="")
    ap.add_argument("--cols", type=int, default=0, help="default: 6 with --full, else the count that gives the biggest tiles")
    ap.add_argument("--full", action="store_true", help="full-size tiles (360x640), 6 columns")
    ap.add_argument("--cuts", action="store_true", help="the frames on both sides of every cut instead of the screens")
    ap.add_argument("--force", action="store_true", help="debugging only: review a video the build slot did not render")
    a = ap.parse_args()
    meta = require_slot(render=a.video, force=a.force)
    if a.cuts:
        return cut_sheet(a, meta)
    tl = load_json(BUILD / "timeline.json")
    tiles = []
    shots = []
    for sc in tl["screens"]:
        for b in sc["blocks"]:                      # one frame per block, right after it is fully typed
            t_last = max(tok["t"] for l in b["lines"] for tok in l["tokens"])
            t_end = b.get("t1", min(sc["t1"], b.get("until", 1e9)))          # a block window (hook, CTA) or its screen
            shots.append(min(t_end - 0.04, t_last + 0.4))
            if b.get("preset"):                     # a hook or CTA card also as it pops
                shots.append(min(t_end - 0.04, b.get("t0", sc["t0"]) + 0.3))
    for ly in tl.get("layers", []):                 # each insert at rest, 0.2 s after its pop
        if ly["cat"] == "insert":
            anim = (layers.ANIMS.get(ly["anim"]) if isinstance(ly.get("anim"), str) else ly.get("anim")) or {}
            shots.append(min(ly["f1"] / FPS - 0.04, ly["f0"] / FPS + anim.get("dur", 0) + 0.2))
    cols, tw, th = (a.cols or 6, 360, 640) if a.full else sheet_grid(len(shots), 360, a.cols)
    for i, t in enumerate(sorted(shots)):
        im = grab(a.video, t)
        im = cv2.resize(im, (tw, th), interpolation=cv2.INTER_AREA)
        if a.full:
            cv2.putText(im, f"#{i} {t:.2f}s", (8, 628), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        else:                                       # drawn at the final size, on black: readable on small tiles
            label = f"#{i} {t:.2f}s"
            (lw, lh), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            cv2.rectangle(im, (0, th - lh - 10), (lw + 8, th), (0, 0, 0), -1)
            cv2.putText(im, label, (4, th - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1, cv2.LINE_AA)
        tiles.append(im)
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    sheet = np.vstack([np.hstack(tiles[k:k + cols]) for k in range(0, len(tiles), cols)])
    out = Path(a.out) if a.out else BUILD / "review" / f"{Path(a.video).stem}_screens.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(out)


if __name__ == "__main__":
    sys.exit(main())
