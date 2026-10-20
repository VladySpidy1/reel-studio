"""Turn raw camera clips into the reel's intermediate media (run once per reel, before prep.py).

python ingest.py <out_dir> <clip> [<clip> ...]

Every clip becomes a 1080x1920 30 fps CFR ProRes 422 HQ file with 48 kHz PCM audio of exactly the same
length as the picture, so all later steps (prep, render, editable-project export) read identical frames.
Rotation from the phone's display matrix is applied, the picture is scaled to cover 1080x1920 and
centre-cropped, variable frame rate is resampled to 30 fps. Holds the studio lock (one heavy job at a time).

Writes to out_dir:
  media/<clip>.mov   intermediate media, one per clip
  source.ffconcat    the clips back to back; use it as the script's "source"
  clips.json         {"fps", "clips": [{"name", "orig", "file", "offset", "duration", "n_frames"}]}
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from common import FPS, H, W, keep_awake, save_json, studio_lock

HDR_TRC = {"arib-std-b67", "smpte2084"}


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    d = json.loads(out)
    v = next(s for s in d["streams"] if s["codec_type"] == "video")
    a = next((s for s in d["streams"] if s["codec_type"] == "audio"), None)
    return v, a, float(d["format"]["duration"])


def video_duration(v, fmt_dur):
    """Picture length; the container duration can include a longer audio track."""
    return float(v["duration"]) if v.get("duration") not in (None, "N/A") else fmt_dur


def safe_name(stem, taken):
    """ASCII name the concat demuxer accepts in safe mode, unique within the reel (two phones both make IMG_0412)."""
    base = re.sub(r"[^A-Za-z0-9_-]", "_", stem).strip("_") or "clip"
    name, k = base, 2
    while name.lower() in taken:
        name, k = f"{base}_{k}", k + 1
    taken.add(name.lower())
    return name


def start_time(stream):
    return float(stream.get("start_time") or 0.0) if stream else 0.0


def ingest(clip, media_dir, name):
    v, a, fmt_dur = probe(clip)
    if v.get("color_transfer") in HDR_TRC:
        raise SystemExit(f"{clip.name}: HDR video ({v['color_transfer']}). Turn off HDR Video on the iPhone "
                         f"(ADR-0006); HDR->SDR tone-mapping is not implemented yet.")
    n = int(round(video_duration(v, fmt_dur) * FPS))
    dur = n / FPS
    out = media_dir / f"{name}.mov"
    # both streams are rebased to the first video frame, so every clip starts at 0 inside the concat
    vf = (f"setpts=PTS-STARTPTS,fps={FPS},scale={W}:{H}:force_original_aspect_ratio=increase"
          f":flags=lanczos+accurate_rnd+full_chroma_int:in_color_matrix=bt709:out_color_matrix=bt709,"
          f"crop={W}:{H},setsar=1,format=yuv422p10le")
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(clip)]
    if a:
        lead = start_time(a) - start_time(v)          # > 0: sound starts after the first frame
        shift = f"adelay={int(round(lead * 1000))}:all=1," if lead > 0.0005 else \
                f"atrim=start={-lead:.6f},asetpts=PTS-STARTPTS," if lead < -0.0005 else ""
        amap, af = "0:a:0", f"aresample=48000,{shift}"
    else:                                             # silent clip: same streams as the others, or the concat drifts
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
        amap, af = "1:a:0", ""
    cmd += ["-map", "0:v:0", "-vf", vf, "-frames:v", str(n), "-c:v", "prores_ks", "-profile:v", "3", "-vendor", "apl0",
            "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", "-color_range", "tv",
            # pad/trim so the audio ends exactly with the last frame (1600 samples per frame at 30 fps)
            "-map", amap, "-af", f"{af}apad,atrim=end_sample={n * 48000 // FPS}", "-ac", "2", "-c:a", "pcm_s24le",
            "-map_metadata", "0", "-movflags", "+write_colr", str(out)]
    subprocess.run(cmd, check=True)
    got = count_frames(out)
    if got != n:
        raise SystemExit(f"{clip.name}: expected {n} frames, got {got}")
    return {"name": name, "orig": str(clip), "file": f"media/{out.name}", "duration": round(dur, 6), "n_frames": n}


def count_frames(path, demux=()):
    return int(subprocess.run(["ffprobe", "-v", "error", *demux, "-select_streams", "v:0", "-count_packets",
                               "-show_entries", "stream=nb_read_packets", "-of", "csv=p=0", str(path)],
                              capture_output=True, text=True, check=True).stdout.strip().split(",")[0])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("clips", nargs="+")
    a = ap.parse_args()
    out = Path(a.out)
    media = out / "media"
    media.mkdir(parents=True, exist_ok=True)
    clips, offset, taken = [], 0.0, set()
    for c in a.clips:
        c = Path(c).resolve()
        info = ingest(c, media, safe_name(c.stem, taken))
        info["offset"] = round(offset, 6)
        offset += info["duration"]
        clips.append(info)
        print(f"{c.name}: {info['n_frames']} frames, {info['duration']:.3f}s @ {info['offset']:.3f}s", flush=True)
    # outpoint makes the concat demuxer cut every clip exactly at its last frame
    lines = ["ffconcat version 1.0"]
    for c in clips:
        lines += [f"file '{c['file']}'", f"duration {c['duration']:.6f}", f"outpoint {c['duration']:.6f}"]
    (out / "source.ffconcat").write_text("\n".join(lines) + "\n", encoding="utf-8")
    total = sum(c["n_frames"] for c in clips)
    got = count_frames(out / "source.ffconcat")
    if got != total:
        raise SystemExit(f"source.ffconcat has {got} frames, clips add up to {total}")
    save_json({"fps": FPS, "clips": clips}, out / "clips.json")
    print(f"{len(clips)} clips, {offset:.3f}s -> {out / 'source.ffconcat'}")


if __name__ == "__main__":
    with studio_lock("ingest " + " ".join(sys.argv[1:2])):
        keep_awake()
        sys.exit(main())
