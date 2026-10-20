# WoW Addon Backup

Standalone macOS tool for versioned addon/UI backups and migration to a new character with a different account, realm, and GUID. Requires Python 3.9 or later; no additional Python packages are needed. The macOS launcher searches PATH and common Homebrew, python.org, and Apple developer-tool locations for a compatible interpreter. If none is found, it prints installation instructions. Keep `python_runtime.zsh` alongside the launcher.

## Getting started

Double-click `WoW-Addon-Backup.command` in Finder. The Backup submenu offers separate addon, macro and built-in Click Casting backups, verification, and backup deletion. The Restore submenu offers addon, macro and built-in Click Casting restoration. The Recovery submenu offers undo and recovery point deletion. After each action, the tool returns to the main menu so you can create a backup and restore it in the same window. Choose **0 – Exit** to quit. Failed or cancelled actions also return to the menu. The interactive tool checks whether WoW is closed and, if necessary, waits up to 30 seconds with a countdown every five seconds. Quit WoW completely during that wait; if it remains open, the action is cancelled.

- [User guide](GUIDE.md)
- [Validation report](VALIDATION.md)

A Git clone does not include personal backups. These are created in `Backups/<Realm>/<Character>/Addons/` or `Macros/`; `latest.json` points to the current snapshot. Recovery data is stored in `Recovery/<Realm>/<Character>/<Timestamp>/`. Backup and recovery selection follows realm → character → file/point, with `0` or Enter to go back. These paths are deliberately excluded from Git. Older `Ruecksicherungen/` directories remain supported and excluded. Back up the entire tool directory, including these local files, separately.

## Macro action bar slots

Interactive **Backup Macros** ensures the identity helper is installed and enabled, then uses the compatible macro-slot snapshot saved at the character's last logout. No additional login is required when that snapshot and character identity already exist. Only missing or incompatible data requires one login and a complete WoW exit with the helper enabled. The snapshot captures macro assignments in standard action slots 1–180, including paged bars, alongside character/account macro files. It does not capture addon-specific buttons that execute macro text directly, bar geometry, or key bindings.

**Restore Macros** first asks you to confirm replacing the selected macro files. Only after that confirmation does it ask whether to restore those slots (`[y/N]`, default no). No files are written until both decisions are complete; declining placement still restores the macros. Only slots belonging to the selected macro scope are queued. On the next login the helper finds macros by scope, name and body, then replaces actions in the captured slots. Other slots are left alone. Completed placements are not repeated on later logins. Combat, an occupied cursor or missing macros can defer placement; check the chat message and use `/wuibars` to retry outside combat with an empty cursor.

Older backups remain usable without placement. Empty slot snapshots from helper 1.1 are unreliable and require one new capture with helper 1.2. New captures count detected macros and report unresolved slots instead of silently dropping them; duplicate macro names may need renaming. Backup and restore print character/account slot counts. The CLI can opt in with `restore-macros --restore-macro-slots`; CLI backups use the last captured slot snapshot and warn if none exists. Refresh it by logging in/out with the updated helper before taking a CLI backup. Local recovery points can cancel a queued placement before login, but cannot undo server-side action slots after they have been applied. In-game verification is still required.

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

AceDB-style imports create or update a private profile for the destination character. Module profiles stored in AceDB namespaces are transferred with the parent profile, including Prat editbox appearance/position and chat-window font sizes (such as the combat log). Existing source/other-character profiles and destination progress are retained. If the normal profile name is shared or occupied, a deterministic ` [UI Backup]` suffix avoids overwriting it. Addons with genuinely account-wide settings still affect the entire destination account.

Both the menu and CLI check the WoW process. CLI write commands retain `--closed` for compatibility, but it never bypasses the process check. Restore plans are checked for destination changes after preview before writing.

See [architecture and maintenance](ARCHITECTURE.md) for module boundaries, adapter policies and development checks.

## Optional RestedXP skin

[RestedXP Text Only](../../addon/RestedXPTextOnly/README.md) is a separate companion addon for a minimal classic RestedXP window. Its per-character settings are supported. After installing it, log in and quit WoW, then create a new addon backup to include the companion files and settings.

## Built-in Click Casting

**1.3 – Backup Click Casting** saves the selected character's native
`click-bindings-cache.txt` under `Backups/<Realm>/<Character>/Click_Casting/`.
**2.3 – Restore Click Casting** browses those backups and restores only that file
after confirmation, with a recovery point. **Verify Backup** is now **1.4** and
**Delete Backup** is **1.5**.

Spell and macro references remain unchanged. Restore matching macros separately
first and check the click bindings after login; this is not an import of
EllesmereUI, DandersFrames or Clique settings. See the user guide for CLI commands.
