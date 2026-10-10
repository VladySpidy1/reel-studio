"""Video pass: decode source, apply per-frame camera (zoom / pan / shake / zoom-blur
transitions), per-take white-balance gains, a light grade, composite the subtitle overlay
PNGs (with text-behind-subject matte), and encode.

Frames are processed in parallel segments (each with its own decoder/encoder), then
concatenated losslessly and muxed with the audio mix.

camera.json: {"frames": [{"s", "cx", "cy", "rot", "dx", "dy", "blur", "flash", "gain": [b, g, r]}]}
"""
import os
import subprocess
import sys
import tempfile
from multiprocessing import Process
from pathlib import Path

import cv2
import numpy as np

import camera
from common import BUILD, FPS, H, SRC, W, load_json

PRESET = os.environ.get("X264_PRESET", "slow")
CRF = os.environ.get("X264_CRF", "14")


def camera_matrix(fr):
    return camera.matrix(fr)


def warp(img, m, interp=cv2.INTER_CUBIC):
    return cv2.warpAffine(img, m, (W, H), flags=interp, borderMode=cv2.BORDER_REFLECT101)


def zoom_blur(img, m, amount, taps=7):
    """Radial zoom blur around screen centre: average of progressively scaled warps."""
    acc = np.zeros((H, W, 3), np.float32)
    for i in range(taps):
        k = 1 + amount * i / (taps - 1)
        z = cv2.getRotationMatrix2D((W / 2, H / 2), 0, k)
        mm = np.vstack([z, [0, 0, 1]]) @ np.vstack([m, [0, 0, 1]])
        cv2.accumulate(warp(img, mm[:2], cv2.INTER_LINEAR), acc)
    return (acc / taps).astype(np.uint8)


class Grade:
    """Light filmic grade on the plate (before subtitles): lift, contrast S-curve, saturation,
    vignette. Params: {"lift", "contrast", "saturation", "vignette", "gamma"}"""

    def __init__(self, p):
        self.p = p or {}
        v = np.arange(256, dtype=np.float32) / 255
        lift = self.p.get("lift", 0.0)
        v = lift + (1 - lift) * v
        v = v ** (1 / self.p.get("gamma", 1.0))
        c = self.p.get("contrast", 1.0)
        v = v - (c - 1) * np.sin(2 * np.pi * v) / (2 * np.pi)   # slope c at mid-grey, ends fixed
        self.lut = np.clip(np.round(v * 255), 0, 255).astype(np.uint8)
        s = self.p.get("saturation", 1.0)
        luma = np.array([0.0722, 0.7152, 0.2126], np.float32)     # BGR
        self.sat = (s * np.eye(3) + (1 - s) * np.tile(luma, (3, 1))).astype(np.float32)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r2 = ((xx - W / 2) / (W * 0.62)) ** 2 + ((yy - H / 2) / (H * 0.62)) ** 2
        vig = 1 - self.p.get("vignette", 0.0) * np.clip(r2, 0, 1.6)
        self.vig = cv2.merge([np.round(vig * 255).astype(np.uint8)] * 3)

    def __call__(self, img):
        if not self.p:
            return img
        x = cv2.LUT(img, self.lut)
        if self.p.get("saturation", 1.0) != 1.0:
            x = cv2.transform(x, self.sat)
        if self.p.get("vignette", 0.0):
            x = cv2.multiply(x, self.vig, scale=1 / 255)
        return x


