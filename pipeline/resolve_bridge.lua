-- Reel Studio bridge: lets the pipeline drive DaVinci Resolve (free) through files, because the free edition
-- does not accept external scripting connections. Installed into Workspace > Scripts > Utility by
-- `python pipeline/resolve_client.py --install`; started once per Resolve session from that menu.
--
-- Protocol (BRIDGE_DIR is filled in at install time):
--   in/<id>.lua    Lua chunk to run; it sees `resolve` and returns a value
--   out/<id>.json  {"ok": true, "result": ...} or {"ok": false, "error": "..."}
--   alive          heartbeat (os.time()), rewritten every poll
--   stop           create it to end the bridge
local BRIDGE_DIR = "@BRIDGE_DIR@"
local resolve = Resolve()

local function json(v, depth)
  depth = depth or 0
  if depth > 12 then return '"<too deep>"' end
  local t = type(v)
  if v == nil then return "null"
  elseif t == "boolean" then return tostring(v)
  elseif t == "number" then
    if v ~= v or v == math.huge or v == -math.huge then return "null" end
    return string.format("%.10g", v)
  elseif t == "string" then
    return '"' .. v:gsub('[%c"\\]', function(c)
      local map = { ['"'] = '\\"', ['\\'] = '\\\\', ['\n'] = '\\n', ['\r'] = '\\r', ['\t'] = '\\t' }
      return map[c] or string.format("\\u%04x", c:byte())
    end) .. '"'
  elseif t == "table" then
    local n, count = #v, 0
    for _ in pairs(v) do count = count + 1 end
    local parts = {}
    if n > 0 and n == count then
      for i = 1, n do parts[#parts + 1] = json(v[i], depth + 1) end
      return "[" .. table.concat(parts, ",") .. "]"
    end
    for k, val in pairs(v) do parts[#parts + 1] = json(tostring(k)) .. ":" .. json(val, depth + 1) end
    return "{" .. table.concat(parts, ",") .. "}"
  end
  return json(tostring(v))
end

local function exists(path)
  local f = io.open(path, "r")
  if f then f:close() return true end
  return false
end

local function write(path, text)
  local tmp = path .. ".tmp"
  local f = assert(io.open(tmp, "w"))
  f:write(text)
  f:close()
  os.rename(tmp, path)
end

os.execute('mkdir -p "' .. BRIDGE_DIR .. '/in" "' .. BRIDGE_DIR .. '/out"')
os.remove(BRIDGE_DIR .. "/stop")
print("Reel Studio bridge running: " .. BRIDGE_DIR)

while not exists(BRIDGE_DIR .. "/stop") do
  write(BRIDGE_DIR .. "/alive", tostring(os.time()))
  local ls = io.popen('ls "' .. BRIDGE_DIR .. '/in" 2>/dev/null')
  local names = {}
  for name in ls:lines() do
    if name:match("%.lua$") then names[#names + 1] = name end
  end
  ls:close()
  table.sort(names)
  for _, name in ipairs(names) do
    local path = BRIDGE_DIR .. "/in/" .. name
    local f = io.open(path, "r")
    local code = f and f:read("*a") or ""
    if f then f:close() end
    os.remove(path)
    local chunk, err = loadstring(code, name)
    local reply
    if not chunk then
      reply = '{"ok":false,"error":' .. json(err) .. '}'
    else
      setfenv(chunk, setmetatable({ resolve = resolve, json = json }, { __index = _G }))
      local ok, res = pcall(chunk)
      reply = ok and ('{"ok":true,"result":' .. json(res) .. '}') or ('{"ok":false,"error":' .. json(tostring(res)) .. '}')
    end
    write(BRIDGE_DIR .. "/out/" .. name:gsub("%.lua$", ".json"), reply)
  end
  if bmd and bmd.wait then bmd.wait(0.25) else os.execute("sleep 0.25") end
end
os.remove(BRIDGE_DIR .. "/alive")
print("Reel Studio bridge stopped")
