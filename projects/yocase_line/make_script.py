"""YOCASE product line (4 shampoos) -> script.json. The worked example of the product-lineup format
(formats/product-lineup/FORMAT.md) and of the videographer skill (.claude/skills/reel-videographer).

python projects/yocase_line/make_script.py [out.json]

Footage notes that drive the edit (watched on contact sheets, not read from the transcript):
- In IMG_2468 she says the Balance lines while holding Fix Color, in IMG_2469 the Fix Color lines holding Balance.
  So both blocks use only shots where her mouth is hidden (bottle raised in front of the face, close-ups) with her
  own words laid over (audio.voice_over), never her talking face with the other product's words.
- Fix Color: she walks the bottle up to the lens herself (115.8-116.5) - a real push; the defocused overshoot
  (116.6-117.9) is cut out with a light zoom-through.
- Ending: she rushes in with all four bottles until they cover the lens, then pulls back (frame-fill reveal).
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "pipeline"))
import beats  # noqa: E402

F = 30
fr = lambda t: int(round(t * F))
q = lambda t: round(round(t * F) / F, 4)
G, R, B, C = "#22A866", "#C4207F", "#4A5BD8", "#0FA0DC"
PURPLE = "#8A2E92"
MUSIC = "music_03_gimme_that_groove_112bpm_full.wav"
BPM = 112

# (name, src a, src b | hold dur, knob that moves the cut at the END of the shot onto a beat: (what, min f, max f)
# of cut movement; a head knob moves the start the other way, so its max is how much earlier the shot may start)
SHOTS = [
    ("intro_a",   19.15, 20.30, ("tail", -3, 3)),       # Наші лінійки.
    ("intro_b",   20.70, 22.533, ("head", 0, 3)),      # Кому і яка підійде. Поїхали!  ends on the wave's peak (swipe)
    ("energy",    33.72, 37.333, ("head", -1, 8)),      # Енерджі ... ; ends with the bottle at the lens (zoom-through)
    ("energy_cu", 59.05, 61.25, ("tail", -8, 8)),       # close-up: Тонізує та стимулює ріст
    ("repair",    76.68, 79.133, ("head", -1, 8)),      # RepairPlex – для сухого волосся ; she swings the bottle up, then to the lens
    ("repair_cu", 96.95, 100.60, ("tail", -4, 8)),      # close-up: Відновлення структури, зменшення ламкості
    ("bal_raise", 141.60, 142.80, ("tail", -6, 4)),     # Balance raised to the lens, face hidden (her words are muted)
    ("bal_b",     149.50, 149.833, ("head", -3, 8)),    # Balance held at the lens, B framing; ends on the sharpest label
    ("hold",      149.833, 1.1, None),                   # hero freeze
    ("bal_c",     149.833, 150.25, ("tail", -6, 2)),    # the hold releases
    ("fix_a",     115.73, 116.53, ("head", -6, 8)),     # Fix Color at her face, she walks it up to the lens (real push)
    ("fix_cu",    117.95, 121.60, ("tail", -6, 6)),     # ...the settled close-up (the defocused overshoot is cut out)
    ("lens",      215.75, 216.17, ("head", -3, 4)),     # she rushes in with all four bottles until they cover the lens
    ("outro",     217.75, 223.75, None),                # the bottles pull away (frame-fill reveal); CTA
]
period = 60 / BPM
phase = beats.beat_phase(ROOT / "assets" / "music" / MUSIC, BPM)
lengths = [fr(b) if name == "hold" else fr(b) - fr(a) for name, a, b, knob in SHOTS]
# many offsets fit equally once the cuts snap (beats.fit finds them); this one starts the track's groove section
offset = 18.423
lengths, m = beats.snap(lengths, [k[1:] if k else None for *_, k in SHOTS], phase, BPM, offset)
shots, out, t = [], {}, 0
for (name, a, b, knob), n in zip(SHOTS, lengths):
    if name == "hold":
        b = n / F
    elif knob and knob[0] == "head":          # the end is pinned (a gesture), the start gives
        a = (fr(b) - n) / F
    else:
        b = (fr(a) + n) / F
    shots.append((name, q(a), round(b, 4) if name == "hold" else q(b)))
    out[name] = (q(t / F), q((t + n) / F))
    t += n
dur = t / F
src0 = {n: a for n, a, b in shots}
o = lambda n: out[n][0]
end = lambda n: out[n][1]
at = lambda n, src_t: q(o(n) + src_t - src0[n])

edl, takes = [], []
for name, a, b in shots:
    if name == "hold":
        edl.append({"hold": a, "dur": b})
    else:
        edl.append({"src": [a, b]}); takes.append([a, b])
tk = {n: i + 1 for i, n in enumerate(n for n, a, b in shots if n != "hold")}      # 1-based take index

# voice laid over the right product (in these two clips she holds the other bottle while speaking)
vo = [
    {"src": [q(112.50), q(114.62)], "at": q(o("bal_raise") + 0.05)},     # Баланс для жирного волосся
    {"src": [q(127.80), q(129.35)], "at": q(o("bal_raise") + 2.17)},     # Зміцнення та блиск
    {"src": [q(145.95), q(149.45)], "at": q(o("fix_cu") + 0.10)},        # FixColor ... on the landed close-up
]
mute = [[o("bal_raise"), end("fix_cu")]]
w_vo = lambda k, src_t: q(vo[k]["at"] + src_t - vo[k]["src"][0])


def label(text, color, t_):
    return {"text": f"*{text}*", "literal": True, "t": t_, "color": color, "scale": 1.3, "anim": "pop"}


# every placement stays inside the IG crop-safe area (x 128-952, y 250-1480; rail x > 850 and y > 1050): the close-up
# callouts sit left of the pump, the Balance ones on the wall right of her
closeup_place = {"x": 128, "y": 280, "safe": [128, 250, 560, 640]}
screens = [
    {"take": tk["intro_a"], "blocks": [{"lines": ["наші лінійки"]}]},
    {"take": tk["intro_b"], "blocks": [{"lines": ["кому і яка _підійде_"]},
                                       {"lines": [{"text": "*поїхали*", "anim": "pop", "scale": 1.8}], "behind": False}]},
    {"take": tk["energy"], "blocks": [{"lines": [label("energy", G, at("energy", 33.85)), "щоденний догляд",
                                                 "для _нормального_ волосся"]}]},
    {"take": tk["energy_cu"], "blocks": [{"lines": [{"text": "тонізує та", "color": G}, {"text": "стимулює *ріст*", "color": G}],
                                          "behind": False, "place": closeup_place}]},
    {"take": tk["repair"], "blocks": [{"lines": [label("repair plex", R, at("repair", 76.80)), "для _сухого_ волосся"]}]},
    {"take": tk["repair_cu"], "blocks": [{"lines": ["відновлення", "структури", {"text": "зменшення", "color": R},
                                                    {"text": "*ламкості*", "color": R}],
                                          "behind": False, "place": closeup_place}]},
    {"take": tk["bal_raise"], "t1_override": end("bal_c"), "blocks": [        # right of the bottle, on the wall
        {"lines": [label("balance", B, w_vo(0, 112.61)), "для _жирного_", "волосся"], "behind": False,
         "place": {"x": 620, "y": 280, "safe": [590, 250, 940, 560]}},
        {"lines": [{"text": "зміцнення та", "color": B}, {"text": "*блиск*", "color": B}], "behind": False,
         "place": {"x": 650, "y": 600, "safe": [590, 560, 940, 820]}}]},
    {"take": tk["fix_cu"], "blocks": [                                         # beside the pump, two short blocks
        {"lines": [label("fix color", C, w_vo(2, 146.09)), "для _фарбованого_", "волосся"], "behind": False,
         "until": w_vo(2, 147.93), "place": closeup_place},
        {"lines": ["без вимивання", {"text": "*кольору*", "color": C}], "behind": False,
         "place": closeup_place}]},
    {"take": tk["outro"], "blocks": [{"lines": ["не знаєш яку", "лінійку _вибрати_"]},
                                     {"lines": ["пиши нам", "в *дірект*"]},
                                     {"lines": ["ми із задоволенням", "тобі допоможемо"]}]},
]

transitions = [   # playbook 2.1 / 2.2: speeds matched at the cut, zoom-throughs within the 1.6 upscale budget
    {"type": "push", "at": o("energy"), "dir": "right", "out": 4, "in": 9, "ease_in": "expo", "roll": 3, "shutter": 0.6},
    {"type": "zoom_through", "at": o("energy_cu"), "target": [516, 630], "scale": 1.35, "land": 1.0, "out": 6, "in": 6,
     "shutter": 0.6},
    {"type": "zoom_through", "at": o("repair_cu"), "target": [544, 601], "scale": 1.35, "land": 1.0, "out": 6, "in": 6,
     "shutter": 0.6},
    {"type": "zoom_through", "at": o("fix_cu"), "target": [480, 760], "scale": 1.3, "land": 1.0, "out": 5, "in": 6,
     "shutter": 0.6},
]
creep = lambda n, s0=1.0, **kw: {"from": s0, "to": round(s0 * (1 + 0.01 * (end(n) - o(n))), 4), "ease": "linear", **kw}
BAL = [600, 680]          # B framing keeps the bottle left of centre, the wall on the right takes the text
push_takes = {str(tk[n]): creep(n) for n in ("intro_a", "energy", "repair", "bal_raise", "outro")}
push_takes.update({
    str(tk["intro_b"]): creep("intro_b", 1.16, target="face"),                                   # A/B on the jump cut
    str(tk["energy_cu"]): {"from": 1.0, "to": 1.10, "ease": "expo", "dur": 0.3, "creep": 0.012, "target": [540, 900]},
    str(tk["repair_cu"]): {"from": 1.0, "to": 1.08, "ease": "expo", "dur": 0.3, "creep": 0.012, "target": [540, 900]},
    str(tk["bal_b"]): {"from": 1.16, "to": 1.16, "target": BAL},                                 # B framing on the label
    str(tk["bal_c"]): {"from": 1.16, "to": 1.195, "ease": "linear", "target": BAL},           # creeps through the freeze
    str(tk["fix_a"]): {"from": 1.0, "to": 1.0},                                                  # she pushes in herself
    str(tk["fix_cu"]): {"from": 1.0, "to": 1.08, "ease": "expo", "dur": 0.3, "creep": 0.012, "target": [540, 900]},
    str(tk["lens"]): {"from": 1.0, "to": 1.0},
})
camera = {
    "push": {"from": 1.0, "to": 1.0},
    "push_takes": push_takes,
    "freezes": [],
    "punches": [   # playbook 2.6: >= 1.12, anchored on the face, held to the cut
        {"t": at("energy", 35.75), "scale": 1.15, "in": 0.1, "until": end("energy"), "out": 0.0, "target": "face", "anchor": True},
        {"t": at("repair", 77.86), "scale": 1.15, "in": 0.1, "until": end("repair"), "out": 0.0, "target": "face", "anchor": True},
        {"t": at("outro", 221.04), "scale": 1.12, "in": 0.1, "until": end("outro"), "out": 0.0, "target": "face", "anchor": True},
    ],
    "shakes": [],
    "flashes": [{"t": o("hold"), "dur": 0.15, "amount": 0.6}],
    "transitions": transitions,
    "motion_blur": 0.5,
    "gains": {},
}
sfx = [
    {"name": "whoosh_quick_03_swish", "peak_at": o("energy"), "gain_db": -12},
    {"name": "whoosh_05_swipe_zoom", "peak_at": o("energy_cu"), "gain_db": -12},
    {"name": "bass_thump_01_sub", "peak_at": q(o("energy_cu") + 1 / F), "gain_db": -14},
    {"name": "whoosh_04_air_into_cut", "peak_at": o("repair_cu"), "gain_db": -12},
    {"name": "punch_soft_impact", "peak_at": q(o("repair_cu") + 1 / F), "gain_db": -14},
    {"name": "whoosh_05_swipe_zoom", "peak_at": o("fix_cu"), "gain_db": -14},
    {"name": "bass_thump_02_synth", "peak_at": q(o("fix_cu") + 1 / F), "gain_db": -14},
    {"name": "camera_shutter_01", "peak_at": o("hold"), "gain_db": -10},
    {"name": "whoosh_soft_02_wind_swoosh", "peak_at": o("outro"), "gain_db": -12, "move": "bottles cover the lens"},
    {"name": "pop_04_light", "peak_at": at("energy", 33.85), "gain_db": -20},
    {"name": "pop_02_bubble_a", "peak_at": at("repair", 76.80), "gain_db": -20},
    {"name": "pop_03_bubble_b", "peak_at": w_vo(0, 112.61), "gain_db": -20},
    {"name": "pop_04_light", "peak_at": w_vo(2, 146.09), "gain_db": -20},
    {"name": "ding_02_soft_chime", "peak_at": at("outro", 221.04), "gain_db": -18},
]
script = {
    "source": "build/yocase_line/source.ffconcat",
    "words": "build/yocase_line/words.json",
    "masks": "build/yocase_line/masks.npy",
    "track": "build/yocase_line/track.json",
    "src_duration": 228.6333,
    "takes": takes,
    "edl": edl,
    "style": {"accent": {"color": PURPLE, "outline": "0 0 1px rgba(40,0,45,.85), 0 0 1px rgba(40,0,45,.85)"},
              "label": {"color": PURPLE}},
    "screens": screens,
    "doodles": [],
    "camera": camera,
    "grade": {"lift": 0.01, "contrast": 1.04, "saturation": 1.04, "vignette": 0.04},
    "audio": {"voice": {"gain_db": 0, "process": False}, "voice_over": vo, "mute": mute,
              "music": {"file": MUSIC, "gain_db": -18, "offset": round(offset, 3), "fade_in": 0, "fade_out": 0.8,
                        "dropouts": []},
              "sfx": sfx},
}
path = sys.argv[1] if len(sys.argv) > 1 else ROOT / "projects" / "yocase_line" / "script.json"
json.dump(script, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(f"duration {dur:.2f}s; music offset {offset:.3f}; cuts miss beats by {1000 * sum(m) / len(m):.0f} ms mean, "
      f"worst {1000 * max(m):.0f}")
for (k, v), mm in zip(out.items(), [0] + m):  # miss of the cut INTO the shot
    print(f"  {k:10s} {v[0]:6.2f}-{v[1]:6.2f}  src {src0[k]:7.3f}  beat miss {mm * 1000:4.0f} ms")
