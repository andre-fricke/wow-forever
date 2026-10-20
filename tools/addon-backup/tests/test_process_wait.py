"""Process waiting uses a fake clock; no real waits or WoW writes."""

import io, subprocess, sys
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import wow_backup as w
import runtime

for output, expected in (
    (
        "/Applications/World of Warcraft/_classic_/World of Warcraft.app/Contents/MacOS/World of Warcraft\n",
        True,
    ),
    (
        "/Applications/World of Warcraft/WoW Launcher.app/Contents/MacOS/Launcher\n",
        False,
    ),
    ("/Applications/World of Warcraft/Helper.app/Contents/MacOS/Helper\n", False),
    ("/bin/zsh\n/usr/bin/python3\n", False),
):
    with patch.object(
        runtime.subprocess,
        "run",
        return_value=SimpleNamespace(returncode=0, stdout=output),
    ):
        assert w.wow_is_running() is expected
for error in (OSError("denied"), subprocess.TimeoutExpired("ps", 2)):
    with patch.object(runtime.subprocess, "run", side_effect=error):
        try:
            w.wow_is_running()
        except ValueError:
            pass
        else:
            raise AssertionError("Failed process check treated as closed")
with patch.object(
    runtime.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout="")
):
    try:
        w.wow_is_running()
    except ValueError:
        pass
    else:
        raise AssertionError("Failed ps accepted")

for exit_at in (0, 7, 30, None):
    clock = [0]
    sleeps = []

    def sleep(seconds):
        clock[0] += seconds
        sleeps.append(seconds)

    with (
        patch.object(
            w,
            "wow_is_running",
            side_effect=lambda: exit_at is None or clock[0] < exit_at,
        ),
        patch.object(runtime.time, "monotonic", side_effect=lambda: clock[0]),
        patch.object(runtime.time, "sleep", side_effect=sleep),
        patch(
            "builtins.input",
            side_effect=AssertionError("Unexpected manual confirmation"),
        ),
        redirect_stdout(io.StringIO()) as output,
    ):
        try:
            w.wait_for_wow_closed()
        except ValueError:
            assert exit_at is None
        else:
            assert exit_at is not None
    expected_time = 30 if exit_at is None else exit_at
    assert clock[0] == expected_time and all(seconds <= 1 for seconds in sleeps)
    text = output.getvalue()
    if exit_at is None:
        lines = [line for line in text.splitlines() if "seconds remaining" in line]
        assert lines == [f"{n} seconds remaining …" for n in (30, 25, 20, 15, 10, 5, 0)]
    elif exit_at == 7:
        assert "30 seconds remaining" in text and "25 seconds remaining" in text
        assert "20 seconds remaining" not in text and "Continuing." in text
    elif exit_at == 0:
        assert "seconds remaining" not in text

# A timeout returns to the menu without starting the backup.
clock = [0]
with (
    patch("builtins.input", side_effect=["1", "1", "0"]),
    patch.object(w, "choose_client", return_value=Path("/test/client")),
    patch.object(w, "choose_character", return_value=Path("/test/character")),
    patch.object(w, "wow_is_running", return_value=True),
    patch.object(runtime.time, "monotonic", side_effect=lambda: clock[0]),
    patch.object(
        runtime.time,
        "sleep",
        side_effect=lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    ),
    patch.object(w, "create_backup") as backup,
    redirect_stdout(io.StringIO()),
    redirect_stderr(io.StringIO()) as errors,
):
    w.menu()
    backup.assert_not_called()
    assert "after 30 seconds" in errors.getvalue()

# Enter and n cancel macro replacement; only y/yes (case-insensitive) apply it.
for answer in ("", "n", "N", "invalid", "y", "Y", "yes", "YES"):
    with (
        patch("builtins.input", side_effect=["2", "2", "character", answer, "0"]),
        patch.object(w, "choose_snapshot", return_value=Path("/test/backup.zip")),
        patch.object(
            w, "verify_backup", return_value={"source_identity": {"full": "Source"}, "source_character": "WTF/Account/A/R/C", "files": {}}
        ),
        patch.object(w, "choose_client", return_value=Path("/test/client")),
        patch.object(w, "choose_character", return_value=Path("/test/character")),
        patch.object(w, "macro_plan", return_value=({"file": b"data"}, [])),
        patch.object(w, "wait_for_wow_closed") as wait,
        patch.object(w, "apply_plan") as apply,
        redirect_stdout(io.StringIO()),
    ):
        w.menu()
        assert wait.call_count == (2 if answer.lower() in ("y", "yes") else 1)
        if answer.lower() in ("y", "yes"):
            apply.assert_called_once()
        else:
            apply.assert_not_called()
print(
    "PASS process detection, fail-closed checks, countdown, early exit, timeout and macro y/N confirmation"
)
