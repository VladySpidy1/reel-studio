"""Quick stills: overlay at output time t composited on the source frame shown then (edl applied; no camera/grade).

python preview.py --script ../projects/<name>/script.json --times 1.0,2.5 --out ../build/preview
Also: --measure prints block bboxes; --debug draws block boxes.
"""
import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np
from playwright.sync_api import sync_playwright

import resolve
from common import BUILD, H, PIPE, W, source_path
from edl import EDL


def source_frame(src, t):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-ss", f"{t:.3f}", "-i", str(src),
                          "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"],
                         capture_output=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, W, 3).copy()


def open_page(p, timeline):
    b = p.chromium.launch(channel="chrome", args=["--font-render-hinting=none", "--disable-lcd-text"])
    pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
    pg.goto((PIPE / "overlay.html").as_uri())
    pg.evaluate("tl => init(tl)", timeline)
    return b, pg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", required=True, help="projects/<name>/script.json (for the source video)")
    ap.add_argument("--timeline", default=str(BUILD / "timeline.json"))
    ap.add_argument("--times", default="")
    ap.add_argument("--out", default=str(BUILD / "preview"))
    ap.add_argument("--measure", action="store_true")
    ap.add_argument("--debug", action="store_true")
    ap.add_argument("--frame", default="", help="override background: comma times of source frame")
    a = ap.parse_args()
    timeline = json.loads(Path(a.timeline).read_text(encoding="utf-8"))
    script = resolve.load_script(a.script)
    src = source_path(script)
    edl = EDL(script.get("edl"), script["src_duration"])
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b, pg = open_page(p, timeline)
        if a.measure:
            print(json.dumps(pg.evaluate("measure()"), ensure_ascii=False))
        if a.debug:
            pg.evaluate("debugBoxes()")
        for ts in [x for x in a.times.split(",") if x]:
            t = float(ts)
            pg.evaluate(f"seek({t})")
            png = pg.screenshot(omit_background=True, type="png")
            ov = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_UNCHANGED)
            bg = source_frame(src, edl.src_time(t)).astype(np.float32)
            al = ov[:, :, 3:4].astype(np.float32) / 255
            comp = bg * (1 - al) + ov[:, :, :3].astype(np.float32) * al
            cv2.imwrite(str(out / f"t{t:06.2f}.jpg"), comp.astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 92])
        b.close()


if __name__ == "__main__":
    main()
