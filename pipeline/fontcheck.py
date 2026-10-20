"""Can the reel's fonts draw every character it shows? A pure-Python read of each font's cmap (sfnt subtable formats 4
and 12): no Chrome, no reference fonts. Chrome would silently draw a missing glyph in some system font.

python fontcheck.py <font> [<font> ...]     prints the probe characters each font lacks
"""
import struct
import sys
from functools import lru_cache

UA = "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
LATIN = "abcdefghijklmnopqrstuvwxyz"
PROBE = "ʼ’№«»–—*" + UA + UA.upper() + LATIN + LATIN.upper() + "0123456789"   # every font must have these
STYLE_OF = {"main": "main", "deco": "main", "accent": "accent", "accent-white": "accent", "label": "label"}  # overlay.html


def faces(fonts, alias):
    """style.fonts[alias] as a list of faces (a single face may be written as a dict)."""
    f = (fonts or {}).get(alias) or []
    return [f] if isinstance(f, dict) else list(f)


@lru_cache(maxsize=None)
def cmap_codepoints(path):
    """The code points a TTF/OTF maps to a glyph (Unicode subtables 3/1, 3/10, 0/3, 0/4)."""
    with open(path, "rb") as f:
        data = f.read()
    n_tables = struct.unpack(">H", data[4:6])[0]
    off = next((toff for i in range(n_tables)
                for tag, _, toff, _ in [struct.unpack(">4sIII", data[12 + 16 * i:28 + 16 * i])] if tag == b"cmap"), None)
    cps = set()
    if off is None:
        return frozenset()
    for i in range(struct.unpack(">H", data[off + 2:off + 4])[0]):
        pid, eid, sub = struct.unpack(">HHI", data[off + 4 + 8 * i:off + 12 + 8 * i])
        if (pid, eid) not in ((3, 1), (3, 10), (0, 3), (0, 4)):
            continue
        s = off + sub
        fmt = struct.unpack(">H", data[s:s + 2])[0]
        if fmt == 4:
            n2 = struct.unpack(">H", data[s + 6:s + 8])[0]
            ends = struct.unpack(f">{n2 // 2}H", data[s + 14:s + 14 + n2])
            starts = struct.unpack(f">{n2 // 2}H", data[s + 16 + n2:s + 16 + 2 * n2])
            deltas = struct.unpack(f">{n2 // 2}h", data[s + 16 + 2 * n2:s + 16 + 3 * n2])
            ro_pos = s + 16 + 3 * n2
            ros = struct.unpack(f">{n2 // 2}H", data[ro_pos:ro_pos + n2])
            for k, (a, b) in enumerate(zip(starts, ends)):
                for c in range(a, min(b, 0xFFFE) + 1):
                    if ros[k] == 0:
                        g = (c + deltas[k]) & 0xFFFF
                    else:
                        p = ro_pos + 2 * k + ros[k] + 2 * (c - a)
                        g = struct.unpack(">H", data[p:p + 2])[0]
                        g = (g + deltas[k]) & 0xFFFF if g else 0
                    if g:
                        cps.add(c)
        elif fmt == 12:
            for k in range(struct.unpack(">I", data[s + 12:s + 16])[0]):
                a, b, _ = struct.unpack(">III", data[s + 16 + 12 * k:s + 28 + 12 * k])
                cps.update(range(a, b + 1))
    return frozenset(cps)


def check_glyphs(style, token_lines):
    """Problems (empty: OK) for the resolved style (style.fonts: {alias: face or [face]}, face["file"] absolute) and
    the display tokens, one list of {text, kind} per line. Each alias gets the characters of the token kinds drawn
    in it, plus the probe set; every face of the alias must have them all."""
    fonts = style.get("fonts", {})
    need = {alias: set() for alias in fonts}
    for st in ("main", "accent", "label"):
        need.setdefault(style[st]["family"], set())
    for toks in token_lines:
        for tok in toks:
            fam = style[STYLE_OF.get(tok["kind"], "main")]["family"]
            need[fam].update(c for c in tok["text"] if not c.isspace())
    problems = []
    for fam, chars in sorted(need.items()):
        if not faces(fonts, fam):
            problems.append(f"font family {fam} has no face in style.fonts")
        for face in faces(fonts, fam):
            cps = cmap_codepoints(face["file"])
            missing = sorted({c for c in chars | set(PROBE) if ord(c) not in cps})
            if missing:
                problems.append(f"font {fam} ({face['file']}) has no glyph for: "
                                + " ".join(c if c.isalnum() else f"{c}(U+{ord(c):04X})" for c in missing))
    return problems


if __name__ == "__main__":
    for f in sys.argv[1:]:
        missing = [c for c in PROBE if ord(c) not in cmap_codepoints(f)]
        print(f"{'FAIL' if missing else 'OK  '} {f}" + (f": no glyph for {''.join(missing)}" if missing else ""))
