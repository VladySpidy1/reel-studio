"""Music and SFX files by name: the library (assets/music, assets/sfx, with their credits JSON) and the creator's own
files (assets/local/music, assets/local/sfx, never in git; or next to the reel's script, in its folder or inserts/).

python assets.py music [query]    tracks: the exact file for audio.music.file, title, bpm, tags
python assets.py sfx [query]      sounds: the name for audio.sfx, peak, what it is for

find() is exact and is what a render uses: a script names one file. search() is for writing the script only: it ranks
by the query's words, and offers similar names only when none has them all (similarity alone turns "whoosh_7" into
whoosh_06_synth). Nothing here writes a file.
"""
import argparse
import re
import subprocess
import sys
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

import numpy as np

from common import ROOT, load_json

LIB = ROOT / "assets"
LOCAL = LIB / "local"           # the creator's own files: local/music, local/sfx (gitignored)
EXTS = (".wav", ".mp3", ".m4a", ".aac", ".aif", ".aiff", ".flac")
KINDS = ("music", "sfx")


def _names(d, name):
    """name itself, then its stem with every audio extension, inside folder d."""
    stem = name[:-len(Path(name).suffix)] if Path(name).suffix.lower() in EXTS else name
    return [d / name] + [d / (stem + e) for e in EXTS]


def find(kind, name, script_dir=None):
    """The file a script names ("music" or "sfx"), or None: an absolute or repo-relative path, else the name or its
    stem with any audio extension in assets/<kind>/, then in assets/local/<kind>/, then in the script's folder and its
    inserts/ (where the creator drops her own file). A library hit is ROOT/assets/<kind>/<file>, the path the mix
    always used, so filter strings do not change."""
    p = Path(name)
    if p.is_absolute():
        return p if p.is_file() else None
    if (ROOT / p).is_file():
        return ROOT / p
    here = [Path(script_dir), Path(script_dir) / "inserts"] if script_dir else []
    for d in (LIB / kind, LOCAL / kind, *here):
        for c in _names(d, name):
            if c.is_file():
                return c
    return None


@lru_cache(maxsize=None)
def _credits(kind):
    """{file stem: credits entry}; a track's edit file maps to the track's entry."""
    out = {}
    for c in load_json(LIB / kind / f"credits_{kind}.json"):
        for f in (c["file"], c.get("edit")):
            if f:
                out[Path(f).stem] = c
    return out


def peak_seconds(x, sr, channels):
    """Seconds to the loudest sample of interleaved samples x (any channel)."""
    x = np.abs(np.asarray(x))
    return float(np.argmax(x) // channels / sr) if len(x) else 0.0


@lru_cache(maxsize=None)
def measure_peak(path):
    """Seconds from the start of an audio file to its loudest sample (any channel), decoded by ffmpeg."""
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-f", "f32le", "-ac", "2", "-ar", "48000",
                          "-"], capture_output=True, check=True).stdout
    return peak_seconds(np.frombuffer(raw, np.float32), 48000, 2)


def seconds(path):
    """An audio file's length (ffprobe)."""
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def credited_peak(path):
    """credits_sfx.json's t_peak_s of a library sound (by stem), or None."""
    c = _credits("sfx").get(Path(path).stem)
    return c["t_peak_s"] if c and c.get("t_peak_s") else None


def sfx_peak(path):
    """Where a sound peaks, in seconds from its start: credits_sfx.json's t_peak_s (by stem), else measured (cached
    in memory; nothing is written to the tracked credits, so git pull never conflicts)."""
    p = credited_peak(path)
    return measure_peak(str(path)) if p is None else p


def _title(c):
    return re.sub(r"\s*\([^)]*\)$", "", c["title"])          # "Gimme that Groove! (Mixkit #872)" -> the name


def music_info(path):
    """{"title", "bpm", "tags"} of a track: credits_music.json for a library track (its full file or its edit), else
    the file's stem and the "<n>bpm" in its name (bpm None without one)."""
    c = _credits("music").get(Path(path).stem)
    if c:
        return {"title": _title(c), "bpm": c.get("bpm"), "tags": c.get("tags", "")}
    m = re.search(r"(\d+)bpm", Path(path).name)
    return {"title": Path(path).stem, "bpm": int(m.group(1)) if m else None, "tags": ""}


def _rows(kind):
    """[{name, path, title, tags, bpm, peak, local}]: name is what the script writes (a music file name, a sound's
    stem)."""
    rows = []
    if kind == "music":
        for c in load_json(LIB / "music" / "credits_music.json"):        # one row per track, not per edit
            p = LIB / c["file"]
            rows.append({"name": p.name, "path": p, "title": _title(c), "tags": c.get("tags", ""), "bpm": c.get("bpm")})
    else:
        sfx = _credits("sfx")
        for p in sorted(q for q in (LIB / "sfx").iterdir() if q.suffix.lower() in EXTS):
            c = sfx.get(p.stem, {})
            rows.append({"name": p.stem, "path": p, "title": c.get("source_title", p.stem), "tags": c.get("use_for", ""),
                         "peak": c.get("t_peak_s")})
    if (LOCAL / kind).is_dir():
        for p in sorted(q for q in (LOCAL / kind).iterdir() if q.suffix.lower() in EXTS):
            row = {"name": p.name if kind == "music" else p.stem, "path": p, "title": p.stem, "tags": "", "local": True}
            if kind == "music":
                row["bpm"] = music_info(p)["bpm"]
            rows.append(row)
    return rows


def _number(stem):
    m = re.search(r"_(\d+)(?:_|$)", stem)
    return int(m.group(1)) if m else None


def search(kind, query=""):
    """(rows, exact): the rows whose stem or title holds every word of the query (a number matches the track number
    or a whole number in the name), else the rows at least 0.6 similar to it (exact False)."""
    rows = _rows(kind)
    words = query.lower().split()
    if not words:
        return rows, True

    def has(row, w):
        hay = f"{Path(row['name']).stem} {row['title']}".lower()
        if w.isdigit():
            return int(w) == _number(Path(row["name"]).stem) or re.search(rf"(?<!\d){w}(?!\d)", hay) is not None
        return w in hay
    hits = [r for r in rows if all(has(r, w) for w in words)]
    if hits:
        return hits, True
    q = query.lower()
    sim = [(max(SequenceMatcher(None, q, Path(r["name"]).stem.lower()).ratio(),
                SequenceMatcher(None, q, r["title"].lower()).ratio()), r) for r in rows]
    return [r for s, r in sorted(sim, key=lambda x: -x[0]) if s >= 0.6], False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kind", choices=KINDS)
    ap.add_argument("query", nargs="*")
    a = ap.parse_args()
    query = " ".join(a.query)
    rows, exact = search(a.kind, query)
    if not rows:
        print(f"nothing like «{query}» in {a.kind}")
        return 1
    if not exact:
        print(f"no {a.kind} has every word of «{query}»; similar names:")
    for r in rows:
        where = "  (local)" if r.get("local") else ""
        if a.kind == "music":
            bpm = f"{r['bpm']:.0f} bpm" if r.get("bpm") else "bpm ?"
            print(f"{r['name']}  «{r['title']}»  {bpm}  {r['tags']}{where}")
        else:
            peak = f"peak {r['peak']:.3f}s" if r.get("peak") is not None else "peak measured"
            print(f"{r['name']}  {peak}  {r['tags']}{where}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
