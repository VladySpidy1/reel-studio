"""One review sheet per render: a frame for every subtitle screen at the moment it is fully typed,
plus the layout report. Cheap to look at (one image, long edge <= 1200 px; --full: 360x640 tiles).

python review_frames.py output/<name>.mp4 [--out build/review/<name>_screens.jpg] [--cols N] [--full] [--force]

It reads the build slot's timeline, so it refuses (exit 2) a video the slot did not render (--force: developer only).
"""
import argparse
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from common import BUILD, H, W, load_json, require_slot, sheet_grid


def grab(video, t):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W, 3).copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", default="")
    ap.add_argument("--cols", type=int, default=0, help="default: 6 with --full, else the count that gives the biggest tiles")
    ap.add_argument("--full", action="store_true", help="full-size tiles (360x640), 6 columns")
    ap.add_argument("--force", action="store_true", help="developer only: review a video the build slot did not render")
    a = ap.parse_args()
    require_slot(render=a.video, force=a.force)
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
