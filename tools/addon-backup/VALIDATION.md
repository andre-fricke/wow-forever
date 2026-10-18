# Validation on October 18, 2026

The first-version refactor was checked with `python3 -B run_tests.py --require-lua` using Python 3.9 and a temporary Lua 5.1.5 build. All 12 self-contained test scripts passed. No live WoW files were modified.

Additional coverage now includes:

- Same-account migration with source, destination and third-character data; unchanged progression and unrelated profiles.
- Shared profile/name collisions and stable private destination profiles on repeated restores.
- Actual Lua `unpack` behavior for RestedXP position lists containing a nil slot.
- Cancelled addon restore with no installation or settings writes.
- Missing addon installation and settings applied in one recoverable transaction.
- CLI preview/apply and automatic process checks, including refusal when the process check fails.
- Changed destination files after preview, rejected before writing.
- Invalid manifest metadata and legacy schema-1 archive compatibility.

The existing local addon snapshot from October 18 was also restored into an isolated temporary client with a different account, realm, GUID and class. The integration test passed, including preserved target progress, visual profiles and an unchanged second restore.

GitHub Actions is configured for macOS with Python 3.9 and 3.13 and Lua 5.1.5. The hosted workflow has not run yet. Tests do not establish future release-client API compatibility or replace an in-game layout check.

---

# Historical validation on October 14, 2026

## Source data

- Template: Cannot Hotalot, Druid, Classic Beta PvP 2.
- Source: `/Applications/World of Warcraft/_classic_beta_`.
- Standalone snapshot: `Backups/20261014-161319-002099.zip`.
- 72 addon directories; 8,414 archived files; 163 MiB compressed.
- Complete raw copies of `Interface/AddOns` and `WTF`, with checksums for each file.
- No unknown, unsupported configuration files detected in this template.

## Verified behavior

1. Full integrity of the actual backup against the stored file checksums.
2. Reading and writing Lua data, including accented characters, Unicode, control characters, tables, and numbers. Configuration files are not executed as code.
3. Mapping full character names and `Name - Realm` profile keys to new names and realms; replacing the character's GUID.
4. Simulation of a new destination account with character `New Surname`, realm `Actual Release Realm`, a new GUID, and the Shaman class.
5. EllesmereUI's complete visual profiles are semantically equal to the backup in this simulation. Additional checks cover UI scale, fonts, colors, anchors, and height/width links.
6. Addon activation and deactivation transferred; character detection disabled after import.
7. Existing destination quest progress, equipment, class, and RXP guide progress preserved; beta gold and old specialization caches excluded.
8. Destination realm and account preserved in client configuration; beta connection settings excluded.
9. Existing addon versions preserved during normal preparation. Missing addons include all archived files in the installation plan. Explicit version replacement accounts for obsolete files.
10. Archived addon files written, verified, and successfully undone in an isolated test installation.
11. Updating a backup creates a new snapshot and updates the current snapshot pointer while preserving the previous snapshot unchanged.
12. An injected write failure rolls back changes already written.
13. Recovery and conflict detection tested against subsequent user edits.
14. Tampered archives rejected; symlink destinations outside the destination client rejected.
15. Actual configuration import applied to the simulated destination: 51 files. A second run makes no additional changes.

## Test limitations

Tests ran in isolated temporary directories. No release installation on this machine was modified. The character detection helper has been prepared but has not run in the future release client. These tests verify offline file import and the structure of preserved settings; actual rendering and addon API compatibility must be checked at the first release login.
