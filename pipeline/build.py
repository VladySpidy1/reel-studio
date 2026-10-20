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
Music and SFX are found by name (assets.py); a missing one is skipped with a warning, and the reel is made without
it. Next to output/<name>.mp4, output/<name>.report.json holds the final report's numbers (lengths, cuts, music,
missing files).
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
import video_pass
from common import (BUILD, OUT, ROOT, default_procs, keep_awake, load_json, reel_id, require_slot, run_log,
                    save_json, short, source_path, studio_lock)


def sfx_cues(sfx):
    """(cues for the mix, missing): sfx is the script's audio.sfx plus the timeline's automatic cues. A cue's name is
    a sound's stem, a file name or a path (assets.find); it peaks at peak_at (its own "t_peak" wins over the sound's
    measured or credited peak) or starts at t. A sound that is not found is skipped with a warning."""
    cues, missing = [], []
    for c in sfx:
        path = assets.find("sfx", c["name"])
        if path is None:
            print(f"WARNING sfx «{c['name']}» not found - skipped")
            missing.append({"kind": "sfx", "name": c["name"]})
            continue
        t = c["peak_at"] - (c["t_peak"] if "t_peak" in c else assets.sfx_peak(path)) if "peak_at" in c else c["t"]
        cues.append({"file": str(path), "t": t, "gain_db": c.get("gain_db", -12)})
    return cues, missing


def find_music(m):
    """(the music spec with its file resolved, missing): (None, [entry]) when the file is not found."""
    path = assets.find("music", m["file"])
    if path is None:
        print(f"WARNING music «{m['file']}» not found - the reel is made without music")
        return None, [{"kind": "music", "name": m["file"]}]
    return {**m, "file": str(path)}, []


def report(script, meta, music, missing, skip_audio):
    """output/<name>.report.json: the numbers of the final report. Lengths are in seconds: raw_s is the footage as
    shot, src_s after a speed-up, out_s the reel; edits counts the cuts of the edl."""
    src = source_path(script)
    clips_json = src.parent / "clips.json"
    clips = load_json(clips_json)["clips"] if src.suffix == ".ffconcat" and clips_json.exists() else []
    src_s = sum(c["duration"] for c in clips) if clips else meta["src_duration"]
    raw_s = sum(c.get("orig_duration", c["duration"]) for c in clips) if clips else meta["src_duration"]
    m = None
    if music:
        info = assets.music_info(music["file"])
        m = {"asked": music.get("asked"), "file": Path(music["file"]).name, "title": info["title"],
             "gain_db": None if skip_audio else music.get("gain_db", -20)}
    return {"raw_s": round(raw_s, 2), "speed": clips[0].get("speed", 1.0) if clips else 1.0, "src_s": round(src_s, 2),
            "out_s": round(meta["duration"], 2), "edits": len(meta["edl"]) - 1, "music": m, "missing": missing,
            "warnings": []}


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
    mix = BUILD / f"{name}_mix.wav"
    cues, missing = sfx_cues(au.get("sfx", []) + load_json(BUILD / "timeline.json").get("sfx", []))
    music = None
    if au.get("music") and not a.no_music:
        music, lost = find_music(au["music"])
        missing += lost
    if not a.skip_audio:
        audio.render({"src": src, "duration": dur, "voice": au.get("voice", {"gain_db": 0}), "edl": meta["edl"],
                      "voice_over": au.get("voice_over", []), "mute": au.get("mute", []),
                      "sfx": cues, "music": music}, mix)
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
        save_json(report(script, meta, music, missing, a.skip_audio), OUT / f"{name}.report.json")
    print(f"[video] rc={rc} {time.time() - T:.1f}s -> {short(out)}", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
