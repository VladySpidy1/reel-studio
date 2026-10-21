"""audio.py filter strings: an old script's mix is unchanged string for string, the keyframed duck rises only in long
gaps (no pump at the reel's start, no swell at its end), and speech cuts get handle-based crossfades. No ffmpeg."""
import contextlib
import io
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import audio  # noqa: E402

SPEC = {"src": "src.mov", "duration": 4.0, "voice": {"gain_db": 0},
        "edl": [{"src": [0.5, 2.0]}, {"hold": 2.0, "dur": 0.5}, {"src": [3.0, 5.0]}],
        "mute": [[1.0, 1.2]], "voice_over": [{"src": [6.0, 6.5], "at": 3.2}],
        "sfx": [{"file": "pop.wav", "t": 1.25, "gain_db": -20}],
        "music": {"file": "m.wav", "gain_db": -18, "offset": 18.423, "fade_in": 0.05, "fade_out": 0.8,
                  "dropouts": [[2.0, 2.4]]}}
# build_filter(SPEC) before the crossfade, duck and stem existed (HEAD of Phase 4a)
OLD = ("[0:a]aresample=48000,aformat=channel_layouts=stereo,atrim=start=0.500000:duration=1.500000,asetpts=PTS-STARTPTS,"
       "afade=t=in:d=0.006,afade=t=out:st=1.494000:d=0.006[e0];anullsrc=r=48000:cl=stereo,atrim=0:0.500000[e1];"
       "[0:a]aresample=48000,aformat=channel_layouts=stereo,atrim=start=3.000000:duration=2.000000,asetpts=PTS-STARTPTS,"
       "afade=t=in:d=0.006,afade=t=out:st=1.994000:d=0.006[e2];[e0][e1][e2]concat=n=3:v=0:a=1[vedl];[vedl]anull[vpic];"
       "[vpic]asetnsamples=n=48:p=0[vps];[vps]volume=eval=frame:volume='if(between(t,1.0000,1.2000),"
       "max(0.0,1-min(t-1.0000,1.2000-t)/0.01),1)'[vm0];[0:a]aresample=48000,aformat=channel_layouts=stereo,"
       "atrim=start=6.000000:end=6.500000,asetpts=PTS-STARTPTS,afade=t=in:d=0.006,afade=t=out:st=0.494000:d=0.006,"
       "volume=0dB,adelay=153600S|153600S[vo0];[vm0][vo0]amix=inputs=2:normalize=0:dropout_transition=0[vsum];"
       "[vsum]volume=0dB[voice];[1:a]aresample=48000,aformat=channel_layouts=stereo,volume=-20dB,adelay=1250|1250[s0];"
       "[2:a]aresample=48000,aformat=channel_layouts=stereo,atrim=start=18.423,asetpts=PTS-STARTPTS,volume=-18dB,"
       "afade=t=in:d=0.05,afade=t=out:st=3.200:d=0.8,volume=eval=frame:volume='if(between(t,2.000,2.400),"
       "max(0.0,1-min(t-2.000,2.400-t)/0.04),1)'[music];[voice][s0][music]amix=inputs=3:normalize=0:"
       "dropout_transition=0,apad=whole_dur=4.000,atrim=0:4.000[mix]")
DUCK = {"rise_db": 4, "lead": 0.15, "release": 0.4, "min_gap": 0.8}


def gain_db(expr, t):
    """The duck's level at output time t: ffmpeg's max/min/t expression evaluated by Python."""
    import math
    return 20 * math.log10(eval(expr, {"max": max, "min": min, "t": t}))


class OldScripts(unittest.TestCase):
    def test_filter_unchanged(self):
        inputs, fc = audio.build_filter(SPEC)
        self.assertEqual(fc, OLD)
        self.assertEqual(inputs, ["-i", "src.mov", "-i", "pop.wav", "-i", "m.wav"])

    def test_xfade_0_is_the_old_path(self):
        self.assertEqual(audio.build_filter({**SPEC, "xfade_frames": 0, "clip_edges": [[0, 10]]})[1], OLD)

    def test_music_chain_without_duck(self):
        self.assertEqual(audio.music_chain(SPEC["music"], 4.0, 2) + "[music]",
                         OLD[OLD.index("[2:a]"):OLD.index(";[voice][s0]")])


