"""One-shot build: script -> timeline/camera -> overlay PNGs -> audio mix -> final mp4.

python build.py ../projects/tosumi_hair/script.json [--draft] [--name out] [--procs N] [--verbose]
                [--skip-timeline] [--skip-overlay] [--skip-audio] [--no-music] [--no-grade] [--force] [--allow-check-fail]

--draft is the fast preview (x264 veryfast), named <reel>_draft unless --name is given. The terminal gets a short
summary (problems first, then one line per stage); the full output is in build/<reel>/logs/build_<name>.log, and
on the terminal too with --verbose. One build at a time (build/.studio.lock): a second one exits 2.
The build slot (build/meta.json, camera.json, timeline.json, overlay/) holds one reel: --skip-timeline and
--skip-overlay refuse unless it holds this script (--force: developer only), and a slot whose checks FAIL is not
rendered without --allow-check-fail.
"""
import argparse
import os
import shutil
import sys
import time
from pathlib import Path

import audio
import build_timeline
import overlay_render
import video_pass
from common import (BUILD, OUT, ROOT, default_procs, keep_awake, load_json, reel_id, require_slot, run_log,
                    save_json, short, source_path, studio_lock)


def sfx_cues(spec):
    credits = {Path(c["file"]).stem: c for c in load_json(ROOT / "assets/sfx/credits_sfx.json")}
    cues = []
    for c in spec.get("sfx", []):
        peak = credits[c["name"]].get("t_peak_s", 0.0) or 0.0
        t = c["peak_at"] - peak if "peak_at" in c else c["t"]
        cues.append({"file": str(ROOT / "assets/sfx" / f"{c['name']}.wav"), "t": t, "gain_db": c.get("gain_db", -12)})
    return cues


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
    script = load_json(a.script)
    src = source_path(script)
    OUT.mkdir(exist_ok=True)
    T = time.time()
    if not a.skip_timeline:
        build_timeline.main(a.script)
        print(f"[timeline] {time.time() - T:.1f}s -> {short(BUILD / 'timeline.json')}", flush=True)
    meta = require_slot(a.script, need_pass=not a.allow_check_fail, force=a.force)
    dur, n = meta["duration"], meta["n_frames"]
    if not a.skip_overlay:
        shutil.rmtree(BUILD / "overlay", ignore_errors=True)
        overlay_render.render(n, BUILD / "overlay", BUILD / "timeline.json", procs=a.procs)
        print(f"[overlay] {time.time() - T:.1f}s -> {short(BUILD / 'overlay')}", flush=True)
    au = script.get("audio", {})
    mix = BUILD / f"{name}_mix.wav"
    if not a.skip_audio:
        music = None
        if au.get("music") and not a.no_music:
            m = au["music"]
            music = {**m, "file": str(ROOT / "assets/music" / m["file"])}
        audio.render({"src": src, "duration": dur, "voice": au.get("voice", {"gain_db": 0}), "edl": meta["edl"],
                      "voice_over": au.get("voice_over", []), "mute": au.get("mute", []),
                      "sfx": sfx_cues(au), "music": music}, mix)
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
    print(f"[video] rc={rc} {time.time() - T:.1f}s -> {short(out)}", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
