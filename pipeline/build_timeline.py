"""Script (human-authored, per video) -> timeline.json (renderer input) + camera.json.

Line markup:
  *text*      accent run (pink italic serif) - the punch/fail words; may contain spaces/brackets
  _text_      emphasis run (WHITE italic serif) - the dream/setup words
  //          pink grotesk ornament
  №3          pink serif label "( №3 )" (pops in)
  a line may be a string or {"text", "align": "right"|"left", "indent": em, "dy": em,
                             "scale": k, "anim": "pop"|"type"|"none", "color": accent colour of this line,
                             "literal": true, "t": out_time}   (literal = not spoken, e.g. a hook title)
All times in the script (camera, audio, doodles, literal lines) are OUTPUT times (after the edl).
Every spoken word in the lines must match the HEARD transcript in output order (punctuation/case ignored;
see edl.VoiceMap for voice-overs and mutes); its reveal time is the word's start time.
"""
import json
import re
import sys
from pathlib import Path

import cv2
import numpy as np
from playwright.sync_api import sync_playwright

import camera as cam
from edl import EDL, VoiceMap
from common import FPS, H, PIPE, ROOT, W, load_json, save_json

Q = 4  # masks are quarter resolution


def norm(w):
    return re.sub(r"[^\w\-ʼ'’]", "", w.lower()).strip("-")


def tokenize(text, literal=False):
    toks = []
    for part in re.split(r"(\*[^*]*\*|_[^_]*_)", text):
        if not part:
            continue
        kind = "main"
        if part.startswith("*") and part.endswith("*") and len(part) > 1:
            kind, part = "accent", part[1:-1]
        elif part.startswith("_") and part.endswith("_") and len(part) > 1:
            kind, part = "accent-white", part[1:-1]
        for w in part.split():
            if w == "//":
                toks.append({"text": "//", "kind": "deco"})
            elif re.fullmatch(r"№\d+", w):
                toks.append({"text": f"( {w} )", "kind": "label", "anim": "pop"})
            elif literal:
                toks.append({"text": w, "kind": kind})
            else:
                toks.append({"text": w, "kind": kind, "word": norm(w)})
    return toks


def assign_times(screens, words):
    """Align script words to transcript words with a character-level diff, so spelling fixes,
    split words ("Ніну" -> "Ні, ну") and merged words ("будь" "-який" -> "будь-який") still get
    the right time. Each script word takes the start time of the transcript word its first
    aligned character falls into."""
    from difflib import SequenceMatcher
    T, t_owner = "", []
    for k, w in enumerate(words):
        n = norm(w["w"])
        T += n
        t_owner += [k] * len(n)
    toks = [tok for sc in screens for blk in sc["blocks"] for ln in blk["lines"] for tok in ln["tokens"] if "word" in tok]
    S, s_start = "", []
    for tok in toks:
        s_start.append(len(S))
        S += tok["word"]
    cmap = [None] * len(S)
    for m in SequenceMatcher(None, S, T, autojunk=False).get_matching_blocks():
        for j in range(m.size):
            cmap[m.a + j] = m.b + j
    warn = []
    for i, tok in enumerate(toks):
        a0, a1 = s_start[i], s_start[i] + len(tok["word"])
        hits = [cmap[c] for c in range(a0, a1) if cmap[c] is not None]
        if hits:
            tok["t"] = words[t_owner[hits[0]]]["s"]
            if len(hits) < len(tok["word"]):
                warn.append(f"'{tok['text']}' ~ '{words[t_owner[hits[0]]]['w'].strip()}'")
        else:
            tok["t"] = None
            warn.append(f"'{tok['text']}' NOT FOUND in transcript")
    # unmatched words: interpolate between neighbours
    for i, tok in enumerate(toks):
        if tok["t"] is None:
            prev = next((toks[j]["t"] for j in range(i - 1, -1, -1) if toks[j]["t"] is not None), 0.0)
            nxt = next((toks[j]["t"] for j in range(i + 1, len(toks)) if toks[j]["t"] is not None), prev + 0.3)
            tok["t"] = (prev + nxt) / 2
    for i in range(1, len(toks)):                      # keep reading order monotonic
        toks[i]["t"] = max(toks[i]["t"], toks[i - 1]["t"])
    used = {t_owner[c] for c in cmap if c is not None}
    missing = [w["w"].strip() for k, w in enumerate(words) if k not in used]
    if warn:
        print("fuzzy word matches:", ", ".join(warn))
    if missing:
        print("WARNING transcript words not shown:", missing)


