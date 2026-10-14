# WoW Addon Backup

Standalone macOS tool for versioned addon/UI backups and migration to a new character with a different account, realm, and GUID. Requires Python 3.9 or later; no additional Python packages are needed.

## Getting started

Double-click `WoW-Addon-Backup.command` in Finder. The menu offers backup creation/updates, restoration, undo, and integrity checks. Quit WoW completely before creating a backup or importing settings.

- [User guide](GUIDE.md)
- [Validation report](VALIDATION.md)

A Git clone does not include personal backups. These are created in `Backups/`; `latest.json` points to the current snapshot. Recovery data is stored in `Recovery/`. These paths are deliberately excluded from Git. Older `Ruecksicherungen/` directories remain supported and excluded. Back up the entire tool directory, including these local files, separately.

## Tests

Run from this directory:

```sh
python3 -B tests/test_core.py
python3 -B tests/test_snapshots.py
```

These tests create synthetic data in temporary directories and do not modify a WoW installation. They cover character mapping, Unicode, archives, backup updates, installation, recovery, and failure handling.

Optional integration test using the existing Cannot beta snapshot (restores only into a temporary directory):

```sh
python3 -B tests/test_saved_snapshot.py /absolute/path/to/backup.zip
```

Run `python3 -B wow_backup.py --help` for the CLI overview.
