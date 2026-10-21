"""Inserts and brand layers on a frame: Python layers outside the person matte (ADR-0009), so her matte never cuts
them. What shows when is inserts.py; build_timeline writes the layers into timeline.json "layers":

  {id, cat: insert|brand, mode: overlay|full, z: under|over, f0, f1 (exclusive; the exit fade is inside it),
   x, y, w, h (the picture's top-left and size on screen, without pad), sprite, pad, anim, exit,
   rides (rides the text's transition matrix ovm), media, kind: still|video, src_f0, n_media, creep, focus,
   sfx, sfx_gain, label}

- style_sprite(): a picture styled once with cv2 into straight-alpha BGRA plus its pad: card (rounded corners,
  border ring, soft shadow), cutout (1 px outline ring, soft shadow), plain, gradient (a vertical alpha ramp).
  sprite_file() caches it as sprites/<hash>.png.
- state(layer, i): (opacity, scale) on output frame i: the pop in (anim), the exit fade.
- Compositor: full(i), the ungraded picture of a full-screen span; composite(img, i, z, ovm), the layers of one z
  over a frame; rgba(layer, i), a full-frame straight-alpha frame for the editable project.
- cues(layers): the layers' SFX cues, peaking on their first frame ("move": true).
"""
import hashlib
import json
import math

import cv2
import numpy as np

from common import FPS, H, ROOT, W, short

ANIMS = {   # dur in seconds; scale / opacity keys [progress, value], smoothstep between them (overlay.html kf)
    "snap": {"dur": 0.085, "scale": [[0, 0.965], [1, 1.0]], "opacity": [[0, 0], [1, 1]]},
    "pop": {"dur": 0.30, "scale": [[0, 0.85], [0.6, 1.04], [1, 1.0]], "opacity": [[0, 0], [0.25, 1]]}}
LOOK = ("radius", "border_px", "border", "shadow", "outline")      # the style.insert keys a sprite depends on


def kf(keys, p):
    """Keyframe interpolation with smoothstep between keys (overlay.html kf)."""
    if p <= keys[0][0]:
        return keys[0][1]
    for (p0, v0), (p1, v1) in zip(keys, keys[1:]):
        if p <= p1:
            u = (p - p0) / (p1 - p0)
            return v0 + (v1 - v0) * u * u * (3 - 2 * u)
    return keys[-1][1]


def state(layer, i):
    """(opacity, scale) of a layer on output frame i. The pop-in progress is p = (i - f0 + 1) / (FPS * dur), so the
    first frame already shows (snap: 0.34, 0.977) and the layer is at rest from p >= 1; the exit fade runs over
    the last `exit` seconds before f1. Full-screen layers switch with a hard cut."""
    f0, f1 = layer["f0"], layer["f1"]
    if not f0 <= i < f1:
        return 0.0, 1.0
    if layer.get("mode") == "full":
        return 1.0, 1.0
    op, sc = 1.0, 1.0
    a = layer.get("anim")
    a = ANIMS[a] if isinstance(a, str) else a
    if a and a.get("dur"):
        p = (i - f0 + 1) / (FPS * a["dur"])
        if p < 1:
            op = kf(a["opacity"], p) if "opacity" in a else 1.0
            sc = kf(a["scale"], p) if "scale" in a else 1.0
    ex = layer.get("exit") or 0
    if ex > 0:
        q = (f1 - i) / (FPS * ex)
        if q < 1:
            op *= kf([[0, 0], [1, 1]], q)
    return op, sc


# ----------------------------------------------------------------------------- sprites

def _bgr(hexcol):
    h = hexcol.lstrip("#")
    return np.array([int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16)], np.float32)


def _split(img):
    """float32 straight BGR (0..255) and alpha (0..1) of a BGR or BGRA uint8 picture."""
    rgb = img[..., :3].astype(np.float32)
    a = img[..., 3].astype(np.float32) / 255 if img.shape[2] == 4 else np.ones(img.shape[:2], np.float32)
    return rgb, a


