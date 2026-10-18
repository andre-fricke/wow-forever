#!/usr/bin/python3
"""Versioned, offline WoW UI snapshots and character-aware release restores.
No network dependencies. Lua SavedVariables are parsed as data, never executed.
"""
import argparse
import json
from pathlib import Path
import re
import sys
import zipfile
import archives
import recovery
import runtime
from runtime import wow_is_running

# Re-export the core API for existing scripts; implementations live in focused modules.
from restore import (
    helper_plan,
    require_backup_kind,
    install_plan,
    activation_data,
    restore_plan,
    macro_plan,
    show_macro_notes,
)
from file_ops import (
    sha,
    file_sha,
    stamp,
    backup_name_part,
    backup_folder_part,
    json_write,
    valid_relative,
    rooted,
    Archived,
    payload_hash,
    atomic_payload,
)
from archives import verify_backup
from recovery import recovery_context
from legacy import english_legacy_text
from addon_support import (
    active_saved_files,
    audit_support,
    pending_reviews,
    skip_unknown_addons,
)
from models import StoragePaths, CharacterIdentity, BackupManifest, FilePlan
from saved_variables import Atom, quote, decode, encode, scalar, parse, dump, plain
from characters import HELPER, characters, identity, inventory
from addon_adapters import (
    REVIEWED,
    CHAR_CONFIG,
    CHAR_SPECIAL,
    CHAR_BLIZZARD_RUNTIME,
    identity_map,
    remap,
    account_config,
    character_config,
    merge_cvars,
    merge_chat,
)

HERE = Path(__file__).resolve().parent
INSTALL_ROOTS = (
    Path("/Applications/World of Warcraft"),
    Path.home() / "Applications/World of Warcraft",
)
SNAPSHOTS = HERE / "Backups"
RECOVERY = HERE / "Recovery"
# Read earlier recovery folders without changing their contents.
LEGACY_RECOVERY = HERE / "Ruecksicherungen"


def storage_paths():
    return StoragePaths(HERE, SNAPSHOTS, RECOVERY, LEGACY_RECOVERY)


def backup_directory(info, kind):
    return archives.backup_directory(info, kind, paths=storage_paths())


def create_backup(client, char, kind="combined"):
    return archives.create_backup(client, char, kind, paths=storage_paths())


def latest_backup(kind=None):
    return archives.latest_backup(kind, paths=storage_paths())


def backup_entries():
    return archives.backup_entries(paths=storage_paths())


def delete_backup(path):
    return archives.delete_backup(path, paths=storage_paths())


def delete_recovery_point(path):
    return recovery.delete_recovery_point(path, paths=storage_paths())


def recovery_entries():
    return recovery.recovery_entries(paths=storage_paths())


def apply_plan(client, plan, label, character=None, context=None):
    return recovery.apply_plan(
        client,
        plan,
        label,
        character,
        context,
        paths=storage_paths(),
        writer=atomic_payload,
    )


def undo(path):
    return recovery.undo(path, paths=storage_paths(), writer=atomic_payload)


def select_supported_addons(manifest):
    reviews = pending_reviews(manifest)
    if not reviews:
        return manifest
    skipped = set()
    print("Unknown addon configurations:")
    for item in reviews:
        print("  - " + item)
        match = re.fullmatch(r"(?:Account|Character) file: ([^/\\]+)\.lua", item)
        if not match:
            raise ValueError("Cannot safely skip this review item: " + item)
        skipped.add(match.group(1))
    print(
        "Skipped addons will not be installed or restored. Their existing settings and enabled state are kept."
    )
    print("1  Skip listed addons and continue\n0  Back")
    while True:
        answer = input("Selection [Enter: back]: ").strip()
        if answer in ("", "0"):
            return None
        if answer == "1":
            break
        print("Choose 1 or 0.")
    return skip_unknown_addons(manifest)


