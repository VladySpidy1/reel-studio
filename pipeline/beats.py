"""Beat grid of a music track and the music offset that puts chosen cuts on beats.

python beats.py <music.wav> <bpm> [--cuts 3.6,7.5,12.9] [--offset 19.3] [--search 2.2]

The tempo is known (assets/music/credits_music.json); the phase comes from the onset envelope (spectral flux).
With --cuts it prints the music offset near --offset (within +-search s) whose beats land closest to the cuts:
transitions and product changes then feel cut to the music (research: within one frame of the beat).

fit() goes further for a script generator: every shot may give a few frames at its head or tail ("knob"), and the
cut at its end moves onto the frame at or just before a beat; the music offset is chosen for the whole chain.
"""
import argparse
import math
import subprocess

import numpy as np

import common  # noqa: F401  (puts ffmpeg on PATH; make_script.py imports beats on its own)

SR = 22050
HOP = 256


def onsets(path):
    raw = subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR),
                          "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32)
    n = (len(x) - 1024) // HOP
    win = np.hanning(1024).astype(np.float32)
    spec = np.abs(np.fft.rfft(np.stack([x[i * HOP:i * HOP + 1024] * win for i in range(n)]), axis=1))
    flux = np.maximum(0, np.diff(np.log1p(spec), axis=0)).sum(axis=1)
    return np.concatenate([[0], flux]), HOP / SR


def beat_phase(path, bpm):
    """Time of the first beat (s) for the given tempo: the phase that collects the most onset strength."""
    env, dt = onsets(path)
    period = 60.0 / bpm
    phases = np.arange(0, period, 0.002)
    t = np.arange(len(env)) * dt
    score = [env[np.clip(np.round((np.arange(ph, t[-1], period)) / dt).astype(int), 0, len(env) - 1)].sum()
             for ph in phases]
    return float(phases[int(np.argmax(score))])


def best_offset(phase, bpm, cuts, around, search):
    """Music offset (s into the file) near `around` that puts the cuts (reel seconds) nearest to beats."""
    period = 60.0 / bpm
    best = None
    for off in np.arange(around - search, around + search, 1 / 300):
        if off < 0:
            continue
        err = [abs(((c + off - phase + period / 2) % period) - period / 2) for c in cuts]
        score = float(np.mean(err))
        if best is None or score < best[0]:
            best = (score, float(off), max(err))
    return best


def snap(lengths, knobs, phase, bpm, offset, fps=30):
    """lengths: shot lengths in frames, in output order; knobs: per shot None or (lo, hi) frames the shot may change
    by (its END cut moves by that much). Returns (new lengths, miss in s of every cut but the reel's end)."""
    period = 60.0 / bpm
    out, t = [], 0
    for n, knob in zip(lengths, knobs):
        if knob:
            end = t + n
            k = round(((end + 0.5) / fps + offset - phase) / period)          # nearest beat
            d = math.floor((k * period + phase - offset) * fps) - end         # cut on the frame at / before it
            if knob[0] <= d <= knob[1]:
                n += d
        out.append(n)
        t += n
    cuts = np.cumsum(out)[:-1] / fps
    return out, [abs(((c + offset - phase + period / 2) % period) - period / 2) for c in cuts]


def fit(lengths, knobs, phase, bpm, around, search=2.2, fps=30):
    """Music offset near `around` and shot lengths that put the most cuts on beats: (offset, lengths, misses)."""
    best = None
    for off in np.arange(max(0.0, around - search), around + search, 1 / 300):
        n, miss = snap(lengths, knobs, phase, bpm, off, fps)
        score = (round(float(np.mean(miss)), 4) if miss else 0.0, abs(off - around))   # ties: nearest to `around`
        if best is None or score < best[0]:
            best = (score, float(off), n, miss)
    return best[1], best[2], best[3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("music")
    ap.add_argument("bpm", type=float)
    ap.add_argument("--cuts", default="")
    ap.add_argument("--offset", type=float, default=0.0)
    ap.add_argument("--search", type=float, default=2.2)
    a = ap.parse_args()
    ph = beat_phase(a.music, a.bpm)
    print(f"first beat at {ph:.3f}s, period {60 / a.bpm:.4f}s")
    if a.cuts:
        cuts = [float(c) for c in a.cuts.split(",")]
        score, off, worst = best_offset(ph, a.bpm, cuts, a.offset, a.search)
        print(f"offset {off:.3f}s: mean miss {score * 1000:.0f} ms, worst {worst * 1000:.0f} ms")


if __name__ == "__main__":
    main()
