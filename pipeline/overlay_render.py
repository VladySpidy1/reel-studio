"""Render the HTML/CSS subtitle overlay to a transparent PNG sequence with headless Chromium (Playwright's own,
pinned by the playwright version; pipeline/setup_mac.sh installs it).

overlay.html must expose window.seek(t, layer) which deterministically lays out the frame at time t,
and window.ready (a Promise) that resolves once fonts are loaded. On the timeline's front_frames a frame is two
PNGs: NNNNN.png without the behind:false blocks (cut by her matte) and front/NNNNN.png with only them (drawn over
her, uncut).
"""
import json
import shutil
import sys
from multiprocessing import Process
from pathlib import Path

from playwright.sync_api import sync_playwright

from common import BUILD, FPS, H, PIPE, W, default_procs, load_json

HTML = PIPE / "overlay.html"


def worker(frames, out_dir, timeline_path):
    timeline = Path(timeline_path).read_text(encoding="utf-8")
    front = set(json.loads(timeline).get("front_frames", []))
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--font-render-hinting=none", "--disable-lcd-text"])
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        pg.goto(HTML.as_uri())
        pg.evaluate(f"init({timeline})")
        pg.evaluate("window.ready")
        for i in frames:
            if i in front:
                pg.evaluate(f"seek({i / FPS:.6f}, 'back')")
                pg.screenshot(path=str(Path(out_dir) / f"{i:05d}.png"), omit_background=True, type="png")
                pg.evaluate(f"seek({i / FPS:.6f}, 'front')")
                pg.screenshot(path=str(Path(out_dir) / "front" / f"{i:05d}.png"), omit_background=True, type="png")
                continue
            pg.evaluate(f"seek({i / FPS:.6f})")
            pg.screenshot(path=str(Path(out_dir) / f"{i:05d}.png"), omit_background=True, type="png")
        b.close()


def render(n_frames, out_dir, timeline_path, procs=4, only=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(out_dir / "front", ignore_errors=True)        # the front layer of this timeline only
    if load_json(timeline_path).get("front_frames"):
        (out_dir / "front").mkdir()
    frames = list(only) if only is not None else list(range(n_frames))
    chunks = [frames[k::procs] for k in range(procs)]
    ps = [Process(target=worker, args=(c, str(out_dir), str(timeline_path))) for c in chunks if c]
    for p in ps:
        p.start()
    for p in ps:
        p.join()
    bad = [p.exitcode for p in ps if p.exitcode != 0]
    if bad:
        raise SystemExit(f"overlay workers failed: {bad}")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeline", default=str(BUILD / "timeline.json"))
    ap.add_argument("--out", default=str(BUILD / "overlay"))
    ap.add_argument("--frames", type=int, required=True)
    ap.add_argument("--only", default="", help="comma separated frame indices (preview)")
    ap.add_argument("--procs", type=int, default=default_procs(), help="default: 2 on 8 GB RAM, else 4")
    a = ap.parse_args()
    only = [int(x) for x in a.only.split(",")] if a.only else None
    render(a.frames, a.out, a.timeline, a.procs, only)
