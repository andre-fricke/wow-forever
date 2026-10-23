"""Automatic templates are tested with synthetic archives and isolated clients."""
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from unittest.mock import patch
from contextlib import redirect_stdout
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import auto_setup as a
import wow_backup as w


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    client = root / "client"
    char = client / "WTF/Account/Target/Release/Existing"
    info = dict(name="Source", full="Source Surname", realm="Beta", realmKey="PvP", guid="Player-source", **{"class": "DRUID"})
    existing = {**info, "name": "Existing", "full": "Existing", "guid": "Player-existing"}
    helper = char / "SavedVariables/WoWUITransferIdentity.lua"
    write(helper, w.dump({"WoWUITransferIdentity": existing}))
    write(char / "AddOns.txt", b"Prat-3.0: enabled\n")
    # First login with the helper writes nil, not an absent file. This must
    # support status, disabling and first-time configuration without a reset.
    write(client / a.state_path(client, char), b"WoWUITransferAuto = nil\n")
    assert a.read_state(client, char)[1] == {}
    assert a.disable_plan(client, char) == {}
    prefix = "client/WTF/Account/Source/Beta/Source/"
    account = "client/WTF/Account/Source/SavedVariables/"
    macro = dict(scope="character", name="Heal", body="/cast Heal", icon=123)
    capture = dict(schema=1, guid=info["guid"], macros={121: macro}, clicks={1: dict(type=2, actionID=121, button="LeftButton", modifiers=1)})
    capture["chat"] = {2: dict(name="Combat Log", x=0.7, y=0.1, width=0.25, height=0.2, dock=0, locked=True)}
    payloads = {
        account + "Prat-3.0.lua": w.dump({"Prat3DB": {
            "profileKeys": {"Source Surname": "MyProfile"},
            "profiles": {"MyProfile": {"owner": "Source Surname", "width": 150}},
            "char": {"Source Surname": {"progress": 999}},
            "namespaces": {"Font": {"profiles": {"MyProfile": {"size": 18}}}},
        }}),
        account + "ForeverDualGathering.lua": w.dump({"ForeverDualGatheringDB": {"size": 30}}),
        account + "Unknown.lua": w.dump({"UnknownDB": {"history": 5}}),
        prefix + "SavedVariables/RXPGuides.lua": w.dump({"RXPCData": {"localDB": {"height": 123}, "completed": {1: True}}}),
        prefix + "SavedVariables/WoWUITransferIdentity.lua": w.dump({"WoWUITransferIdentity": info, "WoWUITransferSetup": capture, "WoWUITransferBars": {"schema": 2, "macroActions": 1, "slots": {3: macro}}}),
        prefix + "AddOns.txt": b"Prat-3.0: enabled\nRXPGuides: enabled\nWoWUITransferIdentity: disabled\n",
        prefix + "macros-cache.txt": b'VER 3 010000001 "Heal" "123"\n/cast Heal\nEND\n',
        "client/Interface/AddOns/Prat-3.0/Prat-3.0.toc": b"## Interface: 16001\n",
    }
    manifest = dict(schema=1, kind="combined", created="2026-10-23", source_character=prefix[len("client/"):].rstrip("/"), source_identity=info,
                    addons={"Prat-3.0": {}, "RXPGuides": {}, "ForeverDualGathering": {}, "Unknown": {}}, files={})
    def archive(name, payload=payloads, metadata=manifest):
        dest = root / name
        meta = copy.deepcopy(metadata)
        meta["files"] = {key: {"sha256": w.sha(data), "size": len(data)} for key, data in payload.items()}
        with zipfile.ZipFile(dest, "w") as z:
            for key, data in payload.items():
                z.writestr(key, data)
            z.writestr("manifest.json", json.dumps(meta))
        return dest
    snapshot = archive("backup.zip")
    orphaned = dict(payloads)
    orphaned[account + "AtlasLootContinued.lua"] = w.dump({"OldDB": {"profileKeys": {info["full"]: "Default"}, "profiles": {"Default": {"size": 10}}}})
    orphaned[prefix + "SavedVariables/MoveAny.lua"] = w.dump({"OldCharDB": {"size": 20}})
    _, filtered, seeds, warnings = a.build_template(archive("orphans.zip", orphaned))
    assert "OldDB" not in filtered["profiles"]
    assert "MoveAny" not in filtered["characters"]
    assert "AtlasLootContinued" not in seeds
    assert any("leftover" in note for note in warnings)
    _, template, shared, notes = a.build_template(snapshot, snapshot, snapshot)
    assert template["profiles"]["Prat3DB"]["profile"]["width"] == 150
    assert template["profiles"]["Prat3DB"]["namespaces"]["Font"]["profile"]["size"] == 18
    assert "progress" not in repr(template)
    assert "completed" not in template["characters"]["RXPGuides"]["RXPCData"]
    assert "WoWUITransferIdentity" not in template["flags"]
    assert "Unknown" not in shared and any("unreviewed" in note for note in notes)
    assert template["clickMacros"][121] == macro
    assert template["chat"] == capture["chat"]
    sparse_payload = dict(payloads)
    sparse_capture = copy.deepcopy(capture)
    sparse_capture["chat"] = {1:{**capture["chat"][2],"name":"General","dock":1},2:capture["chat"][2],3:None,4:{**capture["chat"][2],"name":"NoSpam","dock":2}}
    sparse_capture["chat"][4]["subscriptions"] = {"messages":{1:"SAY",2:"GUILD"},"channels":{}}
    sparse_capture["chat"][4]["alpha"] = 0
    sparse_payload[prefix + "SavedVariables/WoWUITransferIdentity.lua"] = w.dump({"WoWUITransferSetup":sparse_capture})
    _, sparse_template, _, _ = a.build_template(archive("sparse-chat.zip", sparse_payload))
    assert set(sparse_template["chat"]) == {1,2,4}
    assert sparse_template["chat"][4]["name"] == "NoSpam"
    assert sparse_template["chat"][4]["subscriptions"] == sparse_capture["chat"][4]["subscriptions"]
    assert sparse_template["chat"][4]["alpha"] == 0
    assert sparse_template["chat"][2]["name"] == "Combat Log"
    sparse_capture["chat"][11] = capture["chat"][2]
    sparse_payload[prefix + "SavedVariables/WoWUITransferIdentity.lua"] = w.dump({"WoWUITransferSetup":sparse_capture})
    try:
        a.build_template(archive("invalid-chat.zip", sparse_payload))
    except ValueError as error:
        assert "Invalid chat window ID" in str(error)
    else:
        raise AssertionError("Invalid non-nil chat ID accepted")
    shared_path = char.parent.parent / "SavedVariables/Prat-3.0.lua"
    write(shared_path, b'Prat3DB = { untouched = true }\n')
    files, notes = a.configure_plan(client, char, snapshot, snapshot, snapshot)
    assert shared_path.relative_to(client).as_posix() not in files
    statefile = a.state_path(client, char)
    state = w.plain(w.parse(files[statefile]))[a.STATE]
    assert state["excluded"] == {"Player-existing": True} and state["enabled"]
    assert any("seeded once" in note for note in notes)
    assert all(not p.startswith("WTF/Account/Source/") for p in files)
    assert (client / statefile).read_bytes() == b"WoWUITransferAuto = nil\n" # Planning is read-only.
    state["characters"]["Player-new"] = {"phase": "bindings", "template": template}
    legacy = copy.deepcopy(template)
    legacy.pop("macroPolicy")
    legacy.pop("differentClass")
    legacy["profiles"]["Prat3DB"]["profile"]["width"] = 999
    state["characters"]["Player-legacy"] = {"phase":"settings", "template":legacy, "profiles":{"Prat3DB":True}}
    state["characters"]["Player-partial"] = {"phase":"bindings", "template":copy.deepcopy(legacy), "macros":True}
    state["characters"]["Player-done"] = {"done":True,"templateID":"old"}
    write(client / statefile, w.dump({a.STATE: state, "OtherRoot": {"keep": True}}))
    updated, _ = a.configure_plan(client, char, snapshot)
    new = w.plain(w.parse(updated[statefile]))
    assert new[a.STATE]["characters"]["Player-new"]["template"]["hasMacros"]
    assert not new[a.STATE]["template"]["hasMacros"]
    assert new["OtherRoot"]["keep"]
    migrated = new[a.STATE]["characters"]["Player-legacy"]
    assert migrated["template"]["macroPolicy"] == 1
    assert migrated["template"]["differentClass"]["macros"][121]["body"] == "/cast null"
    assert migrated["template"]["profiles"]["Prat3DB"]["profile"]["width"] == 999
    assert migrated["phase"] == "settings" and migrated["profiles"] == {"Prat3DB":True}
    assert "macroPolicy" not in new[a.STATE]["characters"]["Player-partial"]["template"]
    assert new[a.STATE]["characters"]["Player-done"] == state["characters"]["Player-done"]
    stale = dict(payloads)
    stale[prefix + "macros-cache.txt"] = b'VER 3 010000001 "Heal" "123"\n/cast New Heal\nEND\n'
    _, refreshed, _, changed_notes = a.build_template(snapshot, archive("stale.zip", stale), snapshot)
    assert refreshed["macros"][121]["body"] == "/cast New Heal"
    assert refreshed["slots"][3]["body"] == "/cast New Heal"
    assert refreshed["clickMacros"][121]["body"] == "/cast New Heal"
    assert refreshed["differentClass"]["clickMacros"][121]["body"] == "/cast null"
    assert any("Reconciled" in note for note in changed_notes)
    renamed = dict(stale)
    renamed[prefix + "macros-cache.txt"] = stale[prefix + "macros-cache.txt"].replace(b'"Heal"', b'"Renamed"')
    try:
        a.build_template(snapshot, archive("renamed.zip", renamed))
    except ValueError:
        pass
    else:
        raise AssertionError("Renamed/missing macro accepted")
    disabled = w.plain(w.parse(a.disable_plan(client, char)[statefile]))
    assert disabled[a.STATE]["enabled"] is False and disabled[a.STATE]["characters"] == state["characters"]
    # Old snapshots remain valid for manual restore but cannot guess macro IDs.
    old = dict(payloads)
    old[prefix + "SavedVariables/WoWUITransferIdentity.lua"] = w.dump({"WoWUITransferIdentity": info})
    for args in ((snapshot, archive("old.zip", old)), (snapshot, None, snapshot), (snapshot, snapshot, archive("other.zip", metadata={**manifest, "source_identity": {**info, "guid": "another"}}))):
        try:
            a.build_template(*args)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid or incompatible capture accepted")
    # An account-scoped file symlink is rejected even when reading status.
    (client / statefile).unlink()
    (client / statefile).symlink_to(helper)
    try:
        a.read_state(client, char)
    except ValueError:
        pass
    else:
        raise AssertionError("Symlink accepted")

with patch("builtins.input", side_effect=["4", "0", "0"]), redirect_stdout(io.StringIO()) as out:
    w.menu()
    assert out.getvalue().count("0  Exit") == 2
with patch("builtins.input", side_effect=["4", "4", "n", "0"]), patch.object(w, "choose_client", return_value=Path("/synthetic")), patch.object(w, "choose_character", return_value=Path("/synthetic/char")), patch.object(w, "wait_for_wow_closed"), patch.object(a, "disable_plan", return_value={"state.lua": b"state = {}"}), patch.object(w, "execute_plan") as execute, redirect_stdout(io.StringIO()):
    w.menu()
    execute.assert_not_called()

lua = os.environ.get("LUA_RUNTIME") or shutil.which("lua5.1") or shutil.which("lua")
if lua:
    subprocess.run([lua, str(Path(__file__).with_suffix(".lua")), str(Path(a.__file__).parent)], check=True)
print("PASS automatic template verification, privacy, safe preparation, updates, exclusions, disabling, menu cancellation and runtime lifecycle")