def person_alpha(masks, f, m):
    """Screen-space soft person matte (H, W) float32 0..1 for text-behind-subject (f = source frame)."""
    lo, hi = max(0, f - 1), min(len(masks) - 1, f + 1)
    q = masks[lo:hi + 1].max(axis=0).astype(np.uint8)   # cover motion blur: union of neighbours
    soft = q.max() > 1                      # RVM alpha (0..255) vs binary differencing mask (0/1)
    if soft:
        q = cv2.dilate(q, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
    if not soft:
        q = cv2.morphologyEx(q * 255, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    full = cv2.resize(q, (W, H), interpolation=cv2.INTER_CUBIC if soft else cv2.INTER_LINEAR)
    full = cv2.warpAffine(full, m, (W, H), flags=cv2.INTER_LINEAR, borderValue=0)
    full = cv2.GaussianBlur(full, (0, 0), 1.2 if soft else 2.2)
    return full.astype(np.float32) / 255.0


class FrameSource:
    """Source frames by index; sequential reads are streamed, jumps (holds/EDL cuts) re-seek."""

    def __init__(self):
        self.proc, self.next_f, self.last, self.last_f = None, None, None, None

    def _start(self, f):
        if self.proc:
            self.proc.kill()
        self.proc = subprocess.Popen(
            ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{max(0, (f - 0.5) / FPS):.4f}", "-i", str(SRC),
             "-vf", "scale=in_color_matrix=bt709:in_range=tv", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
            stdout=subprocess.PIPE, bufsize=W * H * 3 * 2)
        self.next_f = f

    def _read(self):
        buf = self.proc.stdout.read(W * H * 3)
        self.next_f += 1
        if len(buf) == W * H * 3:
            self.last = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
        return self.last

    def get(self, f):
        if f == self.last_f and self.last is not None:
            return self.last
        if self.proc is None or not (0 <= f - self.next_f < 8):
            self._start(f)
        while self.next_f < f:
            self._read()
        img = self._read()
        self.last_f = f
        return img

    def close(self):
        if self.proc:
            self.proc.kill()


def render_frame(src, i, fr, gr, overlay_dir, occl, masks):
    g = fr.get("gain")
    if g and g != [1, 1, 1]:
        src = cv2.multiply(src, (float(g[0]), float(g[1]), float(g[2]), 0.0))
    m = camera_matrix(fr)
    img = zoom_blur(src, m, fr["blur"]) if fr.get("blur", 0) > 0.002 else warp(src, m)
    img = gr(img)
    if fr.get("flash", 0) > 0:
        img = cv2.addWeighted(img, 1 - fr["flash"], np.full_like(img, 255), fr["flash"], 0)
    if overlay_dir:
        p = Path(overlay_dir) / f"{i:05d}.png"
        if p.exists():
            bgra = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
            a = bgra[:, :, 3].astype(np.float32) / 255.0
            if a.max() > 0:
                if i in occl and masks is not None:
                    a *= 1 - person_alpha(masks, fr.get("src_f", i), m)
                img = cv2.blendLinear(img, np.ascontiguousarray(bgra[:, :, :3]), 1 - a, a)
    return img


def segment(a, b, cam, out_path, overlay_dir, timeline_path, masks_path, grade):
    gr = Grade(grade)
    occl, masks = set(), None
    if timeline_path and masks_path:
        occl = set(load_json(timeline_path).get("occlude_frames", []))
        masks = np.load(masks_path)
    srcs = FrameSource()
    enc = subprocess.Popen(
        ["ffmpeg", "-nostdin", "-v", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
         "-c:v", "libx264", "-preset", PRESET, "-crf", CRF, "-profile:v", "high",
         "-x264-params", "keyint=60:min-keyint=30",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", str(out_path)],
        stdin=subprocess.PIPE)
    for i in range(a, b):
        fr = cam[i]
        src = srcs.get(fr.get("src_f", i))
        img = render_frame(src, i, fr, gr, overlay_dir, occl, masks)
        enc.stdin.write(img.tobytes())
    enc.stdin.close()
    enc.wait()
    srcs.close()
    if enc.returncode:
        raise SystemExit(f"encoder failed for segment {a}-{b}")


def main(camera_path, overlay_dir, out_path, grade_vf, audio_path, duration, timeline_path=None, masks_path=None,
         grade=None, procs=4):
    cam = load_json(camera_path)["frames"]
    n = len(cam)
    tmp = Path(tempfile.mkdtemp(prefix="vp_", dir=BUILD))
    bounds = [round(n * k / procs) for k in range(procs + 1)]
    segs = [tmp / f"seg{k}.mp4" for k in range(procs)]
    ps = [Process(target=segment, args=(bounds[k], bounds[k + 1], cam, segs[k], overlay_dir,
                                        timeline_path, masks_path, grade)) for k in range(procs)]
    for p in ps:
        p.start()
    for p in ps:
        p.join()
    if any(p.exitcode for p in ps):
        return 1
    lst = tmp / "list.txt"
    lst.write_text("".join(f"file '{s.as_posix()}'\n" for s in segs), encoding="utf-8")
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst)]
    if audio_path:
        cmd += ["-i", str(audio_path), "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-b:a", "320k", "-ar", "48000"]
    cmd += ["-c:v", "copy", "-t", f"{duration:.3f}", "-movflags", "+faststart", str(out_path)]
    rc = subprocess.run(cmd).returncode
    if rc == 0:
        for s in segs:
            s.unlink()
        lst.unlink()
        tmp.rmdir()
    return rc


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", default=str(BUILD / "camera.json"))
    ap.add_argument("--overlay", default=str(BUILD / "overlay"))
    ap.add_argument("--out", required=True)
    ap.add_argument("--audio", default="")
    ap.add_argument("--duration", type=float, required=True)
    ap.add_argument("--timeline", default="")
    ap.add_argument("--masks", default="")
    a = ap.parse_args()
    sys.exit(main(a.camera, a.overlay, a.out, "", a.audio or None, a.duration,
                  a.timeline or None, a.masks or None))
