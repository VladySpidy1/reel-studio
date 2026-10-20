"""Edit decision list: maps OUTPUT time to SOURCE time and back.

script["edl"] = [{"src": [a, b]}, {"hold": t_src, "dur": d}, ...]   (default: the whole source)
  src  : play source a..b
  hold : show the single source frame at t_src for d seconds (audio: silence)

The picture's own sound follows the edl. script["audio"] can move the voice independently (J/L cuts,
B-roll under a line, a line laid over the right product shot):
  voice_over: [{"src": [a, b], "at": out_t, "gain_db": 0}]   source sound a..b heard from output time out_t
  mute:       [[t0, t1], ...]                                 output ranges where the picture's sound is off
"""
from common import FPS


class EDL:
    def __init__(self, segs, src_duration):
        self.segs = segs or [{"src": [0.0, src_duration]}]
        self.items = []
        t = 0.0
        for s in self.segs:
            d = (s["src"][1] - s["src"][0]) if "src" in s else s["dur"]
            self.items.append((t, t + d, s))
            t += d
        self.duration = t

    def src_time(self, out_t):
        for o0, o1, s in self.items:
            if out_t < o1 or s is self.items[-1][2]:
                if "src" in s:
                    return min(s["src"][1], s["src"][0] + max(0.0, out_t - o0))
                return s["hold"]
        return self.items[-1][2].get("hold", 0.0)

    def src_frame(self, i, n_src):
        """Source frame shown at output frame i, in whole frames (segment edges snap to frames), so a
        segment never repeats or skips a frame however its times fall between frames."""
        for o0, o1, s in self.items:
            if i < round(o1 * FPS) or s is self.items[-1][2]:
                f = round(s["src"][0] * FPS) + i - round(o0 * FPS) if "src" in s else round(s["hold"] * FPS)
                if "src" in s:
                    f = min(f, round(s["src"][1] * FPS) - 1)
                return max(0, min(n_src - 1, f))
        return 0

    def out_time(self, src_t, clamp=True):
        """First output time showing source time src_t (None if it was cut and clamp=False)."""
        for o0, o1, s in self.items:
            if "src" in s and s["src"][0] - 1e-6 <= src_t <= s["src"][1] + 1e-6:
                return o0 + src_t - s["src"][0]
        if not clamp:
            return None
        # cut away: snap to the nearest kept boundary
        best = None
        for o0, o1, s in self.items:
            if "src" not in s:
                continue
            for st, ot in ((s["src"][0], o0), (s["src"][1], o1)):
                if best is None or abs(st - src_t) < best[0]:
                    best = (abs(st - src_t), ot)
        return best[1]


class VoiceMap:
    """Where source sound is HEARD in the output: the picture's own sound (edl minus audio.mute) plus
    audio.voice_over segments, which win where both apply."""

    def __init__(self, edl, audio=None):
        self.edl = edl
        self.voice_over = (audio or {}).get("voice_over", [])
        self.mute = (audio or {}).get("mute", [])
        self.warnings = []
        for k, v in enumerate(self.voice_over):     # the mix plays both copies; captions follow only the voice-over
            for o0, o1, s in edl.items:
                if "src" not in s:
                    continue
                a, b = max(v["src"][0], s["src"][0]), min(v["src"][1], s["src"][1])
                if b - a > 0.05 and not self._muted(o0 + a - s["src"][0], o0 + b - s["src"][0]):
                    self.warnings.append(f"voice_over {k + 1} ({v['src'][0]:.2f}-{v['src'][1]:.2f}) is also heard "
                                         f"unmuted in the picture at {o0 + a - s['src'][0]:.2f}s: add it to audio.mute")

    def _muted(self, t0, t1, step=0.01):
        t = t0
        while t < t1:
            if not any(m0 <= t < m1 for m0, m1 in self.mute):
                return False
            t += step
        return True

    def _heard(self, src_t):
        """(output time, output start of the segment it plays in) or None."""
        for v in self.voice_over:
            a, b = v["src"]
            if a - 1e-6 <= src_t <= b + 1e-6:
                return v["at"] + src_t - a, v["at"]
        for o0, o1, s in self.edl.items:
            if "src" in s and s["src"][0] - 1e-6 <= src_t <= s["src"][1] + 1e-6:
                o = o0 + src_t - s["src"][0]
                if not any(m0 <= o < m1 for m0, m1 in self.mute):
                    return o, o0
        return None

    def word_time(self, w):
        """Output start of a transcript word {"s", "e"} if it is heard (judged at its midpoint), else None.
        A word clipped by its segment's start begins with the segment."""
        mid = (w["s"] + w["e"]) / 2
        h = self._heard(mid)
        return None if h is None else max(h[1], h[0] - (mid - w["s"]))
