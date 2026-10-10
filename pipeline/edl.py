"""Edit decision list: maps OUTPUT time to SOURCE time and back.

script["edl"] = [{"src": [a, b]}, {"hold": t_src, "dur": d}, ...]   (default: the whole source)
  src  : play source a..b
  hold : show the single source frame at t_src for d seconds (audio: silence)
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
        return max(0, min(n_src - 1, int(round(self.src_time(i / FPS) * FPS))))

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
