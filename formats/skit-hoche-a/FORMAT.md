# Format: skit «хоче X, а Y»

Comedy skits: each take is one numbered situation, "she wants X, but Y happens". First reel: TOSUMI
(`projects/tosumi_hair`, finished on Windows; it stays an untouched archive). Start from `template.json`; the
camera creep, presets and lint profile are in `format.json`.

## Structure that worked
- **Hook title** for the first ~1.6 s (`"preset": "hook"`, literal lines, e.g. «у якому № / _впізнала себе?_»).
- **One screen per take, two blocks:** the setup `№N / хоче … _мрія_` near her at chest height, the punch
  `// а … *(провал)*` elsewhere (often top-left). Both halves stay visible together until the cut.
- Pink = the fail/punch word only (consistent, so viewers anticipate it). Dream words = white serif.
- **Interjection gag** («ой», «ну», «фу») after a silent beat: a video-only freeze on the beat + `record_scratch_01`
  (-9 dB) + a music dropout, then the word as its own block with `"preset": "interjection"` (big pink pop),
  `until` ~0.9 s later, `place` beside the face, plus a punch-in, a shake and a thump.
- **Final punchline:** its own block with `"preset": "punchline"`.
- **Product payoff:** after the last word, a 1.2 s hold in the edl on the sharpest product frame with a flash, the
  brand's `hero` SFX stack and a hand-drawn circle doodle; then let her walk out so the end frame (an empty hallway)
  loops into frame 0. No text in the last 0.6 s.
- Silent beats are the comedy: no pause trimming here.

## Camera and sound
- Slow push 1.00 -> 1.04 per take with a linear creep (`format.json`), punch-ins on fail words (`target: "face"`,
  `anchor: true`), per-take `gains` only if the takes differ in white balance.
- **Changes against tosumi_hair:** a linear creep replaces in-out + `cut_in` (in-out stops at both cuts and
  `cut_in` pumps, lint_edit.py and playbook 2.8-2.9); fail-word punches move from 1.05-1.07 to an anchored 1.12,
  which reads as deliberate (playbook 2.6).
- **SFX:** `whoosh_soft_01_air_sweep` on every take cut (-11 dB), `boing_01_spring` / `punch_soft_impact` on gags
  (-13..-16), `bass_thump_02_synth` on a big pop (-9), `pop_04_light` on pink words (-23). Cartoon SFX and a whoosh
  on every take cut are **allowed only in this format** (its lint profile); a brand's own bans still apply.
- **Music:** the brand bed, static (no sidechain); 40 ms-ramped `dropouts` for a gag freeze.

## Learned rules
- Corrections from reels go to `learned/formats/skit-hoche-a.md` (tracked, shared by both Macs); rules that hold are folded into this file.
