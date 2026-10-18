"""Execute only generated synthetic data in Lua, never personal addon settings."""

import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from saved_variables import parse, dump

runtime = os.environ.get("LUA_RUNTIME") or next(
    (shutil.which(n) for n in ("lua5.1", "lua", "luajit") if shutil.which(n)), None
)
if not runtime:
    print("SKIP Lua runtime test: install Lua 5.1 or set LUA_RUNTIME (required in CI).")
    sys.exit(0)
source = b'DB = {positions={{"LEFT",nil,"LEFT",0,-136.7}},size={220,28},text="Line\\nA\\001",unicode="Gr\xc3\xb6\xc3\x9fe"}'
generated = dump(parse(source))
checks = b"""
local unpack = unpack or table.unpack
local function point(...)
    assert(select('#', ...) == 5, 'SetPoint lost arguments after nil')
    local anchor, relative, relativeAnchor, x, y = ...
    assert(anchor == 'LEFT' and relative == nil and relativeAnchor == 'LEFT')
    assert(x == 0 and y == -136.7)
end
point(unpack(DB.positions[1]))
assert(DB.size[1] == 220 and DB.size[2] == 28)
assert(DB.text == 'Line\\nA\\001')
assert(DB.unicode == 'Gr\xc3\xb6\xc3\x9fe')
"""
result = subprocess.run([runtime, "-"], input=generated + checks, capture_output=True)
assert result.returncode == 0, result.stderr.decode(errors="replace")
print("PASS actual Lua unpack, nil position slots, sizes, control characters and UTF-8")