class Duck(unittest.TestCase):
    def expr(self, spans, dur):
        gaps = audio.duck_gaps(spans, dur, DUCK["min_gap"])
        return gaps, audio.duck_expr(gaps, DUCK)

    def test_rises_only_in_long_gaps(self):
        gaps, e = self.expr([(0.8, 2.0), (2.5, 3.2), (4.6, 5.2)], 6.0)
        self.assertEqual(len(gaps), 3)
        self.assertAlmostEqual(gain_db(e, 0.0), 4.0, places=2)       # a silent opening: up from frame 0, no ramp
        self.assertAlmostEqual(gain_db(e, 1.5), 0.0, places=2)       # speech
        self.assertAlmostEqual(gain_db(e, 2.25), 0.0, places=2)      # a 0.5 s gap stays down
        self.assertAlmostEqual(gain_db(e, 4.0), 4.0, places=2)       # a 1.4 s gap
        self.assertAlmostEqual(gain_db(e, 5.9), 4.0, places=2)       # the ending
        self.assertLess(gain_db(e, 3.4), 4.0)                        # 0.4 s release after speech
        self.assertAlmostEqual(gain_db(e, 3.6), 4.0, places=2)
        self.assertAlmostEqual(gain_db(e, 4.6), 0.0, places=2)       # down again by the next onset (0.15 s lead)

    def test_no_pump_at_the_start(self):
        gaps, e = self.expr([(0.14, 3.8)], 4.0)
        self.assertEqual(gaps, [])
        self.assertAlmostEqual(gain_db(e, 0.05), 0.0, places=3)

    def test_no_swell_at_the_end(self):
        gaps, e = self.expr([(1.0, 3.8)], 4.0)
        self.assertEqual(gaps, [(-1, 1.0)])
        self.assertAlmostEqual(gain_db(e, 3.95), 0.0, places=3)

    def test_chain_order(self):
        music = {**SPEC["music"], "duck": DUCK}
        chain = audio.music_chain(music, 6.0, 2, [(0.8, 2.0), (3.2, 5.2)])
        drop, rise = chain.index("if(between(t,2.000"), chain.index("volume='1+")
        self.assertLess(chain.index("asetnsamples=n=48:p=0"), drop)
        self.assertLess(drop, rise)
        self.assertTrue(chain.startswith(audio.music_chain(SPEC["music"], 6.0, 2).split(",volume=eval")[0]))

    def test_sidechain_ignored_with_duck(self):
        spec = {**SPEC, "music": {**SPEC["music"], "duck": DUCK, "sidechain": {"threshold": 0.05}},
                "speech": [(0.5, 1.5)]}
        with contextlib.redirect_stdout(io.StringIO()) as out:
            fc = audio.build_filter(spec)[1]
        self.assertIn("sidechain ignored", out.getvalue())
        self.assertNotIn("sidechaincompress", fc)
        self.assertNotIn("[vsc]", fc)

    def test_stem(self):
        fc = audio.build_filter({**SPEC, "stem": True})[1]
        self.assertIn("asplit=2[music][ms]", fc)
        self.assertIn("[ms]apad=whole_dur=4.000,atrim=0:4.000[mstem]", fc)


class Crossfade(unittest.TestCase):
    EDL = [{"src": [1.0, 2.0]}, {"src": [3.0, 4.0]}, {"hold": 4.0, "dur": 0.5}, {"src": [4.0, 5.0]},
           {"src": [5.0, 6.0]}]

    def parts(self, edges=((0, 10),)):
        head, parts = audio._voice_edl(self.EDL, 2, [list(e) for e in edges])
        return head, {p[p.rindex("["):]: p for p in parts}

    def test_cut_gets_a_two_frame_crossfade(self):
        head, p = self.parts()
        self.assertEqual(head, "[vedl]")
        e0, e1 = p["[e0]"], p["[e1]"]
        self.assertIn("atrim=start_sample=48000:end_sample=97600", e0)          # 1 frame of handle past 2.0
        self.assertIn("afade=t=in:d=0.006", e0)                                 # the reel's start
        self.assertIn("afade=t=out:st=0.966667:d=0.066667:curve=qsin", e0)
        self.assertIn("atrim=start_sample=142400:end_sample=192000", e1)        # 1 frame before 3.0
        self.assertIn("afade=t=in:st=0:d=0.066667:curve=qsin", e1)
        self.assertIn("adelay=46400S|46400S", e1)                               # placed 1 frame early
        self.assertIn("amix=inputs=4:normalize=0", p["[vedl]"])

    def test_holds_contiguous_pieces_and_reel_ends(self):
        head, p = self.parts()
        self.assertIn("afade=t=out:st=1.027333:d=0.006", p["[e1]"])             # before the hold (after its handle)
        self.assertIn("afade=t=in:d=0.006", p["[e3]"])                          # after the hold
        self.assertNotIn("afade=t=out", p["[e3]"])                               # 4.0-5.0 runs on into 5.0-6.0
        self.assertNotIn("afade=t=in", p["[e4]"])
        self.assertIn("afade=t=out:st=0.994000:d=0.006", p["[e4]"])             # the reel's end
        self.assertNotIn("[e2]", p)                                              # a hold is silence: no input

    def test_handle_limited_by_the_clip(self):
        _, p = self.parts(((0, 2.01), (2.01, 10)))
        self.assertIn("atrim=start_sample=48000:end_sample=96480", p["[e0]"])    # 10 ms left in the clip
        self.assertIn("d=0.020000:curve=qsin", p["[e0]"])
        _, p = self.parts(((0, 2.003), (2.003, 10)))
        self.assertIn("afade=t=out:st=0.994000:d=0.006", p["[e0]"])              # under 6 ms: the old fades


if __name__ == "__main__":
    unittest.main()
