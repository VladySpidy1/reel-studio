"""The subtitle text layer's rules: Latin brand words (terms), asterisk censorship and the spoken CTA, plus the text
checks lint_edit runs (lint_text). Pure Python, no Chrome; build_timeline, lint_edit and times.py use it.

The resolved script (resolve.py: studio -> brand -> format -> script) holds the rules:
  terms        {display: {"heard_as": [variant, ...], "color"?}}: a variant's letters match the transcript with
               optional hyphens between them, from a word start to a word end (a trailing * makes it a prefix, for
               inflections); the match aligns to the display ("U -Case" -> yocase). A term rewrites the transcript
               only when its display is among the script's spoken words, so ordinary words («баланс») stay intact.
               The display is never rewritten: the script types it; a typed heard form is a lint WARN.
  censor       [word | "wo*rd" | "@set"]: spoken display words (and literal lines with "censor": true) get an ASCII
               "*" for one letter. A plain word masks its first vowel after the first letter and matches by its stem
               (trailing vowels, ь and й stripped; at least 3 letters): гроші -> гр*ші, грошей -> гр*шей. "@set"
               expands censor_sets[set] («ЦЕНЗУРА: стандартна» is "@standard").
  cta_phrases  regexes over norm(heard word); hits less than 3 s apart are one spoken CTA
  cta_check    lint FAILs a spoken CTA without a "preset": "cta" block (studio false; talking-head true)
  presets      the block presets (merged by the resolver; the name stays on the block as "preset")
"""
import contextlib
import io
import re
from collections import Counter

from common import FPS, ROOT, load_json, norm

VOWELS = "аеєиіїоуюяaeiouy"
CTA_MERGE = 3.0           # trigger hits closer than this are one CTA
CTA_LEAD = 1.0            # a CTA block's first spoken word may start this long before its trigger
LITERAL_CTA = 0.2         # a literal-only CTA block starts within this of its trigger
HOOK_S = (2.0, 3.0)
TEXT_KINDS = ("main", "accent", "accent-white")


def squash(s):
    """A term or a heard form as it is matched: norm per word, spaces and hyphens dropped ("U -Case" -> "ucase")."""
    return "".join(norm(p) for p in re.split(r"[\s\-]+", s))


def load_rules(script):
    """The text rules of a resolved script; censor "@set" entries expanded."""
    sets = script.get("censor_sets", {})
    censor = []
    for e in script.get("censor", []):
        if e.startswith("@") and e[1:] not in sets:
            raise SystemExit(f"censor: unknown set {e}; known: {', '.join('@' + s for s in sorted(sets))}")
        for w in sets[e[1:]] if e.startswith("@") else [e]:
            if w not in censor:
                censor.append(w)
    return {"terms": script.get("terms", {}), "censor": censor,
            "cta_phrases": [re.compile(p) for p in script.get("cta_phrases", [])],
            "cta_check": bool(script.get("cta_check", False)), "presets": script.get("presets", {})}


def presets_of(b):
    p = b.get("preset", [])
    return [p] if isinstance(p, str) else list(p)


# ----------------------------------------------------------------------------- terms

def variants(terms):
    """[(heard letters, prefix?, display)], longest first. Variants equal to their display are skipped: rewriting
    them would collapse «Plex» onto «Repair»'s time."""
    out = []
    for d, spec in terms.items():
        for h in spec.get("heard_as", []):
            hs = squash(h.rstrip("*"))
            if hs and hs != squash(d):
                out.append((hs, h.endswith("*"), d))
    return sorted(out, key=lambda v: -len(v[0]))


def canon_word(word, terms):
    """A token's match word, with a typed heard form ("рілс", "u-case") replaced by its display's letters."""
    w = squash(word)
    for hs, pre, d in variants(terms):
        if w == hs or (pre and w.startswith(hs)):
            return squash(d)
    return word