def build_screens(script, words, takes):
    screens = []
    for sc in script["screens"]:
        blocks = sc.get("blocks") or [{"lines": sc["lines"]}]
        out_blocks = []
        for bi, b in enumerate(blocks):
            lines = []
            for ln in b["lines"]:
                spec = {"text": ln} if isinstance(ln, str) else dict(ln)
                spec["tokens"] = tokenize(spec.pop("text"), spec.get("literal", False))
                if spec.get("literal"):
                    for tok in spec["tokens"]:
                        tok["t"] = spec["t"]
                for key in ("anim", "scale", "color"):
                    if key in spec:
                        for tok in spec["tokens"]:
                            tok[key] = spec[key]
                lines.append(spec)
            ob = {k: v for k, v in b.items() if k != "lines"}
            ob["lines"] = lines
            out_blocks.append(ob)
        screens.append({"take": sc["take"], "blocks": out_blocks, "place": sc.get("place", {}),
                        **{k: sc[k] for k in ("fade", "t0_override", "t1_override") if k in sc}})
    assign_times(screens, words)
    # screen windows
    for i, sc in enumerate(screens):
        t_take0, t_take1 = takes[sc["take"] - 1]
        first = min(tok["t"] for b in sc["blocks"] for l in b["lines"] for tok in l["tokens"] if "t" in tok)
        prev_same = i > 0 and screens[i - 1]["take"] == sc["take"]
        sc["t0"] = sc.get("t0_override", first if prev_same else t_take0)
        nxt = screens[i + 1] if i + 1 < len(screens) else None
        sc["t1"] = t_take1
        if nxt and nxt["take"] == sc["take"] and "t0_override" not in nxt:
            sc["t1"] = min(tok["t"] for b in nxt["blocks"] for l in b["lines"] for tok in l["tokens"] if "t" in tok)
        sc["t1"] = sc.get("t1_override", sc["t1"])
        late = [tok["text"] for b in sc["blocks"] for l in b["lines"] for tok in l["tokens"]
                if "word" in tok and not sc["t0"] - 1e-6 <= tok["t"] < sc["t1"]]
        if late:              # e.g. a voice-over that runs past the take's picture: extend with t1_override
            print(f"WARNING screen {i + 1} (take {sc['take']}, {sc['t0']:.2f}-{sc['t1']:.2f}s) never shows: {late}")
        # ornaments/labels take the time of the next word in the block (labels: screen start)
        for b in sc["blocks"]:
            flat = [tok for l in b["lines"] for tok in l["tokens"]]
            for j, tok in enumerate(flat):
                if "t" not in tok:
                    if tok["kind"] == "label":
                        tok["t"] = sc["t0"]
                    else:
                        nxt_t = next((x["t"] for x in flat[j + 1:] if "t" in x), sc["t0"])
                        tok["t"] = nxt_t
    return screens


# ----------------------------------------------------------------------------- layout

def row_fill(m):
    """Fill each row between its leftmost and rightmost set pixel (kills holes in the legs)."""
    out = np.zeros_like(m)
    rows = np.where(m.any(axis=1))[0]
    for r in rows:
        xs = np.where(m[r])[0]
        out[r, xs[0]:xs[-1] + 1] = 1
    return out


