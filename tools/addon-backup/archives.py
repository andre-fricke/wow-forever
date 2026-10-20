"""Versioned backup archives, integrity verification and managed deletion."""

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import zipfile
from characters import characters, identity, inventory, HELPER
from macro_placement import placement_snapshot
from saved_variables import parse
from addon_support import audit_support
from models import BackupManifest
from file_ops import (
    rooted,
    stamp,
    backup_name_part,
    backup_folder_part,
    json_write,
    valid_relative,
)

SCHEMA = 1


def backup_directory(info, kind, *, paths):
    rooted(paths.tool, paths.backups.relative_to(paths.tool).as_posix())
    relative = (
        backup_folder_part(info["realm"]) + "/" + backup_folder_part(info["full"])
    )
    for folder in ("Addons", "Macros"):
        rooted(paths.backups, relative + "/" + folder).mkdir(
            parents=True, exist_ok=True
        )
    folder = {"addons": "Addons", "macros": "Macros", "click-casting": "Click_Casting", "combined": "Combined"}[kind]
    destination = rooted(paths.backups, relative + "/" + folder)
    destination.mkdir(parents=True, exist_ok=True)
    return destination


def create_backup(client, char, kind="combined", *, paths):
    if kind not in ("addons", "macros", "click-casting", "combined"):
        raise ValueError("Unknown backup type")
    client = client.resolve()
    char = char.resolve()
    if char not in [p.resolve() for p in characters(client)]:
        raise ValueError("Character does not belong to the selected installation")
    info = identity(char)
    if not info:
        raise ValueError(
            "Template identity is missing. Prepare character detection and log in with the template character first."
        )
    installed = inventory(client / "Interface/AddOns") if kind in ("addons", "combined") else {}
    unsupported = audit_support(client, char) if kind in ("addons", "combined") else []
    destination = backup_directory(info, kind, paths=paths)
    filename = (
        stamp()
        + "_"
        + backup_name_part(info["full"])
        + "_"
        + backup_name_part(info["realm"])
        + "_"
        + kind
        + ".zip"
    )
    dest = destination / filename
    temp = dest.with_suffix(".partial")
    members = {}
    roots = [client / "Interface/AddOns", client / "WTF"]
    selected_paths = {char / "macros-cache.txt", char.parent.parent / "macros-cache.txt"}
    if kind in ("macros", "click-casting"):
        roots = [None]
    if kind == "click-casting":
        selected_paths = {char / "click-bindings-cache.txt"}
        if not (char / "click-bindings-cache.txt").is_file():
            raise ValueError("No saved WoW Click Casting settings found. Configure Click Casting on the source character and quit WoW first.")
    if kind == "macros" and not any(p.exists() for p in selected_paths):
        raise ValueError("No saved macro files found for this character or account.")
    if kind == "macros":
        helper = char / "SavedVariables" / (HELPER + ".lua")
        if helper.exists() and "WoWUITransferBars" in parse(helper.read_bytes()):
            snapshot = placement_snapshot(helper.read_bytes())
            account_slots = sum(entry["scope"] == "account" for entry in snapshot["slots"].values())
            print(f"Macro action slots captured: {len(snapshot['slots']) - account_slots} character, {account_slots} account.")
            selected_paths.add(helper)
        else:
            print("No macro slot snapshot available; this backup contains macro files only. Use the interactive backup to capture slots.")
    print(
        {
            "addons": "Backing up addon files and locally saved UI settings …",
            "macros": "Backing up character and account macros …",
            "click-casting": "Backing up built-in WoW Click Casting settings …",
            "combined": "Backing up addon files, macros, and locally saved WTF settings …",
        }[kind],
        flush=True,
    )
    try:
        with zipfile.ZipFile(temp, "w", zipfile.ZIP_DEFLATED, compresslevel=4) as z:
            count = 0
            for root in roots:
                for p in sorted(selected_paths if root is None else root.rglob("*")):
                    if kind == "addons" and p.name.startswith("macros-cache."):
                        continue
                    if p.is_symlink():
                        raise ValueError(
                            "Review this symlink before creating a backup: " + str(p)
                        )
                    if not p.is_file():
                        continue
                    before = p.stat()
                    rel = p.relative_to(client).as_posix()
                    digest = hashlib.sha256()
                    with p.open("rb") as src, z.open("client/" + rel, "w") as dst:
                        for block in iter(lambda: src.read(1024 * 1024), b""):
                            digest.update(block)
                            dst.write(block)
                    after = p.stat()
                    if (before.st_mtime_ns, before.st_size) != (
                        after.st_mtime_ns,
                        after.st_size,
                    ):
                        raise ValueError(
                            "A file changed during the backup. Quit WoW and try again."
                        )
                    members["client/" + rel] = {
                        "sha256": digest.hexdigest(),
                        "size": after.st_size,
                        "mtime_ns": after.st_mtime_ns,
                    }
                    count += 1
                    if count % 3000 == 0:
                        print(f"{count} files backed up …", flush=True)
            manifest = {
                "schema": SCHEMA,
                "kind": kind,
                "created": dt.datetime.now().astimezone().isoformat(),
                "source_client": str(client),
                "source_character": char.relative_to(client).as_posix(),
                "source_identity": info,
                "addons": installed,
                "unsupported": unsupported,
                "files": members,
            }
            z.writestr(
                "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2)
            )
        # Check content integrity before publishing the new current backup.
        print("Verifying backup …", flush=True)
        verify_backup(temp)
        os.replace(temp, dest)
        json_write(
            paths.tool / "latest.json",
            {"backup": dest.relative_to(paths.tool).as_posix()},
        )
        print(
            f"Backup verified: {dest}\n{len(members)} files, {dest.stat().st_size//1024//1024} MiB compressed."
        )
        if unsupported:
            print("Review before restoring: " + ", ".join(unsupported))
        print(f"Backup created: {dest.name}", flush=True)
        print(
            "Verification successful: all archived files passed their checksum checks.",
            flush=True,
        )
        return dest
    except BaseException:
        temp.unlink(missing_ok=True)
        raise