def canon_transcript(T, owner, starts, terms, spoken):
    """Heard variants in the transcript string T (norm words joined; owner: each character's word index; starts:
    the word start offsets) become squash(display), owned by their first word. Only terms whose display letters
    are in `spoken` (the script's spoken match words joined) apply. Returns (T, owner, hits), hits [(first word,
    last word, display)] in transcript order."""
    ends = set(starts[1:]) | {len(T)}
    found = []
    for hs, pre, d in variants(terms):
        if squash(d) not in spoken:
            continue
        pat = re.compile("-?".join(map(re.escape, hs)))
        for s in sorted(set(starts)):
            m = pat.match(T, s)
            if not m or m.end() == s:
                continue
            e = min(x for x in ends if x >= m.end()) if pre else m.end()
            if e not in ends or any(a < e and s < b for a, b, _ in found):
                continue
            found.append((s, e, d))
    found.sort()
    hits = [(owner[a], owner[b - 1], d) for a, b, d in found]
    for a, b, d in reversed(found):
        sq = squash(d)
        T = T[:a] + sq + T[b:]
        owner = owner[:a] + [owner[a]] * len(sq) + owner[b:]
    return T, owner, hits


def term_runs(tokens, terms):
    """[(i, j, display)]: runs tokens[i:j] of text tokens that spell a term's display ("repair" "plex")."""
    disp = {squash(d): d for d in terms}
    out, i = [], 0
    while i < len(tokens):
        hit = None
        acc = ""
        for j in range(i, len(tokens)):
            if tokens[j]["kind"] not in TEXT_KINDS:
                break
            acc += squash(tokens[j]["text"])
            if acc in disp:
                hit = (i, j + 1, disp[acc])
            if not any(k.startswith(acc) for k in disp):
                break
        if hit:
            out.append(hit)
            i = hit[1]
        else:
            i += 1
    return out


# ----------------------------------------------------------------------------- censorship

def censor_index(word, entry):
    """The index, among the letters of `word`, of the letter `entry` masks; None when it does not match."""
    letters = "".join(re.findall(r"\w", word.lower()))
    e = entry.lower()
    if "*" in e:
        star = e.index("*")
        pat = "".join(r"\w" if c == "*" else re.escape(c) for c in e)
    else:
        star = next((i for i, c in enumerate(e) if i > 0 and c in VOWELS), 1)
        pat = re.escape(e)
    stem = pat if pat.endswith(r"\w") else re.sub(f"[{VOWELS}ьй]+$", "", pat)
    if len(re.sub(r"\\w|\\", "", stem)) < 3:
        stem = pat
    return star if re.match(stem, letters) else None


def mask_letter(text, i):
    """text with its i-th letter (\\w character) replaced by an ASCII *."""
    n = -1
    out = []
    for c in text:
        if re.match(r"\w", c):
            n += 1
            if n == i:
                out.append("*")
                continue
        out.append(c)
    return "".join(out)


def censored(text, entries):
    """text with the first matching entry's letter masked, or None."""
    for e in entries:
        i = censor_index(text, e)
        if i is not None:
            return mask_letter(text, i)
    return None


def display_pass(b, lines, rules, stats=None):
    """The display passes of one block, after alignment (tok["word"] is never touched): term display words are
    counted and coloured (a coloured term on accent tokens of a line without its own colour), spoken text tokens
    (and literal lines with "censor": true) are censored, then the block's "case" applies to every token but deco,
    labels and term words. stats: {"censored": Counter, "latin": Counter}."""
    stats = stats if stats is not None else {"censored": Counter(), "latin": Counter()}
    terms = rules["terms"]
    case = b.get("case")
    for spec in lines:
        toks = spec["tokens"]
        term_tok = set()
        for i, j, d in term_runs(toks, terms):
            term_tok.update(range(i, j))
            stats["latin"][d] += 1
            color = terms[d].get("color")
            if color and "color" not in spec and all(t["kind"] == "accent" for t in toks[i:j]):
                for t in toks[i:j]:
                    t["color"] = color
        for k, tok in enumerate(toks):
            if k in term_tok or tok["kind"] not in TEXT_KINDS:
                continue
            if rules["censor"] and ("word" in tok or spec.get("censor")):
                new = censored(tok["text"], rules["censor"])
                if new is not None:
                    tok["text"] = new
                    stats["censored"][re.sub(r"[^\w*ʼ'’\-]", "", new).lower()] += 1
            if case in ("upper", "lower"):
                tok["text"] = tok["text"].upper() if case == "upper" else tok["text"].lower()
    return stats


