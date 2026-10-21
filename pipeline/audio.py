"""Audio mix: the voice cut like the picture, timed SFX and an optional music bed with keyframed ducking, then
two-pass loudness normalisation to Instagram-friendly -14 LUFS.

mix spec (dict):
  src: source video (its audio is the voice)
  duration: float seconds
  edl: script edl (the picture's own sound is cut exactly like the picture, on the same frame grid)
  xfade_frames: 0 = 6 ms fades at every cut (as always); 2 = an equal-power crossfade over 2 frames at each cut between
                two src pieces, from audio handles (6 ms fades stay next to holds, at the reel's ends and where a clip
                has no room for a handle; pieces that run on in the source get no fades), and the mix is cut to the
                sample (1600 per frame) instead of to the millisecond
  clip_edges: [[start, end], ...] source seconds of each clip: handles never reach into another clip
  voice: {"gain_db": 0}
  voice_over: [{"src": [a, b], "at": out_t, "gain_db": 0}]   extra source sound laid at output time
  mute: [[t0, t1], ...]                                       output ranges where the picture's sound is off
  sfx: [{"file": path, "t": seconds, "gain_db": -12}]
  music: {"file": path, "gain_db": -20, "under_lu": 15, "offset": 0, "fade_in": 0.05, "fade_out": 0.8,
          "dropouts": [[t0, t1]], "duck": {"rise_db": 4, "lead": 0.15, "release": 0.4, "min_gap": 0.8}} | null
  speech: [[a, b], ...] output-time speech spans (edl.speech_spans), for music.duck
  stem: true = the music alone also comes out as [mstem] (render writes it as the music stem)
The music runs from frame 0 at gain_db, or measured to sit under_lu LU under the voice (render). With duck it is
keyframed, never sidechained (a compressor pumps): it rises by rise_db in every gap of min_gap or more between speech
spans, release seconds after speech ends, and is back down lead seconds before speech starts. A sidechain in the
spec is ignored when duck is set.
"""
import json
import math
import re
import subprocess
from pathlib import Path

from common import FPS
from edl import EDL


def _voice_chain(gain_db, process=False):
    # Default: leave the voice as recorded (phone/CapCut exports are already cleaned) - only the
    # final loudness normalisation touches it. process=True adds gentle EQ/de-ess/compression.
    if not process:
        return f"volume={gain_db}dB"
    return ("highpass=f=80,equalizer=f=250:t=q:w=1:g=-2,equalizer=f=4000:t=q:w=1.2:g=2.5,"
            "deesser=i=0.25,acompressor=threshold=-20dB:ratio=2.5:attack=5:release=80:makeup=1.5dB,"
            f"volume={gain_db}dB")


def _voice_edl(edl, xfade_frames=0, clip_edges=None):
    """Cut/hold the source audio exactly like the picture (holds = silence). Segments use the picture's
    frame grid (EDL.src_frame), so sound and picture cannot drift apart over many cuts."""
    if xfade_frames:
        return _voice_xfade(edl, xfade_frames, clip_edges)
    parts, labels = [], []
    for k, (o0, o1, seg) in enumerate(EDL(edl, 0).items if edl else []):
        d = (round(o1 * FPS) - round(o0 * FPS)) / FPS
        if d <= 0:              # shorter than half a frame: the picture skips it too (atrim duration=0 means "all")
            continue
        if "src" in seg:
            a = round(seg["src"][0] * FPS) / FPS
            parts.append(f"[0:a]aresample=48000,aformat=channel_layouts=stereo,"
                         f"atrim=start={a:.6f}:duration={d:.6f},asetpts=PTS-STARTPTS,"
                         f"afade=t=in:d=0.006,afade=t=out:st={max(0, d - 0.006):.6f}:d=0.006[e{k}]")
        else:
            parts.append(f"anullsrc=r=48000:cl=stereo,atrim=0:{d:.6f}[e{k}]")
        labels.append(f"[e{k}]")
    if not labels:
        return "[0:a]aresample=48000,aformat=channel_layouts=stereo", []
    parts.append(f"{''.join(labels)}concat=n={len(labels)}:v=0:a=1[vedl]")
    return "[vedl]", parts


