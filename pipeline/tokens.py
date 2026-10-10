"""Token accounting for a Claude Code session (main loop + all subagents/workflow agents).

Usage:
  python tokens.py <session_dir_or_jsonl> [--since ISO] [--until ISO]

Reads every *.jsonl transcript of the session, de-duplicates assistant messages by id,
and sums usage per model inside the [since, until) time window.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path


def iter_files(root):
    root = Path(root)
    if root.suffix == ".jsonl":
        yield root
        sub = root.with_suffix("")
        if sub.is_dir():
            yield from sub.rglob("agent-*.jsonl")
    else:
        main = root.with_suffix(".jsonl")
        if main.exists():
            yield main
        yield from root.rglob("agent-*.jsonl")


def collect(root, since=None, until=None):
    seen = {}
    for f in iter_files(root):
        who = "main" if f.parent.name != "subagents" and "agent-" not in f.name else "subagents"
        for line in f.open(encoding="utf-8", errors="replace"):
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if d.get("type") != "assistant":
                continue
            msg = d.get("message") or {}
            u = msg.get("usage")
            ts = d.get("timestamp", "")
            if not u or (since and ts < since) or (until and ts >= until):
                continue
            key = (f.name, msg.get("id") or d.get("uuid"))
            seen[key] = (who, msg.get("model", "?"), u)
    tot = defaultdict(lambda: defaultdict(int))
    for who, model, u in seen.values():
        for bucket in (f"{who}:{model}", "TOTAL"):
            t = tot[bucket]
            t["calls"] += 1
            t["input"] += u.get("input_tokens", 0)
            t["cache_write"] += u.get("cache_creation_input_tokens", 0)
            t["cache_read"] += u.get("cache_read_input_tokens", 0)
            t["output"] += u.get("output_tokens", 0)
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--since")
    ap.add_argument("--until")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    tot = collect(a.path, a.since, a.until)
    if a.json:
        print(json.dumps(tot, indent=1))
        return
    print(f"{'bucket':45} {'calls':>6} {'input':>10} {'cache_wr':>11} {'cache_rd':>13} {'output':>10}")
    for k in sorted(tot, key=lambda k: (k == "TOTAL", k)):
        t = tot[k]
        print(f"{k:45} {t['calls']:>6} {t['input']:>10,} {t['cache_write']:>11,} {t['cache_read']:>13,} {t['output']:>10,}")


if __name__ == "__main__":
    main()
