"""Gesture events in the source, for placing transitions on real movement (run by prep.py, or alone).

python motion.py <video> <prep_dir>          writes <prep_dir>/motion.json

Optical flow inside the person matte, per frame:
  sweep     a fast sideways (or vertical) move of a hand or the body: direction, start / peak / end, speed in px per
            frame at 1080 px width. A swipe or whip transition cut on the peak follows the move.
  to_lens   something held toward the camera (the moving region grows frame over frame): start, the moment it
            settles, and where it stopped (screen px) - the target of a zoom-through into a close-up.
Times are SOURCE seconds; times.py prints them in output time.
"""
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

from common import FPS, H, W

QW, QH = W // 4, H // 4             # flow at the masks' quarter resolution
SWEEP_SPEED = 28.0                  # px/frame (1080 px wide) of the fastest 5 % of the person's pixels
APPROACH = 1.012                    # per-frame growth of the moving region


def frames(video):
    p = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video), "-vf", f"scale={QW}:{QH}:flags=area",
                          "-f", "rawvideo", "-pix_fmt", "gray", "-"], stdout=subprocess.PIPE)
    n = QW * QH
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, np.uint8).reshape(QH, QW)
    if p.wait():
        raise RuntimeError(f"ffmpeg could not decode {video}")


def measure(video, masks, cuts=()):
    """Per-frame [sweep_x, sweep_y, growth, cx, cy] (px/frame at full res; growth ~1 = steady)."""
    cut_frames = {int(round(c * FPS)) for c in cuts}
    rows, prev = [], None
    for i, g in enumerate(frames(video)):
        row = [0.0, 0.0, 1.0, W / 2, H / 2]
        if prev is not None and i not in cut_frames and i < len(masks):
            flow = cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            m = masks[i] > 127
            if m.sum() > 300:
                fx, fy = flow[..., 0][m] * 4, flow[..., 1][m] * 4
                hi_x, lo_x = np.percentile(fx, 95), np.percentile(fx, 5)
                hi_y, lo_y = np.percentile(fy, 95), np.percentile(fy, 5)
                row[0] = float(hi_x if abs(hi_x) >= abs(lo_x) else lo_x)
                row[1] = float(hi_y if abs(hi_y) >= abs(lo_y) else lo_y)
                mag = np.hypot(flow[..., 0], flow[..., 1])
                moving = m & (mag > max(0.6, np.percentile(mag[m], 70)))
                if moving.sum() > 150:              # growth of the moving region: fit p -> p + flow as a similarity
                    ys, xs = np.nonzero(moving)
                    pick = np.linspace(0, len(xs) - 1, min(400, len(xs))).astype(int)
                    src = np.stack([xs[pick], ys[pick]], 1).astype(np.float32)
                    dst = src + flow[ys[pick], xs[pick]]
                    a, _ = cv2.estimateAffinePartial2D(src, dst, method=cv2.RANSAC, ransacReprojThreshold=1.5)
                    if a is not None:
                        row[2] = float(np.hypot(a[0, 0], a[1, 0]))
                    top = ys <= np.percentile(ys, 35)      # the object leads, the arm trails below it
                    row[3], row[4] = float(xs[top].mean() * 4), float(ys[top].mean() * 4)
        rows.append(row)
        prev = g
    return np.array(rows)


def runs(flags, min_len):
    out, i = [], 0
    while i < len(flags):
        if flags[i]:
            j = i
            while j + 1 < len(flags) and flags[j + 1]:
                j += 1
            if j - i + 1 >= min_len:
                out.append((i, j))
            i = j + 1
        else:
            i += 1
    return out


def events(rows):
    ev = []
    sx, sy, growth = rows[:, 0], rows[:, 1], rows[:, 2]
    for axis, v, pos, neg in ((0, sx, "right", "left"), (1, sy, "down", "up")):
        for sign, name in ((1, pos), (-1, neg)):
            for a, b in runs(sign * v > SWEEP_SPEED, 3):
                k = a + int(np.argmax(sign * v[a:b + 1]))
                ev.append({"type": "sweep", "dir": name, "t0": round(a / FPS, 3), "t_peak": round(k / FPS, 3),
                           "t1": round((b + 1) / FPS, 3), "speed": round(float(abs(v[k])), 1)})
    smooth = np.convolve(growth, np.ones(3) / 3, mode="same")
    for a, b in runs(smooth > APPROACH, 3):
        settle = min(len(rows) - 1, b + 2)
        ev.append({"type": "to_lens", "t0": round(a / FPS, 3), "t_settle": round(settle / FPS, 3),
                   "growth": round(float(np.prod(growth[a:b + 1])), 2),
                   "at": [int(rows[b, 3]), int(rows[b, 4])]})
    return sorted(ev, key=lambda e: e["t0"])


def main():
    video, out = Path(sys.argv[1]), Path(sys.argv[2])
    masks = np.load(out / "masks.npy", mmap_mode="r")
    cuts = json.loads((out / "cuts.json").read_text())["cuts"] if (out / "cuts.json").exists() else []
    ev = events(measure(video, masks, cuts))
    (out / "motion.json").write_text(json.dumps({"events": ev}, indent=1), encoding="utf-8")
    for e in ev:
        print(e)


if __name__ == "__main__":
    main()
