"""Video pass: decode source, apply per-frame camera (zoom / pan / shake / zoom-blur
transitions), per-take white-balance gains, a light grade, composite the subtitle overlay
PNGs (with text-behind-subject matte), the inserts and brand layers (layers.py, outside the matte), and encode.

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
import layers
from common import BUILD, FPS, H, W, load_json

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

    def __init__(self, src):
        self.src = src
        self.proc, self.next_f, self.last, self.last_f = None, None, None, None

    def _start(self, f):
        if self.proc:
            self.proc.kill()
        self.proc = subprocess.Popen(
            ["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{max(0, (f - 0.5) / FPS):.4f}", "-i", str(self.src),
             "-vf", "scale=in_color_matrix=bt709:in_range=tv", "-fps_mode", "passthrough",
             "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
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


PARAMS = ("s", "cx", "cy", "rot", "dx", "dy")


def layers_of(fr):
    """The shots visible in an output frame: one, or two during a push transition (outgoing first)."""
    return fr.get("layers") or [fr]


def _lerp_layer(a, b, t):
    return {**a, **{k: a[k] + (b[k] - a[k]) * t for k in PARAMS}}


def _motion_end(cam, i, layer):
    """The same shot's camera one frame later (or extrapolated from one frame earlier at a cut), for motion blur."""
    def match(fr):
        return next((l for l in layers_of(fr) if l.get("take") == layer.get("take")
                     and abs(l["src_f"] - layer["src_f"]) <= 2), None)
    if i + 1 < len(cam):
        nxt = match(cam[i + 1])
        if nxt:
            return nxt
    if i > 0:
        prv = match(cam[i - 1])
        if prv:
            return {**layer, **{k: 2 * layer[k] - prv[k] for k in PARAMS}}
    return None


def _corner_shift(m0, m1):
    c = np.array([[0, 0, 1], [W, 0, 1], [0, H, 1], [W, H, 1]], np.float64).T
    return float(np.abs(m0 @ c - m1 @ c).max())


def picture(cam, i, sources, shutter_default=0.0):
    """Camera-moved picture for output frame i (before grade and overlay). Fast camera moves are motion-blurred
    by averaging sub-frame camera positions over the shutter (in frames); two shots are composited during a push."""
    fr = cam[i]
    layers = layers_of(fr)
    imgs = []
    for k, layer in enumerate(layers):
        img = sources[min(k, len(sources) - 1)].get(layer["src_f"]).copy()
        g = layer.get("gain")
        if g and g != [1, 1, 1]:
            img = cv2.multiply(img, (float(g[0]), float(g[1]), float(g[2]), 0.0))
        imgs.append(img)
    shutter = fr.get("shutter", shutter_default)
    ends = [_motion_end(cam, i, l) if shutter > 0 else None for l in layers]
    shift = max([_corner_shift(camera_matrix(l), camera_matrix(_lerp_layer(l, e, shutter)))
                 for l, e in zip(layers, ends) if e] or [0.0])
    n_sub = min(24, int(np.ceil(shift / 4))) if shift > 1.5 else 1
    if n_sub == 1 and len(layers) == 1 and fr.get("blur", 0) > 0.002:
        return zoom_blur(imgs[0], camera_matrix(fr), fr["blur"])
    acc = np.zeros((H, W, 3), np.float32)
    for j in range(n_sub):
        tau = shutter * (j + 0.5) / n_sub if n_sub > 1 else 0.0
        ms = [camera_matrix(_lerp_layer(l, e, tau) if e else l) for l, e in zip(layers, ends)]
        if len(layers) == 1:
            out = warp(imgs[0], ms[0])
        else:                       # incoming shot underneath, outgoing on top where it covers the screen
            out = warp(imgs[1], ms[1]).astype(np.float32)
            top = cv2.warpAffine(imgs[0], ms[0], (W, H), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT)
            cover = cv2.warpAffine(np.ones((H, W), np.float32), ms[0], (W, H), flags=cv2.INTER_LINEAR,
                                   borderMode=cv2.BORDER_CONSTANT)[..., None]
            out = top.astype(np.float32) * cover + out * (1 - cover)
        acc += out
    return np.clip(acc / n_sub + 0.5, 0, 255).astype(np.uint8)


