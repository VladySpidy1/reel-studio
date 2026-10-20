"""Script (human-authored, per video) -> timeline.json (renderer input) + camera.json.

Line markup:
  *text*      accent run (pink italic serif) - the punch/fail words; may contain spaces/brackets
  _text_      emphasis run (WHITE italic serif) - the dream/setup words
  //          pink grotesk ornament
  №3          pink serif label "( №3 )" (pops in)
  \\* \\_       a literal * or _ (JSON "\\\\*"), e.g. a hand-censored word
  shown{heard} the word shows as `shown` and matches `heard` (a one-off mishear: погано{башко}); in literal lines
              the {...} part is dropped
  a line may be a string or {"text", "align": "right"|"left"|"center", "indent": em, "dy": em,
                             "scale": k, "anim": "pop"|"type"|"none", "color": accent colour of this line,
                             "literal": true, "t": out_time,    (literal = not spoken, e.g. a hook title)
                             "censor": true (censor a literal line), "button": true (a cta-lockup's capsule)}
A block may also have: "preset" (hook, cta, count_up...: merged by resolve.py, the name stays), "align", "stroke"
{"px" <= 4, "color"}, "case" upper|lower, "reveal": "block" (the whole block pops on its first word), "dur" (shown
for this long from its first word), "hold" (at least this long), "tail" (to this long after its last spoken word),
"sfx" {"event"} | {"name", "gain_db"} (peaking on its first word), "template": "cta-lockup" | "count-up" (graphic
templates of overlay.html; count-up animates the number of a literal line, from "count_from", default 0), and
"place": {"x": px | "center", "y", "safe", "avoid": "face", ...}. Terms, censorship and the CTA rules: text_rules.
All times in the script (camera, audio, doodles, literal lines) are OUTPUT times (after the edl).
Every spoken word in the lines must match the HEARD transcript in output order (punctuation/case ignored;
see edl.VoiceMap for voice-overs and mutes); its reveal time is the word's start time.

The text checks land in build/meta.json "checks" (fail, warn, applied); build.py and export_fcpxml.py refuse to
render a slot whose checks FAIL. FAIL: a glyph the brand fonts lack, a block OUTSIDE the IG crop-safe area, on the
IG button rail or TOO BIG for the frame, two visible blocks overlapping, letters of two lines colliding, a hook or
CTA over her face, and (lint.occlusion "fail", the talking-head format) a word hidden by her while it is read.
WARN: no free spot, a word hidden by her while it is read, text that does not stand out from the picture under it.
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

import cv2
import numpy as np
from playwright.sync_api import sync_playwright

import camera as cam
import fontcheck
import resolve
import text_rules
import video_pass
from edl import EDL, VoiceMap
from common import FPS, H, PIPE, ROOT, W, load_json, norm, save_json, source_path

Q = 4  # masks are quarter resolution
ESC = {"\\*": "\ue000", "\\_": "\ue001"}            # escaped markup characters, restored in the display text
UNESC = str.maketrans({"\ue000": "*", "\ue001": "_"})
WORD = re.compile(r"[^\s{]*\{[^}]*\}\S*|\S+")       # a word, or a word with an inline {heard} part
TEXT_W = 8                # weight of another block's text: with no free spot, overlap her rather than text
INK_OVERLAP_PX = 200      # letters of two lines collide: TOSUMI's tight leading interleaves up to ~105 px by design
FACE_MIN_PX = 100         # tracked "faces" narrower than this (source px) are hands or bottles
OCCLUDED_ONE, OCCLUDED_TWO = 0.8, 0.5     # a word this hidden, or two neighbouring words this hidden


def tokenize(text, literal=False):
    for k, v in ESC.items():
        text = text.replace(k, v)
    toks = []
    for part in re.split(r"(\*[^*]*\*|_[^_]*_)", text):
        if not part:
            continue
        kind = "main"
        if part.startswith("*") and part.endswith("*") and len(part) > 1:
            kind, part = "accent", part[1:-1]
        elif part.startswith("_") and part.endswith("_") and len(part) > 1:
            kind, part = "accent-white", part[1:-1]
        for w in WORD.findall(part):
            m = re.fullmatch(r"([^{}]*)\{([^{}]*)\}(\S*)", w)
            shown, heard = (m.group(1) + m.group(3), m.group(2)) if m else (w, None)
            shown = shown.translate(UNESC)
            if w == "//":
                toks.append({"text": "//", "kind": "deco"})
            elif re.fullmatch(r"№\d+", w):
                toks.append({"text": f"(\u2009{w}\u2009)", "kind": "label", "anim": "pop"})   # thin spaces
            elif literal:
                toks.append({"text": shown, "kind": kind})
            else:
                toks.append({"text": shown, "kind": kind, "word": norm(heard if heard is not None else shown)})
    return toks


def assign_times(screens, words, terms=None):
    """Align script words to transcript words with a character-level diff, so spelling fixes,
    split words ("Ніну" -> "Ні, ну") and merged words ("будь" "-який" -> "будь-який") still get
    the right time. Each script word takes the start time of the transcript word its first
    aligned character falls into. Terms (text_rules) are canonicalised on both sides first, so a brand
    word aligns to its mangled transcript ("U -Case" -> yocase). Returns {owner: {id(token): (first word,
    last word)}, not_found: [token], hits: [(first word, last word, display)]}."""
    from difflib import SequenceMatcher
    terms = terms or {}
    T, t_owner, starts = "", [], []
    for k, w in enumerate(words):
        n = norm(w["w"])
        starts.append(len(T))
        T += n
        t_owner += [k] * len(n)
    toks = [tok for sc in screens for blk in sc["blocks"] for ln in blk["lines"] for tok in ln["tokens"] if "word" in tok]
    match = [text_rules.canon_word(tok["word"], terms) if terms else tok["word"] for tok in toks]
    S, s_start = "", []
    for mw in match:
        s_start.append(len(S))
        S += mw
    hits = []
    if terms:
        T, t_owner, hits = text_rules.canon_transcript(T, t_owner, starts, terms, S)
    cmap = [None] * len(S)
    for m in SequenceMatcher(None, S, T, autojunk=False).get_matching_blocks():
        for j in range(m.size):
            cmap[m.a + j] = m.b + j
    warn = []
    owner, not_found = {}, []
    for i, tok in enumerate(toks):
        a0, a1 = s_start[i], s_start[i] + len(match[i])
        hit = [cmap[c] for c in range(a0, a1) if cmap[c] is not None]
        if hit:
            tok["t"] = words[t_owner[hit[0]]]["s"]
            owner[id(tok)] = (t_owner[hit[0]], t_owner[hit[-1]])
            if len(hit) < len(match[i]):
                warn.append(f"'{tok['text']}' ~ '{words[t_owner[hit[0]]]['w'].strip()}'")
        else:
            tok["t"] = None
            not_found.append(tok)
            warn.append(f"'{tok['text']}' NOT FOUND in transcript")
    # unmatched words: interpolate between neighbours
    for i, tok in enumerate(toks):
        if tok["t"] is None:
            prev = next((toks[j]["t"] for j in range(i - 1, -1, -1) if toks[j]["t"] is not None), 0.0)
            nxt = next((toks[j]["t"] for j in range(i + 1, len(toks)) if toks[j]["t"] is not None), prev + 0.3)
            tok["t"] = (prev + nxt) / 2
    for i in range(1, len(toks)):                      # keep reading order monotonic
        toks[i]["t"] = max(toks[i]["t"], toks[i - 1]["t"])
    used = {t_owner[c] for c in cmap if c is not None} | {k for k0, k1, _ in hits for k in range(k0, k1 + 1)}
    missing = [w["w"].strip() for k, w in enumerate(words) if k not in used]
    for k0, k1, d in hits:
        print(f"terms: '{' '.join(words[k]['w'].strip() for k in range(k0, k1 + 1))}' -> {d} [{words[k0]['s']:.2f}]")
    if warn:
        print("fuzzy word matches:", ", ".join(warn))
    if missing:
        print("WARNING transcript words not shown:", missing)
    return {"owner": owner, "not_found": not_found, "hits": hits}


def align_words(script):
    """The heard transcript words as assign_times takes them: "s" is the OUTPUT start rounded to 4 decimals ("s_src"
    keeps the source start), in output order. Prints the voice map's warnings."""
    voice = VoiceMap(EDL(script.get("edl"), script.get("src_duration", script.get("duration"))), script.get("audio"))
    for w in voice.warnings:
        print("WARNING", w)
    words = []
    for seg in load_json(ROOT / script["words"])["segments"]:
        for w in seg["words"]:
            t = voice.word_time(w)
            if t is not None:          # only words that are heard can be shown (voice-overs may reorder them)
                words.append({**w, "s_src": w["s"], "s": round(t, 4)})
    words.sort(key=lambda w: w["s"])
    return words


