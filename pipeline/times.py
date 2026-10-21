"""Print what is HEARD in the reel, in OUTPUT time (after the script's edl, voice-overs and mutes), per take.

python times.py ../projects/<name>/script.json
Use these times for camera punches, sfx cues, freezes, literal titles and doodles. The script's inserts print as
resolved (inserts.resolve_times: when, size, sound), with their problems.
"""
import json
import sys
from pathlib import Path

import inserts
import resolve
import text_rules
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
    rules = text_rules.load_rules(sc)
    hits = text_rules.term_hits(sc, words, rules)          # brand words print as the script types them
    canon = {k0: d for k0, k1, d in hits}
    absorbed = {k for k0, k1, _ in hits for k in range(k0 + 1, k1 + 1)}
    takes = [(edl.out_time(a), edl.out_time(b)) for a, b in sc["takes"]]
    print(f"output duration {edl.duration:.3f}s  (edl: {sc.get('edl')})")
    for k, (oa, ob) in enumerate(takes):
        ws = [w for w in words if oa <= w["o"] < ob]
        line = " ".join(f"{canon.get(k, w['w'].strip())}[{w['o']:.2f}]" for k, w in enumerate(words)
                        if oa <= w["o"] < ob and k not in absorbed)
        print(f"take {k + 1}  {oa:6.2f}-{ob:6.2f} | {line}")
        gaps = [(ws[i]["oe"], ws[i + 1]["o"]) for i in range(len(ws) - 1) if ws[i + 1]["o"] - ws[i]["oe"] > 0.22]
        if gaps:
            print("         pauses: " + ", ".join(f"{g0:.2f}-{g1:.2f}" for g0, g1 in gaps))
    loose = [w for w in words if not any(oa <= w["o"] < ob for oa, ob in takes)]
    if loose:
        print("outside takes: " + " ".join(f"{w['w'].strip()}[{w['o']:.2f}]" for w in loose))
    if words:
        print(f"speech ends at {max(w['oe'] for w in words):.2f}")
    for k0, k1, d in hits:
        print(f"terms: {' '.join(words[k]['w'].strip() for k in range(k0, k1 + 1))} -> {d} [{words[k0]['o']:.2f}]")
    for c in text_rules.cta_triggers(words, rules):          # each needs a "preset": "cta" block (cta_check)
        print(f"CTA spoken: «{c['word']}…» [{c['t']:.2f}]")
    if sc.get("inserts"):              # read-only: inserts.json where the files are unchanged, else a probe
        items, fails, warns = inserts.resolve_times(sc, words, edl.duration, sc["style"])
        for it in items:
            look = f"full-screen {it['kind']}" if it["mode"] == "full" else \
                f"{it['style']}{' ' + it['size'] if it['size'] else ''} {it['w']}x{it['h']}"
            heard = f" heard «{it['phrase']['heard']}»" if it["phrase"] else ""
            print(f"insert {it['id']} {it['t0']:6.2f}-{it['t1']:6.2f}  {look}  {it['sfx'] or 'silent'}  | "
                  f"{it['file']}{heard}")
        for tag, found in (("FAIL", fails), ("WARN", warns)):
            for t, m in found:
                print(f"insert {tag} [{t:.2f}] {m}")
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
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0 if sys.argv[1:] in (["-h"], ["--help"]) else 2)
    main(sys.argv[1])
