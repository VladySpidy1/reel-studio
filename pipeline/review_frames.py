"""One review sheet per render: a frame for every subtitle screen at the moment it is fully typed,
plus the layout report. Cheap to look at (one image).

python review_frames.py output/<name>.mp4 [--out build/review/<name>_screens.jpg]
"""
import argparse
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from common import BUILD, H, W, load_json


def grab(video, t):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.3f}", "-i", str(video), "-frames:v", "1",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W, 3).copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--out", default="")
    ap.add_argument("--cols", type=int, default=6)
    a = ap.parse_args()
    tl = load_json(BUILD / "timeline.json")
    tiles = []
    shots = []
    for sc in tl["screens"]:
        for b in sc["blocks"]:                      # one frame per block, right after it is fully typed
            t_last = max(tok["t"] for l in b["lines"] for tok in l["tokens"])
            t_end = min(sc["t1"], b.get("until", 1e9))
            shots.append(min(t_end - 0.04, t_last + 0.4))
    for i, t in enumerate(sorted(shots)):
        im = grab(a.video, t)
        im = cv2.resize(im, (360, 640), interpolation=cv2.INTER_AREA)
        cv2.putText(im, f"#{i} {t:.2f}s", (8, 628), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        tiles.append(im)
    while len(tiles) % a.cols:
        tiles.append(np.zeros_like(tiles[0]))
    sheet = np.vstack([np.hstack(tiles[k:k + a.cols]) for k in range(0, len(tiles), a.cols)])
    out = Path(a.out) if a.out else BUILD / "review" / f"{Path(a.video).stem}_screens.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), sheet, [cv2.IMWRITE_JPEG_QUALITY, 88])
    print(out)


if __name__ == "__main__":
    sys.exit(main())
