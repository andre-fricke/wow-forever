# WoW Addon Backup: last beta day → first release day

Double-click **WoW-Addon-Backup.command** in Finder to open the Terminal menu. After each action, the menu appears again in the same window. Select **0 – Exit** to quit. Keep the entire `tools/addon-backup` directory together: it contains the tool, character detection helper, backups, and recovery data.

## First use

A fresh clone contains no personal backups or recovery points. Choose your own WoW installation and source character, then create a backup. Standard macOS installation locations are listed; installations elsewhere can be selected by entering the full client path. No character or beta client is preselected.

## Updating the backup tomorrow or on the last beta day

1. Configure the template character as desired.
2. **Quit WoW completely.** A `/reload` alone is insufficient for this workflow.
3. Double-click **WoW-Addon-Backup.command**.
4. Select **1 → 1.1 – Backup Addons**.
5. Select the beta installation and template character. Select the installation by number or enter its full path, then choose your character by name or number.
6. The tool checks automatically whether WoW is running. If needed, quit WoW during the 30-second wait; the countdown is displayed every five seconds. If WoW remains open, the action is cancelled. Wait for **Verification successful: all archived files passed their checksum checks.**

Every run creates a new ZIP snapshot of the selected backup type in `Backups/<Realm>/<Character>/Addons/` or `Backups/<Realm>/<Character>/Macros/`. Realm and character folder names use underscores instead of spaces or other separators and preserve Unicode letters, for example `Backups/Classic_Beta_PvP_2/Cannot_Hotalot/Addons/`. Filenames include the timestamp, full character name, and realm, for example `20261014-161319-002099_Cannot-Hotalot_Classic-Beta-PvP-2_addons.zip`. Spaces and filename-unsafe characters are replaced with hyphens; Unicode letters are preserved. Existing backups keep their original names and remain supported. `latest.json` points to the newest successful backup. Earlier snapshots are not overwritten. Settings changes and newly installed addon files are read again during each backup. If a new configuration has no reviewed import adapter, the tool reports it during backup; review the message; during restoration you can skip the listed addons and continue with supported settings.

You can then copy the entire tool directory to another drive. Restoration no longer requires the original beta installation.

## On release day

