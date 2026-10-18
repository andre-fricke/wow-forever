# WoW Addon Backup

Standalone macOS tool for versioned addon/UI backups and migration to a new character with a different account, realm, and GUID. Requires Python 3.9 or later; no additional Python packages are needed. The macOS launcher searches PATH and common Homebrew, python.org, and Apple developer-tool locations for a compatible interpreter. If none is found, it prints installation instructions. Keep `python_runtime.zsh` alongside the launcher.

## Getting started

Double-click `WoW-Addon-Backup.command` in Finder. The Backup submenu offers separate addon and macro backups, verification, and backup deletion. The Restore submenu offers addon and macro restoration. The Recovery submenu offers undo and recovery point deletion. After each action, the tool returns to the main menu so you can create a backup and restore it in the same window. Choose **0 – Exit** to quit. Failed or cancelled actions also return to the menu. The interactive tool checks whether WoW is closed and, if necessary, waits up to 30 seconds with a countdown every five seconds. Quit WoW completely during that wait; if it remains open, the action is cancelled.

- [User guide](GUIDE.md)
- [Validation report](VALIDATION.md)

A Git clone does not include personal backups. These are created in `Backups/<Realm>/<Character>/Addons/` or `Macros/`; `latest.json` points to the current snapshot. Recovery data is stored in `Recovery/<Realm>/<Character>/<Timestamp>/`. Backup and recovery selection follows realm → character → file/point, with `0` or Enter to go back. These paths are deliberately excluded from Git. Older `Ruecksicherungen/` directories remain supported and excluded. Back up the entire tool directory, including these local files, separately.

## Tests

Run from this directory:

```sh
python3 -B run_tests.py
```

For the full release check, install Lua 5.1 (or set `LUA_RUNTIME` to its executable) and run:

```sh
python3 -B run_tests.py --require-lua
```

The tool itself still needs only Python. Lua is a development test dependency: only synthetic fixtures are executed. GitHub Actions runs the full check on macOS with Python 3.9 and 3.13.

These tests create synthetic data in temporary directories and do not modify a WoW installation. They cover character mapping, Unicode, archives, backup updates, installation, recovery, and failure handling.

Optional integration test using the original development beta snapshot (restores only into a temporary directory):

```sh
python3 -B tests/test_saved_snapshot.py /absolute/path/to/backup.zip
```

Run `python3 -B wow_backup.py --help` for the CLI overview.

## Compatibility

Installation and character selection have no personal defaults. A fresh clone includes no backups; create your own first. The character identity helper may require one extra login before the first backup. The launcher is for macOS; Windows startup is not provided. Addon restoration supports reviewed adapters and recognized profile formats, not every addon or WoW version. During interactive addon restoration, unknown configurations are listed. Choose **1 – Skip listed addons and continue** to restore the supported addons, or **0 / Enter** to return. Skipped addons are not installed or restored; their existing settings and activation state are preserved. The backup remains unchanged. CLI restoration also supports skipping these configurations with `--skip-unknown`. Without that option it stops for review. Live macro synchronization and future release-client compatibility still need in-game validation.


## Restore behavior

For a recognized character, installation and settings are planned together and written only after the final y/N confirmation. One recovery point covers that complete operation. If identity detection is needed, a separate confirmed preparation installs/enables only the identity helper; it does not install the backed-up addons. Cancelling the later restore leaves that explicitly accepted preparation in place.

AceDB-style imports create or update a private profile for the destination character. Existing source/other-character profiles and destination progress are retained. If the normal profile name is shared or occupied, a deterministic ` [UI Backup]` suffix avoids overwriting it. Addons with genuinely account-wide settings still affect the entire destination account.

Both the menu and CLI check the WoW process. CLI write commands retain `--closed` for compatibility, but it never bypasses the process check. Restore plans are checked for destination changes after preview before writing.

See [architecture and maintenance](ARCHITECTURE.md) for module boundaries, adapter policies and development checks.
