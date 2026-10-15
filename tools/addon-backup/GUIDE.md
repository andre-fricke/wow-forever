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
6. Press Enter (or type `y`) at **Have you quit WoW completely? [Y/n]:** to confirm that WoW has closed; `n` cancels. Wait for **Verification successful: all archived files passed their checksum checks.**

Every run creates a new ZIP snapshot of the selected backup type in `Backups`. Filenames include the timestamp, full character name, and realm, for example `20261014-161319-002099_Cannot-Hotalot_Classic-Beta-PvP-2_addons.zip`. Spaces and filename-unsafe characters are replaced with hyphens; Unicode letters are preserved. Existing backups keep their original names and remain supported. `latest.json` points to the newest successful backup. Earlier snapshots are not overwritten. Settings changes and newly installed addon files are read again during each backup. If a new configuration has no reviewed import adapter, the tool reports it during backup; have that message reviewed before release.

You can then copy the entire tool directory to another drive. Restoration no longer requires the original beta installation.

## On release day

1. Install the **release client** and updated release versions of your addons if available. The tool keeps existing addon versions by default.
2. Create the new character, log in once, and quit WoW completely. This creates the account, realm, and character directories.
3. Launch **WoW-Addon-Backup.command** and select **2 → 2.1 – Restore Addons**.
4. Press Enter to use the latest backup, or select another ZIP snapshot.
5. Choose the **release installation directory**. You can enter its full path; it must contain `WTF` and the client.
6. Select the new character by name or number and confirm that WoW has closed.
7. The tool installs missing addon files, applies addon activation for this character, and installs the small local **WoW UI Transfer Identity** helper.
8. On the first run, it requests **one additional login with this character**. Quit WoW completely afterward and press Enter in the tool. The helper records the actual name, realm, GUID, and class locally. If needed, enable **WoW UI Transfer Identity** in the **AddOns** menu and enable **Load out of date AddOns**.
9. Review the destination and planned changes, then type `RESTORE`.
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

**Account-wide settings also affect other characters on the destination account.** The tool backs up affected destination files first. Full migration is intended for a fresh release account; consider this shared scope when using an established account.

## Character data and classes

Quest progress, bag/equipment data, gold, guide progress, and other known ongoing character data are not copied from the beta character during import. They remain in the full raw backup but are omitted from the settings import or replaced with existing destination data.

Action bar spells and other server-side character data are not created by this process. Macro files are included in separate macro backups and older combined backups and can be restored separately using Restore → Restore Macros. For a different class, spells, macro-related bindings, and click-casting may require adjustments in the game. The GUI layout is transferred. EllesmereUI uses the saved active layout; automatic beta specialization switching is reset during import.

## Release compatibility limits

The tool backs up and restores files, settings, and their mapping to a new character. Compatibility of today's beta addons with release-day game APIs cannot be guaranteed. Existing release versions are therefore preserved, and version differences are reported. Major changes to an addon's settings format may require an updated import adapter.

The workflow was tested with a simulated empty release installation, new account, different realm, new GUID, and different class. The future release client itself has not been tested.

## Undoing changes

Select **3 → 3.1 – Restore Recovery Point**. At the recovery selection, choose **0 – Back to main menu** or press Enter without a number to return without changing anything. Addon preparation and settings restoration are separate operations. Undo multiple operations in reverse order: settings first, then preparation if needed.

Recovery data is stored in `Recovery`. Older `Ruecksicherungen` directories and their `vorher.zip` archives remain readable; new archives use `before.zip`. Known German operation labels from older records are displayed in English without modifying those records or character names. The tool detects later edits to affected files and stops to avoid overwriting newer settings. Each undo operation creates its own recovery record.

## Verifying a backup

Select **1 → 1.3 – Verify Backup** to check the stored checksums of every archived file. Corrupted backups are rejected before restoration.

## Command-line usage