For automatic initialization of **subsequent new characters**, see
[Automatic setup for new characters](README.md#automatic-setup-for-new-characters).
Menu **4** configures the account template, displays progress, or disables it.
Prepare fresh helper 1.3 captures before the beta ends. The following manual
workflow also covers settings that cannot be applied by the in-game helper.

1. Install the **release client** and updated release versions of your addons if available. The tool keeps existing addon versions by default.
2. Create the new character, log in once, and quit WoW completely. This creates the account, realm, and character directories.
3. Launch **WoW-Addon-Backup.command** and select **2 → 2.1 – Restore Addons**.
4. Select the source realm, then the source character, then an addon backup. Matching backups are listed newest first; older combined backups are also available.
5. Choose the **release installation directory**. You can enter its full path; it must contain `WTF` and the client.
6. Select the new character by name or number. The tool checks whether WoW has closed and waits up to 30 seconds if necessary.
7. If the character identity is unknown, confirm preparation of the small local **WoW UI Transfer Identity** helper. This only installs/enables character detection; it does not install addons from the backup.
8. If detection was needed, it requests **one additional login with this character**. Quit WoW completely afterward and press Enter in the tool. The helper records the actual name, realm, GUID, and class locally. If needed, enable **WoW UI Transfer Identity** in the **AddOns** menu and enable **Load out of date AddOns**.
9. Review the destination and complete plan, then answer `y` to confirm (`Enter` or `n` cancels). Missing addon packages and settings are written together, with one recovery point. For an already recognized character, no files are changed before this confirmation.
10. After the files have been written and verified, start WoW and check the layout. Character detection is now disabled for this character.

The extra login provides reliable identity detection. A numeric realm directory such as `70` is not enough to infer the release realm or new GUID. You do not need to find or enter these values yourself.

## What is restored

- Addon packages missing from the destination. Existing release versions are kept by default.
- Which addons are enabled or disabled for the destination character. Extra destination addons absent from the backup are disabled for this character.
- Account-wide and character-specific addon settings through reviewed adapters: profiles, colors, fonts, positions, sizes, scaling, and anchors.
- EllesmereUI's complete visual profiles, active profile, UI scale, colors, fonts, and layout links.
- WoW Edit Mode layouts, saved window positions, and chat window geometry.
- Key bindings and selected UI/display variables, including UI scale, brightness, contrast, nameplate settings, and damage display settings.
- Known character name formats, realm references, and exact references to your character's GUID, mapped to the identity detected by the release client.

**Account-wide settings also affect other characters on the destination account.** The tool backs up affected destination files first. AceDB-style profiles are copied into a private destination profile, preserving other character profiles and progress. Genuinely account-wide settings still have a shared scope on an established account.

## Character data and classes

Quest progress, bag/equipment data, gold, guide progress, and other known ongoing character data are not copied from the beta character during import. They remain in the full raw backup but are omitted from the settings import or replaced with existing destination data.

Action bar spells and other server-side character data are not created by this process. Macro files are included in separate macro backups and older combined backups and can be restored separately using Restore → Restore Macros. For a different class, spells, macro-related bindings, and click-casting may require adjustments in the game. The GUI layout is transferred. EllesmereUI uses the saved active layout; automatic beta specialization switching is reset during import.

## Release compatibility limits

The tool backs up and restores files, settings, and their mapping to a new character. Compatibility of today's beta addons with release-day game APIs cannot be guaranteed. Existing release versions are therefore preserved, and version differences are reported. Major changes to an addon's settings format may require an updated import adapter.

The workflow was tested with a simulated empty release installation, new account, different realm, new GUID, and different class. The future release client itself has not been tested.

## Undoing changes

Select **3 → 3.1 – Restore Recovery Point**. Select the destination realm, character, and recovery point. At each selection, `0` or Enter returns one level without changes; from the realm list it returns to the main menu. Addon preparation and settings restoration are separate operations. Undo multiple operations in reverse order: settings first, then preparation if needed.

New recovery data is stored in `Recovery/<Realm>/<Character>/<Timestamp>/`, with underscores instead of spaces in folder names. The realm and character refer to the destination of the operation, including account-wide macro restores. Older `Ruecksicherungen` directories and their `vorher.zip` archives remain readable; new archives use `before.zip`. Known German operation labels from older records are displayed in English without modifying those records or character names. The tool detects later edits to affected files and stops to avoid overwriting newer settings. Each undo operation creates its own recovery record.

## Verifying a backup

Select **1 → 1.4 – Verify Backup**, then choose a realm, character, and backup to check the stored checksums of every archived file. Corrupted backups are rejected before restoration.

## Command-line usage

`wow_backup.py` also provides `backup`, `verify`, `prepare`, `restore`, and `undo` commands. Without `--apply`, `prepare` and `restore` only show a preview. CLI operations that write files require `--closed` and also check the WoW process automatically; the flag does not bypass that check. Use `--skip-unknown` with `restore` to leave unsupported addons unchanged. For `prepare`, the explicit `--replace-addons` option replaces existing addon versions with the archived files. The normal menu keeps existing versions.

## Transferring macros between characters

1. Log in with the source character so its macros are saved locally, then quit WoW completely.
2. Use **1 → 1.2 – Backup Macros** and select that source character. This saves only the character and account macro files. Older combined snapshots can also be used if they contain those files.
3. Log in once with the destination character, then quit WoW completely.
4. Select **2 → 2.2 – Restore Macros**, choose the source realm, source character, and macro backup, then the destination installation and destination character.
5. Choose `character` (default), `account`, or `both`. Account macros are shared by every character on that account.
6. Review the destination paths and macro counts. The tool automatically waits for WoW to close. At **Are you sure you want to replace the selected macro files? [Y/n]:**, press Enter or type `y` or `yes` to apply; `n` cancels.

This replaces the complete macro file in each selected scope; it does not merge lists. Missing source files leave the corresponding destination unchanged. Existing destination files are backed up and can be restored through **3 → 3.1 – Restore Recovery Point**. The normal addon/UI restore leaves macros unchanged.

Macro names, icons and identifiers are preserved. For a different destination class, named spells in /cast, /spell, /castrandom and /castsequence become null. Same-class bodies are unchanged. Conditions remain intact; /use, tooltips, scripts, numeric operands and explicit character names are not rewritten. Manual import requires a recorded destination class. New interactive macro backups also capture standard macro action slots through the identity helper. An existing compatible snapshot from the last logout is reused without another login. The tool ensures the helper is installed and enabled; only missing or incompatible capture data requires logging in and quitting WoW once. Restore asks whether to queue those slots for the next login (default no); accepting replaces actions in those slots only. The helper matches scope, name and body instead of assuming macro IDs are unchanged. Use /wuibars outside combat with an empty cursor to retry missing or blocked placements. Old backups have no placement data. Recovery cannot undo action slots already applied in the game. Offline file copying and undo are tested; live client/server macro synchronization and future release compatibility still need an in-game check after login.

CLI preview (add `--apply --closed` to write):

```sh
python3 -B wow_backup.py restore-macros --backup /path/to/snapshot.zip --client /path/to/client --character /path/to/client/WTF/Account/ACCOUNT/REALM/CHARACTER --macro-scope character
```

## Backup and Restore menus

The main menu offers **1 – Backup**, **2 – Restore**, **3 – Recovery**, and **0 – Exit**.

- Backup: **1.1 – Backup Addons**, **1.2 – Backup Macros**, **1.3 – Backup Click Casting**, **1.4 – Verify Backup**, **1.5 – Delete Backup**.
- Restore: **2.1 – Restore Addons**, **2.2 – Restore Macros**, **2.3 – Restore Click Casting**.
- Recovery: **3.1 – Restore Recovery Point**, **3.2 – Delete Recovery Point**.

Within a submenu, enter the last number (for example `2`) or the displayed number (`1.2`). Enter or `0` returns without changes. After an action, the main menu appears again.

Addon backups contain addon packages and locally saved WTF/UI settings, excluding macro cache files. Macro backups contain `macros-cache.txt` from the selected character and its account, plus the helper's captured macro-slot data when available. Both include a manifest and checksums and are automatically verified. The filename ends with `_addons.zip` or `_macros.zip`. The optional combined CLI backup is stored in `Backups/<Realm>/<Character>/Combined/`. Older ZIPs directly inside `Backups` remain supported; they do not need to be moved. Interactive restoration lists compatible backups by realm and character, newest first, and rejects the wrong backup type before writing files. CLI restoration without `--backup` uses the newest compatible snapshot. Older combined snapshots remain compatible with both restoration options. To preserve both addons and macros, create both backup types.

For CLI backup creation, use `backup --backup-kind addons` or `backup --backup-kind macros` together with `--client`, `--character`, and `--closed`. The CLI defaults to addons; `--backup-kind combined` remains available for compatibility.

## Deleting backups and recovery points

Select **1 → 1.5 – Delete Backup** to list ZIP snapshots throughout the tool's `Backups` directory, including all realm, character, and type subdirectories. Choose a realm, character, and backup; the final confirmation shows its full path. Select a number, review the full path, and press Enter or type `y` or `yes` at **Permanently delete this item? [Y/n]:**. `n` cancels. Deletion is permanent. Deleting the current snapshot updates `latest.json` to the newest remaining backup, or removes the pointer if none remain. Recovery points are kept, so previous restores can still be undone.

Select **3 → 3.2 – Delete Recovery Point** to choose a realm, character, and point from `Recovery` or the older recovery directory. Confirmation deletes that point's entire directory, including its manifest and rollback archive. It removes the ability to undo that operation; it does not undo the operation or change the current WoW installation. Other recovery points and backups are kept.

All realm, character, and file selection lists support `0` or Enter to go back one level without changes. These deletion actions operate only on entries in the tool's own storage directories. They do not accept arbitrary external paths.

## Browsing stored data

Verification, addon restoration, macro restoration, and backup deletion use **Realm → Character → Backup**. Addon and macro restoration filter by backup type; verification and deletion show both types. Recovery restoration and deletion use **Realm → Character → Recovery Point**. Each file list is ordered newest first.

The browser uses saved identity metadata, so older flat backups and recovery points remain accessible without moving them. For older recovery records, the destination can often be inferred from affected character files and the local character identity. If no reliable identity exists, records appear under **Unknown Realm / Unassigned**. If only a numeric realm directory is known during preparation, **Realm folder <number>** identifies it explicitly. The tool does not guess a release realm before character detection has recorded it.

New recovery points store the destination identity alongside their rollback files. Restoring a point creates a new point under the same destination identity. Deleting a point removes only that timestamp directory, not the character's entire recovery history. External backup paths remain available through the CLI `--backup` option.

## Automatic WoW process check

Interactive backup creation, addon/macro restoration, and recovery-point restoration check the WoW process automatically. If WoW is already closed, the action continues immediately. Otherwise, quit the game while the tool waits up to 30 seconds. It checks every second and prints `30`, `25`, `20`, `15`, `10`, `5`, and `0` seconds remaining as needed. It continues as soon as WoW closes; a timeout or unavailable process check cancels the current action and returns to the main menu. The tool never force-quits WoW. The same check runs after a character-detection login. CLI write operations use the same process checks and retain the explicit `--closed` flag for compatibility.

## Built-in WoW Click Casting

Use **1 → 1.3 – Backup Click Casting** to save the selected character's
`click-bindings-cache.txt` in `Backups/<Realm>/<Character>/Click_Casting/`.
The file must already have been saved by WoW: configure the source character and
quit the game before backing up. No extra login is required when settings and
character identity are already available.

Use **2 → 2.3 – Restore Click Casting**, browse realm → character → backup,
select the destination character, and confirm with `y`. This replaces only that
character's complete built-in Click Casting settings and creates a recovery point.
It does not change addon click-casting settings, macros, keyboard bindings or
action bar placement. Spell/macro references are copied unchanged: restore the
matching macros first and check that references resolve to the intended macros
on the destination character. Macro names/bodies are not remapped by this operation.
Check the bindings after login, especially when changing classes.

CLI preview: `restore-click-casting --client ... --character ... --backup ...`.
Add `--apply --closed` to write. CLI backup: `backup --backup-kind click-casting
--client ... --character ... --closed`. Archives are checksum-verified like the
other backup types. Future client/server synchronization still needs in-game validation.