def _rounded(w, h, r, ss=4):
    """Alpha 0..1 of a w x h rounded rectangle, drawn at ss x and area-downscaled (smooth corners)."""
    R = int(round(min(r, w / 2, h / 2) * ss))
    m = np.zeros((h * ss, w * ss), np.uint8)
    cv2.rectangle(m, (R, 0), (w * ss - R - 1, h * ss - 1), 255, -1)
    cv2.rectangle(m, (0, R), (w * ss - 1, h * ss - R - 1), 255, -1)
    for cx, cy in ((R, R), (w * ss - R - 1, R), (R, h * ss - R - 1), (w * ss - R - 1, h * ss - R - 1)):
        cv2.circle(m, (cx, cy), R, 255, -1)
    return cv2.resize(m, (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255


def pad_of(kind, style):
    """The transparent margin around a sprite's picture: room for the shadow (3 sigma below, dy down) and the ring."""
    if kind not in ("card", "cutout"):
        return 0
    sh = style["shadow"]
    return int(sh["dy"] + math.ceil(1.5 * sh["blur"]) + 1)


def _finish(C, A, shadow):
    """Premultiplied colour C and alpha A on the padded canvas, plus a black shadow of A (offset dy, blurred with
    sigma blur/2, times alpha) under it -> straight-alpha BGRA uint8."""
    dy = int(shadow["dy"])
    sh = np.zeros_like(A)
    sh[dy:] = A[:A.shape[0] - dy] if dy else A
    if shadow["blur"] > 0:
        sh = cv2.GaussianBlur(sh, (0, 0), shadow["blur"] / 2)
    sh *= shadow["alpha"]
    out_a = A + sh * (1 - A)
    rgb = C / np.maximum(out_a, 1e-6)[..., None]
    return np.clip(np.dstack([rgb, out_a * 255]) + 0.5, 0, 255).astype(np.uint8)


def style_sprite(img, kind, style):
    """(straight-alpha BGRA uint8, pad): img (BGR or BGRA uint8, already at its on-screen size) styled once; the
    picture's top-left sits at (pad, pad) and its interior keeps the exact source pixels.
    card: rounded corners (radius), a border_px ring in `border` (transparent parts of the picture show white),
    `shadow` {dy, blur, alpha}; cutout: a 1 px ring in `outline` just outside the alpha edge plus the shadow;
    plain: the picture as it is; gradient (img None, style = the layer {y0, y1, color, opacity}): full width,
    alpha rising from 0 at y0 to opacity at y1."""
    if kind == "gradient":
        n = int(style["y1"] - style["y0"])
        a = np.linspace(0, style.get("opacity", 1.0), n, dtype=np.float32)[:, None].repeat(W, 1)
        rgb = np.broadcast_to(_bgr(style.get("color", "#000000")), (n, W, 3))
        return np.clip(np.dstack([rgb, a * 255]) + 0.5, 0, 255).astype(np.uint8), 0
    rgb, a = _split(img)
    h, w = a.shape
    pad = pad_of(kind, style)
    if kind == "plain":
        return np.clip(np.dstack([rgb, a * 255]) + 0.5, 0, 255).astype(np.uint8), 0
    if kind == "card":
        rgb = rgb * a[..., None] + 255 * (1 - a[..., None])
        a = _rounded(w, h, style["radius"])
        b = int(style.get("border_px", 0))
        if b > 0:
            inner = cv2.erode((a > 0.5).astype(np.uint8), np.ones((2 * b + 1, 2 * b + 1), np.uint8),
                              borderType=cv2.BORDER_CONSTANT, borderValue=0).astype(np.float32)
            ring = np.clip(a - inner, 0, 1)[..., None]
            rgb = rgb * (1 - ring) + _bgr(style["border"]) * ring
    elif kind != "cutout":
        raise ValueError(f"sprite kind {kind!r}: card, cutout, plain or gradient")
    A = np.zeros((h + 2 * pad, w + 2 * pad), np.float32)
    A[pad:pad + h, pad:pad + w] = a
    C = np.zeros(A.shape + (3,), np.float32)
    C[pad:pad + h, pad:pad + w] = rgb * a[..., None]
    if kind == "cutout":
        ring = np.clip(cv2.dilate(A, cv2.getStructuringElement(cv2.MORPH_CROSS, (3, 3))) - A, 0, 1)
        C += _bgr(style["outline"]) * ring[..., None]
        A += ring
    return _finish(C, A, style["shadow"]), pad


def _resize(bgra, w, h):
    """BGRA resized in premultiplied alpha (no dark fringes): area when shrinking, cubic when enlarging."""
    rgb, a = _split(bgra)
    interp = cv2.INTER_AREA if w <= bgra.shape[1] else cv2.INTER_CUBIC
    prem = cv2.resize(rgb * a[..., None], (w, h), interpolation=interp)
    a = np.clip(cv2.resize(a, (w, h), interpolation=interp), 0, 1)
    rgb = prem / np.maximum(a, 1e-6)[..., None]
    return np.clip(np.dstack([rgb, a * 255]) + 0.5, 0, 255).astype(np.uint8)


def sprite_file(png, kind, style, w, h, crop, out_dir):
    """(repo-relative path, pad) of the styled sprite of a prepared picture (inserts.prepare's PNG), cropped to crop
    (fractions of the picture, or None) and scaled to w x h: out_dir/<hash>.png, made once."""
    key = json.dumps([short(png), kind, {k: style.get(k) for k in LOOK}, w, h, crop], sort_keys=True)
    path = out_dir / f"{hashlib.sha1(key.encode()).hexdigest()[:16]}.png"
    if not path.is_file():
        img = cv2.imread(str(ROOT / png), cv2.IMREAD_UNCHANGED)
        if img.ndim == 2 or img.shape[2] == 3:
            img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGRA if img.ndim == 2 else cv2.COLOR_BGR2BGRA)
        if crop:
            ih, iw = img.shape[:2]
            x0, y0, x1, y1 = (int(round(c * n)) for c, n in zip(crop, (iw, ih, iw, ih)))
            img = img[y0:y1, x0:x1]
        sp, _ = style_sprite(_resize(img, w, h), kind, style)
        out_dir.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(path), sp)
    return short(path), pad_of(kind, style)