`wow_backup.py` also provides `backup`, `verify`, `prepare`, `restore`, and `undo` commands. Without `--apply`, `prepare` and `restore` only show a preview. CLI operations that write files require `--closed`, confirming that WoW has been fully closed. For `prepare`, the explicit `--replace-addons` option replaces existing addon versions with the archived files. The normal menu keeps existing versions.

## Transferring macros between characters

1. Log in with the source character so its macros are saved locally, then quit WoW completely.
2. Use **1 → 1.2 – Backup Macros** and select that source character. This saves only the character and account macro files. Older combined snapshots can also be used if they contain those files.
3. Log in once with the destination character, then quit WoW completely.
4. Select **2 → 2.2 – Restore Macros**, choose the snapshot, destination installation, and destination character.
5. Choose `character` (default), `account`, or `both`. Account macros are shared by every character on that account.
6. Review the destination paths and macro counts. Press Enter (or type `y`) to confirm WoW is closed, then type `RESTORE` to apply.

This replaces the complete macro file in each selected scope; it does not merge lists. Missing source files leave the corresponding destination unchanged. Existing destination files are backed up and can be restored through **3 → 3.1 – Restore Recovery Point**. The normal addon/UI restore leaves macros unchanged.

Macro names, icons, identifiers, and bodies are preserved exactly. Explicit character names, spell names, and class-specific commands are not rewritten automatically: check them in the game. Action bar placement is not restored by the macro transfer. Offline file copying and undo are tested; live client/server macro synchronization and future release compatibility still need an in-game check after login.

CLI preview (add `--apply --closed` to write):

```sh
python3 -B wow_backup.py restore-macros --backup /path/to/snapshot.zip --client /path/to/client --character /path/to/client/WTF/Account/ACCOUNT/REALM/CHARACTER --macro-scope character
```

## Backup and Restore menus

The main menu offers **1 – Backup**, **2 – Restore**, **3 – Recovery**, and **0 – Exit**.

- Backup: **1.1 – Backup Addons**, **1.2 – Backup Macros**, **1.3 – Verify Backup**, **1.4 – Delete Backup**.
- Restore: **2.1 – Restore Addons**, **2.2 – Restore Macros**.
- Recovery: **3.1 – Restore Recovery Point**, **3.2 – Delete Recovery Point**.

Within a submenu, enter the last number (for example `2`) or the displayed number (`1.2`). Enter or `0` returns without changes. After an action, the main menu appears again.

Addon backups contain addon packages and locally saved WTF/UI settings, excluding macro cache files. Macro backups contain only `macros-cache.txt` from the selected character and its account. Both include a manifest and checksums and are automatically verified. The filename ends with `_addons.zip` or `_macros.zip`. Restoration defaults to the newest compatible snapshot, and rejects the wrong backup type before writing files. Older combined snapshots remain compatible with both restoration options. To preserve both addons and macros, create both backup types.

For CLI backup creation, use `backup --backup-kind addons` or `backup --backup-kind macros` together with `--client`, `--character`, and `--closed`. The CLI defaults to addons; `--backup-kind combined` remains available for compatibility.

## Deleting backups and recovery points

Select **1 → 1.4 – Delete Backup** to list ZIP snapshots in the tool's `Backups` directory. Select a number, review the full path, and type `y` or `yes` at **Permanently delete this item? [y/N]:**. Enter or `n` cancels. Deletion is permanent. Deleting the current snapshot updates `latest.json` to the newest remaining backup, or removes the pointer if none remain. Recovery points are kept, so previous restores can still be undone.

Select **3 → 3.2 – Delete Recovery Point** to choose a point from `Recovery` or the older recovery directory. Confirmation deletes that point's entire directory, including its manifest and rollback archive. It removes the ability to undo that operation; it does not undo the operation or change the current WoW installation. Other recovery points and backups are kept.

Both selection lists support `0` or Enter to return without changes. These deletion actions operate only on entries in the tool's own storage directories. They do not accept arbitrary external paths.
