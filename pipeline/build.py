"""One-shot build: script -> timeline/camera -> overlay PNGs -> audio mix -> final mp4.

python build.py ../projects/tosumi_hair/script.json [--draft] [--name out] [--procs N] [--verbose]
                [--skip-timeline] [--skip-overlay] [--skip-audio] [--no-music] [--no-grade] [--force] [--allow-check-fail]

--draft is the fast preview (x264 veryfast), named <reel>_draft unless --name is given. The terminal gets a short
summary (problems first, then one line per stage); the full output is in build/<reel>/logs/build_<name>.log, and
on the terminal too with --verbose. One build at a time (build/.studio.lock): a second one exits 2.
The build slot (build/meta.json, camera.json, timeline.json, overlay/) holds one reel: --skip-timeline and
--skip-overlay refuse unless it holds this script (--force: developer only), and a slot whose checks FAIL is not
rendered without --allow-check-fail. The script is resolved once (resolve.py: studio -> brand -> format -> script);
the log starts with the resolver summary, and build/<reel>/resolved_<name>.json keeps what was rendered.
Music and SFX are found by name (assets.py, also in the script's folder); a missing one is skipped with a warning,
and the reel is made without it. The voice gets 2-frame crossfades at speech cuts with audio.xfade_frames 2; music
with under_lu is measured to sit that many LU under the voice, and music with duck rises in the gaps between speech
spans. build/<name>_music.wav is the music alone as mixed (the editable project's music), rewritten by every audio
render. Next to output/<name>.mp4, output/<name>.report.json holds the final report's numbers: lengths, removed time
(pauses, retakes, dead air), cuts, music, missing files, warnings (other features add their sections).
"""
import argparse
import os
import shutil
import sys
import time
from pathlib import Path

import assets
import audio
import build_timeline
import overlay_render
import resolve
import trim
import video_pass
from common import (BUILD, OUT, ROOT, default_procs, keep_awake, load_json, reel_id, require_slot, run_log,
                    save_json, short, source_path, studio_lock)
from edl import EDL, VoiceMap, speech_spans


def sfx_cues(sfx, here=None):
    """(cues for the mix, missing): sfx is the script's audio.sfx plus the timeline's automatic cues. A cue's name is
    a sound's stem, a file name or a path (assets.find; `here` is the script's folder); it peaks at peak_at (its own
    "t_peak" wins over the sound's measured or credited peak) or starts at t. A sound that is not found is skipped
    with a warning."""
    cues, missing = [], []
    for c in sfx:
        path = assets.find("sfx", c["name"], here)
        if path is None:
            print(f"WARNING sfx «{c['name']}» not found - skipped")
            missing.append({"kind": "sfx", "name": c["name"]})
            continue
        if "peak_at" in c and "t_peak" not in c and assets.credited_peak(path) is None:
            print(f"sfx «{c['name']}»: peak {assets.sfx_peak(path):.3f} s into {path.name} (measured)")
        t = c["peak_at"] - (c["t_peak"] if "t_peak" in c else assets.sfx_peak(path)) if "peak_at" in c else c["t"]
        cues.append({"file": str(path), "t": t, "gain_db": c.get("gain_db", -12)})
    return cues, missing


def find_music(m, here=None):
    """(the music spec with its file resolved, missing): (None, [entry]) when the file is not found."""
    path = assets.find("music", m["file"], here)
    if path is None:
        print(f"WARNING music «{m['file']}» not found - the reel is made without music")
        return None, [{"kind": "music", "name": m["file"]}]
    return {**m, "file": str(path)}, []


def music_short(music, dur):
    """Seconds the track (after its offset) is shorter than the reel, or None; warns."""
    left = assets.seconds(music["file"]) - music.get("offset", 0)
    if left >= dur - 0.05:
        return None
    print(f"WARNING music «{Path(music['file']).name}» ends {dur - left:.1f} s before the reel (offset "
          f"{music.get('offset', 0)} s): silence after it")
    return round(dur - left, 2)


def report(script, music, mixed, missing, warnings, short_by):
    """output/<name>.report.json: the numbers of the final report (trim.stats; audio-timing owns the schema, other
    features add their sections). Lengths are in seconds: raw_s is the footage as shot, src_s after a speed-up,
    out_s the reel; edits counts the cuts of the edl; removed splits the cut time into pauses, retakes and dead air.
    music: what was mixed (gain_db null with --skip-audio); it starts at frame 0, from `offset` into the track."""
    st = trim.stats(script)
    m = None
    if music:
        info = assets.music_info(music["file"])
        m = {"asked": music.get("asked"), "file": Path(music["file"]).name, "title": info["title"],
             "gain_db": mixed["gain_db"] if mixed else None, "under_lu": music.get("under_lu"),
             "ducked_gaps": mixed["ducked_gaps"] if mixed else None, "short_by_s": short_by, "starts_at": 0.0,
             "offset": music.get("offset", 0), "fade_in": music.get("fade_in", 0)}
    return {**{k: st[k] for k in ("raw_s", "speed", "src_s", "out_s", "edits")}, "removed": st["removed"], "music": m,
            "missing": missing, "warnings": warnings}


