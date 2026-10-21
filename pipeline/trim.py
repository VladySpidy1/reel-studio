"""Dead-air trim and take proposal for a talking-head reel shot raw on the phone (audio-timing.md).

python trim.py projects/<name>/script.json [--write] [--force] [--outtakes out.wav]

Without --write it only prints the proposal: each clip's levels, the attempts (takes) with the proposed drops and
"?" doubts, a contact-sheet command per group of repeated takes, wordless clips (B-roll), product moments the cut
would lose, the cuts in output time and the totals. --write puts it in the script: edl and takes (one take per kept
segment), the trim block (the effective parameters, plus drop if it was absent) and audio.xfade_frames 2. Run it
before camera, sfx and screens: it moves output times. --outtakes writes every span the trim removes into one WAV,
a soft tick between spans, and lists them (source time, the words around the cut, length): one listen checks every
cut. --force cuts clips with a constant bed anyway (whisper's end + 0.2 s as the voice end; trim.force).

How it cuts (the format's grammar.trim, overridden by the script's trim block):
- In- and out-points come from the audio energy (20 ms RMS every 5 ms, broadband and first difference), not from
  whisper's word ends, which are early. A word's voice ends after 60 ms of quiet; its onset reaches back over a
  breath (up to 0.3 s with breath "keep", 50 ms with "cut").
- Attempts split at pauses of take_gap or more, at clip edges and after «стоп». An attempt ending in «стоп» is
  dropped; one that a later attempt repeats (text match with Latin folded to Cyrillic and the brand's heard_as) is
  proposed for dropping, so the last complete take stays. trim.drop, when present, is authoritative.
- Inside an attempt, a pause is cut when it is longer than min_cut and than its pads (pad_after, or
  keep_after_sentence after . ! ? … or a trim.punch word, plus pad_before and a frame) and holds less than 150 ms of
  sound (a laugh or «мм» is kept and flagged). Pauses between attempts are always cut. Points sit on the 1/30 grid
  (out-points rounded up, in-points down); a point that lands on sound moves up to 2 frames away from the word to
  a frame 3 dB quieter.
  The reel starts `head` before the first onset and ends `tail` after the last voice end. A segment shorter than
  min_shot undoes its smaller neighbouring cut inside the attempt; a whole attempt that short is flagged.
  trim.keep ranges are never cut.
- A clip whose speech is less than 25 dB over its pauses has a constant bed (music, room noise, an edited video):
  trim refuses and changes nothing.
It never transcribes. If it ever does, pass decoded samples like prep.py: faster-whisper's PyAV decoder (av 19)
breaks on file paths. lint_edit runs lint_audio (HOOKS): a cut in speech, a pause left after a trim, a same-setup
jump cut, a music fade-in that is not from the first frame.
"""
import argparse
import math
import re
import subprocess
import sys
import wave
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np

import camera as cam
import resolve
import text_rules
from common import FPS, ROOT, load_json, norm, reel_id, save_json, short, source_path
from edl import EDL, SENTENCE_END, VoiceMap

SR = 16000                 # analysis rate
HOP, WIN = 0.005, 0.02     # level frames: 20 ms RMS windows centred every 5 ms
BED_MIN = 25.0             # dB of speech over the pauses; under it a constant bed lies under the voice
DROP_DB, FLOOR_DB = 30.0, 10.0      # active: level >= max(speech - 30, floor + 10), per band
QUIET = 0.06               # s of quiet that ends a word's voice
SCAN = 0.6                 # s past whisper's end that the voice end may reach
BREATH = {"keep": 0.3, "cut": 0.05}  # s an onset reaches back over sound before whisper's start
FORCE_END = 0.2            # s after whisper's end: the voice end on a clip with a bed (--force)
SNAP, TIE_DB = 2, 3.0      # a cut point moves up to 2 frames to a frame at least 3 dB quieter
BURST = 0.15               # s of sound that keeps an inner pause
REPEAT_RATIO, REPEAT_LEN, REPEAT_AHEAD = 0.6, 0.7, 3
GROWTH = 1.4               # motion.json to_lens growth of a product moment
STOP = "стоп"
DEFAULTS = {"min_cut": 0.45, "pad_before": 4, "pad_after": 3, "keep_after_sentence": 10, "head": 0.15, "tail": 0.4,
            "min_shot": 1.0, "take_gap": 1.0, "breath": "keep"}
LISTS = ("drop", "keep", "punch")
LATIN = [("sh", "ш"), ("ch", "ч"), ("zh", "ж"), ("kh", "х"), ("ph", "ф"), ("x", "кс")] + list(zip(
    "abcdefghijklmnopqrstuvwyz", "абкдефгхійклмнопкрстуввиз"))
OUT_SR = 48000             # outtakes
TICK_HZ, TICK_GAP = 1000, 0.15


# ----------------------------------------------------------------------------- levels

