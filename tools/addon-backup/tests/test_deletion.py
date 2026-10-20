"""Deletion is exercised only against disposable, isolated tool storage."""

import io, json, sys, tempfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wow_backup as w


def rejected(operation):
    try:
        operation()
    except ValueError:
        pass
    else:
        raise AssertionError("Unsafe selection accepted")


with tempfile.TemporaryDirectory() as td:
    root = Path(td).resolve()
    tool = root / "tool"
    tool.mkdir()
    with patch.multiple(
        w,
        HERE=tool,
        SNAPSHOTS=tool / "Backups",
        RECOVERY=tool / "Recovery",
        LEGACY_RECOVERY=tool / "Ruecksicherungen",
    ):
        w.SNAPSHOTS.mkdir()
        older = w.SNAPSHOTS / "20260101_addons.zip"
        newer = (
            w.SNAPSHOTS
            / "Alpha Realm"
            / "Character Name"
            / "Macros"
            / "20260102_macros.zip"
        )
        newer.parent.mkdir(parents=True)
        older.write_bytes(b"old snapshot")
        newer.write_bytes(b"new snapshot")
        w.json_write(
            tool / "latest.json", {"backup": newer.relative_to(tool).as_posix()}
        )
        client = root / "client"
        client.mkdir()
        (client / "settings").write_bytes(b"before")
        receipt = w.apply_plan(client, {"settings": b"after"}, "test restore")
        for recovery in (False, True):
            for answers in (
                ["0"],
                [""],
                ["1", "1", "1", ""],
                ["1", "1", "1", "n"],
                ["1", "1", "1", "invalid"],
            ):
                with (
                    patch("builtins.input", side_effect=answers),
                    redirect_stdout(io.StringIO()),
                ):
                    w.deletion_menu(recovery)
                assert older.exists() and newer.exists() and receipt.exists()
            with (
                patch("builtins.input", side_effect=["-1", "0"]),
                redirect_stdout(io.StringIO()),
            ):
                w.deletion_menu(recovery)
        # Confirmed menu deletion removes only the chosen backup and repairs latest.json.
        with (
            patch("builtins.input", side_effect=["1", "1", "1", "y"]),
            redirect_stdout(io.StringIO()),
        ):
            w.deletion_menu()
        assert not newer.exists() and older.exists() and receipt.exists()
        assert w.latest_backup() == older
        assert (
            json.loads((tool / "latest.json").read_text())["backup"]
            == older.relative_to(tool).as_posix()
        )
        w.delete_backup(older)
        assert not (tool / "latest.json").exists()
        # Undo is independent of the deleted source backups.
        undo_receipt = w.undo(receipt)
        assert (client / "settings").read_bytes() == b"before"
        with (
            patch("builtins.input", side_effect=["1", "1", "1", "yes"]),
            redirect_stdout(io.StringIO()),
        ):
            w.deletion_menu(recovery=True)
        assert not undo_receipt.exists() and receipt.exists()
        assert (client / "settings").read_bytes() == b"before"
        # Legacy recovery points can also be deleted, without touching live files.
        w.LEGACY_RECOVERY.mkdir()
        legacy = w.LEGACY_RECOVERY / receipt.name
        receipt.rename(legacy)
        w.delete_recovery_point(legacy)
        assert not legacy.exists() and (client / "settings").read_bytes() == b"before"
        for recovery in (False, True):
            with (
                patch(
                    "builtins.input", side_effect=AssertionError("Unexpected prompt")
                ),
                redirect_stdout(io.StringIO()),
            ):
                w.deletion_menu(recovery)
        outside = root / "outside.zip"
        outside.write_bytes(b"keep")
        rejected(lambda: w.delete_backup(outside))
        link = w.SNAPSHOTS / "linked.zip"
        link.symlink_to(outside)
        rejected(lambda: w.delete_backup(link))
        assert outside.read_bytes() == b"keep"
        directory = root / "outside-recovery"
        directory.mkdir()
        (directory / "manifest.json").write_text("{}")
        rejected(lambda: w.delete_recovery_point(directory))
        linked = w.RECOVERY / "linked"
        linked.symlink_to(directory, target_is_directory=True)
        rejected(lambda: w.delete_recovery_point(linked))
        assert directory.exists()
        (directory / "outside.zip").write_bytes(b"keep")
        shortcut = w.SNAPSHOTS / "redirected-realm"
        shortcut.symlink_to(directory, target_is_directory=True)
        assert not any(p.name == "outside.zip" for p in w.backup_entries())
        rejected(lambda: w.delete_backup(shortcut / "outside.zip"))
        assert (directory / "outside.zip").read_bytes() == b"keep"
        # Internal symlinks are removed as links, never followed.
        own = w.RECOVERY / "own"
        own.mkdir()
        (own / "manifest.json").write_text("{}")
        (own / "external").symlink_to(directory, target_is_directory=True)
        w.delete_recovery_point(own)
        assert directory.exists() and not own.exists()
print(
    "PASS deletion selection/cancellation, latest pointer, undo independence, legacy recovery, empty lists and path safety"
)

# The new menu routes invoke the correct deletion flow.
for answers, recovery in ((["1", "5", "0"], False), (["3", "2", "0"], True)):
    with (
        patch("builtins.input", side_effect=answers),
        patch.object(w, "deletion_menu") as deletion,
        redirect_stdout(io.StringIO()),
    ):
        w.menu()
        if recovery:
            deletion.assert_called_once_with(recovery=True)
        else:
            deletion.assert_called_once_with()
print("PASS Backup and Recovery deletion menu routing")