def build_addon_restore(archive, manifest, client, char):
    """Plan installation and settings together, without touching the destination."""
    settings, notes, target = restore_plan(
        archive, manifest, client, char, allow_missing=True
    )
    files = install_plan(archive, manifest, client, character=char)
    files.update(settings)
    # Even when the final flags already match the destination, preparation
    # must not leave character detection enabled.
    with zipfile.ZipFile(archive) as z:
        flags = char / "AddOns.txt"
        files[flags.relative_to(client).as_posix()] = activation_data(
            z,
            manifest,
            set(inventory(client / "Interface/AddOns")) | set(manifest["addons"]),
            target_data=flags.read_bytes() if flags.exists() else None,
        )
    return FilePlan.capture(client, files, rooted, file_sha), notes, target


def execute_plan(client, plan, label, character=None):
    """Shared last-minute process and preview checks for both interfaces."""
    wait_for_wow_closed()
    plan.check_destination(client, rooted, file_sha)
    return apply_plan(client, plan.files, label, character=character)


def deletion_menu(recovery=False):
    selected = choose_recovery() if recovery else choose_snapshot()
    if selected is None:
        return
    print("Selected: " + str(selected))
    print(
        "Deleting this recovery point permanently removes its undo data."
        if recovery
        else "Deleting this backup permanently removes this snapshot. Recovery points are kept."
    )
    if input("Permanently delete this item? [y/N]: ").strip().lower() not in (
        "y",
        "yes",
    ):
        print("Cancelled; nothing deleted.")
        return
    if recovery:
        delete_recovery_point(selected)
    else:
        delete_backup(selected)


def choose_client(release=False):
    candidates = sorted(
        {
            p.resolve()
            for root in INSTALL_ROOTS
            if root.is_dir()
            for p in root.iterdir()
            if p.is_dir() and (p / "WTF").is_dir()
        }
    )
    print(
        "\nSelect a WoW installation"
        + (" – choose the RELEASE client:" if release else ":")
    )
    for i, p in enumerate(candidates, 1):
        print(f"{i}: {p}" + (" [Beta]" if "beta" in p.name.lower() else ""))
    print(
        "Or enter the full path to the client directory (containing WTF and Interface)."
    )
    answer = input("Selection: ").strip()
    if not answer:
        raise ValueError("No installation selected.")
    if answer.isdigit() and 1 <= int(answer) <= len(candidates):
        client = candidates[int(answer) - 1]
    else:
        client = Path(answer.strip("\"'")).expanduser()
    if not (client / "WTF").is_dir():
        raise ValueError(
            "Client WTF directory not found. Log in once using this client, then quit WoW."
        )
    return client.resolve()


def choose_character(client):
    choices = characters(client)
    if not choices:
        raise ValueError(
            "No character directory found. Log in with the character once, then quit WoW completely."
        )
    print("\nTarget / template character:")
    for i, p in enumerate(choices, 1):
        print(
            f'{i}: {p.name.replace("-"," ",1)} | Directory/Realm: {p.parent.name} | Account: {p.parent.parent.name}'
        )
    answer = input("Character name or number: ").strip()
    if answer.isdigit() and 1 <= int(answer) <= len(choices):
        return choices[int(answer) - 1]
    matches = [
        p
        for p in choices
        if answer.casefold()
        in [p.name.casefold(), p.name.replace("-", " ", 1).casefold()]
    ]
    if len(matches) == 1:
        return matches[0]
    raise ValueError(
        "Character name was not found or is ambiguous. Select its number instead."
    )


def wait_for_wow_closed():
    return runtime.wait_for_wow_closed(is_running=wow_is_running)


def select_number(title, labels):
    while True:
        print("\n" + title)
        for index, label in enumerate(labels, 1):
            print(f"{index}: {label}")
        print("0: Back")
        answer = input("Selection [Enter: back]: ").strip()
        if answer in ("", "0"):
            return None
        if answer.isdecimal() and 1 <= int(answer) <= len(labels):
            return int(answer) - 1
        print("Invalid selection. Choose a listed number.")


