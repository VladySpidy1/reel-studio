"""trim.py on synthetic footage: tone bursts as words over a noise floor, a hand-made words list whose ends are early
(as whisper's are), and the pause, pad, take and stats rules of audio-timing.md. numpy only: no ffmpeg, no whisper."""
import math
import sys
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import trim  # noqa: E402

FPS = 30
SR = trim.SR
EARLY = 0.15               # whisper's word ends are early by about this much on raw phone audio
H = 1 / 60                 # tone edges sit mid-frame, so a pad's grid rounding is unambiguous


def rms_db(x):
    return 20 * math.log10(math.sqrt(float(np.mean(x * x))) + 1e-12)


class Synth:
    """One clip of synthetic footage: a noise floor, tone bursts as words, noise bursts as breaths and rustles."""

    def __init__(self, dur, floor_db=-78.0, seed=7, name="A", offset=0.0):
        self.rng = np.random.default_rng(seed)
        self.x = self.rng.standard_normal(int(dur * SR)) * 10 ** (floor_db / 20)
        self.name, self.offset, self.dur = name, offset, dur
        self.words, self.tones = [], []

    def _put(self, t0, t1, y):
        i0 = int(round(t0 * SR))
        self.x[i0:i0 + len(y)] += y

    def word(self, text, t0, t1, db=-18.0, p=0.95, early=EARLY):
        """A word that sounds from t0 to t1 (clip time); its transcript end is `early` seconds before t1."""
        n = int(round((t1 - t0) * SR))
        t = np.arange(n) / SR
        y = sum(np.sin(2 * np.pi * 150 * k * t + k) / k for k in range(1, 5))
        y *= 10 ** (db / 20) / math.sqrt(float(np.mean(y * y)))
        self._put(t0, t1, y)
        self.tones.append((t0 + self.offset, t1 + self.offset))
        self.words.append({"w": text, "s": round(t0 + self.offset, 3), "e": round(t1 - early + self.offset, 3), "p": p,
                           "clip": self.name})
        return self

    def sound(self, t0, t1, db):
        """A breath, laugh, click or rustle: noise nobody transcribed."""
        n = int(round((t1 - t0) * SR))
        self._put(t0, t1, self.rng.standard_normal(n) * 10 ** (db / 20))
        return self

    def clip(self):
        return {"name": self.name, "offset": self.offset, "duration": self.dur}

    def levels(self):
        return trim.band_levels(self.x)


def run(*synths, **kw):
    clips = [s.clip() for s in synths]
    words = [w for s in synths for w in s.words]
    levels = {s.name: s.levels() for s in synths}
    return trim.plan(clips, words, levels, **kw)


def frames(t):
    return round(t * FPS)


def phrase(s, t, words):
    """Words of 0.5 s with 0.08 s between them from clip time t; returns the end of the last word."""
    for w in words:
        s.word(w, t, t + 0.5)
        t += 0.5 + 0.08
    return t - 0.08


