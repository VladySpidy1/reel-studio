"""Resolve a reel script into what the pipeline renders: studio defaults -> brand -> format -> script (ADR-0002).
Every entry point (build, build_timeline, export_fcpxml, lint_edit, times, preview) loads scripts through
load_script, so a brand's look and a format's rules reach all of them and nothing is copied into script.json.

python resolve.py <script> [--json] [--check]   layers, warnings and the key settings; --json prints the resolved
                                                script; --check also checks the font files and glyphs (exit 1)
python resolve.py --list                        brand and format ids with their aliases

Layers, lowest first: pipeline/style_default.json (as "style") + pipeline/studio_default.json; brands/<brand>/
brand.json; formats/<format>/format.json; the script. A script without "brand" and "format" resolves to exactly
what it resolved to before brands existed (style_default.json is the TOSUMI look).
- A dict deep-merges into a dict; a list, scalar or null replaces. "<key>+": [...] appends to the inherited list
  (no duplicates), at any depth, e.g. "style": {"layout": {"exclude+": [[x0, y0, x1, y1]]}}.
- A layer that sets another audio.music.file drops the lower layers' offset and dropouts (they belong to a track);
  a resolved audio.music without a file is None (music off).
- Brands own the look. A format sets structure only (FORMAT_KEYS): grade only as null, audio.music only as null or
  fades/duck, presets only with structure keys, style only as {"layers": []}. Anything else is an error naming the
  key and the file; unknown keys are warnings (typo guard).
- "preset": "name" (or a list) on a block merges presets[name] under it (the block's own keys win; "lines" merges
  into every line); on a line it merges under the line. The name stays on the item.
- "color": "@name" anywhere resolves from "colors"; audio.sfx cues {"event", "peak_at"} expand from sfx_palette,
  rotating its variants by occurrence (a variant is a cue or a list of cues with "dt": a stack).
- style.fonts {alias: face | [face]}: each face's file becomes absolute plus a file:// "url" for overlay.html.
"""
import argparse
import copy
import json
import sys
from pathlib import Path

from common import PIPE, ROOT, load_json, short

BRANDS, FORMATS = ROOT / "brands", ROOT / "formats"
NUM = (int, float)
TYPES = {"brand": str, "format": str, "name": str, "aliases": list, "style": dict, "colors": dict, "terms": dict,
         "censor": list, "censor_sets": dict, "cta_phrases": list, "cta_check": bool, "presets": dict,
         "sfx_palette": dict, "sfx_banned": list, "lint": dict, "grammar": dict, "grade": (dict, type(None)),
         "audio": dict, "camera": dict, "source": str, "words": str, "masks": str, "track": str, "src_duration": NUM,
         "duration": NUM, "takes": list, "edl": list, "screens": list, "doodles": list, "inserts": list, "trim": dict}
BRAND_KEYS = {"name", "aliases", "style", "colors", "terms", "censor", "cta_phrases", "grade", "audio", "sfx_palette",
              "sfx_banned", "lint", "presets"}
FORMAT_KEYS = {"name", "aliases", "camera", "grade", "audio", "presets", "lint", "grammar", "cta_check", "style"}
SCRIPT_KEYS = set(TYPES) - {"name", "aliases", "censor_sets"}
LINT_KEYS = {"sfx_banned", "whoosh_on_cuts", "punch_min", "slow_push", "dead_span", "vignette_max", "beat_cuts"}
GRAMMAR_KEYS = {"trim", "speed_max", "insert"}
PRESET_STRUCT = {"literal", "t", "until", "fade", "behind", "place", "dur", "hold", "tail", "reveal", "lines"}
LINE_STRUCT = {"literal", "t"}
MUSIC_FORMAT = {"fade_in", "fade_out", "duck"}


def fail(msg):
    sys.exit(f"resolve: {msg}")


def ids(root, fname):
    return sorted(p.parent.name for p in root.glob(f"*/{fname}"))


def merge(base, over):
    """`over` merged onto `base` (neither is changed): dicts deep-merge, anything else replaces, "<key>+" appends."""
    out = dict(base)
    for k, v in over.items():
        if not k.endswith("+"):
            out[k] = merge(out[k] if isinstance(out.get(k), dict) else {}, v) if isinstance(v, dict) else copy.deepcopy(v)
    for k, v in over.items():
        if k.endswith("+"):
            have = out.get(k[:-1], [])
            if not isinstance(v, list) or not isinstance(have, list):
                fail(f"{k} appends a list to a list (got {type(v).__name__} onto {type(have).__name__})")
            out[k[:-1]] = have + [copy.deepcopy(x) for x in v if x not in have]
    return out


