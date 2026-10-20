"""Labelled contact sheet of any stretch of a video: the way to WATCH footage and drafts, not just read transcripts.

python contact_sheet.py <video | source.ffconcat> <from_s> <to_s> <step_s> [--words words.json] [--out sheet.jpg]

Each tile carries its time (in that file's time, so source sheets read in source seconds) and, with --words,
a SPEECH bar when a word starts inside the tile. 1 s steps to survey a clip, 0.1 s around a gesture, 1/30 s to
pick a cut frame, 0.25-0.3 s over a draft render.
"""
import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

from common import BUILD

TW, TH, COLS = 180, 320, 10


def sheet(video, t0, t1, step, words=(), out=None):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0:.3f}", "-i", str(video),
                          "-vf", f"fps={1 / step},scale={TW}:{TH}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         capture_output=True, check=True).stdout
    tiles = []
    for k, im in enumerate(np.frombuffer(raw, np.uint8).reshape(-1, TH, TW, 3)):
        im, t = im.copy(), t0 + k * step
        label = f"{t:.2f}" if step < 1 else f"{t:.1f}"
        cv2.rectangle(im, (0, 0), (8 + 9 * len(label), 20), (0, 0, 0), -1)
        cv2.putText(im, label, (4, 15), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 255, 0), 1)
        if any(t <= w < t + step for w in words):
            cv2.rectangle(im, (0, TH - 20), (TW, TH), (0, 0, 0), -1)
            cv2.putText(im, "SPEECH", (4, TH - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 200, 255), 1)
        tiles.append(im)
    if not tiles:
        raise SystemExit("no frames in that range")
    while len(tiles) % COLS:
        tiles.append(np.zeros_like(tiles[0]))
    img = np.vstack([np.hstack(tiles[i:i + COLS]) for i in range(0, len(tiles), COLS)])
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
    ap.add_argument("--out")
    a = ap.parse_args()
    words = [w["s"] for s in json.loads(Path(a.words).read_text())["segments"] for w in s["words"]] if a.words else []
    print(sheet(a.video, a.t0, a.t1, a.step, words, a.out))


if __name__ == "__main__":
    main()
