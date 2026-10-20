"""Check a script's edit against the videographer playbook before rendering (see .claude/skills/reel-videographer).

python lint_edit.py projects/<name>/script.json

Prints FAIL (breaks the picture: over-upscaled frames, strobing, too many transition types) and WARN (reads as
amateur: blips, pumping, mismatched whip speeds, whooshes on plain cuts, dead spans, beats missed) with output
times. Exit code 1 when anything FAILs. It only reads the script, the EDL and the camera path; it does not judge
taste (which shot, which word) - that stays with the editor. The thresholds and bans are the resolved script's lint
profile (pipeline/studio_default.json "lint", changed by the brand and the format); a brand's sfx_banned always
applies.
"""
import re
import sys
from fnmatch import fnmatch
from pathlib import Path

import camera as cam
import resolve
from common import FPS, ROOT, load_json
from edl import EDL

E_HELD, E_MOVING = 1.2, 1.65          # max upscale on a held frame / on a motion-blurred transition frame
MIN_GAP = 15                          # frames between two event moves
WHOOSH = re.compile(r"whoosh|swish|swoosh")
DESIGNED = ("push", "zoom_through", "spin")


def takes_out(script, edl):
    takes = [[round(edl.out_time(a) * FPS) / FPS, round(edl.out_time(b) * FPS) / FPS] for a, b in script["takes"]]
    takes[0][0], takes[-1][1] = 0.0, edl.duration
    return takes


def whip_speeds(tr):
    """Peak screen speed (px/frame) of each half of a push: half the travel (540 px) times the easing slope."""
    out_v = 3 * 540 / tr.get("out", 6)
    in_v = (6.93 if tr.get("ease_in") == "expo" else 3) * 540 / tr.get("in", 6)
    return out_v, in_v


