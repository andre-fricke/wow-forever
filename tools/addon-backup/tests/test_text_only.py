"""Test the companion skin and per-character backup integration."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wow_backup as w

repo = Path(__file__).resolve().parents[3]
addon = repo / "addon/RestedXPTextOnly"
with tempfile.TemporaryDirectory() as td:
    client = Path(td)
    char = client / "WTF/Account/TEST/Realm/Source"
    (char / "SavedVariables").mkdir(parents=True)
    shutil.copytree(addon, client / "Interface/AddOns/RestedXPTextOnly")
    settings = {
        "RestedXPTextOnlyDB": {
            "enabled": True,
            "width": 260,
            "scale": 1.1,
            "unlocked": False,
            "anchor": {"x": -200, "y": -100},
        }
    }
    data = w.dump(settings)
    (char / "SavedVariables/RestedXPTextOnly.lua").write_bytes(data)
    assert w.audit_support(client, char) == []
    source = dict(name="Old", full="Old Name", realm="Beta", guid="Player-1")
    target = dict(name="New", full="New Name", realm="Release", guid="Player-2")
    result = w.character_config("RestedXPTextOnly", data, None, source, target)
    assert w.plain(w.parse(result)) == settings
print("PASS Text Only settings recognized and transferable across characters")
runtime = os.environ.get("LUA_RUNTIME") or next(
    (shutil.which(n) for n in ("lua5.1", "lua", "luajit") if shutil.which(n)), None
)
if not runtime:
    print(
        "SKIP Text Only Lua tests: install Lua 5.1 or set LUA_RUNTIME (required in CI)."
    )
else:
    subprocess.run(
        [
            runtime,
            str(Path(__file__).with_suffix(".lua")),
            str(addon / "RestedXPTextOnly.lua"),
        ],
        check=True,
    )
