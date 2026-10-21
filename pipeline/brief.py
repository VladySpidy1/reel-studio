"""The creator's Ukrainian brief (inbox/<reel>/brief.md, the template is docs/creator/brief_template.uk.md) as data,
and the check that a script does what its brief asks (lint_edit runs it when brief.md sits next to the script).

python brief.py <brief.md>      prints the parsed brief as JSON

Each command is a labelled line («ХУК: …») or, for the free phrases, plain text anywhere: «без музики», «без правок
стилю», «коли кажу … — покажи … [на весь екран] [без звуку]». Lines starting with ">" are the template's hints and
are ignored. A value may also sit under its label: one line for the one-word labels, one paragraph for ХУК, every
line up to the next label for ВСТАВКИ, ІДЕЯ, РЕФЕРЕНС and ПРИМІТКИ. A free phrase on its own line is a command, never
part of the value above it (ІДЕЯ, РЕФЕРЕНС and ПРИМІТКИ keep it in their text too). Values keep her wording: mapping
brand and format words to ids and checking the script against the brief is the skill's and lint's job.

parse(path) / parse_text(text) -> {"brand", "format", "idea", "hook", "code_word", "music", "censor", "inserts",
    "no_style_changes", "speed", "reference", "notes"}
  music: a track name, None (not given: the brand's bed) or False («без музики»)
  censor: words (lowercase); «стандартна» expands to the studio's censor_sets.standard
  inserts: [{"when": phrase, "show": file name or description, "fullscreen": bool, "silent": bool}]: «на весь екран»
           and «без звуку» at the end, in either order, set the flags; a line under ВСТАВКИ: without «коли кажу …»
           keeps her words in "show" with "when": None
  speed: a float («ШВИДКІСТЬ: 1,2») or None
Where each lands in the script: censor -> "censor+"; hook -> the literal line of the "preset": "hook" block;
code_word -> an accent token of the "preset": "cta" block; inserts -> "inserts"; music -> audio.music.file, False ->
"audio": {"music": null}; speed -> inbox.py prep --speed (clips.json "speed"), within the format's grammar.speed_max.

check(brief, script) -> (fails, warns), lists of (t, msg) like lint_edit's (t 0.0 for script-level findings), on the
resolved script (resolve.load_script). FAIL: a brand other than the brief's; a ХУК that is not the text of the
"preset": "hook" block; a КОДОВЕ СЛОВО that is not a spoken (aligned) accent word of a "preset": "cta" block; a
ЦЕНЗУРА word missing from the censor list; music other than the one asked, or music despite «без музики»; footage
ingested at another speed than asked (or than the format allows). WARN: a brand or format word it cannot map, another
format than the brief's (subtitles-only for baked graphics is the skill's call, reported), fewer inserts than asked
or a named file not used, «на весь екран» not full-screen, «без звуку» with a sound, a speed the format caps, and
with «без правок стилю» script style keys other than layout, presets or doodles.
"""
import json
import re
import sys
from pathlib import Path

from common import PIPE, ROOT, norm

LABELS = {"бренд": "brand", "формат": "format", "ідея": "idea", "хук": "hook", "кодове слово": "code_word",
          "музика": "music", "цензура": "censor", "вставки": "inserts", "без правок стилю": "no_style_changes",
          "швидкість": "speed", "референс": "reference", "примітки": "notes"}
LABEL = re.compile(r"^\s*(" + "|".join(sorted(LABELS, key=len, reverse=True)) + r")\s*:\s*(.*)$", re.I)
INSERT = re.compile(r"коли\s+(?:я\s+)?кажу\s+(.+?)\s+[—–-]+\s*(?:покажи|показати|покажіть)\s+(.+)", re.I)
FULL = re.compile(r"[\s,]*\(?на\s+весь\s+екран\)?[\s.]*$", re.I)
SILENT = re.compile(r"[\s,]*\(?без\s+звуку\)?[\s.]*$", re.I)
NO_MUSIC = re.compile(r"\bбез\s+музики\b", re.I)
NO_STYLE = re.compile(r"\bбез\s+правок\s+стилю\b", re.I)
FREE_TEXT = ("idea", "notes", "reference")
YES = {"так", "да", "yes", "+", "true"}
NO = {"ні", "нет", "no", "-", "false"}
CENSOR_SETS = {"стандартна": "standard", "стандартний": "standard", "стандарт": "standard"}
QUOTES = [("«", "»"), ("\"", "\""), ("“", "”"), ("„", "“"), ("'", "'")]