class Pauses(unittest.TestCase):
    def setUp(self):
        s = Synth(14.0)
        # attempt 1: an inner pause after a sentence end (0.70 s, cut to the 10-frame beat), an inner pause inside a
        # phrase (0.70 s, cut to 3 + 4 frames) and a short pause (0.30 s, untouched)
        s.word("Перше", 1.0 + H, 1.6 + H).word("речення", 1.68 + H, 2.4 + H).word("тут.", 2.48 + H, 3.0 + H)
        s.word("Друге", 3.7 + H, 4.4 + H).word("ще", 4.48 + H, 5.1 + H)
        s.word("триває", 5.8 + H, 6.5 + H).word("далі", 6.8 + H, 7.4 + H).word("кінець.", 7.48 + H, 8.2 + H)
        self.s, self.p = s, run(s)

    def test_long_pauses_cut_short_ones_kept(self):
        r = self.p["ranges"]
        self.assertEqual(len(r), 3, r)
        gaps = [(b0, a1) for (a0, b0), (a1, b1) in zip(r, r[1:])]
        self.assertTrue(2.95 < gaps[0][0] < gaps[0][1] < 3.75, gaps)       # after «тут.»
        self.assertTrue(5.05 < gaps[1][0] < gaps[1][1] < 5.85, gaps)       # inside «ще ... триває»
        self.assertFalse(any(6.5 < a < 6.85 or 6.5 < b < 6.85 for a, b in r), r)   # the 0.30 s pause stays

    def test_pads_in_frames(self):
        r = self.p["ranges"]
        # in-points: the onset minus 4 frames, floored to the grid; the onset sits in frame floor(onset * 30)
        for (a, b), onset in zip(r[1:], (3.7 + H, 5.8 + H)):
            self.assertEqual(frames(onset - H) - frames(a), 4, (a, onset))
        # out-point inside a phrase: the voice end plus 3 frames (the frame holding the end, then 3 more)
        end = 5.1 + H
        self.assertEqual(frames(r[1][1]) - (math.floor(end * FPS) + 1), 3, r[1])

    def test_sentence_beat(self):
        a, b = self.p["ranges"][0][1], self.p["ranges"][1][0]
        end, onset = 3.0 + H, 3.7 + H
        kept = (frames(a) - (math.floor(end * FPS) + 1)) + (math.floor(onset * FPS) - frames(b))
        self.assertEqual(frames(a) - (math.floor(end * FPS) + 1), 10)
        self.assertEqual(kept, 14)

    def test_head_and_tail(self):
        # 0.15 s before the first onset and 0.4 s after the last voice end, on the grid (the measured onset and end
        # sit up to 15 ms outside the word: the 20 ms level windows reach past its edges)
        r = self.p["ranges"]
        onset, end = 1.0 + H, 8.2 + H
        self.assertTrue(onset - 0.15 - 1 / FPS - 0.016 < r[0][0] <= onset - 0.15, r[0])
        self.assertTrue(end + 0.4 <= r[-1][1] < end + 0.4 + 1 / FPS + 0.016, r[-1])

    def test_no_word_end_clipped(self):
        for t0, t1 in self.s.tones:
            self.assertTrue(any(a <= t0 and t1 <= b for a, b in self.p["ranges"]), (t0, t1, self.p["ranges"]))
        for (a, b), (a2, b2) in zip(self.p["ranges"], self.p["ranges"][1:]):
            for t0, t1 in self.s.tones:
                self.assertFalse(t0 < b < t1 or t0 < a2 < t1, "a cut lands in a word")
        self.assertTrue(all(b >= 3.0 + H + 3 / FPS for a, b in self.p["ranges"][:1]))

    def test_no_word_end_clipped_at_a_take_boundary(self):
        # a boundary is always cut; after a word without a sentence end only 3 frames (100 ms) follow its voice end,
        # less than whisper is early (150 ms): the end must come from the energy
        s = Synth(10.0)
        phrase(s, 1.0 + H, ["один", "два", "три"])
        phrase(s, 4.5 + H, ["чотири", "пять", "шість."])
        r = run(s)["ranges"]
        self.assertEqual(len(r), 2)
        end = s.tones[2][1]
        self.assertGreaterEqual(r[0][1], end + 3 / FPS - 1 / FPS / 2, (r[0], end))

    def test_grid(self):
        # frame times written with 4 decimals, like make_script.py's q(): within 0.002 frames of the grid
        for a, b in self.p["ranges"]:
            for t in (a, b):
                self.assertLess(abs(t * FPS - round(t * FPS)), 0.002, t)