def count_groups(tokens):
    """A count-up line's digit groups as one token ("10" "000" -> "10\\u00a0000")."""
    out = []
    for tok in tokens:
        if out and re.fullmatch(r"\d{3}\D*", tok["text"]) and re.search(r"\d$", out[-1]["text"]):
            out[-1]["text"] += "\u00a0" + tok["text"]
        else:
            out.append(tok)
    return out


def build_screens(script, words, takes, rules=None):
    """Screens with timed tokens, after the display passes (reveal, terms, censorship, case) and with the block
    windows ("t0"/"t1": blocks with a preset, dur, hold or tail). Returns (screens, info); info: the alignment
    (owner, not_found [(token, block, hard)], hits), the words, the display counts (censored, latin) and the
    automatic SFX cues (sfx)."""
    rules = rules or text_rules.load_rules(script)
    screens = []
    for sc in script["screens"]:
        blocks = sc.get("blocks") or [{"lines": sc["lines"]}]
        out_blocks = []
        for bi, b in enumerate(blocks):
            lines = []
            for ln in b["lines"]:
                spec = {"text": ln} if isinstance(ln, str) else dict(ln)
                spec["tokens"] = tokenize(spec.pop("text"), spec.get("literal", False))
                if b.get("template") == "count-up":
                    spec["tokens"] = count_groups(spec["tokens"])
                if spec.get("literal"):
                    if "t" not in spec:            # e.g. a count_up line: when it shows is the script's choice
                        raise SystemExit(f"literal line «{ln if isinstance(ln, str) else ln['text']}» needs \"t\" "
                                         f"(its output time)")
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
    info = assign_times(screens, words, rules["terms"])
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
    # display passes, block windows, automatic cues
    duration = takes[-1][1]
    stats = {"censored": Counter(), "latin": Counter()}
    lost = {id(t) for t in info["not_found"]}
    info.update(not_found=[], words=words)
    cues = []
    for sc in screens:
        for b in sc["blocks"]:
            toks = [tok for ln in b["lines"] for tok in ln["tokens"]]
            for ln in b["lines"]:
                term_tok = {id(t) for i, j, _ in text_rules.term_runs(ln["tokens"], rules["terms"])
                            for t in ln["tokens"][i:j]}
                for tok in ln["tokens"]:
                    if id(tok) in lost:     # a {heard} word, a term or a preset block's word must align
                        hard = norm(tok["text"]) != tok["word"] or id(tok) in term_tok or bool(text_rules.presets_of(b))
                        info["not_found"].append((tok, b, hard))
            if b.get("reveal") == "block":
                t_pop = min(tok["t"] for tok in toks)
                for tok in toks:
                    tok["t"] = t_pop
            text_rules.display_pass(b, b["lines"], rules, stats)
            if not (text_rules.presets_of(b) or {"dur", "hold", "tail"} & set(b)):
                continue
            t0 = min(tok["t"] for tok in toks)
            limit = [duration] + ([b["until"]] if "until" in b else [])
            if "dur" in b:
                t1 = min(limit + [t0 + b["dur"]])
            else:
                spoken = [tok for tok in toks if id(tok) in info["owner"]]
                longest = [sc["t1"]] + ([t0 + b["hold"]] if "hold" in b else [])
                if "tail" in b and spoken:   # the output end of the word that owns the last spoken character
                    w = words[info["owner"][id(spoken[-1])][1]]
                    longest.append(w["s"] + w["e"] - w["s_src"] + b["tail"])
                t1 = min(limit + [max(longest)])
            b["t0"], b["t1"] = round(t0, 4), round(t1, 4)
            sfx = b.get("sfx")
            if sfx:
                cues.append({**({"event": sfx["event"]} if "event" in sfx else
                                {"name": sfx["name"], "gain_db": sfx.get("gain_db", -18)}), "peak_at": b["t0"]})
    cues = resolve.expand_sfx(cues, script.get("sfx_palette", {})) if cues else []
    own = [c for c in (script.get("audio") or {}).get("sfx", []) if "name" in c]      # a hand-placed cue wins
    info["sfx"] = [c for c in cues if not any(o["name"] == c["name"] and abs(o.get("peak_at", o.get("t", -9))
                                                                             - c["peak_at"]) <= 0.1 for o in own)]
    info.update(censored=dict(stats["censored"]), latin=dict(stats["latin"]))
    return screens, info


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


