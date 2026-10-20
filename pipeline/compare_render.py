"""Compare an editor's render of the editable project with our own render, frame by frame.

python compare_render.py <reference.mp4> <editor_render.mp4> [--out build/compare]

Prints format differences, per-frame PSNR runs where the picture diverges (with the timeline elements on
screen then), loudness of both mixes, and writes a side-by-side sheet (ours | editor | 4x difference) at the
moments that differ most, plus one frame per subtitle block. The reference should be rendered without the
grade (video_pass with grade=None) because the editable project does not carry it yet.
"""
import argparse
import json
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np

from common import BUILD, FPS, H, W, load_json


def probe(p):
    d = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(p)],
                                  capture_output=True, text=True, check=True).stdout)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    return {"size": f"{v['width']}x{v['height']}", "fps": v["r_frame_rate"], "frames": int(v.get("nb_frames", 0)),
            "duration": float(d["format"]["duration"]), "pix_fmt": v["pix_fmt"],
            "color": f"{v.get('color_primaries')}/{v.get('color_transfer')}/{v.get('color_space')}/{v.get('color_range')}"}


def frames(p):
    proc = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", str(p), "-vf",
                             f"scale={W}:{H}:in_color_matrix=bt709:in_range=tv", "-f", "rawvideo", "-pix_fmt", "bgr24",
                             "-"], stdout=subprocess.PIPE)
    n = W * H * 3
    while True:
        b = proc.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, np.uint8).reshape(H, W, 3)
    proc.wait()


def loudness(p):
    r = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(p), "-af", "ebur128=peak=true", "-f", "null", "-"],
                       capture_output=True, text=True)
    i = re.findall(r"I:\s+(-?[\d.]+) LUFS", r.stderr)
    pk = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", r.stderr)
    return (float(i[-1]) if i else None), (float(pk[-1]) if pk else None)


def psnr(a, b):
    mse = np.mean((a.astype(np.float32) - b.astype(np.float32)) ** 2)
    return 99.0 if mse == 0 else 10 * np.log10(255 ** 2 / mse)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ours")
    ap.add_argument("theirs")
    ap.add_argument("--out", default=str(BUILD / "compare"))
    ap.add_argument("--threshold", type=float, default=32.0, help="PSNR below this counts as different")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    po, pt = probe(a.ours), probe(a.theirs)
    for k in po:
        flag = "" if po[k] == pt[k] else "   <-- differs"
        print(f"{k:9} ours {po[k]!s:28} editor {pt[k]!s:28}{flag}")
    lo, lt = loudness(a.ours), loudness(a.theirs)
    print(f"loudness ours {lo[0]} LUFS (peak {lo[1]}), editor {lt[0]} LUFS (peak {lt[1]})")

    tl = load_json(BUILD / "timeline.json")
    blocks = [(b["id"], b.get("t0", sc["t0"]), b.get("t1", sc["t1"]), " ".join(t["text"] for l in b["lines"] for t in l["tokens"]))
              for sc in tl["screens"] for b in sc["blocks"]]          # a block window (hook, CTA) or its screen
    scores, keep = [], {}
    probes = {int(round((max(t0, min(t1 - 0.1, min(tok["t"] for sc in tl["screens"] for bb in sc["blocks"]
                                                    if bb["id"] == bid for l in bb["lines"] for tok in l["tokens"]) + 0.6))) * FPS))
              for bid, t0, t1, _ in blocks}
    worst = []                                    # the 6 most different frames, kept while streaming
    for i, (fa, fb) in enumerate(zip(frames(a.ours), frames(a.theirs))):
        s = psnr(fa, fb)
        scores.append(s)
        if i in probes:
            keep[i] = (fa.copy(), fb.copy())
        if len(worst) < 6 or s < max(w[0] for w in worst):
            worst.append((s, i))
            keep[i] = (fa.copy(), fb.copy())
            if len(worst) > 6:
                drop = max(worst)
                worst.remove(drop)
                if drop[1] not in probes:
                    keep.pop(drop[1], None)
    scores = np.array(scores)
    worst = [i for _, i in worst]
    print(f"compared {len(scores)} frames: median PSNR {np.median(scores):.1f} dB, min {scores.min():.1f} dB at frame "
          f"{int(scores.argmin())} ({scores.argmin() / FPS:.2f}s)")
    bad = scores < a.threshold
    runs, i = [], 0
    while i < len(bad):
        if bad[i]:
            j = i
            while j + 1 < len(bad) and bad[j + 1]:
                j += 1
            runs.append((i, j))
            i = j + 1
        else:
            i += 1
    for f0, f1 in runs:
        t0, t1 = f0 / FPS, (f1 + 1) / FPS
        on = [f"{bid} '{txt[:24]}'" for bid, b0, b1, txt in blocks if b0 < t1 and t0 < b1]
        print(f"  differs {t0:6.2f}-{t1:6.2f}s  min PSNR {scores[f0:f1 + 1].min():5.1f}  | on screen: {', '.join(on) or '-'}")
    # sheet: worst frames + one probe per block
    want = sorted(set(worst) | set(keep))
    rows = []
    for i in want:
        fa, fb = keep[i]
        diff = np.clip(np.abs(fa.astype(np.int16) - fb.astype(np.int16)) * 4, 0, 255).astype(np.uint8)
        row = np.hstack([cv2.resize(x, (360, 640), interpolation=cv2.INTER_AREA) for x in (fa, fb, diff)])
        cv2.putText(row, f"{i / FPS:.2f}s psnr {scores[i]:.1f}", (8, 628), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        rows.append(row)
    for k in range(0, len(rows), 6):
        sheet = np.vstack(rows[k:k + 6])
        p = out / f"compare_{k // 6}.jpg"
        cv2.imwrite(str(p), sheet, [cv2.IMWRITE_JPEG_QUALITY, 85])
        print(p)


if __name__ == "__main__":
    main()
