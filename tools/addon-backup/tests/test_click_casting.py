"""Native Click Casting roundtrips touch only synthetic client directories."""
import io
import sys
import tempfile
import zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wow_backup as w


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    client, tool = root / "client", root / "tool"
    tool.mkdir()
    src = client / "WTF/Account/A/Beta/Source"
    dst = client / "WTF/Account/B/Release/Target"
    info = {"name": "Source", "full": "Source", "realm": "Beta", "guid": "Player-1", "class": "ROGUE"}
    write(src / "SavedVariables/WoWUITransferIdentity.lua", w.dump({"WoWUITransferIdentity": info}))
    data = b"1\r\n1\r\n0\r\n1 0 3 1\r\n2 0 2 123\r\nEND\r\n"
    write(src / "click-bindings-cache.txt", data)
    write(dst / "AddOns.txt", b"Example: enabled\n")
    target = dst / "click-bindings-cache.txt"
    write(target, b"old click bindings")
    write(dst / "macros-cache.txt", b"unchanged macros")
    write(dst / "bindings-cache.wtf", b"unchanged keys")
    with patch.multiple(w, HERE=tool, SNAPSHOTS=tool/"Backups", RECOVERY=tool/"Recovery", LEGACY_RECOVERY=tool/"Legacy"):
        archive = w.create_backup(client, src, kind="click-casting")
        manifest = w.verify_backup(archive)
        assert archive.parent == tool / "Backups/Beta/Source/Click_Casting"
        assert len(manifest["files"]) == 1 and manifest["addons"] == {}
        assert w.latest_backup("click-casting") == archive
        assert len(w.backup_records("click-casting")) == 1
        assert w.backup_records("macros") == []
        plan, _ = w.click_casting_plan(archive, manifest, client, dst)
        assert plan == {target.relative_to(client).as_posix(): data}
        receipt = w.apply_plan(client, plan, "Restore Click Casting", character=dst)
        assert target.read_bytes() == data
        assert (dst / "macros-cache.txt").read_bytes() == b"unchanged macros"
        assert (dst / "bindings-cache.wtf").read_bytes() == b"unchanged keys"
        assert w.click_casting_plan(archive, manifest, client, dst)[0] == {}
        w.undo(receipt)
        assert target.read_bytes() == b"old click bindings"
        for bad in (
            {**manifest, "files": {}},
            {**manifest, "kind": "macros"},
            {**manifest, "files": {key: {**value, "sha256": "0"*64} for key,value in manifest["files"].items()}},
        ):
            try:
                w.click_casting_plan(archive, bad, client, dst)
            except ValueError:
                pass
            else:
                raise AssertionError("Invalid Click Casting backup accepted")
        target.unlink()
        target.symlink_to(dst / "macros-cache.txt")
        try:
            w.click_casting_plan(archive, manifest, client, dst)
        except ValueError:
            pass
        else:
            raise AssertionError("Symlink destination accepted")
        target.unlink()
        assert w.click_casting_plan(archive, manifest, client, dst)[0]
        for answer in ("", "n", "y"):
            with (
                patch("builtins.input", side_effect=["2", "3", answer, "0"]),
                patch.object(w, "choose_snapshot", return_value=archive) as choose,
                patch.object(w, "choose_client", return_value=client),
                patch.object(w, "choose_character", return_value=dst),
                patch.object(w, "wait_for_wow_closed"),
                patch.object(w, "apply_plan") as apply,
                redirect_stdout(io.StringIO()),
            ):
                w.menu()
                choose.assert_called_once_with("click-casting")
                assert apply.call_count == (1 if answer == "y" else 0)
        # CLI defaults to the latest matching backup and supports a read-only preview.
        with (
            patch.object(sys, "argv", ["tool", "restore-click-casting", "--client", str(client), "--character", str(dst)]),
            redirect_stdout(io.StringIO()) as output,
        ):
            w.main()
            assert "Preview only" in output.getvalue()
        assert not target.exists()
        with (
            patch("builtins.input", side_effect=["1", "3", "0"]),
            patch.object(w, "choose_client", return_value=client),
            patch.object(w, "choose_character", return_value=src),
            patch.object(w, "wait_for_wow_closed"),
            patch.object(w, "create_backup") as backup,
            redirect_stdout(io.StringIO()),
        ):
            w.menu()
            backup.assert_called_once_with(client, src, kind="click-casting")
print("PASS Click Casting backup, filtering, exact restore, isolation, recovery, corruption, symlinks, menu confirmation and CLI preview")
