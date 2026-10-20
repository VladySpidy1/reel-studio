"""Labelled contact sheet of any stretch of a video: the way to WATCH footage and drafts, not just read transcripts.

python contact_sheet.py <video | source.ffconcat> <from_s> <to_s> <step_s> [--words words.json] [--phone] [--full]
                        [--out sheet.jpg]

Each tile carries its time (in that file's time, so source sheets read in source seconds) and, with --words,
a SPEECH bar when a word starts inside the tile. 1 s steps to survey a clip, 0.1 s around a gesture, 1/30 s to
pick a cut frame, 0.25-0.3 s over a draft render. --phone draws the Instagram crop lines (97 px per side at 1080).
The sheet's long edge is at most 1200 px, so many tiles get small: to see more, take a shorter stretch or a bigger
step; --full keeps 180x320 tiles in 10 columns.
"""
import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

from common import BUILD, W, sheet_grid

TW, TH, COLS = 180, 320, 10
PHONE_CROP = 97            # px per side at 1080 wide that Instagram crops on 19.5:9 / 20:9 phones


def sheet(video, t0, t1, step, words=(), out=None, phone=False, full=False):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", str(video),
                          "-vf", f"fps={1 / step},scale={TW}:{TH}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         capture_output=True, check=True).stdout
    frames = np.frombuffer(raw, np.uint8).reshape(-1, TH, TW, 3)
    if not len(frames):
        raise SystemExit("no frames in that range")
    cols, tw, th = (COLS, TW, TH) if full else sheet_grid(len(frames), TW)
    tiles = []
    for k, im in enumerate(frames):
        im, t = im.copy(), t0 + k * step
        if (tw, th) != (TW, TH):
            im = cv2.resize(im, (tw, th), interpolation=cv2.INTER_AREA)
        if phone:
            x = round(PHONE_CROP * tw / W)
            for xx in (x, tw - 1 - x):
                cv2.line(im, (xx, 0), (xx, th - 1), (0, 0, 255), 1)
        label = f"{t:.2f}" if step < 1 else f"{t:.1f}"
        cv2.rectangle(im, (0, 0), (8 + 9 * len(label), 20), (0, 0, 0), -1)
        cv2.putText(im, label, (4, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
        if any(t <= w < t + step for w in words):
            cv2.rectangle(im, (0, th - 20), (tw, th), (0, 0, 0), -1)
            cv2.putText(im, "SPEECH", (4, th - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1)
        tiles.append(im)
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    img = np.vstack([np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)])
    out = Path(out or BUILD / "look" / f"{Path(video).stem}_{t0:.1f}_{t1:.1f}.jpg")
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), img, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("t0", type=float)
    ap.add_argument("t1", type=float)
    ap.add_argument("step", type=float)
    ap.add_argument("--words", help="words.json (source time) to mark speech")
    ap.add_argument("--phone", action="store_true", help="draw the Instagram crop lines on each tile")
    ap.add_argument("--full", action="store_true", help="full-size tiles (180x320, 10 columns)")
    ap.add_argument("--out")
    a = ap.parse_args()
    words = [w["s"] for s in json.loads(Path(a.words).read_text())["segments"] for w in s["words"]] if a.words else []
    print(sheet(a.video, a.t0, a.t1, a.step, words, a.out, a.phone, a.full))


if __name__ == "__main__":
    main()