# ----------------------------------------------------------------------------- frames

def _blend(img, prem, a, x, y, op):
    """img (uint8 BGR, changed in place) under premultiplied colour prem and alpha a placed at (x, y), times op."""
    h, w = a.shape
    x0, y0, x1, y1 = max(0, x), max(0, y), min(img.shape[1], x + w), min(img.shape[0], y + h)
    if x0 >= x1 or y0 >= y1:
        return
    sa = a[y0 - y:y1 - y, x0 - x:x1 - x, None] * op
    sp = prem[y0 - y:y1 - y, x0 - x:x1 - x] * op
    roi = img[y0:y1, x0:x1].astype(np.float32)
    img[y0:y1, x0:x1] = np.clip(roi * (1 - sa) + sp + 0.5, 0, 255).astype(np.uint8)


class Compositor:
    """The layers of one render process (each process builds its own: it holds decoders)."""

    def __init__(self, layers):
        self.fulls = [l for l in layers if l.get("mode") == "full"]
        # z "under": brand layers first, then the card insert; "over": brand layers above the text
        self.by_z = {z: sorted((l for l in layers if l.get("mode") != "full" and l.get("z", "under") == z),
                               key=lambda l: l.get("cat") != "brand") for z in ("under", "over")}
        self._sprites, self._stills, self._videos = {}, {}, {}

    def _sprite(self, layer):
        """(premultiplied BGR float32, alpha float32) of a layer's sprite, loaded once."""
        p = layer["sprite"]
        if p not in self._sprites:
            bgra = cv2.imread(str(ROOT / p), cv2.IMREAD_UNCHANGED)
            rgb, a = _split(bgra)
            self._sprites[p] = (rgb * a[..., None], a)
        return self._sprites[p]

    def _matrix(self, layer, sc, ovm):
        """Sprite px -> screen: placed at (x - pad, y - pad), scaled by sc about the picture's centre, then ovm."""
        pad = layer["pad"]
        cx, cy = layer["x"] + layer["w"] / 2, layer["y"] + layer["h"] / 2
        M = np.array([[sc, 0, cx + sc * (layer["x"] - pad - cx)], [0, sc, cy + sc * (layer["y"] - pad - cy)],
                      [0, 0, 1]], np.float64)
        if ovm is not None:
            M = np.vstack([np.asarray(ovm, np.float64), [0, 0, 1]]) @ M
        return M[:2]

    def _placed(self, layer, sc, ovm):
        """The layer's (premultiplied colour, alpha, x, y) for one frame: the sprite itself at rest, else warped
        (premultiplied, so edges do not darken) into the on-screen box it lands in (not a full frame: 8 GB RAM)."""
        prem, a = self._sprite(layer)
        if sc == 1 and ovm is None:
            return prem, a, int(round(layer["x"])) - layer["pad"], int(round(layer["y"])) - layer["pad"]
        M = self._matrix(layer, sc, ovm)
        h, w = a.shape
        c = M @ np.array([[0, w, 0, w], [0, 0, h, h], [1, 1, 1, 1]], np.float64)
        x0, y0 = max(0, int(np.floor(c[0].min())) - 1), max(0, int(np.floor(c[1].min())) - 1)
        x1, y1 = min(W, int(np.ceil(c[0].max())) + 2), min(H, int(np.ceil(c[1].max())) + 2)
        if x1 <= x0 or y1 <= y0:
            return prem[:0, :0], a[:0, :0], 0, 0
        T = M - [[0, 0, x0], [0, 0, y0]]
        kw = dict(flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
        return cv2.warpAffine(prem, T, (x1 - x0, y1 - y0), **kw), cv2.warpAffine(a, T, (x1 - x0, y1 - y0), **kw), x0, y0

    def _still(self, layer):
        """A full-screen picture cover-cropped once to 1080x1920 about focus (transparent parts on black)."""
        if layer["id"] not in self._stills:
            rgb, a = _split(cv2.imread(str(ROOT / layer["media"]), cv2.IMREAD_UNCHANGED))
            rgb = rgb * a[..., None]
            ih, iw = a.shape
            s = max(W / iw, H / ih)
            sw, sh = max(W, int(round(iw * s))), max(H, int(round(ih * s)))
            img = cv2.resize(rgb, (sw, sh), interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
            fx, fy = layer.get("focus") or (0.5, 0.5)
            x0, y0 = int(round((sw - W) * fx)), int(round((sh - H) * fy))
            self._stills[layer["id"]] = np.clip(img[y0:y0 + H, x0:x0 + W] + 0.5, 0, 255).astype(np.uint8)
        return self._stills[layer["id"]]

    def full(self, i):
        """The picture of output frame i when a full-screen layer covers it (BGR uint8, never graded), else None.
        A video plays its converted media from src_f0; a still pushes in by `creep` per second about focus."""
        layer = next((l for l in self.fulls if l["f0"] <= i < l["f1"]), None)
        if layer is None:
            return None
        if layer["kind"] == "video":
            if layer["id"] not in self._videos:
                from video_pass import FrameSource          # video_pass imports this module
                self._videos[layer["id"]] = FrameSource(ROOT / layer["media"])
            f = min(layer.get("src_f0", 0) + i - layer["f0"], layer["n_media"] - 1)
            return self._videos[layer["id"]].get(f).copy()
        base = self._still(layer)
        k = 1 + (layer.get("creep") or 0) * (i - layer["f0"]) / FPS
        if k == 1:
            return base.copy()
        fx, fy = layer.get("focus") or (0.5, 0.5)
        return cv2.warpAffine(base, cv2.getRotationMatrix2D((fx * W, fy * H), 0, k), (W, H), flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REFLECT101)

    def composite(self, img, i, z, ovm=None):
        """img with the visible layers of z ("under" or "over") on frame i blended over it. Layers that ride (card
        inserts) follow ovm, the text's transition matrix; brand layers stay screen-locked."""
        if not img.flags.writeable:
            img = img.copy()
        for layer in self.by_z[z]:
            if not layer["f0"] <= i < layer["f1"]:
                continue
            op, sc = state(layer, i)
            if op <= 0:
                continue
            prem, a, x, y = self._placed(layer, sc, ovm if layer.get("rides") else None)
            _blend(img, prem, a, x, y, op)
        return img

    def rgba(self, layer, i):
        """Frame i of one overlay layer as full-frame straight-alpha BGRA uint8 (the export's alpha clip; its
        transition moves are keyframes there, so ovm is not applied)."""
        out = np.zeros((H, W, 4), np.uint8)
        op, sc = state(layer, i)
        if op <= 0:
            return out
        prem, a, x, y = self._placed(layer, sc, None)
        h, w = a.shape
        x0, y0, x1, y1 = max(0, x), max(0, y), min(W, x + w), min(H, y + h)
        if x0 < x1 and y0 < y1:
            sa = a[y0 - y:y1 - y, x0 - x:x1 - x]
            rgb = prem[y0 - y:y1 - y, x0 - x:x1 - x] / np.maximum(sa, 1e-6)[..., None]
            out[y0:y1, x0:x1] = np.clip(np.dstack([rgb, sa * op * 255]) + 0.5, 0, 255).astype(np.uint8)
        return out

    def close(self):
        for src in self._videos.values():
            src.close()


def cues(layers):
    """The layers' sounds as SFX cues: each peaks on the layer's first frame; "move": true (they sound a move,
    so lint's whoosh-on-a-plain-cut rule skips them)."""
    return [{"name": l["sfx"], "peak_at": round(l["f0"] / FPS, 4), "gain_db": l.get("sfx_gain") or 0, "move": True}
            for l in layers if l.get("sfx")]