def unquote(s):
    s = s.strip()
    for a, b in QUOTES:
        if len(s) >= 2 and s.startswith(a) and s.endswith(b):
            return s[len(a):-len(b)].strip()
    return s


def censor_words(value):
    """«гроші, знижка» -> ["гроші", "знижка"]; a set name («стандартна») -> that set's words."""
    sets = None
    out = []
    for w in re.split(r"[,;]", value):
        w = unquote(w).lower()
        if w in CENSOR_SETS:
            if sets is None:
                sets = json.loads((PIPE / "studio_default.json").read_text(encoding="utf-8")).get("censor_sets", {})
            out += [x for x in sets.get(CENSOR_SETS[w], []) if x not in out]
        elif w and w not in out:
            out.append(w)
    return out


def show_flags(show):
    """«set.jpg на весь екран без звуку» -> ("set.jpg", fullscreen, silent): the two endings in either order."""
    flags = {FULL: False, SILENT: False}
    while True:
        rx = next((rx for rx in flags if rx.search(show)), None)
        if rx is None:
            return show.strip(), flags[FULL], flags[SILENT]
        show, flags[rx] = rx.sub("", show), True


def insert_item(text):
    """«коли кажу «набір» — покажи set.jpg на весь екран» -> {"when", "show", "fullscreen", "silent"}, or None."""
    m = INSERT.search(text)
    if not m:
        return None
    show, full, silent = show_flags(m.group(2).strip())
    return {"when": unquote(m.group(1).strip(" ,")), "show": unquote(show.rstrip(".;")), "fullscreen": full,
            "silent": silent}


def speed_value(value):
    m = re.search(r"\d+(?:[.,]\d+)?", value)
    return float(m.group(0).replace(",", ".")) if m else None


def insert_line(line):
    """A line under ВСТАВКИ: as an insert; without «коли кажу …» her words are kept in "show", never dropped."""
    item = line.lstrip("-•*").strip()
    ins = insert_item(item)
    if not ins:
        show, full, silent = show_flags(item)
        ins = {"when": None, "show": show, "fullscreen": full, "silent": silent}
    return ins


def belongs(key, lines, line):
    """Is a plain line under label `key` (with `lines` so far) part of its value? A free phrase is a command of its
    own, except an insert under ВСТАВКИ; ІДЕЯ, РЕФЕРЕНС and ПРИМІТКИ keep every line (and are scanned for them)."""
    if key in FREE_TEXT:
        return True
    if key == "inserts":
        return bool(INSERT.search(line)) or not (NO_MUSIC.search(line) or NO_STYLE.search(line))
    if INSERT.search(line) or NO_MUSIC.search(line) or NO_STYLE.search(line):
        return False
    return key == "hook" or not lines             # the other values are one line, on the label's or the next one


def parse_text(text):
    blocks, loose, cur = [], [], None             # [key, value lines]; lines outside any label
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith("#") or not line and cur and cur[0] == "hook" and cur[1]:
            cur = None                            # a heading ends a block; a blank line ends the hook's paragraph
        if not line or line.startswith((">", "#")):
            continue
        m = LABEL.match(line)
        if m:
            cur = [LABELS[m.group(1).lower()], [m.group(2).strip()] if m.group(2).strip() else []]
            blocks.append(cur)
        elif cur and belongs(cur[0], cur[1], line):
            cur[1].append(line)
        else:
            loose.append(line)
    b = {"brand": None, "format": None, "idea": None, "hook": None, "code_word": None, "music": None, "censor": [],
         "inserts": [], "no_style_changes": False, "speed": None, "reference": None, "notes": None}
    free_lines = list(loose)                      # where the free phrases count: chat text, ІДЕЯ, ПРИМІТКИ, РЕФЕРЕНС
    for key, lines in blocks:
        value = " ".join(lines)
        if key in FREE_TEXT:
            b[key] = "\n".join(([b[key]] if b[key] else []) + lines) or None
            free_lines += lines
        elif key == "inserts":
            b["inserts"] += [insert_line(ln) for ln in lines]
        elif key == "music":
            b["music"] = False if NO_MUSIC.search(value) or value.lower() in NO else unquote(value) or None
        elif key == "censor":
            b["censor"] = censor_words(",".join(lines))
        elif key == "no_style_changes":
            b["no_style_changes"] = value.lower() in YES
        elif key == "speed":
            b["speed"] = speed_value(value)
        elif lines:
            b[key] = unquote("\n".join(lines) if key == "hook" else value)
    for line in free_lines:
        ins = insert_item(line.lstrip("-•*").strip())
        if ins:
            b["inserts"].append(ins)
        if NO_MUSIC.search(line):
            b["music"] = False
        if NO_STYLE.search(line):
            b["no_style_changes"] = True
    return b


