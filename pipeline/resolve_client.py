"""Drive DaVinci Resolve (free) from the pipeline through the Lua file bridge (resolve_bridge.lua).

python resolve_client.py --install          copy the bridge into Workspace > Scripts > Utility (restart Resolve)
python resolve_client.py 'return resolve:GetVersionString()'
python resolve_client.py --stop             end the bridge loop inside Resolve

The free edition refuses external scripting connections, so a Lua loop started once from Resolve's menu runs
the chunks this client drops into build/resolve_bridge/in and answers in build/resolve_bridge/out.
"""
import argparse
import itertools
import json
import os
import sys
import time
from pathlib import Path

from common import BUILD, PIPE

BRIDGE = BUILD / "resolve_bridge"
SCRIPTS = Path.home() / "Library/Application Support/Blackmagic Design/DaVinci Resolve/Fusion/Scripts/Utility"
_ids = itertools.count()


def install():
    SCRIPTS.mkdir(parents=True, exist_ok=True)
    src = (PIPE / "resolve_bridge.lua").read_text(encoding="utf-8").replace("@BRIDGE_DIR@", str(BRIDGE))
    dest = SCRIPTS / "Reel Studio Bridge.lua"
    dest.write_text(src, encoding="utf-8")
    (BRIDGE / "in").mkdir(parents=True, exist_ok=True)
    (BRIDGE / "out").mkdir(parents=True, exist_ok=True)
    return dest


def alive(max_age=5.0):
    try:
        return time.time() - int((BRIDGE / "alive").read_text()) <= max_age
    except (OSError, ValueError):
        return False


def call(code, timeout=120.0):
    """Run a Lua chunk inside Resolve (it sees `resolve`, returns a value) and return its result."""
    if not alive():
        raise RuntimeError("the bridge is not running: in Resolve choose Workspace > Scripts > Reel Studio Bridge")
    cid = f"{int(time.time() * 1000)}_{os.getpid()}_{next(_ids):04d}"
    tmp = BRIDGE / "in" / f"{cid}.tmp"
    tmp.write_text(code, encoding="utf-8")
    tmp.rename(BRIDGE / "in" / f"{cid}.lua")
    out = BRIDGE / "out" / f"{cid}.json"
    t0 = time.time()
    while not out.exists():
        if time.time() - t0 > timeout:
            raise TimeoutError(f"Resolve did not answer within {timeout:.0f} s")
        time.sleep(0.1)
    reply = json.loads(out.read_text(encoding="utf-8"))
    out.unlink()
    if not reply["ok"]:
        raise RuntimeError(f"Lua error in Resolve: {reply['error']}")
    return reply.get("result")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("code", nargs="?")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--stop", action="store_true")
    a = ap.parse_args()
    if a.install:
        print("installed", install(), "- restart Resolve, then Workspace > Scripts > Reel Studio Bridge")
    if a.stop:
        (BRIDGE / "stop").touch()
    if a.code:
        print(json.dumps(call(a.code), ensure_ascii=False, indent=1))


if __name__ == "__main__":
    sys.exit(main())