def render_frame(cam, i, sources, gr, overlay_dir, occl, masks, shutter_default=0.0, slots=None):
    """Output frame i, bottom to top: the picture (camera, white balance, grade) or a full-screen insert, the flash,
    the "under" layers, the subtitle PNG (cut by her matte on occl frames), the "front" text, the "over" layers.
    slots {name: function} holds the layers the reel has: "full" (i) -> a full-screen picture or None (never
    graded); "under", "front" and "over" (img, i, fr) -> img."""
    slots = slots or {}
    fr = cam[i]
    m = camera_matrix(fr)
    img = slots["full"](i) if "full" in slots else None
    if img is None:
        img = gr(picture(cam, i, sources, shutter_default))
    if fr.get("flash", 0) > 0:
        img = cv2.addWeighted(img, 1 - fr["flash"], np.full_like(img, 255), fr["flash"], 0)
    if "under" in slots:
        img = slots["under"](img, i, fr)
    if overlay_dir:
        p = Path(overlay_dir) / f"{i:05d}.png"
        if p.exists():
            bgra = cv2.imread(str(p), cv2.IMREAD_UNCHANGED)
            if fr.get("ovm"):                      # text rides with its shot through a transition
                bgra = cv2.warpAffine(bgra, np.float32(fr["ovm"]), (W, H), flags=cv2.INTER_LINEAR,
                                      borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            a = bgra[:, :, 3].astype(np.float32) / 255.0
            if a.max() > 0:
                if i in occl and masks is not None:
                    a *= 1 - person_alpha(masks, fr.get("src_f", i), m)
                img = cv2.blendLinear(img, np.ascontiguousarray(bgra[:, :, :3]), 1 - a, a)
    for k in ("front", "over"):
        if k in slots:
            img = slots[k](img, i, fr)
    return img


def segment(a, b, cam, out_path, overlay_dir, timeline_path, masks_path, grade, src, shutter=0.0):
    gr = Grade(grade)
    tl = load_json(timeline_path) if timeline_path else {}
    occl, masks = set(), None
    if timeline_path and masks_path:
        occl = set(tl.get("occlude_frames", []))
        masks = np.load(masks_path, mmap_mode="r")
    slots = {}                      # render_frame's layers, filled from the timeline
    front = set(tl.get("front_frames", []))
    if front and overlay_dir:
        def front_slot(img, i, fr):
            """The behind:false text over her (overlay/front/NNNNN.png): the overlay's warp, no matte."""
            if i not in front:      # the timeline lists the front frames; a stale PNG is never read
                return img
            path = Path(overlay_dir) / "front" / f"{i:05d}.png"
            bgra = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            if bgra is None:
                raise SystemExit(f"front layer {path} is missing: rerun the overlay step")
            if fr.get("ovm"):
                bgra = cv2.warpAffine(bgra, np.float32(fr["ovm"]), (W, H), flags=cv2.INTER_LINEAR,
                                      borderMode=cv2.BORDER_CONSTANT, borderValue=0)
            a = bgra[:, :, 3].astype(np.float32) / 255.0
            if a.max() > 0:
                img = cv2.blendLinear(img, np.ascontiguousarray(bgra[:, :, :3]), 1 - a, a)
            return img
        slots["front"] = front_slot
    comp = layers.Compositor(tl.get("layers", []))       # inserts and brand layers (one per process: it holds decoders)
    if comp.fulls:
        slots["full"] = comp.full
    if comp.by_z["under"]:          # brand "under" layers, then the card insert, which rides the text's transition
        slots["under"] = lambda img, i, fr: comp.composite(img, i, "under", fr.get("ovm"))
    if comp.by_z["over"]:
        slots["over"] = lambda img, i, fr: comp.composite(img, i, "over")
    sources = [FrameSource(src), FrameSource(src)]      # the second one feeds the incoming shot of a push
    enc = subprocess.Popen(
        ["ffmpeg", "-nostdin", "-v", "error", "-y",
         "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-vf", "scale=out_color_matrix=bt709:out_range=tv,format=yuv420p",
         "-c:v", "libx264", "-preset", PRESET, "-crf", CRF, "-profile:v", "high",
         "-x264-params", "keyint=60:min-keyint=30",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", str(out_path)],
        stdin=subprocess.PIPE)
    for i in range(a, b):
        img = render_frame(cam, i, sources, gr, overlay_dir, occl, masks, shutter, slots)
        enc.stdin.write(img.tobytes())
    enc.stdin.close()
    enc.wait()
    for s_ in sources:
        s_.close()
    comp.close()
    if enc.returncode:
        raise SystemExit(f"encoder failed for segment {a}-{b}")


def main(camera_path, overlay_dir, out_path, grade_vf, audio_path, duration, timeline_path=None, masks_path=None,
         grade=None, procs=4, src=None):
    camj = load_json(camera_path)
    cam, shutter = camj["frames"], camj.get("motion_blur", 0.0)
    n = len(cam)
    tmp = Path(tempfile.mkdtemp(prefix="vp_", dir=BUILD))
    bounds = [round(n * k / procs) for k in range(procs + 1)]
    segs = [tmp / f"seg{k}.mp4" for k in range(procs)]
    ps = [Process(target=segment, args=(bounds[k], bounds[k + 1], cam, segs[k], overlay_dir,
                                        timeline_path, masks_path, grade, src, shutter)) for k in range(procs)]
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
    ap.add_argument("--src", required=True, help="source video (e.g. build/<reel>/source.ffconcat)")
    a = ap.parse_args()
    sys.exit(main(a.camera, a.overlay, a.out, "", a.audio or None, a.duration,
                  a.timeline or None, a.masks or None, src=a.src))