def parse(path):
    return parse_text(Path(path).read_text(encoding="utf-8"))


# ----------------------------------------------------------------------------- check (lint_edit)

def ident(kind, word):
    """The brands/ or formats/ id for her word: an id, a display name or an alias in any case, or None."""
    w = word.strip().lower()
    for p in sorted((ROOT / kind).glob(f"*/{kind[:-1]}.json")):
        d = json.loads(p.read_text(encoding="utf-8"))
        if w in [p.parent.name, d.get("name", "").lower()] + [a.lower() for a in d.get("aliases", [])]:
            return p.parent.name
    return None


def words_of(text):
    """The words a line shows, as compared with her wording: markup and {heard} dropped, norm()."""
    from build_timeline import tokenize
    words = (norm(t["text"]) for t in tokenize(text, literal=True) if t["kind"] not in ("deco", "label"))
    return [w for w in words if w] if text else []                  # a free-standing «—», «!» or «…» is no word


def blocks_with(script, preset):
    from text_rules import presets_of
    return [b for sc in script.get("screens", []) for b in sc.get("blocks") or [sc] if preset in presets_of(b)]


def code_word_tokens(script, word):
    """(accent tokens of the CTA blocks that are the code word, the not-found tokens among them): the CTA blocks
    aligned as the build aligns them."""
    import contextlib
    import io

    import build_timeline as bt
    import text_rules
    from edl import EDL
    from lint_edit import takes_out
    edl = EDL(script.get("edl"), script.get("src_duration", script.get("duration")))
    with contextlib.redirect_stdout(io.StringIO()):          # build_timeline's own alignment prints
        screens, info = bt.build_screens(script, bt.align_words(script), takes_out(script, edl))
    want = text_rules.squash(word)
    toks = [t for sc in screens for b in sc["blocks"] if "cta" in text_rules.presets_of(b) for ln in b["lines"]
            for t in ln["tokens"] if t["kind"] == "accent"
            and want in (text_rules.squash(t.get("word", "")), text_rules.squash(t["text"]))]
    lost = {id(t) for t, _, _ in info["not_found"]}
    return toks, [t for t in toks if "word" not in t or id(t) in lost]


