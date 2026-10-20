"""Virtual camera: per-frame scale / centre / shake / zoom-blur / colour gains.

Spec (script["camera"]):
  push:     {"from": 1.0, "to": 1.04}                 slow push-in over every take; optional "ease": "inout" (default,
            over the whole take) | "linear" (constant-velocity creep from the first frame) | "expo" (snap to "to" over
            "dur" s, e.g. the landing after a zoom-through), "creep" (scale per second after "dur")
  cut_in:   {"scale": 1.08, "dur": 0.22, "blur": 0.06} incoming take starts zoomed and settles
  punches:  [{"t": 14.95, "scale": 1.12, "in": 0.10, "until": 16.53, "out": 0.0, "target": "face"|[x,y],
              "ease": "expo"|"in"|"inout"}]          expo snaps in; "in" accelerates to ride a gesture
            "anchor": true keeps the target where it is on screen (the head does not slide to the centre)
  shakes:   [{"t": 14.95, "dur": 0.4, "amp": 12, "rot": 0.6, "freq": 17}]
  gains:    {"1": [b, g, r], ...}                       per-take white-balance gains (1-based take index)
  transitions: at a cut between takes ("at" = output time of the cut; frames before / after the cut are "out" / "in")
    {"type": "push", "at": 3.6, "dir": "right", "out": 5, "in": 5, "roll": 3, "ease_in": "cubic"|"expo"}
        swipe on a sideways gesture: both shots slide one frame width toward dir (the hand's direction), the
        outgoing one runs on past its out point, text slides with its shot; "roll" degrees tilt it like a camera turn.
        Speeds must match at the cut: out-cubic in == out frames, or "ease_in": "expo" with in ~= 2.3 x out (4 / 9)
    {"type": "zoom_through", "at": 7.5, "target": [x, y], "scale": 2.0, "land": 1.35, "out": 10, "in": 7}
        rush into the target (source px, e.g. motion.json to_lens "at") from the gesture's start, cut at the peak,
        the next shot lands from a zoom; scale grows evenly in log space. "land": 1.0 = no pull-out landing (continue
        into the close-up with that take's push_takes "ease": "expo" instead)
    {"type": "spin", "at": 8.17, "dir": "cw", "deg": 30, "zoom": 1.3, "out": 6, "in": 6}   camera roll through the cut
    optional "shutter": motion-blur exposure in frames (default 0.75 for transitions); "dur" = out + in in seconds
  push_takes: {"3": {"from": 1.15, "to": 1.17, "target": "face"}}   per-take framing (same keys as push); target
        "face" keeps the face on the upper third, [x, y] (source px) drifts there as the scale allows (A/B framing on
        jump cuts: 1.0 vs 1.15-1.2)
  motion_blur: 0.5                                             shutter (in frames) for any fast camera move; 0 = off
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


def framing(pk, dt, dur):
    """Scale of a take's own framing dt seconds into it (see push in the module docstring)."""
    d = pk.get("dur") or dur
    u = clamp(dt / max(1e-6, d))
    ease = pk.get("ease", "inout")
    e = u if ease == "linear" else ease_out_expo(u) if ease == "expo" else ease_in_out_cubic(u)
    return lerp(pk["from"], pk["to"], e) * (1 + pk.get("creep", 0.0) * max(0.0, dt - d))


def take_of(t, takes):
    """Take containing t; outside every take (e.g. a hold after a take) the take that started last before t,
    so a held frame keeps that take's settled zoom instead of getting the next take's cut-in."""
    for i, (a, b) in enumerate(takes):
        if a - 1e-6 <= t < b:
            return i
    before = [i for i, (a, b) in enumerate(takes) if a <= t]
    return max(before, key=lambda i: takes[i][0]) if before else 0


