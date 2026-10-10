"""Virtual camera: per-frame scale / centre / shake / zoom-blur / colour gains.

Spec (script["camera"]):
  push:     {"from": 1.0, "to": 1.04}                 slow push-in over every take
  cut_in:   {"scale": 1.08, "dur": 0.22, "blur": 0.06} incoming take starts zoomed and settles
  punches:  [{"t": 14.95, "scale": 1.12, "in": 0.10, "until": 16.53, "out": 0.0, "target": "face"|[x,y]}]
  shakes:   [{"t": 14.95, "dur": 0.4, "amp": 12, "rot": 0.6, "freq": 17}]
  gains:    {"1": [b, g, r], ...}                       per-take white-balance gains (1-based take index)
"""
import json
import math

import numpy as np

from common import FPS, H, W, clamp, ease_in_out_cubic, ease_out_cubic, ease_out_expo, lerp


def face_track(track):
    """t -> face centre (x, y) via linear interpolation over the tracked samples."""
    ts, xs, ys = [], [], []
    for fr in track["frames"]:
        f = fr.get("face")
        if f:
            ts.append(fr["t"]); xs.append(f[0] + f[2] / 2); ys.append(f[1] + f[3] / 2)
    ts, xs, ys = map(np.array, (ts, xs, ys))
    return lambda t: (float(np.interp(t, ts, xs)), float(np.interp(t, ts, ys)))


def take_of(t, takes):
    for i, (a, b) in enumerate(takes):
        if a - 1e-6 <= t < b:
            return i
    return len(takes) - 1


def build(spec, takes, n_frames, track, edl=None, n_src=None):
    """takes are in OUTPUT time; track is indexed by SOURCE time (mapped through edl)."""
    face_src = face_track(track)
    n_src = n_src or n_frames
    push = spec.get("push", {"from": 1.0, "to": 1.0})
    cut_in = spec.get("cut_in")
    frames = []
    for i in range(n_frames):
        t = i / FPS
        src_f = edl.src_frame(i, n_src) if edl else min(i, n_src - 1)
        for fz in spec.get("freezes", []):           # video-only freeze, audio keeps running
            if fz["t0"] <= t < fz["t1"]:
                src_f = edl.src_frame(int(round(fz["t0"] * FPS)), n_src) if edl else int(round(fz["t0"] * FPS))
        face = lambda tt: face_src((edl.src_time(tt) if edl else tt))
        k = take_of(t, takes)
        t0, t1 = takes[k]
        u = clamp((t - t0) / max(1e-6, t1 - t0))
        pk = spec.get("push_takes", {}).get(str(k + 1), push)
        s = lerp(pk["from"], pk["to"], ease_in_out_cubic(u))
        cx, cy = W / 2, H / 2
        blur = 0.0
        if cut_in and k > 0:
            p = clamp((t - t0) / cut_in["dur"])
            extra = (cut_in["scale"] - 1) * (1 - ease_out_expo(p))
            s *= 1 + extra
            blur = max(blur, cut_in.get("blur", 0) * (1 - ease_out_cubic(p)))
        for pu in spec.get("punches", []):
            if pu["t"] <= t < pu["until"]:
                p = clamp((t - pu["t"]) / max(1e-3, pu["in"]))
                amt = ease_out_expo(p) if pu.get("ease", "expo") == "expo" else ease_in_out_cubic(p)
                if pu.get("out") and t > pu["until"] - pu["out"]:
                    amt *= ease_in_out_cubic(clamp((pu["until"] - t) / pu["out"]))
                s *= 1 + (pu["scale"] - 1) * amt
                tgt = pu.get("target", "face")
                tx, ty = face(pu["t"]) if tgt == "face" else tgt
                if pu.get("target_offset"):
                    ty += pu["target_offset"]
                cx, cy = lerp(cx, tx, amt), lerp(cy, ty, amt)
                blur = max(blur, pu.get("blur", 0) * (1 - ease_out_cubic(p)))
        dx = dy = rot = 0.0
        for sh in spec.get("shakes", []):
            if sh["t"] <= t < sh["t"] + sh["dur"]:
                q = (t - sh["t"]) / sh["dur"]
                env = (1 - q) ** 2
                w = 2 * math.pi * sh.get("freq", 15)
                dx += sh["amp"] * env * math.sin(w * (t - sh["t"]))
                dy += sh["amp"] * 0.7 * env * math.sin(w * 1.37 * (t - sh["t"]) + 1.3)
                rot += sh.get("rot", 0) * env * math.sin(w * 0.83 * (t - sh["t"]) + 0.4)
                s *= 1 + (abs(sh["amp"]) * 2.2 / W) * env    # cover the borders
        flash = 0.0
        for fl in spec.get("flashes", []):
            if fl["t"] <= t < fl["t"] + fl["dur"]:
                flash = max(flash, fl.get("amount", 0.85) * (1 - (t - fl["t"]) / fl["dur"]) ** 2)
        hw, hh = W / (2 * s), H / (2 * s)
        cx = clamp(cx, hw, W - hw)
        cy = clamp(cy, hh, H - hh)
        # white balance follows the SOURCE take of the frame actually shown
        g = spec.get("gains", {}).get(str(take_of_src(src_f / FPS, spec) + 1), [1, 1, 1])             if spec.get("src_takes") else spec.get("gains", {}).get(str(k + 1), [1, 1, 1])
        frames.append({"t": round(t, 4), "take": k + 1, "src_f": src_f, "s": s, "cx": cx, "cy": cy, "rot": rot,
                       "dx": dx, "dy": dy, "blur": blur, "flash": flash, "gain": g})
    return {"frames": frames}


def take_of_src(ts, spec):
    return take_of(ts, spec["src_takes"])


def matrix(fr):
    """2x3 affine source->screen, same as video_pass.camera_matrix (no cv2 dependency needed)."""
    s, cx, cy = fr["s"], fr["cx"], fr["cy"]
    a = math.radians(fr.get("rot", 0.0))
    c, si = s * math.cos(a), s * math.sin(a)
    # cv2.getRotationMatrix2D((cx,cy), angle, s): [[c, si, (1-c)cx - si cy], [-si, c, si cx + (1-c) cy]]
    m = np.array([[c, si, (1 - c) * cx - si * cy], [-si, c, si * cx + (1 - c) * cy]], np.float64)
    m[0, 2] += W / 2 - cx + fr.get("dx", 0.0)
    m[1, 2] += H / 2 - cy + fr.get("dy", 0.0)
    return m