class Sounds(unittest.TestCase):
    def test_burst_in_inner_pause_kept_and_flagged(self):
        s = Synth(8.0)
        phrase(s, 1.0 + H, ["один", "два"])
        s.sound(2.5, 2.7, -24)                                  # a 200 ms laugh in a 0.9 s pause
        phrase(s, 3.06 + H, ["три", "чотири"])
        p = run(s)
        self.assertEqual(len(p["ranges"]), 1, p["ranges"])
        self.assertTrue(any("2.1" in f or "2.2" in f for f in p["flags"]), p["flags"])

    def test_click_in_inner_pause_makes_no_segment(self):
        s = Synth(8.0)
        phrase(s, 1.0 + H, ["один", "два"])
        s.sound(2.6, 2.6 + 1 / FPS, -20)                       # a one-frame click (bottle tap) in a 0.9 s pause
        phrase(s, 3.06 + H, ["три", "чотири"])
        p = run(s)
        self.assertEqual(len(p["ranges"]), 2, p["ranges"])
        self.assertFalse(any(a <= 2.6 <= b for a, b in p["ranges"]))

    def test_rustle_in_take_gap_cut(self):
        s = Synth(14.0)
        phrase(s, 1.0 + H, ["один", "два", "три"])
        s.sound(4.5, 4.8, -30)                                  # a 300 ms rustle inside a 5 s gap between attempts
        phrase(s, 7.7 + H, ["чотири", "пять", "шість"])
        p = run(s)
        self.assertEqual(len(p["ranges"]), 2)
        self.assertFalse(any(a <= 4.6 <= b for a, b in p["ranges"]))

    def test_point_on_a_click_moves_off_it(self):
        s = Synth(10.0)
        phrase(s, 1.0 + H, ["один", "два", "три"])
        phrase(s, 4.0 + H, ["чотири", "пять", "шість"])
        base = run(s)["ranges"][1][0]                            # 4 frames before «чотири», on room tone: stays
        self.assertEqual(frames(base), 116)
        s.sound(base - 0.012, base + 0.012, -30)                # a click right on that frame
        self.assertLess(frames(run(s)["ranges"][1][0]), 116)

    def test_breath_kept(self):
        s = Synth(8.0)
        s.sound(1.7, 1.95 + H, -40)                             # an inhale right before the phrase
        phrase(s, 1.95 + H, ["вдих", "перед", "фразою"])
        self.assertLessEqual(run(s)["ranges"][0][0], 1.7)

    def test_breath_cut(self):
        s = Synth(8.0)
        s.sound(1.7, 1.95 + H, -40)
        phrase(s, 1.95 + H, ["вдих", "перед", "фразою"])
        a = run(s, params={"breath": "cut", "head": 0.05})["ranges"][0][0]
        self.assertGreater(a, 1.75)