def _voice_xfade(edl, xfade_frames, clip_edges):
    """The voice edl with crossfades: every src piece is trimmed on exact samples with its handles, placed at its
    output sample with adelay and summed (amix, no normalising), so away from the cuts it is the concat path's sound.
    A cut between two src pieces shares one handle h (xfade_frames/2 frames, less when the clip ends first) and both
    sides fade over 2h with quarter-sine (equal-power) curves; a hold, the reel's ends or h under 6 ms keep the 6 ms
    fades; a piece that runs on in the source gets no fade at that junction (an equal-power fade of the same sound
    would bump it by 3 dB)."""
    S, short = 48000 // FPS, 288                    # samples per frame; 6 ms
    edges = [(round(a * 48000), round(b * 48000)) for a, b in (clip_edges or [[0, 1e6]])]
    pieces = []                                     # (label, output frame, frames, src piece or None)
    for k, (o0, o1, seg) in enumerate(EDL(edl, 0).items if edl else []):
        f0, n = round(o0 * FPS), round(o1 * FPS) - round(o0 * FPS)
        if n > 0:
            pieces.append((k, f0, n, round(seg["src"][0] * FPS) if "src" in seg else None))
    if not any(p[3] is not None for p in pieces):
        return _voice_edl(edl)
    clip = lambda smp: next((e for e in edges if e[0] <= smp < e[1]), (0, 10 ** 12))
    hand = []                                       # per junction: None = 6 ms fades, 0 = runs on, else h samples
    for (_, _, na, a0), (_, _, _, b0) in zip(pieces, pieces[1:]):
        if a0 is None or b0 is None:
            hand.append(None)
        elif a0 + na == b0:
            hand.append(0)
        else:
            out_s, in_s = (a0 + na) * S, b0 * S
            h = min(xfade_frames * S // 2, clip(out_s - 1)[1] - out_s, in_s - clip(in_s)[0])
            hand.append(h if h >= short else None)
    parts, labels = [], []
    for j, (k, f0, n, a0) in enumerate(pieces):
        if a0 is None:
            continue
        hl = hand[j - 1] if j else None
        hr = hand[j] if j < len(hand) else None
        x0, x1 = a0 * S - (hl or 0), (a0 + n) * S + (hr or 0)
        total = (x1 - x0) / 48000
        fade = ""
        if hl is None:
            fade += ",afade=t=in:d=0.006"
        elif hl:
            fade += f",afade=t=in:st=0:d={2 * hl / 48000:.6f}:curve=qsin"
        if hr is None:
            fade += f",afade=t=out:st={max(0, total - 0.006):.6f}:d=0.006"
        elif hr:
            fade += f",afade=t=out:st={total - 2 * hr / 48000:.6f}:d={2 * hr / 48000:.6f}:curve=qsin"
        at = f0 * S - (hl or 0)
        parts.append(f"[0:a]aresample=48000,aformat=channel_layouts=stereo,atrim=start_sample={x0}:end_sample={x1},"
                     f"asetpts=PTS-STARTPTS{fade},adelay={at}S|{at}S[e{k}]")
        labels.append(f"[e{k}]")
    parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:dropout_transition=0[vedl]")
    return "[vedl]", parts


def duck_gaps(speech, dur, min_gap):
    """The music's rise windows [(a, b)]: the gaps before the first speech span, between spans and after the last
    one, kept when at least min_gap long inside [0, dur]. An opening gap starts at -1 (already up at frame 0, no ramp
    there) and a closing one ends at dur + 1 (no swell at the end)."""
    out, t = [], 0.0
    for a, b in sorted(speech):
        out.append((t, a))
        t = max(t, b)
    out.append((t, dur))
    gaps = []
    for a, b in out:
        a, b = max(0.0, a), min(dur, b)
        if b - a >= min_gap - 1e-9:
            gaps.append((-1 if a <= 0 else round(a, 3), round(dur + 1, 3) if b >= dur else round(b, 3)))
    return gaps


def duck_expr(gaps, duck):
    """The volume expression of the duck: 1 under speech, 10^(rise_db/20) in each gap, linear ramps of release
    seconds after a gap opens and lead seconds before it closes."""
    if not gaps:
        return "1"
    g = 10 ** (duck.get("rise_db", 4) / 20)
    rel, lead = duck.get("release", 0.4), duck.get("lead", 0.15)
    terms = "+".join(f"max(0,min(1,min((t-({a:.3f}))/{rel},({b:.3f}-t)/{lead})))" for a, b in gaps)
    return f"1+{g - 1:.5f}*({terms})"


def music_chain(music, dur, idx, speech=None):
    """The music bed from input idx: offset, gain, fades, dropouts and (with duck) the keyframed rise in the gaps
    between speech spans. Without duck it is the chain the mix always had."""
    fo = music.get("fade_out", 0)
    fi = music.get("fade_in", 0)
    chain = (f"[{idx}:a]aresample=48000,aformat=channel_layouts=stereo,"
             f"atrim=start={music.get('offset', 0)},asetpts=PTS-STARTPTS,volume={music.get('gain_db', -20)}dB")
    if fi:
        chain += f",afade=t=in:d={fi}"
    if fo:
        chain += f",afade=t=out:st={max(0, dur - fo):.3f}:d={fo}"
    duck = music.get("duck")
    if duck:                    # 1 ms audio frames: eval=frame then follows the ramps, as the mute does
        chain += ",asetnsamples=n=48:p=0"
    for d0, d1 in music.get("dropouts", []):       # e.g. music dips out for a gag freeze (40 ms ramps)
        r = 0.04
        chain += (f",volume=eval=frame:volume='if(between(t,{d0:.3f},{d1:.3f}),"
                  f"max(0.0,1-min(t-{d0:.3f},{d1:.3f}-t)/{r}),1)'")
    if duck:
        gaps = duck_gaps(speech or [], dur, duck.get("min_gap", 0.8))
        if gaps:
            chain += f",volume=eval=frame:volume='{duck_expr(gaps, duck)}'"
    return chain


def build_filter(spec):
    inputs = ["-i", str(spec["src"])]
    head, edl_parts = _voice_edl(spec.get("edl"), spec.get("xfade_frames", 0), spec.get("clip_edges"))
    parts = list(edl_parts)
    music = spec.get("music")
    chain = _voice_chain(spec["voice"].get("gain_db", 0), spec["voice"].get("process", False))
    sep = "" if head.endswith("]") else ","
    sc = music.get("sidechain") if music else None             # optional compressor ducking; off by default (pumps)
    if sc and music.get("duck"):
        print("WARNING music sidechain ignored: the keyframed duck is set")
        sc = None
    parts.append(f"{head}{sep}anull[vpic]")
    cur = "[vpic]"
    if spec.get("mute"):           # 1 ms audio frames: eval=frame then gives real 10 ms ramps, not ~21 ms steps
        parts.append(f"{cur}asetnsamples=n=48:p=0[vps]")
        cur = "[vps]"
    for k, (m0, m1) in enumerate(spec.get("mute", [])):        # 10 ms ramps, no clicks
        parts.append(f"{cur}volume=eval=frame:volume='if(between(t,{m0:.4f},{m1:.4f}),"
                     f"max(0.0,1-min(t-{m0:.4f},{m1:.4f}-t)/0.01),1)'[vm{k}]")
        cur = f"[vm{k}]"
    vo = []
    for k, v in enumerate(spec.get("voice_over", [])):
        a, b = v["src"]
        n = max(0, int(round(v["at"] * 48000)))
        parts.append(f"[0:a]aresample=48000,aformat=channel_layouts=stereo,atrim=start={a:.6f}:end={b:.6f},"
                     f"asetpts=PTS-STARTPTS,afade=t=in:d=0.006,afade=t=out:st={max(0, b - a - 0.006):.6f}:d=0.006,"
                     f"volume={v.get('gain_db', 0)}dB,adelay={n}S|{n}S[vo{k}]")
        vo.append(f"[vo{k}]")
    if vo:
        parts.append(f"{cur}{''.join(vo)}amix=inputs={1 + len(vo)}:normalize=0:dropout_transition=0[vsum]")
        cur = "[vsum]"
    parts.append(f"{cur}{chain}" + (",asplit=2[voice][vsc]" if sc else "[voice]"))
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
        chain = music_chain(music, dur, idx, spec.get("speech"))
        out = "[mfull]" if spec.get("stem") else "[music]"
        if sc:
            parts.append(chain + "[mraw]")
            parts.append(f"[mraw][vsc]sidechaincompress=threshold={sc.get('threshold', 0.05)}:ratio={sc.get('ratio', 3)}:"
                         f"attack={sc.get('attack', 15)}:release={sc.get('release', 250)}:makeup=1{out}")
        else:
            parts.append(chain + out)
        if spec.get("stem"):       # the music alone, exactly as long as the mix and at its level (before loudnorm)
            parts.append("[mfull]asplit=2[music][ms]")
            parts.append(f"[ms]{_length(spec)}[mstem]")
        labels.append("[music]")
    parts.append(f"{''.join(labels)}amix=inputs={len(labels)}:normalize=0:dropout_transition=0,{_length(spec)}[mix]")
    return inputs, ";".join(parts)


def _length(spec):
    """Pad/cut to the reel's length: with xfade_frames to its whole frames, 1600 samples each (an edl's 4-decimal
    times add up to a few samples off the grid), else as always to the millisecond (up to 16 samples short)."""
    d = spec["duration"]
    if spec.get("xfade_frames"):
        n = round(d * FPS) * (48000 // FPS)
        return f"apad=whole_len={n},atrim=end_sample={n}"
    return f"apad=whole_dur={d:.3f},atrim=0:{d:.3f}"


def _run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       stdin=subprocess.DEVNULL)
    if r.returncode:
        raise RuntimeError(r.stderr[-3000:])
    return r


def _loudness(args):
    """Integrated loudness (LUFS) that loudnorm measures; args are ffmpeg's inputs and the -filter_complex/-af that
    end in a loudnorm=print_format=json."""
    r = _run(["ffmpeg", "-nostdin", "-hide_banner", *args, "-f", "null", "-"])
    return float(json.loads(re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)[-1])["input_i"])