def merge_layer(acc, layer):
    """merge() plus the music track rule: another file drops the lower layers' offset and dropouts."""
    m, low = (layer.get("audio") or {}).get("music"), (acc.get("audio") or {}).get("music")
    if isinstance(m, dict) and "file" in m and isinstance(low, dict) and m["file"] != low.get("file"):
        acc = {**acc, "audio": {**acc["audio"],
                                "music": {k: v for k, v in low.items() if k not in ("offset", "dropouts")}}}
    return merge(acc, layer)


def check_layer(layer, kind, path, warns):
    """Unknown keys warn; a known key of the wrong type, or a key a format may not set, is an error."""
    where = short(path)
    own = {"brand": BRAND_KEYS, "format": FORMAT_KEYS, "script": SCRIPT_KEYS}[kind]
    for k, v in layer.items():
        key = k[:-1] if k.endswith("+") else k
        if key not in TYPES:
            warns.append(f"{where}: unknown key {k!r}")
            continue
        if key not in own:
            if kind == "format":
                fail(f"{where}: a format may not set {k!r} (brands own the look; formats set structure)")
            warns.append(f"{where}: {k!r} is not a {kind} key")
        want = list if k.endswith("+") else TYPES[key]
        if not isinstance(v, want):
            names = [t.__name__.replace("NoneType", "null") for t in (want if isinstance(want, tuple) else (want,))]
            fail(f"{where}: {k} must be {' or '.join(names)}, not {type(v).__name__}")
    for sub, known in (("lint", LINT_KEYS), ("grammar", GRAMMAR_KEYS)):
        for k in layer.get(sub) or {}:
            if k.rstrip("+") not in known:
                warns.append(f"{where}: unknown key {sub}.{k}")
    if kind == "brand":
        safe = ((layer.get("style") or {}).get("layout") or {}).get("safe")
        if safe and wider(safe):
            fail(f"{where}: style.layout.safe {safe} is wider than the studio's crop-safe area")
    if kind != "format":
        return

    def bad(key, why):
        fail(f"{where}: a format may not set {key} ({why})")
    if "grade" in layer and layer["grade"] is not None:
        bad("grade", "only null: the grade is the brand's look")
    if "style" in layer and layer["style"] != {"layers": []}:
        bad("style", "only {\"layers\": []}, which switches the brand layers off")
    for k, v in (layer.get("audio") or {}).items():
        if k != "music":
            bad(f"audio.{k}", "only audio.music")
        elif v is not None and (not isinstance(v, dict) or set(v) - MUSIC_FORMAT):
            bad("audio.music." + ",".join(sorted(set(v) - MUSIC_FORMAT)) if isinstance(v, dict) else "audio.music",
                "only null or fade_in/fade_out/duck: the track's file, gain and offset belong to the brand")
    for name, p in (layer.get("presets") or {}).items():
        if not isinstance(p, dict) or not isinstance(p.get("lines", {}), dict):
            bad(f"presets.{name}", "a preset is a dict whose \"lines\" is a dict")
        for k, v in p.items():
            if k not in PRESET_STRUCT:
                bad(f"presets.{name}.{k}", "look keys belong to the brand")
            if k == "lines":
                for lk in v:
                    if lk not in LINE_STRUCT:
                        bad(f"presets.{name}.lines.{lk}", "look keys belong to the brand")


def wider(safe, studio=None):
    s = studio or load_json(PIPE / "style_default.json")["layout"]["safe"]
    return safe[0] < s[0] or safe[1] < s[1] or safe[2] > s[2] or safe[3] > s[3]


def apply_presets(script):
    """Merge each named preset under its block or line; the name stays on the item (lint and the layout use it)."""
    presets = script.get("presets", {})

    def look(names, where):
        out = {}
        for n in [names] if isinstance(names, str) else names:
            if n not in presets:
                fail(f"unknown preset {n!r} ({where}); known: {', '.join(sorted(presets))}")
            if not isinstance(presets[n], dict) or not isinstance(presets[n].get("lines", {}), dict):
                fail(f"preset {n!r} must be a dict whose \"lines\" is a dict")
            out = merge(out, presets[n])
        return out
    for si, sc in enumerate(script.get("screens", [])):
        for bi, b in enumerate(sc.get("blocks") or [sc]):
            lines_look = {}
            if "preset" in b:
                p = look(b["preset"], f"screen {si + 1} block {bi + 1}")
                lines_look = p.pop("lines", {})
                b.update({**merge(p, b), "lines": b["lines"]})
            for li, ln in enumerate(b.get("lines", [])):
                spec = {"text": ln} if isinstance(ln, str) else ln
                if not lines_look and "preset" not in spec:
                    continue
                base = lines_look
                if "preset" in spec:
                    base = merge(base, look(spec["preset"], f"screen {si + 1} block {bi + 1} line {li + 1}"))
                b["lines"][li] = merge(base, spec)


