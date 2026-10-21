"""assets.py: exact lookup for renders (library, the creator's local folder, any audio extension), ranked search for
writing a script, and the SFX peak. The library files are tracked; nothing here decodes audio."""
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "pipeline"))
import assets  # noqa: E402
from common import ROOT  # noqa: E402


class LocalFolder(unittest.TestCase):
    """assets/local/ replaced by an empty scratch folder (the developer's own files must not change the results)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.saved = assets.LOCAL
        assets.LOCAL = Path(self.tmp.name)

    def tearDown(self):
        assets.LOCAL = self.saved
        self.tmp.cleanup()


class Find(LocalFolder):
    def test_library_paths_unchanged(self):
        self.assertEqual(assets.find("sfx", "pop_04_light"), ROOT / "assets" / "sfx" / "pop_04_light.wav")
        self.assertEqual(assets.find("sfx", "pop_04_light.wav"), ROOT / "assets" / "sfx" / "pop_04_light.wav")
        m = "music_03_gimme_that_groove_112bpm_full.wav"
        self.assertEqual(assets.find("music", m), ROOT / "assets" / "music" / m)

    def test_never_fuzzy(self):
        self.assertIsNone(assets.find("sfx", "whoosh_7"))
        self.assertIsNone(assets.find("sfx", "sparkle"))
        self.assertIsNone(assets.find("music", "groove"))

    def test_local_file_any_extension(self):
        (assets.LOCAL / "sfx").mkdir()
        mine = assets.LOCAL / "sfx" / "boom.mp3"
        mine.write_bytes(b"")
        self.assertEqual(assets.find("sfx", "boom"), mine)
        self.assertEqual(assets.find("sfx", "boom.wav"), mine)        # the stem with any audio extension

    def test_script_folder(self):
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "inserts").mkdir()
            own = Path(d) / "inserts" / "ding.m4a"
            own.write_bytes(b"")
            self.assertIsNone(assets.find("sfx", "ding"))
            self.assertEqual(assets.find("sfx", "ding", Path(d)), own)

    def test_paths(self):
        p = ROOT / "assets" / "sfx" / "pop_04_light.wav"
        self.assertEqual(assets.find("sfx", str(p)), p)
        self.assertEqual(assets.find("sfx", "assets/sfx/pop_04_light.wav"), p)
        self.assertIsNone(assets.find("sfx", "/no/such/file.wav"))


class Search(LocalFolder):
    def test_music_by_a_word(self):
        rows, exact = assets.search("music", "groove")
        self.assertTrue(exact)
        self.assertEqual([r["name"] for r in rows], ["music_03_gimme_that_groove_112bpm_full.wav"])
        self.assertEqual(rows[0]["title"], "Gimme that Groove!")

    def test_one_row_per_track(self):
        names = [r["name"] for r in assets.search("music")[0]]
        self.assertFalse(any("_edit" in n for n in names))
        self.assertEqual(len(names), len(set(names)))

    def test_track_number_and_words(self):
        self.assertEqual([r["name"] for r in assets.search("music", "3")[0]],
                         ["music_03_gimme_that_groove_112bpm_full.wav"])
        self.assertEqual(len(assets.search("music", "gimme groove")[0]), 1)

    def test_similar_only_when_no_word_matches(self):
        rows, exact = assets.search("sfx", "whoosh_7")
        self.assertFalse(exact)
        self.assertNotIn("whoosh_7", [r["name"] for r in rows])
        rows, exact = assets.search("sfx", "sparkle")
        self.assertTrue(exact)
        self.assertEqual(len(rows), 4)

    def test_local_rows(self):
        (assets.LOCAL / "music").mkdir()
        (assets.LOCAL / "music" / "my_song_96bpm.mp3").write_bytes(b"")
        rows, exact = assets.search("music", "song")
        self.assertEqual([(r["name"], r["bpm"], r.get("local")) for r in rows], [("my_song_96bpm.mp3", 96, True)])


class Peaks(unittest.TestCase):
    def test_loudest_sample_of_any_channel(self):
        x = np.zeros((48000, 2), np.float32)
        x[2400, 1] = -0.9                       # 50 ms, right channel, negative
        x[100, 0] = 0.5
        self.assertAlmostEqual(assets.peak_seconds(x.reshape(-1), 48000, 2), 0.05)
        self.assertEqual(assets.peak_seconds(np.zeros(0, np.float32), 48000, 2), 0.0)

    def test_credits_win(self):
        self.assertEqual(assets.sfx_peak(ROOT / "assets" / "sfx" / "whoosh_quick_03_swish.wav"), 0.082)

    def test_music_info(self):
        info = assets.music_info(ROOT / "assets" / "music" / "music_03_gimme_that_groove_112bpm_edit28s_from19.30.wav")
        self.assertEqual((info["title"], info["bpm"]), ("Gimme that Groove!", 112))
        self.assertEqual(assets.music_info(Path("x/her_track_128bpm.mp3"))["bpm"], 128)
        self.assertIsNone(assets.music_info(Path("x/her_track.m4a"))["bpm"])


if __name__ == "__main__":
    unittest.main()
