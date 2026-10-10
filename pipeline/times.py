"""Print the transcript per take in OUTPUT time (after the script's edl), compact.

python times.py ../projects/<name>/script.json
Use these times for camera punches, sfx cues, freezes, literal titles and doodles.
"""
import sys

from common import ROOT, load_json
from edl import EDL


def main(path):
    sys.stdout.reconfigure(encoding="utf-8")
    sc = load_json(path)
    edl = EDL(sc.get("edl"), sc["src_duration"])
    words = [w for s in load_json(ROOT / sc["words"])["segments"] for w in s["words"]]
    takes = sc["takes"]
    print(f"output duration {edl.duration:.3f}s  (edl: {sc.get('edl')})")
    for k, (a, b) in enumerate(takes):
        oa, ob = edl.out_time(a), edl.out_time(b)
        ws = [w for w in words if a <= (w["s"] + w["e"]) / 2 < b]
        line = " ".join(f"{w['w'].strip()}[{edl.out_time(w['s']):.2f}]" for w in ws)
        print(f"take {k + 1}  {oa:6.2f}-{ob:6.2f} | {line}")
        if ws:
            gaps = [(ws[i]['e'], ws[i + 1]['s']) for i in range(len(ws) - 1) if ws[i + 1]['s'] - ws[i]['e'] > 0.22]
            if gaps:
                print("         pauses: " + ", ".join(f"{edl.out_time(g0):.2f}-{edl.out_time(g1):.2f}" for g0, g1 in gaps))
    last = max(w["e"] for w in words)
    print(f"speech ends at {edl.out_time(last):.2f} (source {last:.2f})")


if __name__ == "__main__":
    main(sys.argv[1])
