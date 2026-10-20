"""The creator's Ukrainian brief (inbox/<reel>/brief.md, the template is docs/creator/brief_template.uk.md) as data.

python brief.py <brief.md>      prints the parsed brief as JSON

Each command is a labelled line («ХУК: …») or, for the free phrases, plain text anywhere: «без музики», «без правок
стилю», «коли кажу … — покажи … [на весь екран]». Lines starting with ">" are the template's hints and are ignored.
A value may also sit under its label: one line for the one-word labels, one paragraph for ХУК, every line up to the
next label for ВСТАВКИ, ІДЕЯ, РЕФЕРЕНС and ПРИМІТКИ. A free phrase on its own line is a command, never part of the
value above it (ІДЕЯ, РЕФЕРЕНС and ПРИМІТКИ keep it in their text too). Values keep her wording: mapping brand and
format words to ids and checking the script against the brief is the skill's and lint's job.

parse(path) / parse_text(text) -> {"brand", "format", "idea", "hook", "code_word", "music", "censor", "inserts",
    "no_style_changes", "speed", "reference", "notes"}
  music: a track name, None (not given: the brand's bed) or False («без музики»)
  censor: words (lowercase); «стандартна» expands to the studio's censor_sets.standard
  inserts: [{"when": phrase, "show": file name or description, "fullscreen": bool}]; a line under ВСТАВКИ: without
           «коли кажу …» keeps her words in "show" with "when": None
  speed: a float («ШВИДКІСТЬ: 1,2») or None
Where each lands in the script: censor -> "censor+"; hook -> the literal line of the "preset": "hook" block;
code_word -> an accent token of the "preset": "cta" block; inserts -> "inserts"; music -> audio.music.file, False ->
"audio": {"music": null}; speed -> inbox.py prep --speed (clips.json "speed"), within the format's grammar.speed_max.
"""
import json
import re
import sys
from pathlib import Path

from common import PIPE

LABELS = {"бренд": "brand", "формат": "format", "ідея": "idea", "хук": "hook", "кодове слово": "code_word",
          "музика": "music", "цензура": "censor", "вставки": "inserts", "без правок стилю": "no_style_changes",
          "швидкість": "speed", "референс": "reference", "примітки": "notes"}
LABEL = re.compile(r"^\s*(" + "|".join(sorted(LABELS, key=len, reverse=True)) + r")\s*:\s*(.*)$", re.I)
INSERT = re.compile(r"коли\s+(?:я\s+)?кажу\s+(.+?)\s+[—–-]+\s*(?:покажи|показати|покажіть)\s+(.+)", re.I)
FULL = re.compile(r"[\s,]*\(?на\s+весь\s+екран\)?[\s.]*$", re.I)
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


def insert_item(text):
    """«коли кажу «набір» — покажи set.jpg на весь екран» -> {"when", "show", "fullscreen"}, or None."""
    m = INSERT.search(text)
    if not m:
        return None
    show, full = m.group(2).strip(), False
    if FULL.search(show):
        show, full = FULL.sub("", show).strip(), True
    return {"when": unquote(m.group(1).strip(" ,")), "show": unquote(show.rstrip(".;")), "fullscreen": full}


def speed_value(value):
    m = re.search(r"\d+(?:[.,]\d+)?", value)
    return float(m.group(0).replace(",", ".")) if m else None


def insert_line(line):
    """A line under ВСТАВКИ: as an insert; without «коли кажу …» her words are kept in "show", never dropped."""
    item = line.lstrip("-•*").strip()
    ins = insert_item(item)
    if not ins:
        full = bool(FULL.search(item))
        ins = {"when": None, "show": FULL.sub("", item).strip() if full else item, "fullscreen": full}
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


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit("usage: brief.py <brief.md>")
    print(json.dumps(parse(sys.argv[1]), ensure_ascii=False, indent=1))
