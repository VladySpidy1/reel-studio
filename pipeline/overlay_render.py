"""Render the HTML/CSS subtitle overlay to a transparent PNG sequence with headless Chrome.

overlay.html must expose window.seek(t) which deterministically lays out the frame at time t,
and window.ready (a Promise) that resolves once fonts are loaded.
"""
import sys
from multiprocessing import Process
from pathlib import Path

from playwright.sync_api import sync_playwright

from common import BUILD, FPS, H, PIPE, W, load_json

HTML = PIPE / "overlay.html"


def worker(frames, out_dir, timeline_path):
    timeline = Path(timeline_path).read_text(encoding="utf-8")
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", args=["--font-render-hinting=none", "--disable-lcd-text"])
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        pg.goto(HTML.as_uri())
        pg.evaluate(f"init({timeline})")
        pg.evaluate("window.ready")
        for i in frames:
            pg.evaluate(f"seek({i / FPS:.6f})")
            pg.screenshot(path=str(Path(out_dir) / f"{i:05d}.png"), omit_background=True, type="png")
        b.close()


def render(n_frames, out_dir, timeline_path, procs=4, only=None):
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
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
    ap.add_argument("--procs", type=int, default=4)
    a = ap.parse_args()
    only = [int(x) for x in a.only.split(",")] if a.only else None
    render(a.frames, a.out, a.timeline, a.procs, only)