def occupancy(masks, camframes, f0, f1):
    occ = np.zeros((H // Q, W // Q), np.uint8)
    S = np.diag([1 / Q, 1 / Q, 1.0])
    Si = np.diag([Q, Q, 1.0])
    thr = 127 if masks.max() > 1 else 0
    for f in range(max(0, f0), min(len(camframes), f1 + 1)):
        m = row_fill((masks[camframes[f]["src_f"]] > thr).astype(np.uint8))
        M = np.vstack([cam.matrix(camframes[f]), [0, 0, 1]])
        Mq = (S @ M @ Si)[:2]
        mw = cv2.warpAffine(m, Mq, (W // Q, H // Q), flags=cv2.INTER_NEAREST)
        occ |= mw
    return occ


def person_box(masks, camframes, f):
    m = masks[camframes[min(f, len(camframes) - 1)]["src_f"]]
    ys, xs = np.nonzero(m > (127 if m.max() > 1 else 0))
    if len(xs) == 0:
        return None
    pts = np.stack([xs * Q, ys * Q, np.ones_like(xs)], 0).astype(np.float64)
    M = cam.matrix(camframes[f])
    sp = M @ pts
    return sp[0].min(), sp[1].min(), sp[0].max(), sp[1].max()


def solve_block(occ, bw, bh, style, face, pbox, place):
    L = style["layout"]
    margin = place.get("margin", L["margin"])
    occ = occ.copy()
    k = max(1, int(round(margin / Q)))
    occ = cv2.dilate(occ, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * k + 1, 2 * k + 1)))
    # static exclusions + safe area; a block's own safe box never reaches past the global one (the phone crop)
    gx0, gy0, gx1, gy1 = L["safe"]
    x0s, y0s, x1s, y1s = place.get("safe", L["safe"])
    x0s, y0s, x1s, y1s = max(x0s, gx0), max(y0s, gy0), min(x1s, gx1), min(y1s, gy1)
    block = np.ones_like(occ)
    block[y0s // Q:y1s // Q, x0s // Q:x1s // Q] = 0
    for ex in L["exclude"] + place.get("exclude", []):
        block[ex[1] // Q:ex[3] // Q, ex[0] // Q:ex[2] // Q] = 1
    occ = np.maximum(occ, block)
    qw, qh = int(np.ceil(bw / Q)), int(np.ceil(bh / Q))
    Hq, Wq = occ.shape
    ys = np.arange(0, Hq - qh)
    xs = np.arange(0, Wq - qw)
    Y, X = np.meshgrid(ys, xs, indexing="ij")

    def window_sum(m):
        ii = np.pad(m.astype(np.int32), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
        return ii[Y + qh, X + qw] - ii[Y, X + qw] - ii[Y + qh, X] + ii[Y, X]
    cnt = window_sum(occ)
    out = window_sum(block)          # cells outside the safe area or inside an exclusion
    # preferences (screen px)
    px, py = X * Q, Y * Q
    fx, fy, fw, fh = face
    y_pref = place.get("y", fy + fh * 0.95)
    gap = place.get("gap", L["gap"])
    side = place.get("side", L["prefer_side"])
    if pbox is not None:
        left_target = pbox[0] - gap - bw          # block right edge just left of her
        right_target = pbox[2] + gap
    else:
        left_target, right_target = 80, W - 80 - bw
    cost_left = np.abs(px - left_target) * 0.8
    cost_right = np.abs(px - right_target) * 0.8 + (0 if side == "right" else 160)
    if side == "left":
        cost_x = np.minimum(cost_left, cost_right)
    elif side == "right":
        cost_x = np.minimum(cost_right - 160, cost_left + 160)
    else:
        cost_x = np.minimum(cost_left, cost_right)
    if "x" in place:
        cost_x = np.abs(px - place["x"]) * 1.0
    cost = np.abs(py - y_pref) * 1.0 + cost_x
    snap = place.get("left_snap", L.get("left_snap", 0))       # keep a stable left column
    if snap and "x" not in place:
        cost = cost + snap * np.abs(px - L["safe"][0])
    feasible = cnt == 0
    if feasible.any():
        c = np.where(feasible, cost, np.inf)
        warn = None
    else:
        # no free spot: overlap the person rather than leave the safe area (text past it is cropped on phones)
        c = cost + cnt * 400.0
        if (out == 0).any():
            c = np.where(out == 0, c, np.inf)
        warn = f"no free spot; min overlap {cnt[np.isfinite(c)].min()} q-px"
    j = np.unravel_index(np.argmin(c), c.shape)
    return int(px[j]), int(py[j]), warn


def measure(timeline):
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome")
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto((PIPE / "overlay.html").as_uri())
        pg.evaluate("tl => init(tl)", timeline)
        res = pg.evaluate("measure()")
        b.close()
    return res


def main(script_path):
    script_path = Path(script_path)
    script = load_json(script_path)
    style = load_json(PIPE / "style_default.json")
    for k, v in script.get("style", {}).items():
        style[k] = {**style[k], **v} if isinstance(v, dict) and isinstance(style.get(k), dict) else v
    src_dur = script.get("src_duration", script.get("duration"))
    edl = EDL(script.get("edl"), src_dur)
    n_src = int(round(src_dur * FPS))
    duration = edl.duration
    n_frames = int(round(duration * FPS))
    voice = VoiceMap(edl, script.get("audio"))
    for w in voice.warnings:
        print("WARNING", w)
    words = []
    for seg in load_json(ROOT / script["words"])["segments"]:
        for w in seg["words"]:
            t = voice.word_time(w)
            if t is not None:          # only words that are heard can be shown (voice-overs may reorder them)
                words.append({**w, "s_src": w["s"], "s": round(t, 4)})
    words.sort(key=lambda w: w["s"])
    # on the frame grid, like the picture (EDL.src_frame): float sums of segment lengths would put a take's first
    # frame into the previous take
    takes = [[round(edl.out_time(a) * FPS) / FPS, round(edl.out_time(b) * FPS) / FPS] for a, b in script["takes"]]
    takes[0][0], takes[-1][1] = 0.0, duration
    screens = build_screens(script, words, takes)
    track = load_json(ROOT / script["track"])
    cam_spec = {**script.get("camera", {}), "src_takes": script["takes"]}
    clips_json = ROOT / Path(script.get("source", "")).parent / "clips.json"
    if str(script.get("source", "")).endswith(".ffconcat") and clips_json.exists():   # transition handles stay in their clip
        cam_spec["clips"] = [[round(c["offset"] * FPS), round(c["offset"] * FPS) + c["n_frames"]]
                             for c in load_json(clips_json)["clips"]]
    camera = cam.build(cam_spec, takes, n_frames, track, edl, n_src)
    build_dir = ROOT / "build"
    save_json(camera, build_dir / "camera.json")
    save_json({"duration": duration, "n_frames": n_frames, "src_duration": src_dur, "edl": edl.segs,
               "takes": takes, "words": [{"w": w["w"], "s": w["s"]} for w in words]}, build_dir / "meta.json")

    # pass 1: measure blocks at origin
    ids = 0
    for sc in screens:
        for b in sc["blocks"]:
            b["id"] = f"b{ids}"; ids += 1
            b["x"], b["y"] = 0, 0
    timeline = {"style": style, "screens": screens, "doodles": script.get("doodles", []), "duration": duration}
    sizes = {m["id"]: m["bbox"] for m in measure(timeline)}

    masks = np.load(ROOT / script["masks"])
    face = cam.face_track(track)
    report = []
    for sc in screens:
        placed = []
        for b in sc["blocks"]:
            bb = sizes[b["id"]]
            toks = [tok for l in b["lines"] for tok in l["tokens"]]
            t_first = min(tok["t"] for tok in toks)
            t_last = max(tok["t"] for tok in toks)
            t_end = min(sc["t1"], b.get("until", sc["t1"]))
            behind = b.get("behind", sc.get("behind", style["layout"].get("behind", True)))
            b["behind"] = behind
            place = {**sc.get("place", {}), **b.get("place", {})}
            # text-behind-subject: she may walk in front of the block once it has been read
            t_free = min(t_end, t_last + style["layout"].get("read_time", 0.9)) if behind else t_end
            t_free = place.get("free_until", t_free)
            f0, f1 = int(t_first * FPS), int(np.ceil(t_free * FPS)) - 1
            occ = occupancy(masks, camera["frames"], f0, f1)
            for (x, y, w, h, pa, pb) in placed:          # other blocks visible at the same time
                if pa < t_end and t_first < pb:
                    occ[max(0, y // Q - 2):(y + h) // Q + 3, max(0, x // Q - 2):(x + w) // Q + 3] = 1
            fr = camera["frames"][min(f0, n_frames - 1)]
            fx, fy = face(edl.src_time(t_first))
            M = cam.matrix(fr)
            sfx, sfy = M @ np.array([fx, fy, 1.0])
            fs = 80 * fr["s"]
            boxes = [person_box(masks, camera["frames"], f) for f in range(f0, max(f0 + 1, min(f1, f0 + 24)), 3)]
            boxes = [bx for bx in boxes if bx is not None]
            pbox = (min(bx[0] for bx in boxes), min(bx[1] for bx in boxes),
                    max(bx[2] for bx in boxes), max(bx[3] for bx in boxes)) if boxes else None
            x, y, warn = solve_block(occ, bb["w"], bb["h"], style, (sfx - fs / 2, sfy - fs / 2, fs, fs), pbox, place)
            placed.append((x, y, int(bb["w"]), int(bb["h"]), t_first, t_end))
            b["x"] = x - bb["x"]
            b["y"] = y - bb["y"]
            text = " / ".join(" ".join(t["text"] for t in l["tokens"]) for l in b["lines"])
            sx0, sy0, sx1, sy1 = style["layout"]["safe"]
            if x < sx0 - Q or y < sy0 - Q or x + bb["w"] > sx1 + Q or y + bb["h"] > sy1 + Q:   # Q: solver grid
                warn = (warn + "; " if warn else "") + "OUTSIDE the IG crop-safe area, shorten the lines"
            report.append(f"{sc['t0']:6.2f}-{sc['t1']:6.2f} {b['id']} at ({x},{y}) {int(bb['w'])}x{int(bb['h'])}"
                          f"{'  !! ' + warn if warn else ''}  | {text}")
    occl = sorted({f for sc in screens if any(b.get("behind") for b in sc["blocks"])
                   for f in range(int(sc["t0"] * FPS), int(np.ceil(sc["t1"] * FPS)))})
    timeline["occlude_frames"] = occl
    save_json(timeline, build_dir / "timeline.json")
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(report))


if __name__ == "__main__":
    main(sys.argv[1])