def verify_backup(path):
    with zipfile.ZipFile(path) as z:
        names = z.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Duplicate archive paths")
        manifest = json.loads(z.read("manifest.json"))
        BackupManifest.from_mapping(manifest)
        valid_relative(manifest["source_character"])
        expected = set(manifest["files"]) | {"manifest.json"}
        if set(names) != expected:
            raise ValueError("Archive contents do not match the manifest")
        for name, meta in manifest["files"].items():
            valid_relative(name)
            h = hashlib.sha256()
            size = 0
            with z.open(name) as f:
                for block in iter(lambda: f.read(1024 * 1024), b""):
                    h.update(block)
                    size += len(block)
            if h.hexdigest() != meta["sha256"] or size != meta["size"]:
                raise ValueError("Corrupted backup file: " + name)
        return manifest


def latest_backup(kind=None, *, paths):
    if kind:
        for candidate in backup_entries(paths=paths):
            try:
                with zipfile.ZipFile(candidate) as z:
                    manifest = json.loads(z.read("manifest.json"))
            except (OSError, ValueError, KeyError, zipfile.BadZipFile):
                continue
            if manifest.get("kind", "combined") in (kind, "combined"):
                return candidate
        raise ValueError(
            f"No {kind} backup found. Create one in the Backup menu first."
        )
    p = paths.tool / "latest.json"
    if p.exists():
        candidate = rooted(paths.tool, json.loads(p.read_text())["backup"])
        if candidate.is_file():
            return candidate
    candidates = backup_entries(paths=paths)
    if not candidates:
        raise ValueError("No backup found. Create one in the Backup menu first.")
    return candidates[0]


def backup_entries(*, paths):
    rooted(paths.tool, paths.backups.relative_to(paths.tool).as_posix())
    entries = []
    for directory, folders, files in os.walk(paths.backups, followlinks=False):
        folders[:] = [
            name for name in folders if not (Path(directory) / name).is_symlink()
        ]
        for name in files:
            path = Path(directory) / name
            if path.suffix == ".zip" and path.is_file() and not path.is_symlink():
                entries.append(path)
    # Timestamp-prefixed filenames determine age, not realm/character directory order.
    return sorted(entries, key=lambda p: (p.name, p.as_posix()), reverse=True)


def managed_entry(path, root, nested=False, *, paths):
    """Allow deletion only inside the selected tool storage directory."""
    path = Path(path).absolute()
    root = Path(root).absolute()
    if (
        not path.is_relative_to(root)
        or path == root
        or (not nested and path.parent != root)
    ):
        raise ValueError("Selection is outside the managed storage directory.")
    rooted(paths.tool, root.relative_to(paths.tool.absolute()).as_posix())
    return rooted(root, path.relative_to(root).as_posix())


def delete_backup(path, *, paths):
    path = managed_entry(path, paths.backups, nested=True, paths=paths)
    if path.suffix != ".zip" or not path.is_file():
        raise ValueError("Select an existing backup ZIP.")
    pointer = paths.tool / "latest.json"
    # Resolve the pointer before deleting, so invalid metadata causes no partial deletion.
    current = (
        rooted(paths.tool, json.loads(pointer.read_text())["backup"])
        if pointer.exists()
        else None
    )
    path.unlink()
    if current == path:
        remaining = backup_entries(paths=paths)
        if remaining:
            json_write(
                pointer, {"backup": remaining[0].relative_to(paths.tool).as_posix()}
            )
        else:
            pointer.unlink()
    print("Backup deleted: " + path.name)
