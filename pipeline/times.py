"""Print what is HEARD in the reel, in OUTPUT time (after the script's edl, voice-overs and mutes), per take.

python times.py ../projects/<name>/script.json
Use these times for camera punches, sfx cues, freezes, literal titles and doodles.
"""
import json
import sys
from pathlib import Path

import resolve
from common import ROOT, load_json
from edl import EDL, VoiceMap


def main(path):
    sys.stdout.reconfigure(encoding="utf-8")
    sc = resolve.load_script(path)
    edl = EDL(sc.get("edl"), sc["src_duration"])
    voice = VoiceMap(edl, sc.get("audio"))
    for w in voice.warnings:
        print("WARNING", w)
    words = voice.heard_words(load_json(ROOT / sc["words"]))
    takes = [(edl.out_time(a), edl.out_time(b)) for a, b in sc["takes"]]
    print(f"output duration {edl.duration:.3f}s  (edl: {sc.get('edl')})")
    for k, (oa, ob) in enumerate(takes):
        ws = [w for w in words if oa <= w["o"] < ob]
        line = " ".join(f"{w['w'].strip()}[{w['o']:.2f}]" for w in ws)
        print(f"take {k + 1}  {oa:6.2f}-{ob:6.2f} | {line}")
        gaps = [(ws[i]["oe"], ws[i + 1]["o"]) for i in range(len(ws) - 1) if ws[i + 1]["o"] - ws[i]["oe"] > 0.22]
        if gaps:
            print("         pauses: " + ", ".join(f"{g0:.2f}-{g1:.2f}" for g0, g1 in gaps))
    loose = [w for w in words if not any(oa <= w["o"] < ob for oa, ob in takes)]
    if loose:
        print("outside takes: " + " ".join(f"{w['w'].strip()}[{w['o']:.2f}]" for w in loose))
    if words:
        print(f"speech ends at {max(w['oe'] for w in words):.2f}")
    mpath = ROOT / Path(sc["words"]).parent / "motion.json"
    if mpath.exists():                 # gestures inside the edit, in output time (transition points)
        print("gestures (output time):")
        shown = []
        for e in json.loads(mpath.read_text(encoding="utf-8"))["events"]:
            key = "t_peak" if e["type"] == "sweep" else "t_settle"
            o = edl.out_time(e[key], clamp=False)
            if o is not None:
                shown.append((o, key, e))
        for o, key, e in sorted(shown, key=lambda x: x[0]):
            what = f"sweep {e['dir']:5} speed {e['speed']:5.0f}" if e["type"] == "sweep" else \
                   f"to lens, settles at {e['at']} (x{e['growth']})"
            print(f"  {o:6.2f}  {what}   (source {e[key]:.2f})")


if __name__ == "__main__":
    main(sys.argv[1])
