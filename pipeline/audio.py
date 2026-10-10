"""Audio mix: cleaned voice + timed SFX + (optional) music bed ducked under the voice,
then two-pass loudness normalisation to Instagram-friendly -14 LUFS.

mix spec (dict):
  duration: float seconds
  voice: {"gain_db": 0}
  sfx: [{"file": path, "t": seconds, "gain_db": -12}]
  music: {"file": path, "gain_db": -20, "offset": 0, "fade_in": 0.3, "fade_out": 1.2} | null
"""
import json
import re
import subprocess
from pathlib import Path

from common import SRC


def _voice_chain(gain_db, process=False):
    # Default: leave the voice as recorded (phone/CapCut exports are already cleaned) - only the
    # final loudness normalisation touches it. process=True adds gentle EQ/de-ess/compression.
    if not process:
        return f"volume={gain_db}dB"
    return ("highpass=f=80,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=4000:t=q:w=1.2:g=2.5,"
            "deesser=i=0.25,acompressor=threshold=-20dB:ratio=2.5:attack=5:release=80:makeup=1.5dB,"
            f"volume={gain_db}dB")


def _voice_edl(edl):
    """Cut/hold the source audio exactly like the picture (holds = silence)."""
    parts, labels = [], []
    for k, seg in enumerate(edl or []):
        if "src" in seg:
            a, b = seg["src"]
            parts.append(f"[0:a]aresample=48000,aformat=channel_layouts=stereo,"
                         f"atrim=start={a:.4f}:end={b:.4f},asetpts=PTS-STARTPTS,"
                         f"afade=t=in:d=0.006,afade=t=out:st={max(0, b - a - 0.006):.4f}:d=0.006[e{k}]")
        else:
            parts.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{seg['dur']:.4f}[e{k}]")
        labels.append(f"[e{k}]")
    if not labels:
        return "[0:a]aresample=48000,aformat=channel_layouts=stereo", []
    parts.append(f"{''.join(labels)}concat=n={len(labels)}:v=0:a=1[vedl]")
    return "[vedl]", parts


def build_filter(spec):
    inputs = ["-i", str(SRC)]
    head, edl_parts = _voice_edl(spec.get("edl"))
    parts = list(edl_parts)
    music = spec.get("music")
    chain = _voice_chain(spec["voice"].get("gain_db", 0), spec["voice"].get("process", False))
    sep = "" if head.endswith("]") else ","
    duck = bool(music and music.get("sidechain"))
    parts.append(f"{head}{sep}{chain}" + (",asplit=2[voice][vsc]" if duck else "[voice]"))
    labels = ["[voice]"]
    idx = 1
    for k, cue in enumerate(spec.get("sfx", [])):
        inputs += ["-i", cue["file"]]
        ms = max(0, int(round(cue["t"] * 1000)))
        parts.append(f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,"
                     f"volume={cue.get('gain_db', -12)}dB,adelay={ms}|{ms}[s{k}]")
        labels.append(f"[s{k}]")
        idx += 1
    if music:
        inputs += ["-i", music["file"]]
        dur = spec["duration"]
        fo = music.get("fade_out", 0)
        fi = music.get("fade_in", 0)
        chain = (f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,"
                 f"atrim=start={music.get('offset', 0)},asetpts=PTS-STARTPTS,volume={music.get('gain_db', -20)}dB")
        if fi:
            chain += f",afade=t=in:d={fi}"
        if fo:
            chain += f",afade=t=out:st={max(0, dur - fo):.3f}:d={fo}"
        for d0, d1 in music.get("dropouts", []):       # e.g. music dips out for a gag freeze (40 ms ramps)
            r = 0.04
            chain += (f",volume=eval=frame:volume='if(between(t,{d0:.3f},{d1:.3f}),"
                      f"max(0.0,1-min(t-{d0:.3f},{d1:.3f}-t)/{r}),1)'")
        sc = music.get("sidechain")                    # optional ducking; off by default (it "pumps")
        if sc:
            parts.append(chain + "[mraw]")
            parts.append(f"[mraw][vsc]sidechaincompress=threshold={sc.get('threshold', 0.05)}:ratio={sc.get('ratio', 3)}:"
                         f"attack={sc.get('attack', 15)}:release={sc.get('release', 250)}:makeup=1[music]")
        else:
            parts.append(chain + "[music]")
        labels.append("[music]")
    parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:dropout_transition=0,"
                 f"apad=whole_dur={spec['duration']:.3f},atrim=0:{spec['duration']:.3f}[mix]")
    return inputs, ";".join(parts)


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       stdin=subprocess.DEVNULL)
    if r.returncode:
        raise RuntimeError(r.stderr[-3000:])
    return r


def render(spec, out_wav):
    out_wav = Path(out_wav)
    raw = out_wav.with_name(out_wav.stem + "_raw.wav")
    inputs, fc = build_filter(spec)
    _run(["ffmpeg", "-nostdin", "-v", "error", "-y", *inputs, "-filter_complex", fc,
          "-map", "[mix]", "-c:a", "pcm_f32le", str(raw)])
    r = _run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(raw),
              "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"])
    m = json.loads(re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)[-1])
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
          f"offset={m['target_offset']}:linear=true")
    _run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(raw), "-af", f"{ln},aresample=48000",
          "-c:a", "pcm_s24le", str(out_wav)])
    return m