class Takes(unittest.TestCase):
    def test_later_repeat_proposed(self):
        s = Synth(12.0)
        phrase(s, 1.0 + H, ["Відновлення", "структури,", "зменшення", "ламкості."])
        phrase(s, 6.0 + H, ["Відновлення", "структури,", "зменшення", "ламкості."])
        p = run(s)
        self.assertEqual([a["drop"] is not None for a in p["attempts"]], [True, False])
        self.assertEqual(len(p["ranges"]), 1)
        self.assertGreater(p["ranges"][0][0], 5.5)

    def test_fragment_does_not_supersede(self):
        s = Synth(12.0)
        phrase(s, 1.0 + H, ["Фікс-колор", "для", "фарбованого", "волосся."])
        phrase(s, 6.0 + H, ["Фікс-колор!"])
        p = run(s)
        self.assertIsNone(p["attempts"][0]["drop"])

    def test_template_lines_are_not_repeats(self):
        # two products said with the same template («для ... волосся») are two lines, not a retake
        s = Synth(16.0)
        phrase(s, 1.0 + H, ["RepairPlex", "–", "для", "сухого", "волосся."])
        phrase(s, 6.0 + H, ["Відновлення", "структури."])
        phrase(s, 10.0 + H, ["Баланс", "для", "жирного", "волосся"])
        self.assertEqual([a["drop"] for a in run(s)["attempts"]], [None, None, None])

    def test_latin_folds_to_cyrillic(self):
        self.assertEqual(trim.fold("FixColor для"), trim.fold("Фікс-колор для"))
        terms = {"fix color": {"heard_as": ["pixcolor"]}}
        self.assertEqual(trim.fold("PIXCOLOR", terms), trim.fold("Фікс колор", terms))

    def test_stop_drops_attempt(self):
        s = Synth(12.0)
        phrase(s, 1.0 + H, ["Енерджі", "щоденний", "стоп"])
        phrase(s, 3.2 + H, ["Енерджі", "щоденний", "догляд."])     # 0.48 s after «стоп»: no take gap, still split
        p = run(s)
        self.assertEqual(p["attempts"][0]["drop"], "стоп")
        self.assertEqual(len(p["ranges"]), 1)
        self.assertGreater(p["ranges"][0][0], 3.0)

    def test_min_shot_never_joins_across_a_dropped_attempt(self):
        s = Synth(14.0)
        s.word("Так.", 1.0 + H, 1.3 + H)                                   # a 0.3 s attempt
        phrase(s, 3.0 + H, ["це", "погано", "стоп"])                       # dropped
        phrase(s, 5.5 + H, ["А", "тепер", "добре."])
        p = run(s)
        self.assertEqual(len(p["ranges"]), 2, p["ranges"])
        self.assertLess(p["ranges"][0][1], 2.2)
        self.assertTrue(any("min_shot" in f for f in p["flags"]), p["flags"])

    def test_min_shot_undoes_the_smaller_inner_cut(self):
        s = Synth(12.0)
        phrase(s, 1.0 + H, ["один", "два"])                     # 1.08 s
        s.word("три", 2.8 + H, 3.3 + H)                         # alone: 0.5 s between two long pauses
        phrase(s, 4.3 + H, ["чотири", "пять"])                  # 1.0 s after «три»: the bigger cut stays
        p = run(s, params={"take_gap": 2.0})
        self.assertEqual(len(p["ranges"]), 2, p["ranges"])
        self.assertLess(p["ranges"][0][1], 3.8)
        self.assertGreater(p["ranges"][1][0], 3.6)

    def test_doubts(self):
        s = Synth(14.0)
        phrase(s, 1.0 + H, ["Зміцнення", "та", "блиск"])        # no sentence end
        s.word("Ну", 4.0 + H, 4.5 + H, p=0.3).word("ось.", 4.58 + H, 5.0 + H, p=0.4)
        p = run(s)
        d0, d1 = p["attempts"][0]["doubt"], p["attempts"][1]["doubt"]
        self.assertTrue(any("sentence" in d for d in d0), d0)
        self.assertTrue(any("probability" in d for d in d1), d1)

    def test_clip_edge_splits_attempts(self):
        a, b = Synth(4.0, name="A"), Synth(4.0, name="B", offset=4.0, seed=8)
        phrase(a, 2.0 + H, ["Наші", "лінійки."])
        phrase(b, 0.3 + H, ["Кому", "і", "яка."])
        p = run(a, b)
        self.assertEqual(len(p["attempts"]), 2)
        self.assertLessEqual(p["ranges"][0][1], 4.0)
        self.assertGreaterEqual(p["ranges"][1][0], 4.0)


class Beds(unittest.TestCase):
    def test_constant_bed_refused(self):
        s = Synth(8.0, floor_db=-30)
        phrase(s, 1.0 + H, ["музика", "під", "голосом."])
        p = run(s)
        self.assertEqual(len(p["refused"]), 1)
        self.assertLess(p["refused"][0][1], 25)
        self.assertIsNone(p["ranges"])

    def test_noisy_floor_finds_the_same_cuts(self):
        def make(floor):
            s = Synth(14.0, floor_db=floor)
            s.word("Перше", 1.0 + H, 1.6 + H).word("речення", 1.68 + H, 2.4 + H).word("тут.", 2.48 + H, 3.0 + H)
            s.word("Друге", 3.7 + H, 4.4 + H).word("ще", 4.48 + H, 5.1 + H)
            s.word("триває", 5.8 + H, 6.5 + H).word("кінець.", 6.58 + H, 7.3 + H)
            return run(s)
        quiet, noisy = make(-78), make(-46)
        self.assertGreater(noisy["clips"][0]["bed"], 25)
        self.assertEqual(quiet["ranges"], noisy["ranges"])