def matte_q(masks, camframes, f, thr):
    """Her matte on screen at output frame f, quarter resolution (0/1), without occupancy's hole filling."""
    S, Si = np.diag([1 / Q, 1 / Q, 1.0]), np.diag([Q, Q, 1.0])
    M = np.vstack([cam.matrix(camframes[f]), [0, 0, 1]])
    return cv2.warpAffine((masks[camframes[f]["src_f"]] > thr).astype(np.uint8), (S @ M @ Si)[:2], (W // Q, H // Q),
                          flags=cv2.INTER_NEAREST)


def face_boxes(track, camframes, edl, f0, f1, min_px=0):
    """Her face on screen over output frames f0..f1 as (x0, y0, x1, y1): the per-coordinate median of the tracked
    face boxes (track.json, the sample nearest each frame's source time, mapped through that frame's camera). Boxes
    narrower than min_px source px are dropped (prep estimates "faces" on hands and bottles from the top of the
    matte); the median rejects stray big ones. None when no face is seen."""
    ts = np.array([fr["t"] for fr in track["frames"]])
    boxes = []
    for f in range(max(0, f0), min(len(camframes), f1 + 1)):
        face = track["frames"][int(np.argmin(np.abs(ts - edl.src_time(f / FPS))))].get("face")
        if not face or face[2] < min_px:
            continue
        x, y, w, h = face
        sp = cam.matrix(camframes[f]) @ np.array([[x, x + w, x, x + w], [y, y, y + h, y + h], [1, 1, 1, 1]], np.float64)
        boxes.append((sp[0].min(), sp[1].min(), sp[0].max(), sp[1].max()))
    return tuple(float(v) for v in np.median(boxes, axis=0)) if boxes else None


def person_box(masks, camframes, f):
    m = masks[camframes[min(f, len(camframes) - 1)]["src_f"]]
    ys, xs = np.nonzero(m > (127 if m.max() > 1 else 0))
    if len(xs) == 0:
        return None
    pts = np.stack([xs * Q, ys * Q, np.ones_like(xs)], 0).astype(np.float64)
    M = cam.matrix(camframes[f])
    sp = M @ pts
    return sp[0].min(), sp[1].min(), sp[0].max(), sp[1].max()


def solve_block(occ, bw, bh, style, face, pbox, place, text=None):
    """(x, y, warn) of the block's layout box: the cheapest spot clear of occ (her and the other blocks, with
    margins) inside the safe area; with no free spot, the least-covered one ("no free spot"), where a cell of
    another block's text (text) weighs TEXT_W; a block too big for the frame is not solved ("TOO BIG")."""
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
    if qw >= Wq or qh >= Hq:         # no position at all (the grid below would be empty)
        return x0s, y0s, "TOO BIG, split the line"
    ys = np.arange(0, Hq - qh)
    xs = np.arange(0, Wq - qw)
    Y, X = np.meshgrid(ys, xs, indexing="ij")

    def window_sum(m):
        ii = np.pad(m.astype(np.int32), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
        return ii[Y + qh, X + qw] - ii[Y, X + qw] - ii[Y + qh, X] + ii[Y, X]
    cnt = window_sum(occ)
    if text is not None and text.any():
        cnt = cnt + (TEXT_W - 1) * window_sum(text)
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
        warn = "no free spot"
    j = np.unravel_index(np.argmin(c), c.shape)
    return int(px[j]), int(py[j]), warn


def measure(timeline):
    with sync_playwright() as p:
        b = p.chromium.launch()
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.goto((PIPE / "overlay.html").as_uri())
        pg.evaluate("tl => init(tl)", timeline)
        res = pg.evaluate("measure()")
        b.close()
    return res


# ----------------------------------------------------------------------------- readability checks
# The occlusion and contrast rules follow HyperFrames' `check` (Apache-2.0, see NOTICE).

def word_cover(masks, camframes, words, f_end, thr):
    """The share of each word's box (screen px) her matte covers, averaged over the frames from the word's reveal
    to f_end (the end of the block's reading time)."""
    acc, n = np.zeros(len(words)), np.zeros(len(words))
    fw = [int(w["t"] * FPS) for w in words]
    for f in range(max(0, min(fw, default=f_end)), min(len(camframes), f_end)):
        m = matte_q(masks, camframes, f, thr)
        for k, w in enumerate(words):
            if f < fw[k]:
                continue
            x0, y0 = max(0, int(w["x"] // Q)), max(0, int(w["y"] // Q))
            x1, y1 = min(W // Q, int(np.ceil((w["x"] + w["w"]) / Q))), min(H // Q, int(np.ceil((w["y"] + w["h"]) / Q)))
            acc[k] += m[y0:y1, x0:x1].mean() if x1 > x0 and y1 > y0 else 0.0
            n[k] += 1
    return [float(a / c) if c else 0.0 for a, c in zip(acc, n)]


def hidden_words(words, cover):
    """The words a viewer cannot read: one at least 80 % hidden, or two neighbours at least 50 % hidden."""
    bad = {k for k, c in enumerate(cover) if c >= OCCLUDED_ONE}
    bad |= {j for k in range(len(cover) - 1) if cover[k] >= OCCLUDED_TWO and cover[k + 1] >= OCCLUDED_TWO
            for j in (k, k + 1)}
    return sorted(bad)


def hex_rgb(c):
    m = re.fullmatch(r"#?([0-9a-fA-F]{3}|[0-9a-fA-F]{6})", (c or "").strip())
    if not m:
        return None
    h = m.group(1) if len(m.group(1)) == 6 else "".join(ch * 2 for ch in m.group(1))
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def rel_lum(rgb):
    c = [v / 255 for v in rgb]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def wcag(a, b):
    la, lb = rel_lum(a), rel_lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


def compliant(rgb, bg, need=3.0):
    """The text colour moved toward black (on a light background) or white until it reaches `need` against bg."""
    to = (0, 0, 0) if rel_lum(bg) > 0.18 else (255, 255, 255)
    for k in range(1, 21):
        c = tuple(int(round(v + (t - v) * k / 20)) for v, t in zip(rgb, to))
        if wcag(c, bg) >= need:
            return "#%02X%02X%02X" % c, wcag(c, bg)
    return "#%02X%02X%02X" % to, wcag(to, bg)


def contrast_findings(img, words, matte, ring, stroke):
    """Messages for text that does not stand out from the graded picture under it (img, quarter resolution BGR),
    after HyperFrames' check: per text colour, the mean colour under its words (matte, or None: leaves out where
    she covers a behind block) and the WCAG ratio (large text needs 3:1). Light text reads as it is over a dark
    background (luma < 60), needs a ring (the style's shadow, or a stroke) over a mid one and a stroke over a
    light one (luma >= 180: the white-on-beige-wall case); darker text needs 3:1, or a contrasting stroke."""
    out = []
    groups = {}
    for w in words:
        if not w.get("fill") and hex_rgb(w.get("color")):
            groups.setdefault(w["color"], []).append(w)
    for color, ws in groups.items():
        sel = np.zeros(img.shape[:2], bool)
        for w in ws:
            x0, y0 = max(0, int(w["x"] // Q)), max(0, int(w["y"] // Q))
            x1, y1 = min(W // Q, int(np.ceil((w["x"] + w["w"]) / Q))), min(H // Q, int(np.ceil((w["y"] + w["h"]) / Q)))
            sel[y0:y1, x0:x1] = True
        if matte is not None:
            sel &= matte == 0
        if sel.sum() < 8:
            continue
        b, g, r = img[sel].reshape(-1, 3).mean(axis=0)
        bg = (int(round(r)), int(round(g)), int(round(b)))
        luma = 0.2126 * r + 0.7152 * g + 0.0722 * b
        fg = hex_rgb(color)
        ratio = wcag(fg, bg)
        light = rel_lum(fg) >= 0.4
        sk = hex_rgb((stroke or {}).get("color", "#171717")) if stroke else None
        if light:
            bad = (luma >= 180 and not stroke) or (60 <= luma < 180 and ratio < 3.0 and not ring)
        else:
            bad = ratio < 3.0 and not (sk and wcag(fg, sk) >= 3.0)
        if not bad:
            continue
        alt, alt_ratio = compliant(fg, bg)
        what = " ".join(w["text"] for w in ws)
        out.append(f"contrast: «{what[:30]}{'…' if len(what) > 30 else ''}» {color.upper()} over luma {luma:.0f} "
                   f"({ratio:.1f}:1, needs 3:1): add \"stroke\": {{\"px\": 3, \"color\": "
                   f"\"{'#171717' if light else '#FFFFFF'}\"}}, a {'darker' if light else 'lighter'} spot, or {alt} "
                   f"({alt_ratio:.1f}:1)")
    return out


def main(script_path, script=None):
    """script: the resolved script (build.py resolves it once); default: resolve script_path here."""
    script_path = Path(script_path)
    (ROOT / "build" / "meta.json").unlink(missing_ok=True)      # the slot stamp is written last: a crash leaves none
    if script is None:
        script = resolve.load_script(script_path, check_fonts=True)
    style = script["style"]
    rules = text_rules.load_rules(script)
    src_dur = script.get("src_duration", script.get("duration"))
    edl = EDL(script.get("edl"), src_dur)
    n_src = int(round(src_dur * FPS))
    duration = edl.duration
    n_frames = int(round(duration * FPS))
    words = align_words(script)
    # on the frame grid, like the picture (EDL.src_frame): float sums of segment lengths would put a take's first
    # frame into the previous take
    takes = [[round(edl.out_time(a) * FPS) / FPS, round(edl.out_time(b) * FPS) / FPS] for a, b in script["takes"]]
    takes[0][0], takes[-1][1] = 0.0, duration
    screens, info = build_screens(script, words, takes, rules)
    checks = {"fail": [], "warn": []}
    lines_out = []                     # check lines that are not part of a block's layout-report line

    def check(level, msg, b=None, t=None, own_line=True):
        line = (f"{b['id']} {t:.2f}s " if b is not None else "") + msg
        checks[level].append(line)
        if own_line:
            lines_out.append(f"!! {level.upper()} {line}")
    # glyphs of the final display text, before Chrome (which would draw a missing one in some system font)
    for p in fontcheck.check_glyphs(style, [ln["tokens"] for sc in screens for b in sc["blocks"] for ln in b["lines"]]):
        check("fail", f"glyph: {p}")
    track = load_json(ROOT / script["track"])
    cam_spec = {**script.get("camera", {}), "src_takes": script["takes"]}
    clips_json = ROOT / Path(script.get("source", "")).parent / "clips.json"
    if str(script.get("source", "")).endswith(".ffconcat") and clips_json.exists():   # transition handles stay in their clip
        cam_spec["clips"] = [[round(c["offset"] * FPS), round(c["offset"] * FPS) + c["n_frames"]]
                             for c in load_json(clips_json)["clips"]]
    camera = cam.build(cam_spec, takes, n_frames, track, edl, n_src)
    build_dir = ROOT / "build"
    save_json(camera, build_dir / "camera.json")
    meta = {"duration": duration, "n_frames": n_frames, "src_duration": src_dur, "edl": edl.segs,
            "takes": takes, "words": [{"w": w["w"], "s": w["s"]} for w in words],
            "script": str(script_path.resolve()), "brand": script.get("brand"), "format": script.get("format"),
            "renders": [],
            "checks": {"fail": [], "warn": [], "applied": []}}

    # pass 1: measure blocks at origin
    ids = 0
    for sc in screens:
        for b in sc["blocks"]:
            b["id"] = f"b{ids}"; ids += 1
            b["x"], b["y"] = 0, 0
    timeline = {"style": style, "screens": screens, "doodles": script.get("doodles", []), "duration": duration}
    measured = {m["id"]: m for m in measure(timeline)}
    sizes = {k: m["bbox"] for k, m in measured.items()}

    masks = np.load(ROOT / script["masks"])
    thr = 127 if masks.max() > 1 else 0
    face = cam.face_track(track)
    L = style["layout"]
    face_margin = L.get("face_margin", 40)
    report, geo = {}, {}
    placed = []                        # every placed block (x, y, w, h, t_first, t_end): a CTA outlives its screen
    # preset blocks (hook, CTA) first: the subtitles make room for them
    order = sorted([(sc, b) for sc in screens for b in sc["blocks"]], key=lambda sb: not text_rules.presets_of(sb[1]))
    for sc, b in order:
        bb = sizes[b["id"]]
        toks = [tok for l in b["lines"] for tok in l["tokens"]]
        t_first = min(tok["t"] for tok in toks)
        t_last = max(tok["t"] for tok in toks)
        t_end = b.get("t1", min(sc["t1"], b.get("until", sc["t1"])))
        behind = b.get("behind", sc.get("behind", style["layout"].get("behind", True)))
        b["behind"] = behind
        place = {**sc.get("place", {}), **b.get("place", {})}
        if place.get("x") == "center":
            place["x"] = int(round(W / 2 - bb["w"] / 2))
        # text-behind-subject: she may walk in front of the block once it has been read
        t_read = min(t_end, t_last + style["layout"].get("read_time", 0.9))
        t_free = t_read if behind else t_end
        t_free = place.get("free_until", t_free)
        f0, f1 = int(t_first * FPS), int(np.ceil(t_free * FPS)) - 1
        fbox = face_boxes(track, camera["frames"], edl, f0, f1, FACE_MIN_PX) if place.get("avoid") == "face" else None
        if fbox:                       # face-avoid: big centred text may sit over her hair or torso, not her face
            occ = np.zeros((H // Q, W // Q), np.uint8)
            fx0, fy0, fx1, fy1 = [int(v) for v in (fbox[0] - face_margin, fbox[1] - face_margin,
                                                   fbox[2] + face_margin, fbox[3] + face_margin)]
            occ[max(0, fy0 // Q):max(0, fy1 // Q + 1), max(0, fx0 // Q):max(0, fx1 // Q + 1)] = 1
        else:
            occ = occupancy(masks, camera["frames"], f0, f1)
        text_q = np.zeros_like(occ)
        for (x, y, w, h, pa, pb) in placed:          # other blocks visible at the same time
            if pa < t_end and t_first < pb:
                occ[max(0, y // Q - 2):(y + h) // Q + 3, max(0, x // Q - 2):(x + w) // Q + 3] = 1
                text_q[max(0, y // Q):(y + h) // Q + 1, max(0, x // Q):(x + w) // Q + 1] = 1
        fr = camera["frames"][min(f0, n_frames - 1)]
        fx, fy = face(edl.src_time(t_first))
        M = cam.matrix(fr)
        sfx, sfy = M @ np.array([fx, fy, 1.0])
        fs = 80 * fr["s"]
        boxes = [person_box(masks, camera["frames"], f) for f in range(f0, max(f0 + 1, min(f1, f0 + 24)), 3)]
        boxes = [bx for bx in boxes if bx is not None]
        pbox = (min(bx[0] for bx in boxes), min(bx[1] for bx in boxes),
                max(bx[2] for bx in boxes), max(bx[3] for bx in boxes)) if boxes else None
        x, y, warn = solve_block(occ, bb["w"], bb["h"], style, (sfx - fs / 2, sfy - fs / 2, fs, fs), pbox, place,
                                 text_q)
        w_, h_ = int(bb["w"]), int(bb["h"])
        placed.append((x, y, w_, h_, t_first, t_end))
        b["x"] = x - bb["x"]
        b["y"] = y - bb["y"]
        t0r, t1r = b.get("t0", sc["t0"]), b.get("t1", sc["t1"])
        # the words while they are read, and how much of each she hides (behind blocks only: front ones are drawn
        # over her)
        words_s = [{**w, "x": w["x"] + b["x"], "y": w["y"] + b["y"]} for w in measured[b["id"]]["words"]]
        f_read = int(np.ceil(t_read * FPS))
        cover = word_cover(masks, camera["frames"], words_s, f_read, thr) if behind and words_s else [0.0] * len(words_s)
        geo[b["id"]] = {"b": b, "sc": sc, "x": x, "y": y, "w": w_, "h": h_, "t_first": t_first, "t_last": t_last,
                        "t_end": t_end, "behind": behind, "words": words_s}
        if warn == "no free spot":
            shown = sorted(((c, w["text"]) for c, w in zip(cover, words_s) if c >= 0.1), reverse=True)[:3]
            warn += ("; she hides " + ", ".join(f"«{t}» {c:.0%}" for c, t in shown) + " while read" if shown else
                     "; no word hidden while read" if behind else "; drawn over her (front), no word hidden")
            check("warn", warn, b, t_first, own_line=False)
        text = " / ".join(" ".join(t["text"] for t in l["tokens"]) for l in b["lines"])
        sx0, sy0, sx1, sy1 = style["layout"]["safe"]
        if warn and warn.startswith("TOO BIG"):
            check("fail", f"TOO BIG ({w_}x{h_} px for a {W}x{H} frame): split the line", b, t_first, own_line=False)
        elif x < sx0 - Q or y < sy0 - Q or x + bb["w"] > sx1 + Q or y + bb["h"] > sy1 + Q:   # Q: solver grid
            warn = (warn + "; " if warn else "") + "OUTSIDE the IG crop-safe area, shorten the lines"
            check("fail", f"OUTSIDE the IG crop-safe area ({x},{y} {w_}x{h_}; safe {sx0}-{sx1} x {sy0}-{sy1}): "
                          f"shorten the lines or move it", b, t_first, own_line=False)
        for ex in L["exclude"]:
            if x < ex[2] and ex[0] < x + bb["w"] and y < ex[3] and ex[1] < y + bb["h"]:
                warn = (warn + "; " if warn else "") + "on the IG button rail"
                check("fail", f"on the IG button rail {ex}: move it or shorten the lines", b, t_first, own_line=False)
        if len(b["lines"]) > style["layout"].get("max_lines", len(b["lines"])):     # a brand's limit
            warn = (warn + "; " if warn else "") + f"{len(b['lines'])} lines, the brand allows " \
                                                   f"{style['layout']['max_lines']}: split the screen"
        report[b["id"]] = (f"{t0r:6.2f}-{t1r:6.2f} {b['id']} at ({x},{y}) {w_}x{h_}"
                           f"{'  !! ' + warn if warn else ''}  | {text}")
        hid = hidden_words(words_s, cover) if behind else []
        if hid:
            check("fail" if script.get("lint", {}).get("occlusion") == "fail" else "warn",
                  "she hides " + ", ".join(f"«{words_s[k]['text']}» {cover[k]:.0%}" for k in hid)
                  + f" while it is read ({t_first:.2f}-{t_read:.2f} s): place it beside her (place.side or place.x), "
                    f"draw it in front (\"behind\": false) or move the line", b, t_first)
        ink = measured[b["id"]].get("ink")
        if ink:                        # ink past the layout box is cropped on phones when it leaves the safe area
            ix0, iy0 = ink["x"] + b["x"], ink["y"] + b["y"]
            over = max(sx0 - ix0, sy0 - iy0, ix0 + ink["w"] - sx1, iy0 + ink["h"] - sy1)
            if over > Q:
                check("warn", f"letters reach {over:.0f} px past the IG crop-safe area: shorten or move it", b, t_first)
        for li, lj, n in measured[b["id"]].get("collisions", []):
            if n >= L.get("ink_overlap_px", INK_OVERLAP_PX):
                check("fail", f"letters of lines {li + 1} and {lj + 1} collide ({n} px): raise the leading or split "
                              f"the block", b, t_first)
    occl = sorted({f for sc in screens if any(b.get("behind") for b in sc["blocks"])
                   for f in range(int(sc["t0"] * FPS), int(np.ceil(sc["t1"] * FPS)))})
    timeline["occlude_frames"] = occl
    # the front layer: frames that show a behind:false block while a screen with a behind block is on (her matte
    # cuts the whole picture there, even after that behind block left through until/t1); the front block is drawn
    # over her, uncut. A screen's first occl frame can still belong to the screen before it: not counted
    def shown(g):           # overlay.html's window: t0 <= f / FPS < t1
        t0 = g["b"].get("t0", g["sc"]["t0"])
        return {f for f in range(int(t0 * FPS), int(np.ceil(g["t_end"] * FPS)) + 1) if t0 <= f / FPS < g["t_end"]}
    on_back = {f for sc in screens if any(b.get("behind") for b in sc["blocks"])
               for f in range(int(sc["t0"] * FPS), int(np.ceil(sc["t1"] * FPS))) if sc["t0"] <= f / FPS < sc["t1"]}
    front = sorted(set().union(*[shown(g) for g in geo.values() if g["behind"] is False]) & on_back & set(occl))
    if front:
        timeline["front_frames"] = front
    timeline["sfx"] = info["sfx"]         # automatic cues (CTA chime, insert pops and whooshes), from sfx_palette

    # checks over the whole layout
    gs = sorted(geo.values(), key=lambda g: int(g["b"]["id"][1:]))
    for i, a in enumerate(gs):
        for c in gs[i + 1:]:
            if a["t_first"] < c["t_end"] and c["t_first"] < a["t_end"] and a["x"] < c["x"] + c["w"] and \
                    c["x"] < a["x"] + a["w"] and a["y"] < c["y"] + c["h"] and c["y"] < a["y"] + a["h"]:
                check("fail", f"overlaps {c['b']['id']} (both shown at {max(a['t_first'], c['t_first']):.2f} s): move "
                              f"one (place) or split the screen", a["b"], max(a["t_first"], c["t_first"]))
    for g in gs:
        names = [p for p in text_rules.presets_of(g["b"]) if p in ("hook", "cta")]
        fb = face_boxes(track, camera["frames"], edl, int(g["t_first"] * FPS), int(np.ceil(g["t_end"] * FPS)) - 1,
                        FACE_MIN_PX) if names else None
        if fb and g["x"] < fb[2] + face_margin and fb[0] - face_margin < g["x"] + g["w"] and \
                g["y"] < fb[3] + face_margin and fb[1] - face_margin < g["y"] + g["h"]:
            check("fail", f"{names[0]} over her face ({fb[0]:.0f},{fb[1]:.0f}-{fb[2]:.0f},{fb[3]:.0f}): move it "
                          f"(place.y) or shorten it", g["b"], g["t_first"])
    # contrast against the graded picture, at the moment each block is fully shown
    ring = style.get("shadow") not in (None, "", "none")
    samples = sorted(((min(n_frames - 1, max(0, int(round(min(g["t_end"] - 0.04, g["t_last"] + 0.4) * FPS)))), g)
                      for g in gs if g["words"]), key=lambda fg: fg[0])     # frame only: two blocks may share one
    if samples:
        gr = video_pass.Grade(script.get("grade"))
        src = source_path(script)
        sources = [video_pass.FrameSource(src), video_pass.FrameSource(src)]
        weak = []
        try:
            for f, g in samples:
                img = cv2.resize(gr(video_pass.picture(camera["frames"], f, sources)), (W // Q, H // Q),
                                 interpolation=cv2.INTER_AREA)
                matte = matte_q(masks, camera["frames"], f, thr) if g["behind"] else None
                for msg in contrast_findings(img, g["words"], matte, ring, g["b"].get("stroke")):
                    check("warn", msg, g["b"], f / FPS, own_line=False)
                    lines_out.append(f"   {g['b']['id']} {f / FPS:.2f}s {msg}")      # the log keeps the details
                    weak.append(g["b"]["id"])
        finally:
            for s_ in sources:
                s_.close()
        if weak:                       # one summary line: the white-on-beige case hits many blocks at once
            ids_ = list(dict.fromkeys(weak))
            lines_out.append(f"!! WARN contrast: {len(ids_)} blocks hard to read over the picture ({', '.join(ids_[:8])}"
                             f"{', …' if len(ids_) > 8 else ''}): a stroke, another spot or another colour (details "
                             f"in the log)")

    # what the text layer did, for the final report
    heard = VoiceMap(edl, script.get("audio")).heard_words(load_json(ROOT / script["words"]))
    triggers = text_rules.cta_triggers(heard, rules)

    def card(g):
        return {"t0": round(g["b"].get("t0", g["sc"]["t0"]), 2), "t1": round(g["t_end"], 2), "x": g["x"], "y": g["y"],
                "w": g["w"], "h": g["h"], "text": " ".join(t["text"] for l in g["b"]["lines"] for t in l["tokens"])}
    hook = next((card(g) for g in gs if "hook" in text_rules.presets_of(g["b"])), None)
    ctas = []
    for g in gs:
        if "cta" in text_rules.presets_of(g["b"]):
            c = card(g)
            c["trigger"] = next((x["t"] for x in triggers if c["t0"] - 0.2 <= x["t"] < c["t1"]), None)
            c["dx"] = g["x"] - int(round(W / 2 - g["w"] / 2))        # a wide card is pushed off centre by the rail
            c["chime"] = any(abs(s["peak_at"] - c["t0"]) < 0.01 for s in info["sfx"])
            ctas.append(c)
    applied = {"censored": info["censored"], "latin": info["latin"], "hook": hook, "cta": ctas,
               "terms": [{"heard": " ".join(words[k]["w"].strip() for k in range(k0, k1 + 1)), "display": d,
                          "t": words[k0]["s"]} for k0, k1, d in info["hits"]]}
    meta["checks"] = {**checks, "applied": applied}
    save_json(timeline, build_dir / "timeline.json")
    save_json(meta, build_dir / "meta.json")
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n".join(report[b["id"]] for sc in screens for b in sc["blocks"]))
    print("\n".join(lines_out + [f"checks: {len(checks['fail'])} FAIL, {len(checks['warn'])} WARN"]))


if __name__ == "__main__":
    import argparse
    import time
    from common import BUILD, reel_id, run_log, short, studio_lock
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--verbose", action="store_true", help="the full output on the terminal (it is always in the log)")
    a = ap.parse_args()
    with studio_lock("timeline " + reel_id(a.script)), \
            run_log(BUILD / reel_id(a.script) / "logs" / "timeline.log", a.verbose):
        T = time.time()
        main(a.script)
        print(f"[timeline] {time.time() - T:.1f}s -> {short(BUILD / 'timeline.json')}")