def build(spec, takes, n_frames, track, edl=None, n_src=None):
    """takes are in OUTPUT time; track is indexed by SOURCE time (mapped through edl)."""
    face_src = face_track(track)
    n_src = n_src or n_frames
    push = spec.get("push", {"from": 1.0, "to": 1.0})
    cut_in = spec.get("cut_in")
    eased_in = {int(round(tr["at"] * FPS)) for tr in spec.get("transitions", [])}   # their transition lands them
    frames = []
    for i in range(n_frames):
        t = i / FPS
        # spans in whole frames: times rounded to 4 decimals can end a hair after a frame starts (a punch held "until"
        # a cut would leak onto the next shot's first frame)
        within = lambda a, b: round(a * FPS) <= i < round(b * FPS)
        src_f = edl.src_frame(i, n_src) if edl else min(i, n_src - 1)
        for fz in spec.get("freezes", []):           # video-only freeze, audio keeps running
            if within(fz["t0"], fz["t1"]):
                src_f = edl.src_frame(int(round(fz["t0"] * FPS)), n_src) if edl else int(round(fz["t0"] * FPS))
        face = lambda tt: face_src((edl.src_time(tt) if edl else tt))
        k = take_of(t, takes)
        t0, t1 = takes[k]
        pk = spec.get("push_takes", {}).get(str(k + 1), push)
        s = framing(pk, t - t0, t1 - t0)
        cx, cy = W / 2, H / 2
        if pk.get("target") == "face" and s > 1:        # face on the upper third of the tighter frame
            fx, fy = face_src(edl.src_time(t) if edl else t)
            cx, cy = fx, fy + (H / 2 - H / 3) / s
        elif isinstance(pk.get("target"), (list, tuple)):   # clamped below: drifts onto it as the scale grows
            cx, cy = pk["target"]
        blur = 0.0
        if cut_in and k > 0 and int(round(t0 * FPS)) not in eased_in:
            p = clamp((t - t0) / cut_in["dur"])
            extra = (cut_in["scale"] - 1) * (1 - ease_out_expo(p))
            s *= 1 + extra
            blur = max(blur, cut_in.get("blur", 0) * (1 - ease_out_cubic(p)))
        for pu in spec.get("punches", []):
            if within(pu["t"], pu["until"]):
                p = clamp((t - pu["t"]) / max(1e-3, pu["in"]))
                ease = pu.get("ease", "expo")       # expo = snap in; in = accelerate (ride a gesture); else in-out
                amt = ease_out_expo(p) if ease == "expo" else _ease_in(p) if ease == "in" else ease_in_out_cubic(p)
                if pu.get("out") and t > pu["until"] - pu["out"]:
                    amt *= ease_in_out_cubic(clamp((pu["until"] - t) / pu["out"]))
                kz = 1 + (pu["scale"] - 1) * amt
                s *= kz
                tgt = pu.get("target", "face")
                tx, ty = face(pu["t"]) if tgt == "face" else tgt
                if pu.get("target_offset"):
                    ty += pu["target_offset"]
                if pu.get("anchor"):                   # the target keeps its screen position: c' = a - (a - c) / k
                    cx, cy = tx - (tx - cx) / kz, ty - (ty - cy) / kz
                else:
                    cx, cy = lerp(cx, tx, amt), lerp(cy, ty, amt)
                blur = max(blur, pu.get("blur", 0) * (1 - ease_out_cubic(p)))
        dx = dy = rot = 0.0
        for sh in spec.get("shakes", []):
            if within(sh["t"], sh["t"] + sh["dur"]):
                q = (t - sh["t"]) / sh["dur"]
                env = (1 - q) ** 2
                w = 2 * math.pi * sh.get("freq", 15)
                dx += sh["amp"] * env * math.sin(w * (t - sh["t"]))
                dy += sh["amp"] * 0.7 * env * math.sin(w * 1.37 * (t - sh["t"]) + 1.3)
                rot += sh.get("rot", 0) * env * math.sin(w * 0.83 * (t - sh["t"]) + 0.4)
                s *= 1 + (abs(sh["amp"]) * 2.2 / W) * env    # cover the borders
        if rot:      # zoom in just enough that a rolled frame has no empty corners (portrait: height dominates)
            r = math.radians(abs(rot))
            s *= math.cos(r) + (H / W) * math.sin(r)
        flash = 0.0
        for fl in spec.get("flashes", []):
            if within(fl["t"], fl["t"] + fl["dur"]):
                flash = max(flash, fl.get("amount", 0.85) * (1 - (t - fl["t"]) / fl["dur"]) ** 2)
        hw, hh = W / (2 * s), H / (2 * s)
        cx = clamp(cx, hw, W - hw)
        cy = clamp(cy, hh, H - hh)
        # white balance follows the SOURCE take of the frame actually shown
        g = spec.get("gains", {}).get(str(take_of_src(src_f / FPS, spec) + 1), [1, 1, 1])             if spec.get("src_takes") else spec.get("gains", {}).get(str(k + 1), [1, 1, 1])
        frames.append({"t": round(t, 4), "take": k + 1, "src_f": src_f, "s": s, "cx": cx, "cy": cy, "rot": rot,
                       "dx": dx, "dy": dy, "blur": blur, "flash": flash, "gain": g})
    apply_transitions(frames, spec, n_src)
    return {"frames": frames, "motion_blur": spec.get("motion_blur", 0.5)}


LAYER_KEYS = ("take", "src_f", "s", "cx", "cy", "rot", "dx", "dy", "gain")


def _ease_in(q):
    return clamp(q) ** 3