def music_gain(spec):
    """(gain_db, voice LUFS, music LUFS) that puts the music spec["music"]["under_lu"] LU under the voice: loudnorm
    measures the voice-only mix and the track over offset .. offset + duration."""
    m, dur = spec["music"], spec["duration"]
    inputs, fc = build_filter({**spec, "sfx": [], "music": None, "stem": False})
    iv = _loudness([*inputs, "-filter_complex", fc + ";[mix]loudnorm=print_format=json[ln]", "-map", "[ln]"])
    im = _loudness(["-ss", str(m.get("offset", 0)), "-t", f"{dur:.3f}", "-i", str(m["file"]),
                    "-af", "loudnorm=print_format=json"])
    return iv - m["under_lu"] - im, iv, im


def render(spec, out_wav, music_stem=None):
    """Mix spec into out_wav (-14 LUFS, 24-bit; the mix before loudnorm stays as <out>_raw.wav). With music_stem, the
    music alone also goes there, ducked and at the raw mix's level, exactly as long as the mix. Returns
    {"loudnorm": loudnorm's measurement, "gain_db": the music's gain (measured with under_lu), "ducked_gaps": the
    music's rises (None without duck), "warnings": [...]}."""
    out_wav = Path(out_wav)
    raw = out_wav.with_name(out_wav.stem + "_raw.wav")
    info = {"gain_db": None, "ducked_gaps": None, "warnings": []}

    def warn(msg):
        print("WARNING " + msg)
        info["warnings"].append(msg)
    music = spec.get("music")
    if music:
        music = dict(music)
        if music.get("under_lu") is not None:
            g, iv, im = music_gain(spec)
            if math.isfinite(g):
                music["gain_db"] = round(g, 1)
                print(f"music gain {g:+.1f} dB = {music['under_lu']} LU under the voice (voice {iv:.1f} LUFS, "
                      f"music {im:.1f} LUFS)")
                if not -30 <= g <= -6:
                    warn(f"music gain {g:+.1f} dB is outside -30..-6 dB: listen to the music level")
            else:
                warn(f"music under_lu not measurable (voice {iv} LUFS, music {im} LUFS): gain_db "
                     f"{music.get('gain_db', -20)} dB")
        info["gain_db"] = music.get("gain_db", -20)
        if music.get("duck"):
            info["ducked_gaps"] = len(duck_gaps(spec.get("speech") or [], spec["duration"],
                                                music["duck"].get("min_gap", 0.8)))
        if music.get("sidechain") and music.get("duck"):
            info["warnings"].append("music sidechain ignored: the keyframed duck is set")
    spec = {**spec, "music": music, "stem": bool(music and music_stem)}
    inputs, fc = build_filter(spec)
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-y", *inputs, "-filter_complex", fc,
           "-map", "[mix]", "-c:a", "pcm_f32le", str(raw)]
    if spec["stem"]:
        cmd += ["-map", "[mstem]", "-c:a", "pcm_s24le", str(music_stem)]
    _run(cmd)
    r = _run(["ffmpeg", "-nostdin", "-hide_banner", "-i", str(raw),
              "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json", "-f", "null", "-"])
    m = json.loads(re.findall(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)[-1])
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
          f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
          f"offset={m['target_offset']}:linear=true")
    _run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-i", str(raw), "-af", f"{ln},aresample=48000",
          "-c:a", "pcm_s24le", str(out_wav)])
    return {**info, "loudnorm": m}
