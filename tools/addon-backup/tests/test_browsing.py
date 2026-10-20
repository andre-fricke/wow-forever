"""Exercise archive browsing and nested recovery points in isolated storage."""

import io, json, sys, tempfile, zipfile
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wow_backup as w


def pick(operation, answers):
    with (
        patch("builtins.input", side_effect=answers),
        redirect_stdout(io.StringIO()) as output,
    ):
        result = operation()
    return result, output.getvalue()


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

        def snapshot(date, realm, character, kind, legacy=False):
            folder = (
                w.SNAPSHOTS
                if legacy
                else w.backup_directory({"realm": realm, "full": character}, kind)
            )
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / (date + ".zip")
            manifest = {
                "schema": 1,
                "source_identity": {"realm": realm, "full": character},
                "files": {},
                "addons": {},
                "unsupported": [],
            }
            if not legacy:
                manifest["kind"] = kind
            with zipfile.ZipFile(path, "w") as z:
                z.writestr("manifest.json", json.dumps(manifest))
            return path

        older = snapshot("20260101", "Alpha Realm", "Alice", "addons")
        newer = snapshot("20260102", "Alpha Realm", "Alice", "addons")
        macro = snapshot("20260103", "Alpha Realm", "Bob", "macros")
        other = snapshot("20260104", "Zulu Realm", "Zoë Name", "addons")
        legacy = snapshot("20250101", "Legacy Realm", "Old Name", "combined", True)
        assert {r["path"] for r in w.backup_records("addons")} == {
            older,
            newer,
            other,
            legacy,
        }
        assert {r["path"] for r in w.backup_records("macros")} == {macro, legacy}
        selected, text = pick(lambda: w.choose_snapshot("addons"), ["1", "1", "2"])
        assert (
            selected == older
            and "Bob" not in text
            and text.index(newer.name) < text.index(older.name)
        )
        assert pick(lambda: w.choose_snapshot("macros"), ["1", "1", "1"])[0] == macro
        assert pick(w.choose_snapshot, ["1", "2", "1"])[0] == macro
        # Back from files to characters, then realms, then select a different realm.
        assert (
            pick(
                lambda: w.choose_snapshot("addons"), ["1", "1", "0", "0", "3", "1", "1"]
            )[0]
            == other
        )
        for answers in (
            ["0"],
            [""],
            ["1", "0", "0"],
            ["1", "1", "0", "0", "0"],
            ["-1", "99", "0"],
        ):
            assert pick(w.choose_snapshot, answers)[0] is None
        assert pick(lambda: w.choose_snapshot("macros"), ["2", "1", "1"])[0] == legacy
        bad = w.SNAPSHOTS / "broken.zip"
        bad.write_bytes(b"not a zip")
        assert bad in {r["path"] for r in w.backup_records()}
        assert bad not in {r["path"] for r in w.backup_records("addons")}
        # Account-only changes still retain the selected target character.
        client = root / "client"
        char = client / "WTF/Account/NEW/70/Target-Name"
        char.mkdir(parents=True)
        (char / "SavedVariables").mkdir()
        identity = {
            "name": "Target",
            "full": "Target Name",
            "realm": "Actual Realm",
            "guid": "Player-1-T",
            "class": "DRUID",
        }
        (char / "SavedVariables" / f"{w.HELPER}.lua").write_bytes(
            w.dump({w.HELPER: identity})
        )
        account_file = char.parent.parent / "macros-cache.txt"
        account_file.write_bytes(b"before")
        relative = account_file.relative_to(client).as_posix()
        point = w.apply_plan(
            client, {relative: b"after"}, "Restore account macros", character=char
        )
        assert point.parent == w.RECOVERY / "Actual_Realm" / "Target_Name"
        assert (
            json.loads((point / "manifest.json").read_text())["target"][
                "character_path"
            ]
            == char.relative_to(client).as_posix()
        )
        selected, text = pick(w.choose_recovery, ["1", "1", "1"])
        assert selected == point and "Actual Realm" in text and "Target Name" in text
        undo_point = w.undo(point)
        assert (
            undo_point.parent == point.parent and account_file.read_bytes() == b"before"
        )
        # Old flat records are grouped using their recorded target file paths.
        w.LEGACY_RECOVERY.mkdir()
        old = w.LEGACY_RECOVERY / "20200101"
        old.mkdir()
        log = json.loads((point / "manifest.json").read_text())
        log.pop("target")
        log["files"] = [{"path": (char / "AddOns.txt").relative_to(client).as_posix()}]
        (old / "manifest.json").write_text(json.dumps(log))
        records = w.recovery_records()
        record = next(r for r in records if r["path"] == old)
        assert (
            record["realm"] == "Actual Realm" and record["character"] == "Target Name"
        )
        # A group/character directory is not a deletable recovery point.
        try:
            w.delete_recovery_point(point.parent)
        except ValueError:
            pass
        else:
            raise AssertionError("Character directory deletion accepted")
        w.delete_recovery_point(point)
        assert not point.exists() and undo_point.exists() and old.exists()
        assert account_file.read_bytes() == b"before"
print(
    "PASS realm/character browsing, type filtering, ordering, back navigation, legacy discovery and nested account-scope recovery"
)

# Cancelling any restore/verify selection must not perform work.
for action in ("1.4", "2.1", "2.2", "2.3"):
    with (
        patch("builtins.input", side_effect=[action, "0"]),
        patch.object(w, "choose_snapshot", return_value=None),
        patch.object(w, "verify_backup") as verify,
        patch.object(w, "apply_plan") as apply,
        redirect_stdout(io.StringIO()),
    ):
        w.menu()
        verify.assert_not_called()
        apply.assert_not_called()
print("PASS cancelled verify/restore selection returns to the menu without writes")