def resolve_colors(obj, colors):
    """"color": "@name" -> colors[name], anywhere; subtitle text is never touched."""
    items = obj.items() if isinstance(obj, dict) else enumerate(obj) if isinstance(obj, list) else ()
    for k, v in items:
        if k == "color" and isinstance(v, str) and v.startswith("@"):
            if v[1:] not in colors:
                fail(f"unknown colour {v}; known: {', '.join('@' + c for c in sorted(colors))}")
            obj[k] = colors[v[1:]]
        else:
            resolve_colors(v, colors)


def expand_sfx(cues, palette):
    """Cues {"event", "peak_at"} without "name" become the palette's sample(s); variants rotate by occurrence in
    time order. A cue's gain_db replaces a single sample's gain; on a stack it is an error."""
    nth, count = {}, {}
    for i, c in sorted(enumerate(cues), key=lambda ic: ic[1].get("peak_at", 0)):
        if "event" in c and "name" not in c:
            nth[i] = count.get(c["event"], 0)
            count[c["event"]] = nth[i] + 1
    out = []
    for i, c in enumerate(cues):
        if i not in nth:
            out.append(c)
            continue
        ev = c["event"]
        if ev not in palette:
            fail(f"unknown sfx event {ev!r}; known: {', '.join(sorted(palette))}")
        if "peak_at" not in c:
            fail(f"sfx event {ev!r} needs peak_at")
        v = palette[ev][nth[i] % len(palette[ev])]
        if isinstance(v, list) and "gain_db" in c:
            fail(f"sfx event {ev!r} at {c['peak_at']}: gain_db would flatten the stack's layered gains")
        for s in v if isinstance(v, list) else [{**v, **({"gain_db": c["gain_db"]} if "gain_db" in c else {})}]:
            out.append({**c, **{k: x for k, x in s.items() if k != "dt"},
                        "peak_at": round(c["peak_at"] + s.get("dt", 0), 4)})
    return out


def font_urls(style):
    """Each style.fonts face as a list entry with an absolute file and a file:// url (repo-relative files allowed)."""
    for alias, fs in style.get("fonts", {}).items():
        out = []
        for f in [fs] if isinstance(fs, dict) else fs:
            if not isinstance(f, dict) or "file" not in f:
                fail(f"style.fonts.{alias}: a face is {{\"file\", \"weight\", \"style\", \"features\"}}")
            p = Path(f["file"]) if Path(f["file"]).is_absolute() else ROOT / f["file"]
            out.append({**f, "file": str(p), "url": p.as_uri()})
        style["fonts"][alias] = out


def check_font_files(style, brand):
    for alias, fs in style.get("fonts", {}).items():
        for f in fs:
            p = Path(f["file"])
            if not p.is_file():
                fail(f"font file missing: {p} (licensed fonts are not in git; copy into "
                     f"brands/{brand or '<brand>'}/local/)")
            with open(p, "rb") as fh:
                magic = fh.read(4)
            if magic == b"ttcf":
                fail(f"font {alias}: {p} is a font collection; convert to .ttf/.otf")
            if magic not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
                fail(f"font {alias}: {p} is not a TTF/OTF font")


