#!/usr/bin/env python3
"""Run all self-contained tests without reading personal WoW data."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-lua",
        action="store_true",
        help="Fail unless a Lua runtime is available",
    )
    args = parser.parse_args()
    if args.require_lua and not (
        os.environ.get("LUA_RUNTIME")
        or any(shutil.which(name) for name in ("lua5.1", "lua", "luajit"))
    ):
        parser.error("Install Lua 5.1 (used by CI) to run the Lua semantics test.")
    root = Path(__file__).resolve().parent
    failed = []
    for test in sorted((root / "tests").glob("test_*.py")):
        if test.name == "test_saved_snapshot.py":
            continue  # Explicit opt-in integration test for a user's local archive.
        print("Running " + test.name, flush=True)
        try:
            result = subprocess.run(
                [sys.executable, "-B", str(test)],
                cwd=root,
                capture_output=True,
                text=True,
                timeout=90,
            )
            print(result.stdout, end="")
            if result.returncode:
                print(result.stderr, end="", file=sys.stderr)
                failed.append(test.name)
        except subprocess.TimeoutExpired:
            failed.append(test.name)
            print("FAIL: test timed out", file=sys.stderr)
    print(
        "Failed: " + ", ".join(failed) if failed else "All test scripts passed.",
        flush=True,
    )
    return bool(failed)


if __name__ == "__main__":
    sys.exit(main())
