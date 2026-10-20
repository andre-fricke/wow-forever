"""Action slot capture/restore tests use synthetic files and WoW APIs only."""
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout
import io

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wow_backup as w
import archives
from models import StoragePaths
from macro_placement import placement_member, placement_snapshot, has_placement

for snapshot in (
    {"schema": 1, "slots": {}},
    {"schema": 2, "slots": {}, "macroActions": 1, "unresolvedSlots": {3: True}},
    {"schema": 2, "slots": {}, "macroActions": 1},
):
    try:
        placement_snapshot(w.dump({"WoWUITransferBars": snapshot}))
    except ValueError:
        pass
    else:
        raise AssertionError("Unreliable empty/incomplete snapshot accepted")
assert placement_snapshot(w.dump({
    "WoWUITransferBars": {"schema": 2, "slots": {}, "macroActions": 0}
}))["slots"] == {}

with tempfile.TemporaryDirectory() as td:
    client = Path(td)
    char = client / "WTF/Account/NEW/Realm/Target"
    (char / "SavedVariables").mkdir(parents=True)
    manifest = {"kind": "macros", "source_character": "WTF/Account/OLD/Beta/Source", "files": {}}
    slots = {1: {"scope": "account", "name": "A", "body": "/say hi"},
             73: {"scope": "character", "name": "C", "body": "/dance"}}
    payloads = {
        "client/WTF/Account/OLD/macros-cache.txt": b'VER 3 1 "A" "1"\n/say hi\nEND\n',
        "client/WTF/Account/OLD/Beta/Source/macros-cache.txt": b'VER 3 1 "C" "1"\n/dance\nEND\n',
        placement_member(manifest): w.dump({"WoWUITransferBars": {"schema": 1, "slots": slots}}),
    }
    archive = client / "backup.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for name, data in payloads.items():
            z.writestr(name, data)
            manifest["files"][name] = {"sha256": w.sha(data)}
    assert has_placement(archive, manifest)
    path = char / "SavedVariables/WoWUITransferIdentity.lua"
    path.write_bytes(w.dump({"WoWUITransferIdentity": {"guid": "TargetGUID"}}))
    for scope, expected in (("character", {73}), ("account", {1}), ("both", {1, 73})):
        plan, notes = w.macro_plan(archive, manifest, client, char, scope, restore_slots=True)
        saved = w.plain(w.parse(plan[path.relative_to(client).as_posix()]))
        assert set(saved["WoWUITransferBarsPending"]["slots"]) == expected
        assert saved["WoWUITransferIdentity"]["guid"] == "TargetGUID"
        assert b"actionbars.lua" in plan["Interface/AddOns/WoWUITransferIdentity/WoWUITransferIdentity.toc"]
        assert b"WoWUITransferIdentity: enabled" in plan[(char / "AddOns.txt").relative_to(client).as_posix()]
    plan, _ = w.macro_plan(archive, manifest, client, char, "both")
    assert all("WoWUITransferIdentity" not in name for name in plan)
    path.write_bytes(w.dump({"WoWUITransferBarsPending": {"schema": 1, "slots": slots}}))
    plan, _ = w.macro_plan(archive, manifest, client, char)
    assert "WoWUITransferBarsPending" not in w.parse(plan[path.relative_to(client).as_posix()])
    try:
        placement_snapshot(w.dump({"WoWUITransferBars": {"schema": 1, "slots": {999: slots[1]}}}))
    except ValueError:
        pass
    else:
        raise AssertionError("Invalid slot accepted")
    legacy = {**manifest, "files": {k:v for k,v in manifest["files"].items() if k != placement_member(manifest)}}
    assert not has_placement(archive, legacy)
    try:
        w.macro_plan(archive, legacy, client, char, restore_slots=True)
    except ValueError:
        pass
    else:
        raise AssertionError("Missing slot snapshot accepted")
    # New archives really include the checksum-protected captured slot payload.
    path.write_bytes(w.dump({
        "WoWUITransferIdentity": {"name": "Target", "full": "Target", "realm": "Realm", "guid": "Player-2", "class": "ROGUE"},
        "WoWUITransferBars": {"schema": 1, "slots": slots},
    }))
    (char / "macros-cache.txt").write_bytes(payloads["client/WTF/Account/OLD/Beta/Source/macros-cache.txt"])
    (char.parent.parent / "macros-cache.txt").write_bytes(payloads["client/WTF/Account/OLD/macros-cache.txt"])
    tool = client / "tool"
    tool.mkdir()
    paths = StoragePaths(tool, tool / "Backups", tool / "Recovery", tool / "Legacy")
    snapshot_file = archives.create_backup(client, char, "macros", paths=paths)
    saved_manifest = archives.verify_backup(snapshot_file)
    assert has_placement(snapshot_file, saved_manifest)
    assert len(saved_manifest["files"]) == 3

# The menu explicitly offers yes/no placement independently of macro replacement.
for answer, enabled in (("", False), ("n", False), ("y", True)):
    with (
        patch("builtins.input", side_effect=["2", "2", "both", "y", answer, "0"]) as prompts,
        patch.object(w, "choose_snapshot", return_value=Path("/test/backup.zip")),
        patch.object(w, "verify_backup", return_value={
            "source_identity": {"full": "Source"}, "source_character": "WTF/Account/A/R/C", "files": {}
        }),
        patch("macro_placement.has_placement", return_value=True),
        patch.object(w, "choose_client", return_value=Path("/test/client")),
        patch.object(w, "choose_character", return_value=Path("/test/client/WTF/Account/A/R/C")),
        patch.object(w, "macro_plan", return_value=({"file": b"data"}, [])) as plan,
        patch.object(w, "wait_for_wow_closed"),
        patch.object(w, "apply_plan") as apply,
        redirect_stdout(io.StringIO()) as output,
    ):
        w.menu()
        assert plan.call_args.kwargs["restore_slots"] is enabled
        apply.assert_called_once()
        questions = [call.args[0] for call in prompts.call_args_list]
        confirm = next(i for i, text in enumerate(questions) if "replace the selected macro files" in text)
        placement = next(i for i, text in enumerate(questions) if "Also restore macro action bar slots" in text)
        assert confirm < placement

# Cancelling macro replacement must not even ask about action bar placement.
with (
    patch("builtins.input", side_effect=["2", "2", "both", "n", "0"]) as prompts,
    patch.object(w, "choose_snapshot", return_value=Path("/test/backup.zip")),
    patch.object(w, "verify_backup", return_value={"source_identity": {"full": "Source"}}),
    patch("macro_placement.has_placement", return_value=True),
    patch.object(w, "choose_client", return_value=Path("/test/client")),
    patch.object(w, "choose_character", return_value=Path("/test/client/WTF/Account/A/R/C")),
    patch.object(w, "macro_plan", return_value=({"file": b"data"}, [])),
    patch.object(w, "wait_for_wow_closed"),
    patch.object(w, "apply_plan") as apply,
    redirect_stdout(io.StringIO()),
):
    w.menu()
    apply.assert_not_called()
    assert not any("Also restore macro action bar slots" in call.args[0] for call in prompts.call_args_list)

runtime = os.environ.get("LUA_RUNTIME") or shutil.which("lua")
if runtime:
    subprocess.run([runtime, str(Path(__file__).with_suffix(".lua")),
                    str(Path(__file__).resolve().parents[1] / "actionbars.lua")], check=True)
else:
    print("SKIP macro slot Lua test: set LUA_RUNTIME.")
print("PASS macro slot scopes, helper installation, destination identity, opt-out, legacy backups and validation")
