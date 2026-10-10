"""Prepare a new source video for the reel pipeline (run once per video).

python prep.py <video> <out_dir> [--lang uk] [--skip-words] [--skip-masks]

Writes to out_dir:
  words.json   faster-whisper large-v3 word timings  {"segments": [{"words": [{"w","s","e","p"}]}]}
  cuts.json    {"fps", "n_frames", "duration", "cuts": [t...], "takes": [[t0, t1], ...]}
  masks.npy    (n, 480, 270) uint8 person alpha 0..255 (Robust Video Matting, quarter res)
  track.json   {"fps", "frames": [{"f","t","person":[x,y,w,h]|null,"face":[x,y,w,h]|null}]}  (1080x1920 px)
  sheet.jpg    1 fps contact sheet for a quick look
"""
import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

W, H, FPS = 1080, 1920, 30


def probe(video):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-count_packets",
                          "-show_entries", "stream=nb_read_packets,r_frame_rate:format=duration",
                          "-of", "json", str(video)], capture_output=True, text=True).stdout
    d = json.loads(out)
    return int(d["streams"][0]["nb_read_packets"]), float(d["format"]["duration"])


def frames(video, w, h, fmt="rgb24"):
    p = subprocess.Popen(["ffmpeg", "-nostdin", "-v", "error", "-i", str(video),
                          "-vf", f"scale={w}:{h}:flags=area", "-f", "rawvideo", "-pix_fmt", fmt, "-"],
                         stdout=subprocess.PIPE)
    ch = 3 if fmt == "rgb24" else 1
    n = w * h * ch
    while True:
        b = p.stdout.read(n)
        if len(b) < n:
            break
        yield np.frombuffer(b, np.uint8).reshape(h, w, ch) if ch == 3 else np.frombuffer(b, np.uint8).reshape(h, w)
    p.wait()


