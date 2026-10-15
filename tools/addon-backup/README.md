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
python3 -B tests/test_core.py
python3 -B tests/test_snapshots.py
python3 -B tests/test_macros.py
python3 -B tests/test_menu.py
python3 -B tests/test_deletion.py
python3 -B tests/test_portability.py
python3 -B tests/test_browsing.py
python3 -B tests/test_process_wait.py
```

These tests create synthetic data in temporary directories and do not modify a WoW installation. They cover character mapping, Unicode, archives, backup updates, installation, recovery, and failure handling.

Optional integration test using the original development beta snapshot (restores only into a temporary directory):

```sh
python3 -B tests/test_saved_snapshot.py /absolute/path/to/backup.zip
```

Run `python3 -B wow_backup.py --help` for the CLI overview.

## Compatibility

Installation and character selection have no personal defaults. A fresh clone includes no backups; create your own first. The character identity helper may require one extra login before the first backup. The launcher is for macOS; Windows startup is not provided. Addon restoration supports reviewed adapters and recognized profile formats, not every addon or WoW version. Unsupported configurations are reported and can block restoration. Live macro synchronization and future release-client compatibility still need in-game validation.