def clip_edges(script):
    """[[start, end]] source seconds of each clip (crossfade handles stay inside their clip)."""
    return [[c["offset"], c["offset"] + c["duration"]] for c in trim.source_clips(script)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("script")
    ap.add_argument("--skip-timeline", action="store_true")
    ap.add_argument("--skip-overlay", action="store_true")
    ap.add_argument("--skip-audio", action="store_true")
    ap.add_argument("--no-music", action="store_true")
    ap.add_argument("--no-grade", action="store_true", help="skip the grade (reference for comparing the editable project)")
    ap.add_argument("--name", default="")
    ap.add_argument("--draft", action="store_true", help="fast preview: x264 veryfast, default name <reel>_draft")
    ap.add_argument("--procs", type=int, default=default_procs(), help="render processes (default: 2 on 8 GB RAM, else 4)")
    ap.add_argument("--verbose", action="store_true", help="the full output on the terminal (it is always in the log)")
    ap.add_argument("--force", action="store_true", help="developer only: use the build slot although it holds another reel")
    ap.add_argument("--allow-check-fail", action="store_true", help="render although the slot's checks FAIL")
    a = ap.parse_args()
    reel = reel_id(a.script)
    name = a.name or reel + ("_draft" if a.draft else "")
    with studio_lock("build " + name):
        keep_awake()
        if a.skip_timeline or a.skip_overlay:
            require_slot(a.script, force=a.force)            # before anything is written
        if a.draft:                                          # spawned encoders re-read it from the environment
            video_pass.PRESET = os.environ["X264_PRESET"] = "veryfast"
        with run_log(BUILD / reel / "logs" / f"build_{name}.log", a.verbose):
            return build(a, name)


def build(a, name):
    script = resolve.load_script(a.script, check_fonts=not a.skip_timeline)
    print(resolve.summary(script))
    save_json(script, BUILD / reel_id(a.script) / f"resolved_{name}.json")
    src = source_path(script)
    OUT.mkdir(exist_ok=True)
    T = time.time()
    if not a.skip_timeline:
        build_timeline.main(a.script, script)
        print(f"[timeline] {time.time() - T:.1f}s -> {short(BUILD / 'timeline.json')}", flush=True)
    meta = require_slot(a.script, need_pass=not a.allow_check_fail, force=a.force)
    dur, n = meta["duration"], meta["n_frames"]
    if not a.skip_overlay:
        shutil.rmtree(BUILD / "overlay", ignore_errors=True)
        overlay_render.render(n, BUILD / "overlay", BUILD / "timeline.json", procs=a.procs)
        print(f"[overlay] {time.time() - T:.1f}s -> {short(BUILD / 'overlay')}", flush=True)
    au = script.get("audio", {})
    here = Path(a.script).resolve().parent
    mix, stem = BUILD / f"{name}_mix.wav", BUILD / f"{name}_music.wav"
    cues, missing = sfx_cues(au.get("sfx", []) + load_json(BUILD / "timeline.json").get("sfx", []), here)
    music, warnings, short_by, mixed = None, [], None, None
    if au.get("music") and not a.no_music:
        music, lost = find_music(au["music"], here)
        missing += lost
    if music:
        short_by = music_short(music, dur)
        if short_by:
            warnings.append(f"music ends {short_by} s before the reel")
    if not a.skip_audio:
        stem.unlink(missing_ok=True)         # never a stale stem (e.g. after --no-music) for the export
        speech = None
        if music and music.get("duck"):      # output-time speech spans: the music rises in the gaps between them
            heard = VoiceMap(EDL(meta["edl"], meta["src_duration"]), au).heard_words(load_json(ROOT / script["words"]))
            speech = speech_spans(heard, hang=0.2, join=music["duck"].get("min_gap", 0.8))
        mixed = audio.render({"src": src, "duration": dur, "voice": au.get("voice", {"gain_db": 0}), "edl": meta["edl"],
                              "xfade_frames": au.get("xfade_frames", 0),
                              "clip_edges": clip_edges(script),
                              "voice_over": au.get("voice_over", []), "mute": au.get("mute", []),
                              "sfx": cues, "music": music, "speech": speech}, mix, stem if music else None)
        warnings += mixed["warnings"]
        print(f"[audio] {time.time() - T:.1f}s -> {short(mix)}", flush=True)
    out = OUT / f"{name}.mp4"
    rc = video_pass.main(BUILD / "camera.json", BUILD / "overlay", out, "", mix, dur,
                         BUILD / "timeline.json", ROOT / script["masks"], None if a.no_grade else script.get("grade"),
                         procs=a.procs, src=src)
    if rc == 0:                     # the slot record: review_frames only looks at videos rendered from this slot
        meta = load_json(BUILD / "meta.json")
        meta.setdefault("renders", [])
        if name not in meta["renders"]:
            meta["renders"].append(name)
        save_json(meta, BUILD / "meta.json")
        save_json(report(script, music, mixed, missing, warnings, short_by), OUT / f"{name}.report.json")
    print(f"[video] rc={rc} {time.time() - T:.1f}s -> {short(out)}", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