def display_tokens(script):
    """The tokens every line shows, censored and cased but without timing (the glyph check of doctor and
    resolve.py --check): one list of {text, kind} per line."""
    from build_timeline import tokenize
    rules = load_rules(script)
    out = []
    for sc in script.get("screens", []):
        for b in sc.get("blocks") or [sc]:
            lines = []
            for ln in b["lines"]:
                spec = {"text": ln} if isinstance(ln, str) else dict(ln)
                spec["tokens"] = tokenize(spec.pop("text"), spec.get("literal", False))
                lines.append(spec)
            display_pass(b, lines, rules)
            out += [ln["tokens"] for ln in lines]
    return out


# ----------------------------------------------------------------------------- the spoken CTA

def cta_triggers(words, rules):
    """Spoken CTAs among heard words ({w, o, oe} in output order; edl.VoiceMap.heard_words): [{t, word, end}], the
    first trigger word of each group of hits less than 3 s apart."""
    out = []
    for w in words:
        n = norm(w["w"])
        if not n or not any(p.search(n) for p in rules["cta_phrases"]):
            continue
        if out and w["o"] - out[-1]["_last"] < CTA_MERGE:
            out[-1].update(end=w["oe"], _last=w["o"])
        else:
            out.append({"t": round(w["o"], 2), "word": w["w"].strip(), "end": round(w["oe"], 2), "_last": w["o"]})
    return [{k: v for k, v in c.items() if k != "_last"} for c in out]


def heard(script):
    from edl import EDL, VoiceMap
    edl = EDL(script.get("edl"), script.get("src_duration", script.get("duration")))
    return VoiceMap(edl, script.get("audio")).heard_words(load_json(ROOT / script["words"]))


# ----------------------------------------------------------------------------- lint (lint_edit.HOOKS)

def block_text(b):
    return " ".join(t["text"] for ln in b["lines"] for t in ln["tokens"])


