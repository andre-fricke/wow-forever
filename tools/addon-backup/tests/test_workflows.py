"""Exercise restore confirmation, CLI guards and preview conflicts in temporary clients."""

import copy
import io
import json
import sys
import tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wow_backup as w
from models import BackupManifest


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(value)


with tempfile.TemporaryDirectory() as td, redirect_stdout(io.StringIO()):
    root = Path(td).resolve()
    tool = root / "tool"
    tool.mkdir()
    beta = root / "beta"
    src = beta / "WTF/Account/OLD/Beta/Old-Name"
    source = dict(
        name="Old", full="Old Name", realm="Beta", guid="Player-1", **{"class": "DRUID"}
    )
    target = dict(
        name="New",
        full="New Name",
        realm="Release",
        guid="Player-2",
        **{"class": "DRUID"},
    )
    write(src / "SavedVariables" / f"{w.HELPER}.lua", w.dump({w.HELPER: source}))
    write(
        beta / "Interface/AddOns/TestAce/TestAce.toc",
        b"## Interface: 16001\n## SavedVariables: DB\n",
    )
    write(
        src.parent.parent / "SavedVariables/TestAce.lua",
        w.dump(
            {
                "DB": {
                    "profileKeys": {"Old Name": "Shared"},
                    "profiles": {"Shared": {"width": 220}},
                }
            }
        ),
    )
    write(src / "AddOns.txt", b"TestAce: enabled\n")
    client = root / "release"
    char = client / "WTF/Account/NEW/Release/New-Name"
    write(char / "SavedVariables" / f"{w.HELPER}.lua", w.dump({w.HELPER: target}))
    write(char / "AddOns.txt", b"TestAce: disabled\n")
    with (
        patch.object(w, "HERE", tool),
        patch.object(w, "SNAPSHOTS", tool / "Backups"),
        patch.object(w, "RECOVERY", tool / "Recovery"),
    ):
        archive = w.create_backup(beta, src, "addons")
        manifest = w.verify_backup(archive)

        def state():
            return {
                p.relative_to(client): p.read_bytes()
                for p in client.rglob("*")
                if p.is_file()
            }

        original = state()
        # Cancel after the full plan, with a missing addon: not even preparation may write.
        with (
            patch("builtins.input", side_effect=["2", "1", "n"]),
            patch.object(w, "choose_snapshot", return_value=archive),
            patch.object(w, "choose_client", return_value=client),
            patch.object(w, "choose_character", return_value=char),
            patch.object(w, "wait_for_wow_closed"),
        ):
            w.menu_action()
        assert state() == original
        assert not w.recovery_entries()
        # Confirm: missing addon + settings are one transaction, not two.
        with (
            patch("builtins.input", side_effect=["2", "1", "y"]),
            patch.object(w, "choose_snapshot", return_value=archive),
            patch.object(w, "choose_client", return_value=client),
            patch.object(w, "choose_character", return_value=char),
            patch.object(w, "wait_for_wow_closed") as wait,
        ):
            w.menu_action()
        assert wait.call_count == 2
        assert (client / "Interface/AddOns/TestAce/TestAce.toc").exists()
        settings = w.plain(
            w.parse((char.parent.parent / "SavedVariables/TestAce.lua").read_bytes())
        )["DB"]
        assert settings["profiles"][settings["profileKeys"]["New Name"]]["width"] == 220
        assert (w.HELPER + ": disabled").encode() in (char / "AddOns.txt").read_bytes()
        assert len(w.recovery_entries()) == 1
        w.undo(w.recovery_entries()[0])
        assert state() == original
        # CLI preview uses the same combined plan and performs no writes.
        argv = [
            "wow_backup.py",
            "restore",
            "--client",
            str(client),
            "--character",
            str(char),
            "--backup",
            str(archive),
        ]
        with (
            patch.object(sys, "argv", argv),
            patch.object(w, "wait_for_wow_closed") as wait,
        ):
            w.main()
        wait.assert_not_called()
        assert state() == original
        with (
            patch.object(sys, "argv", argv + ["--apply", "--closed"]),
            patch.object(w, "wait_for_wow_closed") as wait,
        ):
            w.main()
        assert wait.call_count == 2
        assert (client / "Interface/AddOns/TestAce/TestAce.toc").exists()
        # Changed destination files after preview are never overwritten.
        plan = w.FilePlan.capture(client, {"WTF/test": b"new"}, w.rooted, w.file_sha)
        write(client / "WTF/test", b"changed after preview")
        with (
            patch.object(w, "wait_for_wow_closed"),
            patch.object(w, "apply_plan") as apply,
        ):
            try:
                w.execute_plan(client, plan, "conflict")
            except ValueError as error:
                assert "after preview" in str(error)
            else:
                raise AssertionError("Stale plan accepted")
            apply.assert_not_called()
        # --closed is an acknowledgement, never a bypass for process checks.
        with (
            patch.object(
                sys,
                "argv",
                [
                    "wow_backup.py",
                    "backup",
                    "--client",
                    str(beta),
                    "--character",
                    str(src),
                    "--closed",
                ],
            ),
            patch.object(
                w, "wait_for_wow_closed", side_effect=ValueError("WoW is running")
            ),
            patch.object(w, "create_backup") as backup,
        ):
            try:
                w.main()
            except ValueError:
                pass
            else:
                raise AssertionError("Running WoW accepted by CLI")
            backup.assert_not_called()
        # Invalid metadata is rejected intentionally, not via an incidental traceback.
        for field, value in [
            ("source_identity", []),
            ("files", []),
            ("unsupported", [1]),
            ("kind", "unknown"),
        ]:
            bad = copy.deepcopy(manifest)
            bad[field] = value
            try:
                BackupManifest.from_mapping(bad)
            except ValueError:
                pass
            else:
                raise AssertionError("Invalid manifest accepted: " + field)
print(
    "PASS cancelled restore, single transaction, undo, CLI preview/apply, process checks, stale plans and metadata validation"
)
