"""Fail-closed WoW process checks shared by menu and CLI."""

import math
import subprocess
import time


def wow_is_running():
    try:
        result = subprocess.run(
            ["/bin/ps", "-axo", "comm="], capture_output=True, text=True, timeout=2
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise ValueError(
            "Could not check whether WoW is running. Try again before modifying files."
        ) from error
    if result.returncode != 0:
        raise ValueError(
            "Could not check whether WoW is running. Try again before modifying files."
        )
    return any(
        "World of Warcraft" in line
        and "/Contents/MacOS/" in line
        and "Launcher" not in line
        and "Helper" not in line
        for line in result.stdout.splitlines()
    )


def wait_for_wow_closed(*, is_running=wow_is_running):
    if not is_running():
        print("WoW is closed. Continuing.", flush=True)
        return
    print(
        "WoW is still running. Quit WoW completely; waiting up to 30 seconds …",
        flush=True,
    )
    deadline = time.monotonic() + 30
    countdown = 30
    while True:
        remaining = deadline - time.monotonic()
        while countdown >= max(0, math.ceil(remaining)):
            print(f"{countdown} seconds remaining …", flush=True)
            countdown -= 5
        if remaining <= 0:
            raise ValueError(
                "WoW is still running after 30 seconds. Quit WoW and select the action again."
            )
        # Check every second; display the countdown every five seconds.
        time.sleep(min(1, remaining))
        if not is_running():
            print("WoW has closed. Continuing.", flush=True)
            return