def band_levels(x):
    """(broadband, first-difference) levels in dBFS of 16 kHz mono samples: 20 ms RMS, level j centred on j * HOP."""
    x = np.asarray(x, np.float64)
    step, half = int(SR * HOP), int(SR * WIN) // 2
    c = np.arange(max(1, -(-len(x) // step))) * step
    i0, i1 = np.clip(c - half, 0, len(x)), np.clip(c + half, 0, len(x))
    out = []
    for y in (x, np.diff(x, prepend=x[:1])):
        cs = np.concatenate([[0.0], np.cumsum(y * y)])
        out.append(10 * np.log10((cs[i1] - cs[i0]) / np.maximum(i1 - i0, 1) + 1e-12))
    return out[0], out[1]


def decode(path, sr=SR):
    """Mono float32 samples of a clip's sound, decoded by ffmpeg."""
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", str(sr),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def levels(path):
    """band_levels of a clip (about 20 MB per minute while it runs)."""
    return band_levels(decode(path))


def _i(t, n):
    return min(max(int(round(t / HOP)), 0), n)


# ----------------------------------------------------------------------------- inputs

def params_of(script):
    """The trim parameters: code defaults <- the format's grammar.trim <- the script's trim block."""
    g = (script.get("grammar") or {}).get("trim") or {}
    t = script.get("trim") or {}
    return {**DEFAULTS, **{k: v for k, v in g.items() if k in DEFAULTS}, **{k: v for k, v in t.items() if k in DEFAULTS}}


def source_clips(script):
    """[{name, offset, duration, orig_duration, speed, path}] of the source: clips.json next to a source.ffconcat, else
    the source file as one clip."""
    src = source_path(script)
    cj = src.parent / "clips.json"
    if src.suffix == ".ffconcat" and cj.exists():
        return [{"name": c["name"], "offset": c["offset"], "duration": c["duration"], "speed": c.get("speed", 1.0),
                 "orig_duration": c.get("orig_duration", c["duration"]), "path": src.parent / c["file"]}
                for c in load_json(cj)["clips"]]
    d = script.get("src_duration", script.get("duration"))
    return [{"name": src.stem, "offset": 0.0, "duration": d, "speed": 1.0, "orig_duration": d, "path": src}]


def words_of(words_json, clips):
    """The transcript's words in source order, each with its clip; a zero-length word lasts 50 ms."""
    names = {c["name"] for c in clips}
    out = []
    for seg in words_json["segments"]:
        for w in seg["words"]:
            out.append({"w": w["w"], "s": w["s"], "e": w["e"] if w["e"] > w["s"] else w["s"] + 0.05,
                        "p": w.get("p"), "clip": seg.get("clip") if seg.get("clip") in names else None})
    for w in out:
        if w["clip"] is None:
            w["clip"] = next((c["name"] for c in clips if c["offset"] <= w["s"] < c["offset"] + c["duration"]),
                             clips[-1]["name"])
    return sorted(out, key=lambda w: w["s"])


def fold(text, terms=None):
    """A line as repeats are compared: lowercase letters only, brand heard_as forms -> the term, Latin -> Cyrillic."""
    s = "".join(text_rules.squash(p) for p in text.split())
    for heard, _, display in text_rules.variants(terms or {}):
        s = s.replace(heard, text_rules.squash(display))
    s = re.sub(r"[\W_]", "", s)
    for a, b in LATIN:
        s = s.replace(a, b)
    return s


# ----------------------------------------------------------------------------- analysis

def analyse(clips, words, lv, P, force=False):
    """Per clip with words: speech, floor and pause levels, the bed and the active frames; each word gets its onset
    "on" and voice end "ve" (source time). Returns (rows by clip name, [(clip, bed)] of clips with a constant bed)."""
    rows, beds = {}, []
    for c in clips:
        ws = [w for w in words if w["clip"] == c["name"]]
        if not ws:
            continue
        db, hdb = lv[c["name"]]
        n, off = len(db), c["offset"]
        inw = np.zeros(n, bool)
        for w in ws:
            inw[_i(w["s"] - off, n):max(_i(w["e"] - off, n), _i(w["s"] - off, n) + 1)] = True
        speech, hspeech = float(np.median(db[inw])), float(np.median(hdb[inw]))
        floor, hfloor = float(np.percentile(db, 10)), float(np.percentile(hdb, 10))
        gap = float(np.median(db[~inw])) if (~inw).any() else floor
        act = (db >= max(speech - DROP_DB, floor + FLOOR_DB)) | (hdb >= max(hspeech - DROP_DB, hfloor + FLOOR_DB))
        bed = speech - gap < BED_MIN
        if bed:
            beds.append((c["name"], round(speech - gap, 1)))
        rows[c["name"]] = {"name": c["name"], "speech": speech, "floor": floor, "gap": gap, "bed": speech - gap,
                           "words": len(ws), "db": db, "act": act, "off": off, "end": off + c["duration"],
                           "f0": round(off * FPS), "f1": round((off + c["duration"]) * FPS), "forced": bed and force}
        prev_ve = off
        for k, w in enumerate(ws):
            nxt = ws[k + 1]["s"] if k + 1 < len(ws) else off + c["duration"]
            if bed:
                w["ve"] = max(w["e"], min(w["e"] + FORCE_END, nxt))
                w["on"] = max(w["s"], prev_ve)
            else:
                w["ve"] = _voice_end(w, nxt, act, off)
                w["on"] = max(prev_ve, _onset(w, act, off, BREATH[P["breath"]]))
            prev_ve = w["ve"]
    return rows, beds


def _voice_end(w, nxt, act, off):
    """Where the voice of w ends: from 60% into the word, the last active frame before 60 ms of quiet, capped at the
    next word's start and SCAN past whisper's end; never before whisper's end."""
    n = len(act)
    j = start = _i(w["s"] + 0.6 * (w["e"] - w["s"]) - off, n)
    lim = _i(min(nxt, w["e"] + SCAN) - off, n)
    last, quiet = None, round(QUIET / HOP)
    while j < lim:
        if act[j]:
            last = j
        elif j - (start - 1 if last is None else last) >= quiet:
            break
        j += 1
    ve = off + (last + 1) * HOP if last is not None else w["e"]
    return max(w["e"], min(ve, max(nxt, w["e"])))


def _onset(w, act, off, back):
    """Where w starts: whisper's start, moved back over the active frames right before it (up to `back` seconds)."""
    n = len(act)
    k = m = _i(w["s"] - off, n)
    lim = _i(w["s"] - back - off, n)
    while m - 1 >= lim and act[m - 1]:
        m -= 1
    return min(w["s"], off + (m - 1) * HOP) if m < k else w["s"]


def split_attempts(words, P):
    """Attempts: runs of words split at pauses of take_gap or more, at clip edges and after «стоп»."""
    atts, prev = [], None
    for w in words:
        if prev is None or w["clip"] != prev["clip"] or w["on"] - prev["ve"] >= P["take_gap"] or norm(prev["w"]) == STOP:
            atts.append({"words": []})
        atts[-1]["words"].append(w)
        prev = w
    for k, a in enumerate(atts):
        ws = a["words"]
        a.update(i=k, clip=ws[0]["clip"], start=ws[0]["on"], end=ws[-1]["ve"],
                 text=" ".join(w["w"].strip() for w in ws), stop=norm(ws[-1]["w"]) == STOP, drop=None, by=None,
                 doubt=[])
    return atts


def propose(atts, terms=None):
    """Proposed drops: attempts ending in «стоп», and an attempt that one of the next 3 repeats: the later one is at
    least 0.7 as long (so a later fragment such as «Фікс-колор!» never replaces a whole take) and the two folded texts
    match at least 0.6 over the shorter one's length (the whole earlier text against a shorter later one would make
    «RepairPlex – для сухого волосся.» a repeat of «Баланс для жирного волосся»). Then the kept attempts' doubts."""
    for a in atts:
        a["fold"] = fold(a["text"], terms)
    for i, a in enumerate(atts):
        if a["stop"]:
            a["drop"] = STOP
            continue
        for j in range(i + 1, min(len(atts), i + 1 + REPEAT_AHEAD)):
            b = atts[j]
            if b["stop"] or not a["fold"] or len(b["fold"]) < REPEAT_LEN * len(a["fold"]):
                continue
            n = min(len(a["fold"]), len(b["fold"]))
            r = SequenceMatcher(None, a["fold"][:n], b["fold"][:n], autojunk=False).ratio()
            if r >= REPEAT_RATIO:
                a["drop"], a["by"] = f"repeat of #{j + 1} ({r:.2f})", j
                break
    for a in atts:
        k = a["i"]
        while atts[k]["by"] is not None:
            k = atts[k]["by"]
        a["group"] = k
    for a in atts:
        if a["drop"]:
            continue
        group = [b for b in atts if b["group"] == a["group"]]
        longest = max(len(b["fold"]) for b in group)
        if len(group) > 1 and len(a["fold"]) < REPEAT_LEN * longest:
            a["doubt"].append(f"shorter than the longest take ({len(a['fold']) / longest:.0%})")
        last = a["words"][-1]["w"].strip()
        if last.endswith(("…", "...")):
            a["doubt"].append("ends in …")
        elif not SENTENCE_END.search(last):
            a["doubt"].append("no sentence end")
        ps = [w["p"] for w in a["words"] if w.get("p") is not None]
        if ps and sum(ps) / len(ps) < 0.7:
            a["doubt"].append(f"mean word probability {sum(ps) / len(ps):.2f}")


# ----------------------------------------------------------------------------- the cut

def plan(clips, words, lv, params=None, terms=None, drop=None, keep=None, punch=None, force=False):
    """The proposed edit. clips [{name, offset, duration}], words [{w, s, e, p, clip}] (source time), lv {clip name:
    band_levels of its sound}. Returns {"clips", "refused", "attempts", "drop", "ranges" ([[a, b]] source seconds on
    the frame grid, None when a bed refuses), "cuts", "flags"}."""
    P = {**DEFAULTS, **(params or {})}
    words = sorted((dict(w) for w in words), key=lambda w: w["s"])
    rows, beds = analyse(clips, words, lv, P, force)
    out = {"clips": list(rows.values()), "refused": beds, "attempts": [], "drop": drop, "ranges": None, "cuts": [],
           "flags": []}
    if beds and not force:
        return out
    atts = split_attempts(words, P)
    propose(atts, terms)
    out["attempts"] = atts
    given = drop is not None
    if not given:
        drop = out["drop"] = [[round(a["start"], 3), round(a["end"], 3)] for a in atts if a["drop"]]
    for w in words:
        mid = (w["s"] + w["e"]) / 2
        w["removed"] = any(a <= mid <= b for a, b in drop)
    if given:                          # trim.drop decides; the proposal is only printed
        for a in atts:
            gone = sum(w["removed"] for w in a["words"])
            a["proposed"] = a["drop"]
            a["drop"] = "trim.drop" if gone == len(a["words"]) else f"{gone} words by trim.drop" if gone else None
    keep = keep or []
    flags = out["flags"]
    beat = _beats(punch or [])

    def in_keep(a, b):
        return any(k0 < b and a < k1 for k0, k1 in keep)

    runs = []                          # kept words of one attempt with nothing dropped between them
    for a in atts:
        cur = []
        for w in a["words"]:
            if w["removed"]:
                if cur:
                    runs.append((a, cur))
                cur = []
            else:
                cur.append(w)
        if cur:
            runs.append((a, cur))
    by_clip, pos = {}, {}
    for w in words:
        pos[id(w)] = len(by_clip.setdefault(w["clip"], []))
        by_clip[w["clip"]].append(w)
    pieces = []                        # [in frame, out frame, clip] per kept segment
    for r, (a, run) in enumerate(runs):
        row = rows[a["clip"]]
        groups = [[run[0], run[0]]]
        for w0, w1 in zip(run, run[1:]):
            g = w1["on"] - w0["ve"]
            need = ((P["keep_after_sentence"] if beat(w0) else P["pad_after"]) + P["pad_before"] + 1) / FPS
            if g > max(P["min_cut"], need) and not in_keep(w0["ve"], w1["on"]):
                sound = 0.0 if row["forced"] else _active(row, w0["ve"], w1["on"])
                if sound < BURST:
                    groups.append([w1, w1])
                    continue
                flags.append(f"#{a['i'] + 1}: sound in the pause {w0['ve']:.2f}-{w1['on']:.2f} ({sound:.2f} s), "
                             f"kept (a laugh or «мм»?)")
            groups[-1][1] = w1
        segs = []
        for k, (wa, wb) in enumerate(groups):
            first, last = r == 0 and k == 0, r == len(runs) - 1 and k == len(groups) - 1
            cw = by_clip[a["clip"]]
            ia, ib = pos[id(wa)], pos[id(wb)]
            lo = max(row["f0"], math.ceil(cw[ia - 1]["ve"] * FPS - 1e-6) if ia else row["f0"])
            hi = min(row["f1"], math.floor(cw[ib + 1]["on"] * FPS + 1e-6) if ib + 1 < len(cw) else row["f1"])
            f_in = math.floor((wa["on"] - (P["head"] if first else P["pad_before"] / FPS)) * FPS + 1e-6)
            pad = P["tail"] if last else (P["keep_after_sentence"] if beat(wb) else P["pad_after"]) / FPS
            f_out = math.ceil((wb["ve"] + pad) * FPS - 1e-6)
            f_in, f_out = max(lo, f_in), min(hi, f_out)
            f_in, f_out = _snap(row, f_in, -1, lo, hi), _snap(row, f_out, 1, lo, hi)
            segs.append([f_in, max(f_out, f_in + 1)])     # overlapping transcript words: never an empty segment
        while len(segs) > 1:           # min_shot: each pass undoes one inner cut, so this ends
            short_ = [k for k, (fa, fb) in enumerate(segs) if (fb - fa) / FPS < P["min_shot"]]
            if not short_:
                break
            k = short_[0]
            cuts = [(segs[j + 1][0] - segs[j][1], j) for j in (k - 1, k) if 0 <= j < len(segs) - 1]
            j = min(cuts)[1]
            segs[j:j + 2] = [[segs[j][0], segs[j + 1][1]]]
        if len(segs) == 1 and (segs[0][1] - segs[0][0]) / FPS < P["min_shot"]:
            flags.append(f"#{a['i'] + 1}: {(segs[0][1] - segs[0][0]) / FPS:.2f} s kept alone, under min_shot "
                         f"{P['min_shot']} s (drop it or keep its neighbours by hand)")
        pieces += [[fa, fb, a["clip"]] for fa, fb in segs]
    for k0, k1 in keep:                # trim.keep: whole frames, split at clip edges
        for c in clips:
            f0, f1 = round(c["offset"] * FPS), round((c["offset"] + c["duration"]) * FPS)
            fa, fb = max(f0, math.floor(k0 * FPS + 1e-6)), min(f1, math.ceil(k1 * FPS - 1e-6))
            if fa < fb:
                pieces.append([fa, fb, c["name"]])
    merged = []
    for p in sorted(pieces):
        if merged and merged[-1][2] == p[2] and p[0] <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], p[1])
        else:
            merged.append(list(p))
    out["ranges"] = [[round(fa / FPS, 4), round(fb / FPS, 4)] for fa, fb, _ in merged]
    o = 0
    for (fa, fb, ca), (ga, gb, cb) in zip(merged, merged[1:]):
        o += fb - fa
        out["cuts"].append({"t": round(o / FPS, 4), "src": [round(fb / FPS, 4), round(ga / FPS, 4)],
                            "same_clip": ca == cb})
    return out


def _beats(punch):
    """A word after which keep_after_sentence applies: a sentence end, or a trim.punch time inside it."""
    return lambda w: bool(SENTENCE_END.search(w["w"].strip())) or any(w["s"] - 0.05 <= t <= w["e"] + 0.05 for t in punch)


def _active(row, a, b):
    """Seconds of active frames whose centre lies in [a, b)."""
    n = len(row["act"])
    return float(row["act"][_i(a - row["off"], n):_i(b - row["off"], n)].sum()) * HOP


def _snap(row, f, way, lo, hi):
    """A cut point that lands on sound (over the clip's floor + 10 dB: a click, a rustle) moved up to SNAP frames away
    from the word (way -1 earlier, +1 later) to the quietest frame, when that one is at least TIE_DB quieter. On room
    tone it stays: a few dB of difference there is noise, and moving would only lengthen the pause."""
    n = len(row["db"])
    level = lambda g: row["db"][min(_i(g / FPS - row["off"], n), n - 1)]
    if level(f) <= row["floor"] + FLOOR_DB:
        return f
    best = min((g for g in (f + way * k for k in range(SNAP + 1)) if lo <= g <= hi), key=level, default=f)
    return best if level(best) < level(f) - TIE_DB else f


# ----------------------------------------------------------------------------- report numbers and listings

def removed_spans(clips, kept):
    """Each clip's span minus the kept source ranges, slivers of a frame or less ignored."""
    kept, out = sorted(kept), []
    for c in clips:
        a0, a1 = c["offset"], c["offset"] + c["duration"]
        t = a0
        for a, b in kept:
            if b <= t or a >= a1:
                continue
            if a > t + 1 / FPS:
                out.append((t, min(a, a1)))
            t = max(t, b)
        if a1 > t + 1 / FPS:
            out.append((t, a1))
    return out


def classify(spans, words, kept, clips, take_gap):
    """Each removed span's kind: "retakes" (a word's midpoint inside), "pauses" (silent, between two heard words of
    one clip less than take_gap apart) or "dead_air" (clip heads and tails, between takes, wordless clips)."""
    mid = lambda w: (w["s"] + w["e"]) / 2
    heard = lambda w: any(a - 1e-6 <= mid(w) <= b + 1e-6 for a, b in kept)
    clip = lambda t: next((c["name"] for c in clips if c["offset"] <= t < c["offset"] + c["duration"]), None)
    kinds = []
    for a, b in spans:
        if any(a <= mid(w) < b for w in words):
            kinds.append("retakes")
            continue
        before = [w for w in words if w["e"] <= a + 1e-6]
        after = [w for w in words if w["s"] >= b - 1e-6]
        inner = (before and after and heard(before[-1]) and heard(after[0])
                 and after[0]["s"] - before[-1]["e"] < take_gap and clip(before[-1]["s"]) == clip(after[0]["s"]))
        kinds.append("pauses" if inner else "dead_air")
    return kinds


def stats(script, clips=None, words=None):
    """The report's numbers, from the script, its words and clips.json (no audio decode): raw_s as shot (before a
    speed-up), src_s, out_s, edits (edl item boundaries) and the removed time by kind."""
    if clips is None:
        clips = source_clips(script)
    if words is None:
        wp = ROOT / script["words"] if script.get("words") else None
        words = words_of(load_json(wp), clips) if wp and wp.exists() else []
    edl = EDL(script.get("edl"), script.get("src_duration", script.get("duration")))
    kept = sorted([s["src"] for s in edl.segs if "src" in s]
                  + [v["src"] for v in (script.get("audio") or {}).get("voice_over", [])])
    spans = removed_spans(clips, kept)
    kinds = classify(spans, words, kept, clips, params_of(script)["take_gap"])
    removed = {k: {"n": kinds.count(k), "s": round(sum(b - a for (a, b), kk in zip(spans, kinds) if kk == k), 3)}
               for k in ("pauses", "retakes", "dead_air")}
    return {"raw_s": round(sum(c.get("orig_duration", c["duration"]) for c in clips), 2),
            "speed": clips[0].get("speed", 1.0) if clips else 1.0,
            "src_s": round(sum(c["duration"] for c in clips), 2), "out_s": round(edl.duration, 2),
            "edits": len(edl.items) - 1, "removed": removed}


def product_moments(events, ranges):
    """motion.json to_lens events of growth >= 1.4 that the cut loses (t0..t_settle not inside one kept range), each
    with a ready trim.keep entry."""
    return [{**e, "keep": [round(e["t0"] - 0.2, 2), round(e["t_settle"] + 0.3, 2)]} for e in events
            if e.get("type") == "to_lens" and e.get("growth", 0) >= GROWTH
            and not any(a <= e["t0"] and e["t_settle"] <= b for a, b in ranges)]


def join_outtakes(spans, sr):
    """(samples, start second of each span): the spans one after another, 10 ms fades, a soft tick between them."""
    t = np.arange(int(0.03 * sr)) / sr
    gap = np.zeros(int(TICK_GAP * sr), np.float32)
    tick = np.concatenate([gap, (0.1 * np.sin(2 * np.pi * TICK_HZ * t) * np.exp(-t / 0.008)).astype(np.float32), gap])
    out, at, pos = [], [], 0
    for k, y in enumerate(spans):
        if k:
            out.append(tick)
            pos += len(tick)
        y = np.array(y, np.float32)
        r = np.linspace(0, 1, min(int(0.01 * sr), len(y) // 2), dtype=np.float32)
        if len(r):
            y[:len(r)] *= r
            y[len(y) - len(r):] *= r[::-1]
        at.append(pos / sr)
        out.append(y)
        pos += len(y)
    return (np.concatenate(out) if out else np.zeros(0, np.float32)), at


def write_outtakes(path, clips, words, ranges, take_gap):
    """Every span the trim removes, joined with ticks into a 16-bit mono WAV; prints where each one is in the file,
    its source time and length, its kind and the words around its cut in output time."""
    spans = removed_spans(clips, ranges)
    kinds = classify(spans, words, ranges, clips, take_gap)
    edl = EDL([{"src": r} for r in ranges], 0)
    heard = VoiceMap(edl).heard_words({"segments": [{"words": words}]})
    pieces, cache = [], {}
    for a, b in spans:
        c = _clip_at(clips, a + 0.5 / FPS)
        if c["name"] not in cache:
            cache.clear()
            cache[c["name"]] = decode(c["path"], OUT_SR)
        x = cache[c["name"]]
        pieces.append(x[int(round((a - c["offset"]) * OUT_SR)):int(round((b - c["offset"]) * OUT_SR))])
    y, at = join_outtakes(pieces, OUT_SR)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(OUT_SR)
        f.writeframes((np.clip(y, -1, 1) * 32767).astype("<i2").tobytes())
    print(f"outtakes: {len(spans)} spans, {sum(b - a for a, b in spans):.1f} s -> {short(path)} ({len(y) / OUT_SR:.1f} s"
          f" with ticks)")
    for k, ((a, b), kind, t) in enumerate(zip(spans, kinds, at)):
        o = edl.out_time(a)
        before = [w for w in heard if w["s"] < a]
        after = [w for w in heard if w["s"] >= b]
        around = (f"«{before[-1]['w'].strip()}» | «{after[0]['w'].strip()}»" if before and after else
                  f"«{before[-1]['w'].strip()}» | end" if before else f"start | «{after[0]['w'].strip()}»" if after else "")
        print(f"  {k + 1:2d}  file {int(t // 60)}:{t % 60:04.1f}  src {a:7.2f}-{b:7.2f} ({b - a:5.2f} s)  "
              f"{kind.replace('_', ' '):8}  cut at {o:6.2f}s  {around}")


# ----------------------------------------------------------------------------- lint (lint_edit HOOKS)

def lint_audio(script, ctx):
    """lint_edit's audio checks: (a) a cut that lands in speech (every reel), (b) a pause left after a trim (scripts
    with a trim block), (c) a same-setup jump cut with no A/B switch, and a music fade-in that is not from the first
    frame. (a) and (b) decode the clips' sound; they skip with a WARN when build/<reel>/media was cleaned up."""
    warns = []
    music = (script.get("audio") or {}).get("music")
    if music and music.get("fade_in", 0) > 0.1:
        warns.append((0.0, f"music fades in over {music['fade_in']} s: it starts from the first frame "
                           f"(fade_in <= 0.1)"))
    clips = source_clips(script)
    warns += _same_setup(script, ctx, clips)
    edges = _cut_edges(script, ctx["edl"], clips)
    trimmed = bool(script.get("trim"))
    if not edges and not trimmed:
        return [], warns
    gone = [c for c in clips if not Path(c["path"]).exists()]
    wp = ROOT / script["words"]
    if gone or not wp.exists():
        warns.append((0.0, f"audio checks skipped: {short(gone[0]['path'] if gone else wp)} is gone (cleaned up?)"))
        return [], warns
    P = params_of(script)
    t = script.get("trim") or {}
    words = words_of(load_json(wp), clips)
    need = {e[3] for e in edges} | ({w["clip"] for w in words} if trimmed and not t.get("force") else set())
    lv = {c["name"]: levels(c["path"]) for c in clips if c["name"] in need and any(w["clip"] == c["name"] for w in words)}
    rows, _ = analyse([c for c in clips if c["name"] in lv], [w for w in words if w["clip"] in lv], lv, P)
    for o, s, what, name in edges:
        row = rows.get(name)
        if row is None:
            continue
        n = len(row["db"])
        lvl = row["db"][min(_i(s - row["off"], n), n - 1)]
        if lvl > max(row["speech"] - 24, row["gap"] + 6):
            warns.append((o, f"cut at {o:.2f}s lands in speech ({lvl - row['speech']:+.1f} dB re speech; {what} at "
                             f"source {s:.2f}s)"))
    if trimmed:
        warns += _pauses_left(script, ctx["edl"], words, P, t)
    return [], warns


def _clip_at(clips, t):
    """The clip holding source time t (pass a frame's centre: clip offsets are not on the 4-decimal grid)."""
    return next((c for c in clips if c["offset"] <= t < c["offset"] + c["duration"]), clips[-1])


def _cut_edges(script, edl, clips):
    """[(output time, source time, what, clip)] of every heard cut point: src segment ends that do not run on into the
    next segment and are not a clip edge, the picture's sound not muted there, and both ends of each voice-over."""
    mute = (script.get("audio") or {}).get("mute", [])
    muted = lambda o: any(m0 <= o < m1 for m0, m1 in mute)
    edge = lambda t: any(abs(t - c["offset"]) < 0.5 / FPS or abs(t - c["offset"] - c["duration"]) < 0.5 / FPS
                         for c in clips)
    out, items = [], edl.items
    for k, (o0, o1, s) in enumerate(items):
        if "src" not in s:
            continue
        a, b = s["src"]
        prev, nxt = items[k - 1][2] if k else None, items[k + 1][2] if k + 1 < len(items) else None
        if not edge(a) and not (prev and "src" in prev and abs(prev["src"][1] - a) < 0.5 / FPS) \
                and not muted(o0 + 0.5 / FPS):
            out.append((o0, a, "segment start", _clip_at(clips, a + 0.5 / FPS)["name"]))
        if not edge(b) and not (nxt and "src" in nxt and abs(nxt["src"][0] - b) < 0.5 / FPS) \
                and not muted(o1 - 0.5 / FPS):
            out.append((o1, b, "segment end", _clip_at(clips, b - 0.5 / FPS)["name"]))
    for k, v in enumerate((script.get("audio") or {}).get("voice_over", [])):
        a, b = v["src"]
        out.append((v["at"], a, f"voice_over {k + 1} start", _clip_at(clips, a + 0.5 / FPS)["name"]))
        out.append((v["at"] + b - a, b, f"voice_over {k + 1} end", _clip_at(clips, b - 0.5 / FPS)["name"]))
    return out


def _pauses_left(script, edl, words, P, t):
    """(b): pauses between heard words in output time, on trim's voice ends, outside trim.keep and without a hold (a
    deliberate freeze) in them: over min_cut, or after a sentence end or a trim.punch word over keep_after_sentence +
    pad_before + 2 frames of rounding + 2 x SNAP frames (trim's own move off a click on each side)."""
    keep, beat = t.get("keep") or [], _beats(t.get("punch") or [])
    vm = VoiceMap(edl, script.get("audio"))
    spans = [(o0, o1) for o0, o1, s in edl.items if "src" in s] + \
            [(v["at"], v["at"] + v["src"][1] - v["src"][0]) for v in vm.voice_over]
    heard = []
    for w in words:
        o = vm.word_time(w)
        if o is None:
            continue
        on, ve = w.get("on", w["s"]), w.get("ve", w["e"] + FORCE_END)
        g0, g1 = next(((a, b) for a, b in spans if a - 1e-6 <= o + (w["e"] - w["s"]) / 2 <= b + 1e-6), (o, o + 99))
        heard.append((max(g0, o - (w["s"] - on)), min(g1, o + ve - w["s"]), w))
    heard.sort(key=lambda h: h[0])
    holds = [(o0, o1) for o0, o1, s in edl.items if "hold" in s]
    out = []
    for (a0, a1, w0), (b0, b1, w1) in zip(heard, heard[1:]):
        gap = b0 - a1
        if any(k0 < w1["s"] and w0["e"] < k1 for k0, k1 in keep) or any(a1 < h1 and h0 < b0 for h0, h1 in holds):
            continue
        limit = (P["keep_after_sentence"] + P["pad_before"] + 2 + 2 * SNAP) / FPS if beat(w0) else P["min_cut"]
        if gap > limit + 1e-6:
            out.append((a1, f"pause left: {gap:.2f} s after «{w0['w'].strip()}» (limit {limit:.2f} s)"))
    return out


def _same_setup(script, ctx, clips):
    """(c): consecutive src segments of one clip with no designed transition at the cut, whose scale changes by less
    than 10% and whose face moves less than 55 px on screen: the head teleports."""
    frames, edl = ctx["frames"], ctx["edl"]
    trs = [tr["at"] for tr in (script.get("camera") or {}).get("transitions", [])]
    track = load_json(ROOT / script["track"])
    face = cam.face_track(track) if any(f.get("face") for f in track["frames"]) else None
    out = []
    for (o0, o1, s), (p0, p1, t) in zip(edl.items, edl.items[1:]):
        if "src" not in s or "src" not in t or abs(t["src"][0] - s["src"][1]) < 0.5 / FPS:
            continue
        if _clip_at(clips, s["src"][0] + 0.5 / FPS) is not _clip_at(clips, t["src"][0] + 0.5 / FPS):
            continue
        f = round(p0 * FPS)
        if not 0 < f < len(frames) or any(abs(x - p0) <= 2 / FPS for x in trs):
            continue
        A, B = frames[f - 1], frames[f]
        moved = 0.0
        if face:
            pa = cam.matrix(A) @ np.array([*face(A["src_f"] / FPS), 1.0])
            pb = cam.matrix(B) @ np.array([*face(B["src_f"] / FPS), 1.0])
            moved = float(np.hypot(*(pb - pa)))
        if abs(B["s"] / A["s"] - 1) < 0.10 and moved < 55:
            out.append((p0, f"same-setup jump cut (push {A['s']:.2f} -> {B['s']:.2f}, face moves {moved:.0f} px): the "
                            f"head teleports; switch A/B framing (push_takes) or don't cut"))
    return out


# ----------------------------------------------------------------------------- CLI

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--write", action="store_true", help="put the proposal in the script (edl, takes, trim block)")
    ap.add_argument("--force", action="store_true", help="cut clips with a constant bed (whisper's end + 0.2 s)")
    ap.add_argument("--outtakes", metavar="WAV", help="write every removed span into one WAV, ticks between spans")
    a = ap.parse_args()
    raw = load_json(a.script)
    script = resolve.load_script(a.script)
    P, t = params_of(script), script.get("trim") or {}
    force = a.force or bool(t.get("force"))
    clips = source_clips(script)
    words = words_of(load_json(ROOT / script["words"]), clips)
    talk = {w["clip"] for w in words}
    lv = {c["name"]: levels(c["path"]) for c in clips if c["name"] in talk}
    p = plan(clips, words, lv, P, script.get("terms"), t.get("drop"), t.get("keep"), t.get("punch"), force)
    rid = reel_id(a.script)
    print(f"{rid}: {len(clips)} clips, {sum(c['duration'] for c in clips):.2f} s; min_cut {P['min_cut']} s, pads "
          f"{P['pad_before']}/{P['pad_after']} f, {P['keep_after_sentence']} f after a sentence, take gap "
          f"{P['take_gap']} s, breath {P['breath']}")
    print("levels (dB)   speech  floor  pause   bed")
    for r in p["clips"]:
        print(f"  {r['name']:11} {r['speech']:6.1f} {r['floor']:6.1f} {r['gap']:6.1f} {r['bed']:5.1f}"
              + ("  constant bed" if r["bed"] < BED_MIN else ""))
    if p["refused"] and not force:
        print("constant bed under the voice (music or noise, or an edited video): no pause cutting. "
              "Hand edit, or --force (whisper's end + 0.2 s as the voice end)")
        return 0
    for c in clips:
        if c["name"] not in talk:
            print(f"no speech: B-roll candidate {c['name']} {c['offset']:.2f}-{c['offset'] + c['duration']:.2f} s "
                  f"(move the clip to inserts/ for a full-screen insert)")
    atts = p["attempts"]
    print("attempts (? = doubt):")
    for at in atts:
        what = f"drop: {at['drop']}" if at["drop"] else "keep" + (" ?" if at["doubt"] else "")
        why = f" [{'; '.join(at['doubt'])}]" if at["doubt"] and not at["drop"] else ""
        was = f" (proposed: {at['proposed'] or 'keep'})" if "proposed" in at else ""
        print(f"  #{at['i'] + 1:<2} {at['clip']:9} {at['start']:7.2f}-{at['end']:7.2f}  {what}{was}  {at['text']}{why}")
    sheet = ".venv/bin/python pipeline/contact_sheet.py"
    src, wrel = short(source_path(script)), script["words"]
    groups = {}
    for at in atts:
        groups.setdefault(at["group"], []).append(at)
    reps = [g for g in groups.values() if len(g) > 1]
    if reps:
        print("repeat groups: watch the takes, then set trim.drop to change the choice")
    for g in reps:
        print(f"  #{'/#'.join(str(x['i'] + 1) for x in g)}: {sheet} {src} {max(0, g[0]['start'] - 0.5):.2f} "
              f"{g[-1]['end'] + 0.5:.2f} 0.25 --words {wrel}")
    mpath = ROOT / Path(script["words"]).parent / "motion.json"
    moments = product_moments(load_json(mpath)["events"], p["ranges"]) if mpath.exists() else []
    if moments:
        print(f"product moments the cut loses (to keep one, add its keep range to trim.keep; watch it with: {sheet} "
              f"{src} <from> <to> 0.1):")
    for m in moments:
        print(f"  {m['t0']:7.2f} x{m['growth']:.2f}  keep {m['keep']}  watch {m['t0'] - 0.3:.2f} {m['t_settle'] + 0.5:.2f}")
    for f in p["flags"]:
        print("flag " + f)
    inner = sum(1 for c in p["cuts"] if c["same_clip"])
    print("cuts (output time): " + ", ".join(f"{c['t']:.2f}" + ("*" if c["same_clip"] else "") for c in p["cuts"])
          + (f"   (* {inner} same-clip jump cuts: A/B framing)" if inner else ""))
    st = stats({**script, "edl": [{"src": r} for r in p["ranges"]]}, clips, words)
    rm = st["removed"]
    print(f"proposal: {len(p['ranges'])} segments, {st['raw_s']:.2f} s -> {st['out_s']:.2f} s, {st['edits']} edits; "
          f"removed pauses {rm['pauses']['n']} ({rm['pauses']['s']:.2f} s), retakes {rm['retakes']['n']} "
          f"({rm['retakes']['s']:.2f} s), dead air {rm['dead_air']['n']} ({rm['dead_air']['s']:.2f} s)")
    if a.outtakes:
        write_outtakes(a.outtakes, clips, words, p["ranges"], P["take_gap"])
    if not a.write:
        print("(print only: --write puts it in the script)")
        return 0
    old = raw.get("takes") or []
    raw["edl"] = [{"src": r} for r in p["ranges"]]
    raw["takes"] = [list(r) for r in p["ranges"]]
    block = {k: P[k] for k in DEFAULTS}
    block.update({k: t[k] for k in LISTS if t.get(k) is not None})
    block.setdefault("drop", p["drop"])
    if force:
        block["force"] = True
    raw["trim"] = block
    raw.setdefault("audio", {}).setdefault("xfade_frames", 2)
    save_json(raw, a.script)
    print(f"wrote {len(p['ranges'])} segments (edl = takes) and the trim block to {short(a.script)}")
    if old and old != raw["takes"]:
        moves = []
        for k, (x0, x1) in enumerate(old):
            new = [j + 1 for j, (y0, y1) in enumerate(raw["takes"]) if y0 < x1 and x0 < y1]
            moves.append(f"{k + 1}->{'+'.join(map(str, new)) or 'gone'}")
        print("takes renumbered: " + ", ".join(moves))
        print("output times moved: re-derive camera/sfx/literal/screens with times.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