def lint_text(script, ctx):
    """The text checks of lint_edit: CTA cards for spoken CTAs (cta_check), hook timing, alignment of terms and
    preset blocks, the {heard} grammar, typed heard forms and uncensored literal lines. Returns (fails, warns) as
    lists of (t, msg); ctx["hook"] gets the hook window (the inserts' checks keep inserts out of it)."""
    import build_timeline as bt
    fails, warns = [], []
    if not script.get("screens"):
        return fails, warns
    rules = load_rules(script)
    with contextlib.redirect_stdout(io.StringIO()):          # build_timeline's own alignment prints
        screens, info = bt.build_screens(script, bt.align_words(script), ctx["takes"], rules)
    blocks = [(sc, b) for sc in screens for b in sc["blocks"]]

    def window(sc, b):
        return b.get("t0", sc["t0"]), b.get("t1", min(sc["t1"], b.get("until", sc["t1"])))
    for sc, b in blocks:
        for ln in b["lines"]:
            for tok in ln["tokens"]:
                if tok["text"] == "" or tok.get("word") == "":
                    fails.append((window(sc, b)[0], f"empty display or empty {{}} in «{block_text(b)}»: every shown "
                                                    f"word is spoken (literal lines show unspoken text)"))
                elif "word" in tok and norm(tok["text"]) == tok["word"] and \
                        canon_word(tok["word"], rules["terms"]) != tok["word"]:      # typed, not an inline {heard}
                    d = next(d for hs, pre, d in variants(rules["terms"])
                             if squash(tok["word"]) == hs or (pre and squash(tok["word"]).startswith(hs)))
                    warns.append((tok["t"], f"«{tok['text']}» is how «{d}» is heard: type the display form {d}"))
            if ln.get("literal") and not ln.get("censor") and rules["censor"]:
                plain = [t["text"] for t in ln["tokens"] if t["kind"] in TEXT_KINDS and censored(t["text"], rules["censor"])]
                if plain:
                    warns.append((ln["tokens"][0]["t"], f"the literal line «{' '.join(t['text'] for t in ln['tokens'])}» "
                                                        f"shows {', '.join(f'«{w}»' for w in plain)} uncensored "
                                                        f"(\"censor\": true masks it)"))
    for tok, b, hard in info["not_found"]:
        (fails if hard else warns).append((tok["t"], f"«{tok['text']}» NOT FOUND in the transcript"
                                                     + (" (a term, {heard} or preset word: fix the spelling or {heard})"
                                                        if hard else "")))
    hooks = [window(sc, b) + (b,) for sc, b in blocks if "hook" in presets_of(b)]
    ctas = [(sc, b) for sc, b in blocks if "cta" in presets_of(b)]
    for t0, t1, b in hooks:
        if not HOOK_S[0] <= t1 - t0 <= HOOK_S[1] or t0 > 1e-6:
            warns.append((t0, f"hook shown {t0:.2f}-{t1:.2f} s: show it from 0 for {HOOK_S[0]:.0f}-{HOOK_S[1]:.0f} s"))
        n = sum(1 for ln in b["lines"] for t in ln["tokens"] if t["kind"] in TEXT_KINDS)
        if n > 7:
            warns.append((t0, f"hook has {n} words: keep it to 7"))
    if hooks:
        ctx["hook"] = hooks[0][:2]
    hold = (rules["presets"].get("cta") or {}).get("hold", 2.0)
    for sc, b in ctas:
        t0, t1 = window(sc, b)
        if t1 - t0 < hold - 1e-3:
            fails.append((t0, f"CTA «{block_text(b)}» shown {t1 - t0:.2f} s, cut by the reel end: extend the last edl "
                              f"segment or end with a hold ({{\"hold\": t, \"dur\": d}})"))
        n = sum(1 for ln in b["lines"] for t in ln["tokens"] if t["kind"] in TEXT_KINDS)
        if n > 5:
            warns.append((t0, f"CTA «{block_text(b)}» has {n} words: keep it to 5"))
        for h0, h1, _ in hooks:
            if t0 < h1 and h0 < t1:
                fails.append((t0, f"CTA {t0:.2f}-{t1:.2f} s while the hook is up ({h0:.2f}-{h1:.2f} s)"))
    if rules["cta_check"]:
        for c in cta_triggers(heard(script), rules):
            ok = False
            for sc, b in ctas:
                spoken = [t for ln in b["lines"] for t in ln["tokens"] if "word" in t]
                if spoken:
                    first = min(t["t"] for t in spoken)
                    owns = any(id(t) in info["owner"] and abs(info["words"][info["owner"][id(t)][0]]["s"] - c["t"]) < 0.02
                               for t in spoken)
                    ok |= owns and first >= c["t"] - CTA_LEAD - 1e-6
                else:
                    ok |= abs(window(sc, b)[0] - c["t"]) <= LITERAL_CTA + 1e-6
            if not ok:
                fails.append((c["t"], f"spoken CTA «{c['word']}» (trigger {c['t']:.2f}) is not in a CTA block: give "
                                      f"the block of that phrase \"preset\": \"cta\""))
    ctx["cta"] = [window(sc, b) for sc, b in ctas]
    ctx["cues"] += info["sfx"]                               # the CTA chime, for lint's sound checks
    return fails, warns


def term_hits(script, words, rules):
    """[(first word, last word, display)]: the term rewrites of the heard words (edl.VoiceMap.heard_words), as
    build_timeline aligns them (only terms whose display the script's spoken lines type)."""
    from build_timeline import tokenize
    spoken = ""
    for sc in script.get("screens", []):
        for b in sc.get("blocks") or [sc]:
            for ln in b["lines"]:
                spec = {"text": ln} if isinstance(ln, str) else ln
                if not spec.get("literal"):
                    spoken += "".join(canon_word(t["word"], rules["terms"]) for t in tokenize(spec["text"]) if "word" in t)
    T, owner, starts = "", [], []
    for k, w in enumerate(words):
        n = norm(w["w"])
        starts.append(len(T))
        T += n
        owner += [k] * len(n)
    return canon_transcript(T, owner, starts, rules["terms"], spoken)[2] if rules["terms"] else []