def browse_records(records, item_name):
    if not records:
        print(f"No {item_name.lower()}s found.")
        return None
    realms = sorted({r["realm"] for r in records}, key=str.casefold)
    while True:
        selected = select_number("Select realm", realms)
        if selected is None:
            return None
        realm = realms[selected]
        characters = sorted(
            {r["character"] for r in records if r["realm"] == realm}, key=str.casefold
        )
        while True:
            selected = select_number("Select character – " + realm, characters)
            if selected is None:
                break
            character = characters[selected]
            choices = [
                r
                for r in records
                if r["realm"] == realm and r["character"] == character
            ]
            selected = select_number(
                f"Select {item_name.lower()} – {realm} / {character} (newest first)",
                [r["label"] for r in choices],
            )
            if selected is not None:
                return choices[selected]["path"]


def backup_records(kind=None):
    records = []
    for path in backup_entries():
        try:
            with zipfile.ZipFile(path) as z:
                manifest = json.loads(z.read("manifest.json"))
            stored = manifest.get("kind", "combined")
            if kind and stored not in (kind, "combined"):
                continue
            info = manifest["source_identity"]
            realm = info["realm"]
            character = info["full"]
            if not isinstance(realm, str) or not isinstance(character, str):
                raise ValueError("Invalid identity")
            label = f"{path.name} [{stored}]"
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            AttributeError,
            zipfile.BadZipFile,
        ):
            if kind:
                continue
            realm = "Unknown Realm"
            character = "Unreadable backups"
            label = path.name + " [unreadable metadata]"
        records.append(
            {"path": path, "realm": realm, "character": character, "label": label}
        )
    return records


def recovery_records():
    records = []
    for path in recovery_entries():
        try:
            log = json.loads((path / "manifest.json").read_text())
            target = log.get("target") or recovery_context(
                log["client"], (e["path"] for e in log["files"])
            )
            realm = target["realm"]
            character = target["character"]
            if not isinstance(realm, str) or not isinstance(character, str):
                raise ValueError("Invalid identity")
            label = (
                f'{path.name} – {english_legacy_text(log["label"])} [{log["status"]}]'
            )
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            realm = "Unknown Realm"
            character = "Unassigned"
            label = path.name + " [unreadable metadata]"
        records.append(
            {"path": path, "realm": realm, "character": character, "label": label}
        )
    return records


def choose_snapshot(kind=None):
    return browse_records(backup_records(kind), "Backup")


def choose_recovery():
    return browse_records(recovery_records(), "Recovery point")


def menu():
    while True:
        try:
            if menu_action() is False:
                return
        except EOFError:
            print("\nExiting.")
            return
        except KeyboardInterrupt:
            print("\nAction cancelled. Returning to the main menu.")
        except (ValueError, OSError, KeyError, IndexError, zipfile.BadZipFile) as error:
            print("\nCancelled: " + str(error), file=sys.stderr)
        print()


