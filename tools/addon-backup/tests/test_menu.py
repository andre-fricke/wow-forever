"""Exercise repeated interactive actions without touching a WoW installation."""

import io, sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wow_backup as w

# A backup can be followed immediately by another action in the same session.
with (
    patch("builtins.input", side_effect=["1", "1", "1", "4", "0"]),
    patch.object(w, "choose_client", return_value=Path("/test/client")),
    patch.object(w, "choose_character", return_value=Path("/test/character")),
    patch.object(w, "wait_for_wow_closed"),
    patch.object(w, "identity", return_value={"name": "Test"}),
    patch.object(w, "create_backup") as backup,
    patch.object(w, "choose_snapshot", return_value=Path("/test/snapshot.zip")),
    patch.object(
        w,
        "verify_backup",
        return_value={"files": {}, "addons": {}, "created": "test", "unsupported": []},
    ) as verify,
    redirect_stdout(io.StringIO()) as output,
):
    w.menu()
    backup.assert_called_once()
    verify.assert_called_once()
    assert output.getvalue().count("0  Exit") == 3

# Invalid selections and interrupted actions do not terminate the session.
with (
    patch("builtins.input", side_effect=["invalid", KeyboardInterrupt(), "0"]),
    redirect_stdout(io.StringIO()) as output,
    redirect_stderr(io.StringIO()) as errors,
):
    w.menu()
    assert "Unknown selection" in errors.getvalue()
    assert "Action cancelled" in output.getvalue()
    assert output.getvalue().count("0  Exit") == 3

# Closed stdin exits rather than spinning forever.
with (
    patch("builtins.input", side_effect=EOFError()),
    redirect_stdout(io.StringIO()) as output,
):
    w.menu()
    assert output.getvalue().count("0  Exit") == 1
print(
    "PASS repeated menu actions, explicit exit, recoverable errors, interruption and EOF"
)

# A cancelled recovery selection never runs undo or asks to close WoW.
for selected in (None, Path("/test/recovery/entry")):
    with (
        patch("builtins.input", side_effect=["3", "1", "0"]),
        patch.object(w, "choose_recovery", return_value=selected),
        patch.object(w, "wait_for_wow_closed") as closed,
        patch.object(w, "undo") as undo,
        redirect_stdout(io.StringIO()),
    ):
        w.menu()
        if selected is None:
            closed.assert_not_called()
            undo.assert_not_called()
        else:
            closed.assert_called_once()
            undo.assert_called_once_with(selected)

# Both nested menus support a no-action return.
for answers in (["1", "0", "0"], ["2", "", "0"], ["3", "0", "0"]):
    with (
        patch("builtins.input", side_effect=answers),
        redirect_stdout(io.StringIO()) as output,
    ):
        w.menu()
        assert output.getvalue().count("0  Exit") == 2
# Macro backup is dispatched separately from addon backup.
with (
    patch("builtins.input", side_effect=["1", "2", "0"]),
    patch.object(w, "choose_client", return_value=Path("/test/client")),
    patch.object(w, "choose_character", return_value=Path("/test/character")),
    patch.object(w, "wait_for_wow_closed"),
    patch.object(w, "identity", return_value={"name": "Test"}),
    patch.object(w, "helper_plan", return_value={}),
    patch.object(w, "apply_plan") as prepare,
    patch.object(Path, "read_bytes", return_value=b'WoWUITransferBars = {schema=2, slots={}, macroActions=0, savedAt=1}'),
    patch.object(w, "create_backup") as backup,
    redirect_stdout(io.StringIO()) as output,
):
    w.menu()
    backup.assert_called_once_with(
        Path("/test/client"), Path("/test/character"), kind="macros"
    )
    prepare.assert_not_called()
    assert "Start WoW" not in output.getvalue()
    assert "last logout" in output.getvalue()
print("PASS backup submenus, macro dispatch and back navigation")

# Repair a missing/disabled helper without forcing a login for a valid snapshot.
# Only an absent/incompatible snapshot requires the capture login.
for missing in (False, True):
    responses = ["1", "2"] + ([""] if missing else []) + ["0"]
    snapshots = [ValueError("Missing snapshot"), {"slots": {}}] if missing else [{"slots": {}}]
    with (
        patch("builtins.input", side_effect=responses),
        patch.object(w, "choose_client", return_value=Path("/test/client")),
        patch.object(w, "choose_character", return_value=Path("/test/character")),
        patch.object(w, "wait_for_wow_closed") as wait,
        patch.object(w, "identity", return_value={"name": "Test"}),
        patch.object(w, "helper_plan", return_value={"helper.lua": b"updated"}),
        patch.object(w, "apply_plan") as prepare,
        patch.object(Path, "exists", return_value=False),
        patch.object(Path, "read_bytes", return_value=b"snapshot"),
        patch("macro_placement.placement_snapshot", side_effect=snapshots),
        patch.object(w, "create_backup") as backup,
        redirect_stdout(io.StringIO()) as output,
    ):
        w.menu()
        prepare.assert_called_once()
        backup.assert_called_once()
        assert ("Start WoW" in output.getvalue()) == missing
        assert wait.call_count == (2 if missing else 1)
print("PASS saved macro slots avoid relogin, helper repair, first-capture login")

# Legacy tool labels are translated, but embedded character names are left intact.
assert (
    w.english_legacy_text("Addon-Dateien und Charaktererkennung vorbereiten")
    == "Prepare addon files and character detection"
)
assert (
    w.english_legacy_text("Charaktererkennung für Backup vorbereiten")
    == "Prepare character detection for backup"
)
assert (
    w.english_legacy_text("Rückgängig: UI-Backup auf Miese Makrele – Realm")
    == "Undo: Restore UI backup to Miese Makrele – Realm"
)
assert (
    w.english_legacy_text("Undo: Rückgängig: UI-Backup auf Name")
    == "Undo: Undo: Restore UI backup to Name"
)
assert w.english_legacy_text("Kontodatei: Example.lua") == "Account file: Example.lua"
assert (
    w.english_legacy_text("Charakterdatei: Example.lua")
    == "Character file: Example.lua"
)
assert w.english_legacy_text("Restore macros to Name") == "Restore macros to Name"
with (
    patch.object(w, "recovery_entries", return_value=[Path("/test/recovery/entry")]),
    patch.object(
        Path,
        "read_text",
        return_value='{"label":"UI-Backup auf Miese Makrele","status":"complete","target":{"realm":"Realm","character":"Miese Makrele"}}',
    ),
):
    records = w.recovery_records()
    assert "Restore UI backup to Miese Makrele" in records[0]["label"]
    assert "UI-Backup auf" not in records[0]["label"]
print("PASS English legacy labels and unchanged character names")