class Keeps(unittest.TestCase):
    def test_keep_fills_a_cut(self):
        s = Synth(14.0)
        phrase(s, 1.0 + H, ["Поїхали!"])
        phrase(s, 3.0 + H, ["перший", "продукт"])
        self.assertEqual(len(run(s)["ranges"]), 2)
        self.assertEqual(len(run(s, keep=[[1.6, 2.9]])["ranges"]), 1)

    def test_punch_keeps_the_beat(self):
        s = Synth(14.0)
        s.word("Поїхали", 1.0 + H, 2.0 + H)                     # no sentence end: 3 frames after it
        phrase(s, 2.7 + H, ["перший", "продукт"])               # 0.7 s later, inside the attempt
        base, punch = run(s)["ranges"], run(s, punch=[1.5])["ranges"]
        self.assertEqual((len(base), len(punch)), (2, 2))
        self.assertEqual(frames(punch[0][1]) - frames(base[0][1]), 7)       # 10 frames instead of 3


class Stats(unittest.TestCase):
    def test_removed_time_by_kind(self):
        clips = [{"name": "A", "offset": 0.0, "duration": 10.0}, {"name": "B", "offset": 10.0, "duration": 5.0}]
        words = [{"w": "раз", "s": 1.0, "e": 1.5}, {"w": "два.", "s": 2.0, "e": 2.5},       # a 0.5 s pause cut
                 {"w": "три", "s": 4.0, "e": 4.5}, {"w": "три", "s": 6.0, "e": 6.5},        # a retake dropped
                 {"w": "чотири.", "s": 11.0, "e": 11.6}]
        script = {"src_duration": 15.0, "edl": [{"src": [0.9, 1.6]}, {"src": [1.9, 2.6]}, {"src": [5.9, 6.6]},
                                                {"src": [10.9, 11.7]}]}
        st = trim.stats(script, clips, words)
        self.assertEqual(st["edits"], 3)
        self.assertAlmostEqual(st["out_s"], 2.9, places=3)
        self.assertEqual(st["raw_s"], 15.0)
        self.assertEqual(st["removed"]["pauses"], {"n": 1, "s": 0.3})
        self.assertEqual(st["removed"]["retakes"], {"n": 1, "s": 3.3})
        self.assertEqual(st["removed"]["dead_air"]["n"], 4)                 # clip heads and tails

    def test_untouched_reel(self):
        clips = [{"name": "A", "offset": 0.0, "duration": 28.8333}]
        st = trim.stats({"src_duration": 28.8333, "edl": [{"src": [0.0, 28.8333]}]}, clips, [])
        self.assertEqual((st["edits"], st["removed"]["pauses"]["n"], st["removed"]["dead_air"]["n"]), (0, 0, 0))


class Listing(unittest.TestCase):
    def test_product_moments_in_cut_ranges(self):
        events = [{"type": "to_lens", "t0": 5.0, "t_settle": 5.6, "growth": 2.0},
                  {"type": "to_lens", "t0": 8.0, "t_settle": 8.3, "growth": 1.2},          # too small
                  {"type": "to_lens", "t0": 1.2, "t_settle": 1.5, "growth": 1.8},          # inside the kept range
                  {"type": "sweep", "t0": 6.0, "t_peak": 6.1}]
        got = trim.product_moments(events, [[1.0, 3.0]])
        self.assertEqual([m["t0"] for m in got], [5.0])
        self.assertEqual(got[0]["keep"], [4.8, 5.9])

    def test_outtakes_join_spans_with_ticks(self):
        sr = 8000
        spans = [np.ones(4000), np.ones(2400) * 0.5]
        x, at = trim.join_outtakes(spans, sr)
        self.assertEqual(len(at), 2)
        self.assertEqual(at[0], 0.0)
        self.assertGreater(at[1], 0.5)
        tick = x[int(0.5 * sr):int(at[1] * sr)]
        self.assertGreater(np.abs(tick).max(), 0.01)                      # a tick between the spans
        self.assertLess(np.abs(tick).max(), 0.5)                          # and a soft one
        self.assertAlmostEqual(len(x) / sr, at[1] + 0.3, places=2)


if __name__ == "__main__":
    unittest.main()
