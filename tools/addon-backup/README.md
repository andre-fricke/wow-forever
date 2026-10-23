# WoW Addon Backup

Standalone macOS tool for versioned addon/UI backups and migration to a new character with a different account, realm, and GUID. Requires Python 3.9 or later; no additional Python packages are needed. The macOS launcher searches PATH and common Homebrew, python.org, and Apple developer-tool locations for a compatible interpreter. If none is found, it prints installation instructions. Keep `python_runtime.zsh` alongside the launcher.

## Getting started

Double-click `WoW-Addon-Backup.command` in Finder. The Backup submenu offers separate addon, macro and built-in Click Casting backups, verification, and backup deletion. The Restore submenu offers addon, macro and built-in Click Casting restoration. The Recovery submenu offers undo and recovery point deletion. After each action, the tool returns to the main menu so you can create a backup and restore it in the same window. Choose **0 – Exit** to quit. Failed or cancelled actions also return to the menu. The interactive tool checks whether WoW is closed and, if necessary, waits up to 30 seconds with a countdown every five seconds. Quit WoW completely during that wait; if it remains open, the action is cancelled.

- [User guide](GUIDE.md)
- [Shared chat layout investigation and November 4 test](CHAT_LAYOUT_INVESTIGATION.md)
- [Validation report](VALIDATION.md)

A Git clone does not include personal backups. These are created in `Backups/<Realm>/<Character>/Addons/` or `Macros/`; `latest.json` points to the current snapshot. Recovery data is stored in `Recovery/<Realm>/<Character>/<Timestamp>/`. Backup and recovery selection follows realm → character → file/point, with `0` or Enter to go back. These paths are deliberately excluded from Git. Older `Ruecksicherungen/` directories remain supported and excluded. Back up the entire tool directory, including these local files, separately.

## Macro action bar slots

Interactive **Backup Macros** ensures the identity helper is installed and enabled, then uses the compatible macro-slot snapshot saved at the character's last logout. No additional login is required when that snapshot and character identity already exist. Only missing or incompatible data requires one login and a complete WoW exit with the helper enabled. The snapshot captures macro assignments in standard action slots 1–180, including paged bars, alongside character/account macro files. It does not capture addon-specific buttons that execute macro text directly, bar geometry, or key bindings.

**Restore Macros** first asks you to confirm replacing the selected macro files. Only after that confirmation does it ask whether to restore those slots (`[Y/n]`, Enter confirms). No files are written until both decisions are complete; declining placement still restores the macros. Only slots belonging to the selected macro scope are queued. On the next login the helper finds macros by scope, name and body, then replaces actions in the captured slots. Other slots are left alone. Completed placements are not repeated on later logins. Combat, an occupied cursor or missing macros can defer placement; check the chat message and use `/wuibars` to retry outside combat with an empty cursor.

Older backups remain usable without placement. Empty slot snapshots from helper 1.1 are unreliable and require one new capture with helper 1.2. New captures count detected macros and report unresolved slots instead of silently dropping them; duplicate macro names may need renaming. Backup and restore print character/account slot counts. The CLI can opt in with `restore-macros --restore-macro-slots`; CLI backups use the last captured slot snapshot and warn if none exists. Refresh it by logging in/out with the updated helper before taking a CLI backup. Local recovery points can cancel a queued placement before login, but cannot undo server-side action slots after they have been applied. In-game verification is still required.

## Automatic setup for new characters

The **4 – Automatic setup** submenu prepares an account template for the existing
**WoW UI Transfer Identity** helper; no separate addon is required.

Helper 1.5 selects the existing custom Edit Mode layout named exactly `default`
once, before applying addon profiles. It does not overwrite or import shared
layout contents. Missing or duplicate names leave setup pending with an explicit
message. On a fresh account, create/import this layout first. After completion,
later layout choices are preserved. For an already initialized character,
`/wuieditmode` explicitly selects `default` without replaying addon settings.

1. Use **4.1 – Install / update capture helper** on the source character. Log in
   once with the current helper, wait at least five seconds after editing macros or native
   Click Casting, then quit WoW completely. Create addon, macro and Click Casting
   backups. Existing compatible captures can be reused; each backup stays immutable.
2. Use **4.2 – Configure / update automatic setup**. Select the destination client
   and an existing character to identify the account, then choose the three source
   backups (macros and Click Casting are optional). Review the compatibility notes
   and confirm. This installs missing packages, updates the helper, and writes the
   account template in one recoverable transaction. Existing addon versions stay.
3. Keep the helper enabled. Create a **new level-1 character** on that account and
   log in. The helper applies supported settings and may reload the UI up to three
   times, including a final reload to initialize restored chat windows. Completion
   is saved before that final reload, so subsequent logins do not repeat setup.
   Completion or a specific pending error is printed in chat. `/wuisetup` retries
   outside combat with an empty cursor. **4.3** shows the last saved status.
4. **4.2** can select newer backups for future characters. Completed characters
   are never reset; pending characters retain their original template. **4.4**
   disables future/pending imports without undoing already applied changes.