def transcribe(video, out, lang, cuts=()):
    from faster_whisper import WhisperModel
    wav = out / "audio16k.wav"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
                    str(wav)], check=True)
    m = WhisperModel("large-v3", device="cpu", compute_type="int8")
    segs, info = m.transcribe(str(wav), language=lang, word_timestamps=True, beam_size=5)
    res = {"lang": info.language, "segments": []}
    for s in segs:
        res["segments"].append({"start": s.start, "end": s.end, "text": s.text,
                                "words": [{"w": w.word, "s": round(w.start, 3), "e": round(w.end, 3),
                                           "p": round(w.probability, 2)} for w in s.words]})
    snap_onsets(wav, res)
    for seg in res["segments"]:               # a word that is mostly after a cut starts at the cut
        for w in seg["words"]:
            for c in cuts:
                if w["s"] < c < (w["s"] + w["e"]) / 2:
                    w["s"] = round(c, 3)
    (out / "words.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for s in res["segments"]:
        print(f"[{s['start']:6.2f}-{s['end']:6.2f}] {s['text']}")


def snap_onsets(wav, res, hop=0.005):
    """Whisper often starts a word inside the silence before it (e.g. after a dramatic pause).
    Move each start forward to where the voice energy actually rises."""
    import wave
    with wave.open(str(wav)) as wf:
        sr = wf.getframerate()
        x = np.frombuffer(wf.readframes(wf.getnframes()), np.int16).astype(np.float32) / 32768
    win, step = int(sr * 0.02), int(sr * hop)
    n = max(1, (len(x) - win) // step)
    rms = np.array([np.sqrt(np.mean(x[i * step:i * step + win] ** 2) + 1e-12) for i in range(n)])
    db = 20 * np.log10(rms)
    floor = np.percentile(db, 10)
    thr = max(-45.0, floor + 14)
    for seg in res["segments"]:
        for w in seg["words"]:
            i, end = int(w["s"] / hop), int(w["e"] / hop)
            j = i
            while j < min(end - 6, n - 1) and db[j] < thr:
                j += 1
            if i + 4 < j < min(end - 6, n - 1):     # moved >20 ms and the voice really starts inside the word
                w["s_whisper"] = w["s"]
                w["s"] = round(j * hop, 3)


def detect_cuts(video, n, dur):
    prev, diffs = None, []
    for g in frames(video, 64, 114, "gray"):
        g = g.astype(np.float32)
        diffs.append(0.0 if prev is None else float(np.abs(g - prev).mean()))
        prev = g
    d = np.array(diffs)
    med = np.median(d[1:]) + 1e-3
    # a cut = an isolated spike: much larger than the typical motion and ~2x both neighbours
    cuts = [i / FPS for i in range(1, len(d) - 1)
            if d[i] > max(6.0, 6 * med) and d[i] > 2 * d[i - 1] and d[i] > 2 * d[i + 1]]
    edges = [0.0] + cuts + [dur]
    return {"fps": FPS, "n_frames": len(d), "duration": dur, "cuts": [round(c, 4) for c in cuts],
            "takes": [[round(a, 4), round(b, 4)] for a, b in zip(edges[:-1], edges[1:])]}


def matte(video, cuts, n):
    import torch
    model = torch.hub.load("PeterL1n/RobustVideoMatting", "mobilenetv3", trust_repo=True).eval()
    cut_frames = {int(round(c * FPS)) for c in cuts}
    out = np.zeros((n, H // 4, W // 4), np.uint8)
    rec = [None] * 4
    with torch.no_grad():
        for i, f in enumerate(frames(video, W // 2, H // 2)):
            if i >= n:
                break
            if i in cut_frames:
                rec = [None] * 4
            x = torch.from_numpy(f.copy()).permute(2, 0, 1).float().unsqueeze(0) / 255
            _, pha, *rec = model(x, *rec, downsample_ratio=0.5)
            a = (pha[0, 0].numpy() * 255).astype(np.uint8)
            out[i] = cv2.resize(a, (W // 4, H // 4), interpolation=cv2.INTER_AREA)
            if i % 60 == 0:
                print(f"matte {i}/{n}", flush=True)
    return out


def track(video, masks, step=3):
    cascades = [cv2.CascadeClassifier(cv2.data.haarcascades + n) for n in
                ("haarcascade_frontalface_default.xml", "haarcascade_frontalface_alt2.xml")]
    res = []
    for i, f in enumerate(frames(video, W, H, "gray")):
        if i >= len(masks):
            break
        if i % step:
            continue
        m = masks[i] > 127
        rec = {"f": i, "t": round(i / FPS, 4), "person": None, "face": None}
        ys, xs = np.nonzero(m)
        if len(xs) > 50:
            x0, x1, y0, y1 = xs.min() * 4, xs.max() * 4 + 4, ys.min() * 4, ys.max() * 4 + 4
            rec["person"] = [int(x0), int(y0), int(x1 - x0), int(y1 - y0)]
            # head = top part of the mask; search faces there
            top = ys.min()
            rows = m[top:top + 30]
            cols = np.nonzero(rows.any(0))[0]
            hx0, hx1 = cols.min() * 4, cols.max() * 4 + 4
            hw = max(40, hx1 - hx0)
            roi_y0, roi_y1 = int(y0), int(min(H, y0 + hw * 2.2))
            roi_x0, roi_x1 = int(max(0, hx0 - hw * 0.5)), int(min(W, hx1 + hw * 0.5))
            roi = f[roi_y0:roi_y1, roi_x0:roi_x1]
            best = None
            for c in cascades:
                if roi.size == 0:
                    break
                det = c.detectMultiScale(roi, 1.1, 5, minSize=(max(24, hw // 4),) * 2)
                for (fx, fy, fw, fh) in det:
                    if best is None or fw > best[2]:
                        best = [int(fx + roi_x0), int(fy + roi_y0), int(fw), int(fh)]
            if best is None:  # estimate from the head blob
                fw = int(hw * 0.75)
                best = [int((hx0 + hx1) / 2 - fw / 2), int(y0 + hw * 0.35), fw, fw]
            rec["face"] = best
        res.append(rec)
    return {"fps": FPS, "step": step, "frames": res}


def sheet(video, out):
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(video), "-vf",
                    "fps=1,scale=216:384,tile=8x4", "-frames:v", "1", str(out / "sheet.jpg")])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("out")
    ap.add_argument("--lang", default="uk")
    ap.add_argument("--skip-words", action="store_true")
    ap.add_argument("--skip-masks", action="store_true")
    a = ap.parse_args()
    video, out = Path(a.video), Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    n, dur = probe(video)
    print(f"{video.name}: {n} frames, {dur:.3f}s")
    sheet(video, out)
    cuts = detect_cuts(video, n, dur)
    (out / "cuts.json").write_text(json.dumps(cuts, indent=1), encoding="utf-8")
    print("cuts:", cuts["cuts"])
    if not a.skip_words:
        transcribe(video, out, a.lang, cuts["cuts"])
    if not a.skip_masks:
        masks = matte(video, cuts["cuts"], n)
        np.save(out / "masks.npy", masks)
        tr = track(video, masks)
        (out / "track.json").write_text(json.dumps(tr), encoding="utf-8")
    print("done ->", out)


if __name__ == "__main__":
    main()