def lint(script):
    """script: resolved (resolve.load_script), for its lint profile."""
    P = script["lint"]
    who = f"{script.get('brand') or 'no brand'}/{script.get('format') or 'no format'}"
    fails, warns = [], []
    fail = lambda t, m: fails.append((t, m))
    warn = lambda t, m: warns.append((t, m))
    src_dur = script.get("src_duration", script.get("duration"))
    edl = EDL(script.get("edl"), src_dur)
    n = int(round(edl.duration * FPS))
    takes = takes_out(script, edl)
    spec = script.get("camera", {})
    track = load_json(ROOT / script["track"])
    frames = cam.build({**spec, "src_takes": script["takes"]}, takes, n, track, edl, int(round(src_dur * FPS)))["frames"]

    # resolution budget: held frames stay sharp, only blurred transition frames may go further
    for kind, limit, pick in (("held", E_HELD, lambda f: "tr" not in f), ("transition", E_MOVING, lambda f: "tr" in f)):
        over = [f for f in frames if pick(f) and f["s"] > limit + 1e-3]
        if over:
            worst = max(over, key=lambda f: f["s"])
            (fail if kind == "transition" or worst["s"] > 1.3 else warn)(
                worst["t"], f"{len(over)} {kind} frames upscaled past {limit} (max {worst['s']:.2f}): soft picture")

    trs = spec.get("transitions", [])
    kinds = {t["type"] for t in trs if t["type"] in DESIGNED}
    if len(kinds) > 2:
        fail(0, f"{len(kinds)} designed transition types ({', '.join(sorted(kinds))}); keep to 2 per reel")
    for tr in trs:
        tot = tr.get("out", 6) + tr.get("in", 6)
        if tr["type"] == "push":
            if not 9 <= tot <= 16:
                warn(tr["at"], f"push {tot} f long; a whip reads at 10-14 f")
            ov, iv = whip_speeds(tr)
            if abs(ov - iv) / max(ov, iv) > 0.2:
                warn(tr["at"], f"push speeds jump at the cut ({ov:.0f} -> {iv:.0f} px/f): use in == out, "
                               f"or ease_in expo with in ~= 2.3 x out")
        if tr["type"] == "zoom_through":
            if tr.get("scale", 2.0) > 1.8:
                warn(tr["at"], f"zoom_through scale {tr.get('scale', 2.0)}: above 1.8 the last frames go soft")
            if tr.get("land", 1.35) > 1.0:
                warn(tr["at"], "zoom_through lands with a pull-out (impact mode); the default is land 1.0 plus an "
                               "expo push_takes landing on the close-up")
            if tr.get("out", 6) > 8:
                warn(tr["at"], f"zoom_through out {tr.get('out')} f: more than 8 f of upscaled frames become readable")
        if tr["type"] == "spin" and tr.get("deg", 30) > 20:
            warn(tr["at"], f"spin {tr.get('deg', 30)} deg: corners mirror; keep it under 20 or skip it")

    # event moves must not pile up
    events = [(tr["at"] - tr.get("out", 6) / FPS, tr["at"] + tr.get("in", 6) / FPS, f"{tr['type']}") for tr in trs]
    events += [(p["t"], p["t"] + p.get("in", 0.1), "punch") for p in spec.get("punches", [])]
    events += [(f["t"], f["t"] + f.get("dur", 0.15), "flash") for f in spec.get("flashes", [])]
    events += [(s["t"], s["t"] + s.get("dur", 0.3), "shake") for s in spec.get("shakes", [])]
    events.sort()
    for (a0, a1, an), (b0, b1, bn) in zip(events, events[1:]):
        gap = round((b0 - a1) * FPS)
        if 0 <= gap < MIN_GAP and not {an, bn} <= {"flash", "shake"} and not (an == "punch" and bn == "flash"):
            warn(b0, f"{bn} starts {gap} f after the {an} ends; give each move {MIN_GAP} f of calm")

    for p in (p for p in spec.get("punches", []) if p.get("in", 0.1) < 0.5):      # slower ones are creeps
        held = p["until"] - p["t"]
        if p["scale"] < P["punch_min"] and held < 1.5:
            warn(p["t"], f"punch {p['scale']} reads as a twitch; commit to >= 1.12 or drop it")
        elif p["scale"] < P["punch_min"] and not P["slow_push"]:       # a slow push is not this brand's move
            warn(p["t"], f"punch {p['scale']}: moves under 10% read as nothing ({script.get('brand')})")
        if p.get("out") and held < 1.0:
            warn(p["t"], f"punch in-out blip ({held:.2f} s); hold it to the end of the thought")
        if p.get("target", "face") == "face" and not p.get("anchor"):
            warn(p["t"], "punch on the face without anchor: the head slides to the centre (\"anchor\": true)")
    if spec.get("cut_in"):
        warn(0, "cut_in zooms out on every plain cut; with a push-in that pumps. Drop it (use creeps / A/B framing)")
    for key, pk in [("push", spec.get("push"))] + [(f"take {k}", v) for k, v in spec.get("push_takes", {}).items()]:
        if not pk or pk["to"] == pk["from"]:
            continue
        if pk.get("ease", "inout") == "inout" and not pk.get("dur"):
            warn(0, f"{key}: in-out creep over the whole take stops at both cuts; use \"ease\": \"linear\"")
    for i in range(n - 1):        # creep speed on held frames
        a, b = frames[i], frames[i + 1]
        if a["take"] == b["take"] and "tr" not in a and "tr" not in b and not a.get("flash"):
            rate = (b["s"] / a["s"] - 1) * FPS
            if rate > 0.03 and not any(p["t"] <= a["t"] < p["t"] + p.get("in", 0.1) + 0.05
                                       for p in spec.get("punches", [])) and not any(
                    pk.get("ease") == "expo" for pk in spec.get("push_takes", {}).values()):
                warn(a["t"], f"creep {rate * 100:.1f} %/s reads as a zoom; keep slow pushes under 3 %/s")
                break

    flashes = sorted(f["t"] for f in spec.get("flashes", []))
    for a, b in zip(flashes, flashes[1:]):
        if b - a < 1.0:
            fail(b, "flashes less than 1 s apart (strobe; WCAG 2.3.1)")
    if len(flashes) > max(2, edl.duration / 15):
        warn(flashes[-1], f"{len(flashes)} flashes; keep 1-2 per 30 s")
    for s in spec.get("shakes", []):
        if s.get("freq", 15) > 12:
            warn(s["t"], f"shake at {s.get('freq', 15)} Hz aliases at 30 fps; use 9-11")

    holds = [it for it in edl.items if "hold" in it[2]]
    for o0, o1, s in holds:
        if o1 - o0 > 1.5 and o1 < edl.duration - 0.5:
            warn(o0, f"freeze {o1 - o0:.1f} s mid-reel; keep it under 1.5 s")

    # sound: every designed transition gets its sound on the cut, plain cuts get none
    sfx = script.get("audio", {}).get("sfx", [])
    tr_at = [tr["at"] for tr in trs]
    for tr in trs:
        if not any(-1 <= round((x["peak_at"] - tr["at"]) * FPS) <= 3 for x in sfx):
            warn(tr["at"], f"{tr['type']} has no SFX peaking within C-1..C+3 f")
    cuts = sorted({round(t0, 3) for t0, t1 in takes[1:]} | {round(o0, 3) for o0, o1, s in edl.items[1:]})
    banned = P["sfx_banned"] + script.get("sfx_banned", [])
    for x in sfx:
        if any(fnmatch(x["name"], b) for b in banned):
            warn(x["peak_at"], f"{x['name']}: banned for {who}")
        # "move": the real motion it sounds (frame-fill...); whoosh_on_cuts: a format that whooshes every take cut
        if WHOOSH.search(x["name"]) and not x.get("move") and not P["whoosh_on_cuts"]:
            near_tr = any(abs(x["peak_at"] - t) <= 4 / FPS for t in tr_at)
            near_cut = [c for c in cuts if abs(x["peak_at"] - c) <= 2 / FPS]
            if near_cut and not near_tr:
                warn(x["peak_at"], f"{x['name']} on a plain cut advertises the edit; keep whooshes for moves")
    whooshes = [x["name"] for x in sorted(sfx, key=lambda x: x["peak_at"]) if WHOOSH.search(x["name"])]
    for a, b in zip(whooshes, whooshes[1:]):
        if a == b:
            warn(0, f"{a} twice in a row; rotate samples")
            break

    # no dead spans: a cut, a transition, a punch, a flash or an A/B change at least every few seconds
    changes = sorted(set(cuts) | set(tr_at) | {p["t"] for p in spec.get("punches", [])} | set(flashes) | {0.0, edl.duration})
    for a, b in zip(changes, changes[1:]):
        if P["dead_span"] is not None and b - a > P["dead_span"]:
            warn(a, f"{b - a:.1f} s with no visible change (cut, punch, transition); add one by {a + 3:.1f} s")

    if (script.get("grade") or {}).get("vignette", 0) > P["vignette_max"]:
        warn(0, f"vignette above {P['vignette_max']} reads as a filter")

    music = script.get("audio", {}).get("music")
    m = re.search(r"(\d+)bpm", (music or {}).get("file", ""))
    if m and P["beat_cuts"]:                  # off where cuts follow speech, not beats (talking head)
        import beats
        bpm = int(m.group(1))
        phase = beats.beat_phase(ROOT / "assets" / "music" / music["file"], bpm)
        period = 60 / bpm
        miss = [(c, abs(((c + music.get("offset", 0) - phase + period / 2) % period) - period / 2)) for c in cuts]
        late = [(c, d) for c, d in miss if d > 2.5 / FPS]
        if late:
            warn(late[0][0], f"{len(late)} of {len(cuts)} cuts miss the beat by > 2 f: "
                             + ", ".join(f"{c:.2f}s ({d * 1000:.0f} ms)" for c, d in late[:6]))
    return fails, warns


def main():
    path = Path(sys.argv[1])
    fails, warns = lint(resolve.load_script(path))
    for tag, items in (("FAIL", fails), ("WARN", warns)):
        for t, m in sorted(items):
            print(f"{tag} {t:6.2f}s  {m}")
    print(f"{len(fails)} fail, {len(warns)} warn")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