def check(b, script):
    """Does the resolved script do what the brief asks? (fails, warns) as lists of (t, msg)."""
    import assets
    import text_rules
    fails, warns = [], []
    fail = lambda m: fails.append((0.0, "brief: " + m))
    warn = lambda m: warns.append((0.0, "brief: " + m))
    raw = json.loads(Path(script["_resolve"]["script"]).read_text(encoding="utf-8"))

    for kind, key in (("brands", "brand"), ("formats", "format")):
        if b[key]:
            want = ident(kind, b[key])
            if want is None:
                warn(f"{key} «{b[key]}» is not a known id or alias (resolve.py --list): check \"{key}\" by hand")
            elif raw.get(key) != want:
                (fail if key == "brand" else warn)(
                    f"{key} «{b[key]}» is {want}, the script says {raw.get(key)!r}"
                    + (" (another format: say why in the report)" if key == "format" else ""))

    if b["hook"]:
        hooks = blocks_with(script, "hook")
        shown = [w for h in hooks[:1] for ln in h["lines"]
                 for w in words_of(ln["text"] if isinstance(ln, dict) else ln)]
        if not hooks:
            fail(f"ХУК «{b['hook']}» has no \"preset\": \"hook\" block")
        elif shown != words_of(b["hook"]):
            fail(f"ХУК «{b['hook']}» is not the hook block's text «{' '.join(shown)}»: keep her words verbatim "
                 f"(split into lines only)")

    if b["code_word"]:
        if not blocks_with(script, "cta"):
            fail(f"КОДОВЕ СЛОВО «{b['code_word']}» has no \"preset\": \"cta\" block")
        else:
            toks, lost = code_word_tokens(script, b["code_word"])
            if not toks:
                fail(f"КОДОВЕ СЛОВО «{b['code_word']}» is not an accent word (*…*) of the CTA block")
            elif len(lost) == len(toks):
                fail(f"КОДОВЕ СЛОВО «{b['code_word']}» in the CTA block is not aligned to what she says (a literal "
                     f"line, or NOT FOUND): type it as heard, or display{{heard}}")

    have = text_rules.load_rules(script)["censor"]
    missing = [w for w in b["censor"] if w not in have]
    if missing:
        fail(f"ЦЕНЗУРА: {', '.join(missing)} not in the censor list (\"censor+\": [...])")

    music = (script.get("audio") or {}).get("music")
    if b["music"] is False and music:
        fail(f"«без музики», but the reel has music {Path(music['file']).name}: \"audio\": {{\"music\": null}}")
    elif b["music"]:
        if not music:
            fail(f"МУЗИКА «{b['music']}», but the reel has no music")
        else:
            name = Path(music["file"]).name
            rows, exact = assets.search("music", b["music"])
            words = b["music"].lower().split()
            if not (exact and name in [r["name"] for r in rows]) and \
                    not all(w in Path(name).stem.lower() for w in words):
                (warn if name in [r["name"] for r in rows] else fail)(
                    f"МУЗИКА «{b['music']}», the reel has {name} (assets.py music {b['music']})")

    ins = script.get("inserts", [])
    if len(ins) < len(b["inserts"]):
        warn(f"{len(b['inserts'])} inserts asked, the script has {len(ins)}: list each one left out under «Не "
             f"вставлено» with the reason")
    named = {Path(i.get("file", "")).name.lower(): i for i in ins}
    for want in b["inserts"]:
        f = Path(want["show"]).name.lower()
        if not Path(f).suffix:
            continue                                  # a description: the skill picks the file
        if f not in named:
            warn(f"insert «{want['show']}» is not among the script's inserts")
        else:
            if want["fullscreen"] and named[f].get("mode") != "full":
                warn(f"insert «{want['show']}» asked «на весь екран»: \"mode\": \"full\"")
            if want["silent"] and named[f].get("sfx", "") is not None:
                warn(f"insert «{want['show']}» asked «без звуку»: \"sfx\": null")

    smax = (script.get("grammar") or {}).get("speed_max")
    want = max(1.0, min(b["speed"], smax)) if b["speed"] and smax else 1.0      # never a slow-down
    if b["speed"] and b["speed"] != want:
        warn(f"ШВИДКІСТЬ {b['speed']:g}: this format allows " + (f"up to {smax:g}" if smax else "no speed-up")
             + f"; the reel is at {want:g} (say so in the report)")
    cj = ROOT / Path(script["source"]).parent / "clips.json"
    speeds = {c.get("speed", 1.0) for c in json.loads(cj.read_text(encoding="utf-8"))["clips"]} if cj.is_file() \
        else set()
    if speeds and speeds != {want}:
        fail(f"the footage was ingested at speed {', '.join(f'{s:g}' for s in sorted(speeds))}, the brief means "
             f"{want:g}: inbox.py prep <reel> --speed {want:g} --force")

    if b["no_style_changes"]:
        extra = [k for k in raw.get("style", {}) if k != "layout"] + [k for k in ("presets",) if raw.get(k)] + \
                (["doodles"] if raw.get("doodles") else [])
        if extra:
            warn(f"«без правок стилю», but the script sets {', '.join(extra)}: brand and format look only")
    return fails, warns


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if sys.argv[1:] in (["-h"], ["--help"]) else 2)
    print(json.dumps(parse(sys.argv[1]), ensure_ascii=False, indent=1))