def menu_action():
    print("WoW – Addon Backup for Beta → Release\n")
    print("1  Backup\n2  Restore\n3  Recovery\n0  Exit")
    action = input("Selection: ").strip()
    if action == "0":
        return False
    if action in ("1", "2", "3"):
        parent = action
        print(
            {
                "1": "1.1  Backup Addons\n1.2  Backup Macros\n1.3  Verify Backup\n1.4  Delete Backup",
                "2": "2.1  Restore Addons\n2.2  Restore Macros",
                "3": "3.1  Restore Recovery Point\n3.2  Delete Recovery Point",
            }[parent]
        )
        print("0  Back to main menu")
        selected = input("Selection [Enter: back]: ").strip()
        if selected in ("", "0"):
            return
        action = selected if "." in selected else parent + "." + selected
        if not action.startswith(parent + "."):
            raise ValueError("Unknown selection")
    if action in ("1.1", "1.2"):
        client = choose_client()
        char = choose_character(client)
        wait_for_wow_closed()
        if not identity(char):
            apply_plan(
                client,
                helper_plan(client, character=char),
                "Prepare character detection for backup",
                character=char,
            )
            print(
                'Start WoW, log in with the template character, then quit completely. If needed, enable "WoW UI Transfer Identity" in the AddOns menu (and Load out of date AddOns).'
            )
            input("Press Enter when finished …")
            wait_for_wow_closed()
        create_backup(client, char, kind="addons" if action == "1.1" else "macros")
    elif action == "2.1":
        archive = choose_snapshot("addons")
        if archive is None:
            return
        print("Verifying backup …", flush=True)
        manifest = verify_backup(archive)
        require_backup_kind(manifest, "addons")
        manifest = select_supported_addons(manifest)
        if manifest is None:
            return
        client = choose_client(release=True)
        char = choose_character(client)
        wait_for_wow_closed()
        if not identity(char):
            print(
                "Character detection needs one login. This preparation only installs/enables the identity helper."
            )
            if input(
                "Prepare character detection now? [y/N]: "
            ).strip().lower() not in ("y", "yes"):
                return
            preparation = FilePlan.capture(
                client, helper_plan(client, character=char), rooted, file_sha
            )
            execute_plan(
                client, preparation, "Prepare character detection", character=char
            )
            print(
                "Start WoW, log in with "
                + char.name.replace("-", " ", 1)
                + ", then quit WoW completely."
            )
            input("Press Enter when finished …")
            wait_for_wow_closed()
        if not identity(char):
            raise ValueError(
                "Character identity has not been saved. Enable the identity addon, log in, and quit WoW."
            )
        plan, notes, target = build_addon_restore(archive, manifest, client, char)
        print(
            f'\nBackup: {manifest["created"]}\nTemplate: {manifest["source_identity"]["full"]}\nTarget: {target["full"]} – {target["realm"]}\nInstallation: {client}\n{len(plan.files)} files in the restore plan.'
        )
        print(
            "Existing addon versions are kept. Shared account settings and key bindings also affect other characters."
        )
        for note in notes:
            print(note)
        if input(
            "Are you sure you want to restore the selected addon settings? [y/N]: "
        ).strip().lower() not in ("y", "yes"):
            print("Cancelled; no addon files or settings restored.")
            return
        execute_plan(
            client,
            plan,
            "Restore UI backup to " + target["full"] + " – " + target["realm"],
            character=char,
        )
        print(
            "Done. Start WoW and check the layout. Character detection is now disabled for this character."
        )
    elif action == "2.2":
        archive = choose_snapshot("macros")
        if archive is None:
            return
        print("Verifying backup …", flush=True)
        manifest = verify_backup(archive)
        require_backup_kind(manifest, "macros")
        print("Source character: " + manifest["source_identity"]["full"])
        client = choose_client()
        char = choose_character(client)
        scope = (
            input("Macro scope: character / account / both [Enter: character]: ")
            .strip()
            .lower()
            or "character"
        )
        wait_for_wow_closed()
        plan, notes = macro_plan(archive, manifest, client, char, scope)
        preview = FilePlan.capture(client, plan, rooted, file_sha)
        print("Destination: " + str(char))
        if scope in ("account", "both"):
            print(
                "Account macros are shared by ALL characters on the destination account."
            )
        show_macro_notes(notes)
        if not plan:
            print("No changes required.")
            return
        if input(
            "Are you sure you want to replace the selected macro files? [y/N]: "
        ).strip().lower() not in ("y", "yes"):
            print("Cancelled; no macros restored.")
            return
        execute_plan(
            client,
            preview,
            "Restore macros to " + char.name + " (" + scope + ")",
            character=char,
        )
    elif action == "3.1":
        selected = choose_recovery()
        if selected is None:
            return
        wait_for_wow_closed()
        undo(selected)
    elif action == "1.4":
        deletion_menu()
    elif action == "3.2":
        deletion_menu(recovery=True)
    elif action == "1.3":
        archive = choose_snapshot()
        if archive is None:
            return
        manifest = verify_backup(archive)
        print(
            f'Backup is valid: {len(manifest["files"])} files, {len(manifest["addons"])} addon directories, created {manifest["created"]}.'
        )
        if pending_reviews(manifest):
            print("Needs review: " + ", ".join(pending_reviews(manifest)))
    else:
        raise ValueError("Unknown selection")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "action",
        nargs="?",
        choices=[
            "menu",
            "backup",
            "verify",
            "prepare",
            "restore",
            "restore-macros",
            "undo",
        ],
        default="menu",
    )
    ap.add_argument("--client", type=Path)
    ap.add_argument("--character", type=Path)
    ap.add_argument("--backup", type=Path)
    ap.add_argument("--recovery", type=Path)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--closed", action="store_true")
    ap.add_argument(
        "--skip-unknown",
        action="store_true",
        help="Skip unknown addon files, settings and activation states",
    )
    ap.add_argument(
        "--replace-addons",
        action="store_true",
        help="Also replace existing addon versions with versions from the backup",
    )
    ap.add_argument(
        "--macro-scope",
        choices=["character", "account", "both"],
        default="character",
        help="Macro files to replace with restore-macros (default: character)",
    )
    ap.add_argument(
        "--backup-kind",
        choices=["addons", "macros", "combined"],
        default="addons",
        help="Contents for backup (default: addons)",
    )
    args = ap.parse_args()
    if args.action == "menu":
        return menu()
    if args.action == "backup":
        if not args.closed:
            raise ValueError("Quit WoW before backing up and specify --closed.")
        if not args.client or not args.character:
            raise ValueError("--client and --character are required")
        wait_for_wow_closed()
        return create_backup(args.client, args.character, kind=args.backup_kind)
    if args.action == "undo":
        if not args.closed or not args.recovery:
            raise ValueError("--closed and --recovery are required")
        wait_for_wow_closed()
        return undo(args.recovery)
    archive = args.backup or latest_backup(
        "macros"
        if args.action == "restore-macros"
        else "addons" if args.action in ("prepare", "restore") else None
    )
    manifest = verify_backup(archive)
    if args.action == "verify":
        print(f'Backup is valid: {len(manifest["files"])} files.')
        return
    if args.skip_unknown:
        manifest = skip_unknown_addons(manifest)
    if not args.client:
        raise ValueError("--client is required")
    if args.apply:
        if not args.closed:
            raise ValueError("Quit WoW before applying changes and specify --closed.")
        wait_for_wow_closed()
    client = args.client.resolve()
    if args.action == "restore-macros":
        if not args.character:
            raise ValueError("--character is required")
        plan, notes = macro_plan(
            archive, manifest, client, args.character, args.macro_scope
        )
        if args.macro_scope in ("account", "both"):
            print(
                "Account macros are shared by ALL characters on the destination account."
            )
        show_macro_notes(notes)
    elif args.action == "prepare":
        if not args.character:
            raise ValueError("--character is required")
        char = args.character.resolve()
        if char not in [p.resolve() for p in characters(client)]:
            raise ValueError("Character does not belong to the destination client")
        plan = install_plan(
            archive, manifest, client, args.replace_addons, character=char
        )
    else:
        if not args.character:
            raise ValueError("--character is required")
        char = args.character.resolve()
        if char not in [p.resolve() for p in characters(client)]:
            raise ValueError(
                "Target character does not belong to the destination client"
            )
        combined, notes, target = build_addon_restore(archive, manifest, client, char)
        plan = combined.files
        for note in notes:
            print(note)
        print("Target:", target["full"], target["realm"])
    preview = (
        combined
        if args.action == "restore"
        else FilePlan.capture(client, plan, rooted, file_sha)
    )
    print(
        f"Plan: {len(plan)} files. "
        + ("Applying changes next." if args.apply else "Preview only; no changes.")
    )
    if args.apply:
        return execute_plan(client, preview, args.action, character=args.character)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError, IndexError, zipfile.BadZipFile) as error:
        print("\nCancelled: " + str(error), file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)