Existing local characters are excluded by GUID. When no GUID is recorded, their
name is conservatively excluded across all realms. Unseen characters above level
1 are also excluded. A new release account needs one initial login to establish
its account directory before configuration; that initial character uses manual
restore, and subsequent new characters can use automatic setup. Realms, names and
GUIDs for new characters are taken from the game, not guessed from folder names.

**Scope:** active AceDB profiles and their namespaces get private per-character
copies, including supported Prat and RestedXP profiles. Reviewed character settings
are copied with identity remapping and existing progress retained. Shared settings
(including EllesmereUI's account profile) are inherited. If a reviewed account
file is missing, preparation seeds it once; the preview explicitly lists these
account-wide changes. Existing shared files are not overwritten. This is not an
automatic equivalent of every offline restore adapter: unknown configurations are
listed. Helper 1.4 additionally captures persistent chat-window positions, sizes,
docking order and lock state, including Combat Log, into addon backups. These are
applied once after the settings reload. New captures include each window's background
opacity (including fully transparent backgrounds), and custom-window
message groups and channel assignments. Restore reuses a persistent window with
the same name or creates one, then restores its subscriptions and geometry.
Window IDs may differ on the destination. Unrelated windows are not renamed.
Private channels are not joined automatically; their membership/passwords are not
part of this capture. Older captures without subscriptions skip missing custom
windows with a message. Capture a fresh addon backup to enable window creation.
Older captures without opacity retain the destination opacity. After updating the
helper, log into the source, quit WoW and create a fresh addon backup to capture it.
Automatic setup retries temporary errors for up to one minute after entering the
world or finishing the cinematic. Persistent errors are reported and remain pending;
completed steps are not replayed by retries.
Full Edit Mode layouts, key
bindings and display CVars are not imported. The primary chat window can still be
positioned by Edit Mode. On clients with Edit Mode, the helper leaves the main
chat window's position and size untouched to avoid changing a shared layout;
Combat Log and custom-window geometry are still restored. Background opacity
is restored for all captured windows. Reloads prefer `C_UI.Reload`, falling back
to `ReloadUI` on older clients.

To add chat geometry to an existing template, install the updated helper on the
source with **4.1**, log in, wait five seconds with the desired layout and quit.
Create a new **addon** backup and select it in **4.2**; unchanged macro and Click
Casting backups can be reused. On an already initialized destination, `/wuichat`
explicitly restores only chat geometry from the current account template. It does
not reapply other settings or change the automatic setup completion marker.

Macros and native Click Casting are imported even when the character's class
differs from the source. A shared Python import policy replaces named spell
operands in `/cast`, `/spell`, `/castrandom` and `/castsequence` with literal `null`
when classes differ. Conditions, sequence reset options, names, icons and file IDs
are preserved. `/use`, tooltips, Lua scripts, numeric operands and item references
are not guessed or rewritten. Same-class bodies remain byte-for-byte unchanged.
Native Click Casting spell IDs remain unchanged; its macro references resolve to
the transformed macro bodies. Manual menu/CLI restoration and automatic templates
use `macro_transform.py`; Lua selects a precompiled variant rather than parsing
macro text again. Update prepared templates with **4.2** after policy changes.
Manual restoration needs a recorded destination class to select the right variant.
Menu **4.2** also upgrades older pending imports that have not applied any bindings:
it compiles variants from each pending import's original macros, retaining its
settings and completed stages. Already applied bindings and completed characters
are not migrated or replayed. Resume the same pending character after configuration.
For characters
marked complete by an older helper that skipped bindings because of their class,
update the helper with **4.1**, then run `/wuisetup bindings` in game. This explicitly
imports only the skipped bindings from the current account template, without
reapplying addon profiles or chat geometry. Identical macros are reused; different macros
with the same name and insufficient capacity leave the operation pending without
overwriting existing macros. Account macros remain shared. Imports and action-slot
placement reuse current same-scope `Decursive` and `RS_MACRO` macros when their
owning addon is loaded and the name is unique. These addon-maintained contents
are not overwritten with an older body or a cross-class `null` variant. Other
same-name/different-body conflicts still stop the import. A missing owner does
not grant this exception. Click Casting macro
references are remapped by identity, never by copying source API indices. Only
captured macro action slots are replaced, once. Native API restrictions can block
an import; read-back verification keeps it pending instead of reporting success.

Older backups without helper 1.3 API captures remain valid for manual restores.
Automatic macros/Click Casting require new captures; macro captures are also
checked against their archived cache files. If the scope/name sets match uniquely,
the archived macro files supply the bodies and icons, including bodies regenerated
by addons after the API capture. Slot and Click Casting macro references receive
the same bodies before the import policy is compiled. Missing, renamed or duplicate
macro names are rejected rather than guessing index mappings. The template is
stored in the selected account's `SavedVariables/WoWUITransferIdentity.lua`, outside
Git, and is independent of the source ZIPs after preparation. Do not share that
file publicly. Local recovery can undo preparation, but cannot undo in-game macro,
action-slot or Click Casting changes already applied to the server. Check a new
test character in game before relying on this workflow on release day.

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
