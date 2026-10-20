"""Import an editable project into DaVinci Resolve, render it there and compare with our own render.

python resolve_check.py output/<name>_project/<name>.fcpxml output/<name>_project/reference_nograde.mp4

Needs Resolve running with the bridge started (Workspace > Scripts > Reel Studio Bridge, see resolve_client.py).
Creates a new 1080x1920 30 fps project, imports the FCPXML, lists what landed on which track (with each clip's
alpha mode), renders ProRes 422 HQ next to the FCPXML and runs compare_render.py on it. The project stays in
Resolve for a look by eye.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from common import BUILD, PIPE
from resolve_client import call


def lua_str(s):
    return json.dumps(str(s), ensure_ascii=False)


def import_project(fcpxml, name):
    return call(f'''
local pm = resolve:GetProjectManager()
local p = pm:CreateProject({lua_str(name)})
if not p then error("a project named " .. {lua_str(name)} .. " already exists") end
for k, v in pairs({{timelineResolutionWidth = "1080", timelineResolutionHeight = "1920", timelineFrameRate = "30",
                   videoMonitorFormat = "HD 1080p 30"}}) do p:SetSetting(k, v) end
local tl = p:GetMediaPool():ImportTimelineFromFile({lua_str(fcpxml)}, {{timelineName = {lua_str(name)}, importSourceClips = true}})
if not tl then error("ImportTimelineFromFile failed") end
p:SetCurrentTimeline(tl)
local items = {{}}
for _, kind in ipairs({{"video", "audio"}}) do
  for i = 1, tl:GetTrackCount(kind) do
    for _, it in ipairs(tl:GetItemListInTrack(kind, i) or {{}}) do
      local mpi = it:GetMediaPoolItem()
      items[#items + 1] = {{track = kind:sub(1, 1):upper() .. i, name = it:GetName(), start = it:GetStart(),
                           dur = it:GetDuration(), alpha = (kind == "video" and mpi) and mpi:GetClipProperty("Alpha mode") or nil}}
    end
  end
end
return {{frames = tl:GetEndFrame() - tl:GetStartFrame(), w = tl:GetSetting("timelineResolutionWidth"),
        h = tl:GetSetting("timelineResolutionHeight"), fps = tl:GetSetting("timelineFrameRate"), items = items}}
''', timeout=300)


def render(target_dir, name):
    job = call(f'''
local p = resolve:GetProjectManager():GetCurrentProject()
local hq
for desc, codec in pairs(p:GetRenderCodecs("mov")) do if desc:find("422 HQ") then hq = codec end end
p:SetCurrentRenderFormatAndCodec("mov", hq)
p:SetRenderSettings({{SelectAllFrames = true, TargetDir = {lua_str(target_dir)}, CustomName = {lua_str(name)},
  FormatWidth = 1080, FormatHeight = 1920, FrameRate = 30, ExportVideo = true, ExportAudio = true,
  AudioCodec = "lpcm", AudioSampleRate = 48000, AudioBitDepth = 24}})
local job = p:AddRenderJob()
p:StartRendering({{job}}, false)
return job
''')
    while True:
        st = call(f'local p = resolve:GetProjectManager():GetCurrentProject() '
                  f'return {{busy = p:IsRenderingInProgress(), st = p:GetRenderJobStatus({lua_str(job)})}}')
        if not st["busy"]:
            return st["st"]
        time.sleep(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("fcpxml")
    ap.add_argument("reference")
    a = ap.parse_args()
    fcpxml, ref = Path(a.fcpxml).resolve(), Path(a.reference).resolve()
    name = f"{fcpxml.stem}_check_{time.strftime('%H%M%S')}"
    r = import_project(fcpxml, name)
    print(f"imported: {r['w']}x{r['h']} @ {r['fps']} fps, {r['frames']} frames")
    for it in sorted(r["items"], key=lambda x: (x["track"], x["start"])):
        print(f"  {it['track']:4} {it['name']:42} @{it['start']:5}+{it['dur']:<4}" + (f" alpha {it['alpha']}" if it.get("alpha") else ""))
    st = render(str(fcpxml.parent), name)
    print("render:", st)
    out = fcpxml.parent / f"{name}.mov"
    return subprocess.run([sys.executable, str(PIPE / "compare_render.py"), str(ref), str(out),
                           "--out", str(BUILD / "compare" / name)]).returncode


if __name__ == "__main__":
    sys.exit(main())