def load_script(path, check_fonts=False):
    """The resolved script. check_fonts: the font files must exist and be TTF/OTF (build, export, --check)."""
    path = Path(path)
    raw = load_json(path.resolve())
    warns = []
    check_layer(raw, "script", path, warns)
    studio_style = load_json(PIPE / "style_default.json")
    layers = [("studio", {**load_json(PIPE / "studio_default.json"), "style": studio_style})]
    names = {}
    for kind, root, fname in (("brand", BRANDS, "brand.json"), ("format", FORMATS, "format.json")):
        ident = raw.get(kind)
        if ident is None:
            continue
        if ident not in ids(root, fname):
            fail(f"unknown {kind} {ident!r}; known: {', '.join(ids(root, fname))}")
        layer = load_json(root / ident / fname)
        check_layer(layer, kind, root / ident / fname, warns)
        names[kind] = layer.pop("name", ident)
        layer.pop("aliases", None)
        layers.append((f"{kind} {ident}", layer))
    layers.append(("script", raw))
    if "brand" not in raw:
        warns.append("no brand: the studio look (= TOSUMI); set \"brand\"")
    safe = ((raw.get("style") or {}).get("layout") or {}).get("safe")
    if safe and wider(safe, studio_style["layout"]["safe"]):
        warns.append(f"style.layout.safe {safe} is wider than the studio's crop-safe area: text may be cut on phones")

    script = {}
    for _, layer in layers:
        script = merge_layer(script, layer)
    au = script.get("audio") or {}
    if "music" in au and not (au["music"] or {}).get("file"):
        au["music"] = None
    apply_presets(script)
    resolve_colors(script, script.get("colors", {}))
    if au.get("sfx"):
        au["sfx"] = expand_sfx(au["sfx"], script.get("sfx_palette", {}))
    style = script["style"]
    font_urls(style)
    if check_fonts:
        check_font_files(style, raw.get("brand"))
    for r in studio_style["layout"]["exclude"]:
        if r not in style["layout"].get("exclude", []):
            warns.append(f"style.layout.exclude drops {r} (the IG button rail); add rectangles with \"exclude+\"")
    script["_resolve"] = {"script": str(path.resolve()), "layers": [n for n, _ in layers], "names": names,
                          "warnings": warns}
    return script


def summary(script):
    """A few lines for the build log and the report: layers, fonts, look, music, grade, lint, grammar, warnings."""
    r, st = script["_resolve"], script["style"]
    m, g = (script.get("audio") or {}).get("music"), script.get("grade")
    out = ["resolve: " + " → ".join(r["layers"]),
           "  fonts: " + ", ".join(f"{a} {Path(f['file']).name}" for a, fs in st["fonts"].items() for f in fs),
           f"  look: accent {st['accent']['color']}, main {st['main']['weight']} {st['main']['size']} px, "
           f"leading {st['leading']}",
           "  music: " + (f"{m['file']} {m.get('gain_db', -20)} dB, offset {m.get('offset', 0)}, fades "
                          f"{m.get('fade_in', 0)} / {m.get('fade_out', 0)}" if m else "off"),
           "  grade: " + (", ".join(f"{k} {v}" for k, v in g.items()) if g else "off"),
           "  lint: " + json.dumps(script.get("lint", {}), ensure_ascii=False)]
    if script.get("grammar"):
        out.append("  grammar: " + json.dumps(script["grammar"], ensure_ascii=False))
    return "\n".join(out + [f"WARNING {w}" for w in r["warnings"]])


def display_tokens(script):
    """The tokens every line shows, without timing (the glyph check of --check)."""
    from build_timeline import tokenize
    out = []
    for sc in script.get("screens", []):
        for b in sc.get("blocks") or [sc]:
            for ln in b["lines"]:
                spec = {"text": ln} if isinstance(ln, str) else ln
                out.append(tokenize(spec["text"], spec.get("literal", False)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script", nargs="?")
    ap.add_argument("--json", action="store_true", help="print the resolved script")
    ap.add_argument("--check", action="store_true", help="check the font files and glyphs (exit 1 on failure)")
    ap.add_argument("--list", action="store_true", help="brand and format ids with their aliases")
    a = ap.parse_args()
    if a.list:
        for kind, root, fname in (("brands", BRANDS, "brand.json"), ("formats", FORMATS, "format.json")):
            print(f"{kind}:")
            for i in ids(root, fname):
                d = load_json(root / i / fname)
                print(f"  {i:15} {d.get('name', i)}: {', '.join(d.get('aliases', []))}")
        return 0
    if not a.script:
        ap.error("a script, or --list")
    script = load_script(a.script, check_fonts=a.check)
    if a.json:
        print(json.dumps({k: v for k, v in script.items() if k != "_resolve"}, ensure_ascii=False, indent=1))
    else:
        print(summary(script))
    if a.check:
        import fontcheck
        problems = fontcheck.check_glyphs(script["style"], display_tokens(script))
        for p in problems:
            print("FAIL", p)
        print("fonts: " + ("FAIL" if problems else "OK"))
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