def apply_transitions(frames, spec, n_src):
    """Rewrite the frames around each cut that has a transition (see the module docstring)."""
    clips = spec.get("clips")                 # [[f0, f1), ...] source clip frame ranges, for handles
    n = len(frames)

    def handle(src_f, delta):
        """Source frame `delta` frames away, kept inside the clip (no frames from a neighbouring clip)."""
        lo, hi = 0, n_src - 1
        for f0, f1 in clips or []:
            if f0 <= src_f < f1:
                lo, hi = f0, f1 - 1
        return int(min(hi, max(lo, src_f + delta)))

    for k_tr, tr in enumerate(spec.get("transitions", [])):
        fa = int(round(tr["at"] * FPS))
        half = max(1, int(round(tr.get("dur", 0.4) * FPS / 2)))
        h_out, h_in = int(tr.get("out", half)), int(tr.get("in", half))
        if not (h_out <= fa <= n - h_in):
            raise ValueError(f"transition at {tr['at']}s does not fit inside the reel")
        shutter = tr.get("shutter", 0.75)
        kind = tr["type"]
        if kind == "push":
            vx, vy = {"left": (-1, 0), "right": (1, 0), "up": (0, -1), "down": (0, 1)}[tr.get("dir", "left")]
            span = W if vx else H
            out_last, in_first = dict(frames[fa - 1]), dict(frames[fa])
            roll = tr.get("roll", 0.0) * (-1 if vx > 0 or vy > 0 else 1)      # lean into the move
            land = ease_out_expo if tr.get("ease_in") == "expo" else ease_out_cubic
            for i in range(fa - h_out, fa + h_in):
                # accelerate to the cut (u = 0.5 there), then decelerate: fastest exactly on the cut
                u = 0.5 * _ease_in((i - (fa - h_out) + 1) / h_out) if i < fa else \
                    0.5 + 0.5 * land((i - fa + 1) / h_in)
                if i < fa:
                    lo, li = dict(frames[i]), dict(in_first)
                    li["src_f"] = handle(in_first["src_f"], i - fa)
                else:
                    lo, li = dict(out_last), dict(frames[i])
                    lo["src_f"] = handle(out_last["src_f"], i - fa + 1)
                off_out = (vx * u * span, vy * u * span)
                off_in = (vx * (u - 1) * span, vy * (u - 1) * span)
                tilt = roll * math.sin(math.pi * u)               # 0 at both ends, full at the cut
                for layer, (ox, oy) in ((lo, off_out), (li, off_in)):
                    layer["dx"] += ox
                    layer["dy"] += oy
                    layer["rot"] += tilt
                    if tilt:
                        r = math.radians(abs(tilt))
                        layer["s"] *= math.cos(r) + (H / W) * math.sin(r)
                own, ov = (lo, off_out) if i < fa else (li, off_in)
                frames[i] = {**frames[i], **{k: own[k] for k in LAYER_KEYS}, "blur": 0.0, "shutter": shutter,
                             "layers": [{k: lo[k] for k in LAYER_KEYS}, {k: li[k] for k in LAYER_KEYS}],
                             "ovm": [[1, 0, round(ov[0], 2)], [0, 1, round(ov[1], 2)]], "tr": k_tr}
        elif kind in ("spin", "zoom_through"):
            sign = 1 if tr.get("dir", "cw") == "cw" else -1
            tx, ty = tr.get("target", (W / 2, H / 2))
            for i in range(fa - h_out, fa + h_in):
                fr = frames[i]
                base = np.vstack([matrix(fr), [0, 0, 1]])
                if i < fa:                                     # outgoing: accelerate into the move
                    e = _ease_in((i - (fa - h_out) + 1) / h_out)
                    if kind == "spin":
                        fr["rot"] -= sign * tr.get("deg", 30) * e        # cv2 angles are counter-clockwise
                        fr["s"] *= 1 + (tr.get("zoom", 1.3) - 1) * e
                    else:                                      # even growth per frame: log space
                        fr["s"] *= math.exp(math.log(tr.get("scale", 2.0)) * e)
                        fr["cx"], fr["cy"] = lerp(fr["cx"], tx, min(1.0, 3 * e)), lerp(fr["cy"], ty, min(1.0, 3 * e))
                else:                                          # incoming: decelerate out of it
                    e = 1 - ease_out_cubic((i - fa + 1) / h_in)
                    if kind == "spin":
                        fr["rot"] += sign * tr.get("deg", 30) * e
                        fr["s"] *= 1 + (tr.get("zoom", 1.3) - 1) * e
                    else:
                        fr["s"] *= math.exp(math.log(tr.get("land", 1.35)) * e)
                hw, hh = W / (2 * fr["s"]), H / (2 * fr["s"])
                fr["cx"], fr["cy"] = clamp(fr["cx"], hw, W - hw), clamp(fr["cy"], hh, H - hh)
                fr["blur"], fr["shutter"], fr["tr"] = 0.0, shutter, k_tr
                # the text on screen moves with the picture: the extra camera move relative to the shot's own
                fr["ovm"] = np.round((np.vstack([matrix(fr), [0, 0, 1]]) @ np.linalg.inv(base))[:2], 5).tolist()
        else:
            raise ValueError(f"unknown transition type {kind}")


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
