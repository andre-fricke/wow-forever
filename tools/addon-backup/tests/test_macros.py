"""Macro snapshot restoration only touches isolated temporary clients."""

import sys, tempfile, zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wow_backup as w


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


with tempfile.TemporaryDirectory() as td:
    root = Path(td).resolve()
    client = root / "client"
    char = client / "WTF/Account/NEW/New Realm/New-Character"
    write(char / "AddOns.txt", b"Example: enabled\n")
    target = char / "macros-cache.txt"
    account = char.parent.parent / "macros-cache.txt"
    write(target, b"old character macros")
    write(account, b"old account macros")
    source = "WTF/Account/OLD/Old Realm/Old-Character"
    character_member = "client/" + source + "/macros-cache.txt"
    account_member = "client/WTF/Account/OLD/macros-cache.txt"
    character_data = 'VER 3 0100000000000001 "Heal é" "134400"\r\n/cast [@mouseover] Healing Touch\r\nEND\r\n'.encode()
    account_data = b'VER 3 0000000000000001 "Focus" "134400"\r\n/focus\r\nEND\r\n'
    payloads = {character_member: character_data, account_member: account_data}
    manifest = {
        "source_character": source,
        "files": {n: {"sha256": w.sha(d)} for n, d in payloads.items()},
    }
    archive = root / "snapshot.zip"
    with zipfile.ZipFile(archive, "w") as z:
        for name, data in payloads.items():
            z.writestr(name, data)
    saved = w.RECOVERY
    w.RECOVERY = root / "Recovery"
    try:
        plan, notes = w.macro_plan(archive, manifest, client, char)
        assert list(plan) == [target.relative_to(client).as_posix()]
        receipt = w.apply_plan(client, plan, "macro test")
        assert (
            target.read_bytes() == character_data
            and account.read_bytes() == b"old account macros"
        )
        assert w.macro_plan(archive, manifest, client, char)[0] == {}
        w.undo(receipt)
        assert target.read_bytes() == b"old character macros"
        plan, _ = w.macro_plan(archive, manifest, client, char, "both")
        assert len(plan) == 2
        receipt = w.apply_plan(client, plan, "both macro scopes")
        assert account.read_bytes() == account_data
        w.undo(receipt)
        assert account.read_bytes() == b"old account macros"
        assert len(w.macro_plan(archive, manifest, client, char, "account")[0]) == 1
        missing = {"source_character": source, "files": {}}
        assert w.macro_plan(archive, missing, client, char, "both")[0] == {}
        bad = {
            "source_character": source,
            "files": {character_member: {"sha256": "invalid"}},
        }
        try:
            w.macro_plan(archive, bad, client, char)
        except ValueError:
            pass
        else:
            raise AssertionError("Corrupted macros accepted")
        try:
            w.macro_plan(archive, manifest, client, root / "outside")
        except ValueError:
            pass
        else:
            raise AssertionError("Outside character accepted")
        target.unlink()
        target.symlink_to(account)
        try:
            w.macro_plan(archive, manifest, client, char)
        except ValueError:
            pass
        else:
            raise AssertionError("Symlink accepted")
    finally:
        w.RECOVERY = saved
print(
    "PASS macro scopes, exact Unicode/CRLF payloads, idempotency, undo, missing files, corruption, destination validation"
)
