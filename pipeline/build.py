"""One-shot build: script -> timeline/camera -> overlay PNGs -> audio mix -> final mp4.

python build.py ../projects/tosumi_hair/script.json [--skip-timeline] [--skip-overlay] [--skip-audio] [--name out]
"""
import argparse
import shutil
import sys
import time
from pathlib import Path

import audio
import build_timeline
import overlay_render
import video_pass
from common import BUILD, FPS, OUT, ROOT, load_json


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
    ap.add_argument("--name", default="")
    a = ap.parse_args()
    script = load_json(a.script)
    name = a.name or Path(a.script).parent.name
    OUT.mkdir(exist_ok=True)
    T = time.time()
    if not a.skip_timeline:
        build_timeline.main(a.script)
        print(f"[timeline] {time.time() - T:.1f}s", flush=True)
    meta = load_json(BUILD / "meta.json")
    dur, n = meta["duration"], meta["n_frames"]
    if not a.skip_overlay:
        shutil.rmtree(BUILD / "overlay", ignore_errors=True)
        overlay_render.render(n, BUILD / "overlay", BUILD / "timeline.json", procs=4)
        print(f"[overlay] {time.time() - T:.1f}s", flush=True)
    au = script.get("audio", {})
    mix = BUILD / f"{name}_mix.wav"
    if not a.skip_audio:
        music = None
        if au.get("music") and not a.no_music:
            m = au["music"]
            music = {**m, "file": str(ROOT / "assets/music" / m["file"])}
        audio.render({"duration": dur, "voice": au.get("voice", {"gain_db": 0}), "edl": meta["edl"],
                      "sfx": sfx_cues(au), "music": music}, mix)
        print(f"[audio] {time.time() - T:.1f}s", flush=True)
    out = OUT / f"{name}.mp4"
    rc = video_pass.main(BUILD / "camera.json", BUILD / "overlay", out, "", mix, dur,
                         BUILD / "timeline.json", ROOT / script["masks"], script.get("grade"))
    print(f"[video] rc={rc} {time.time() - T:.1f}s -> {out}", flush=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())
