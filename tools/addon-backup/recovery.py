"""Transactional writes and independent recovery archives."""

import json
import os
from pathlib import Path, PurePosixPath
import shutil
import zipfile
from characters import identity
from archives import managed_entry
from legacy import english_legacy_text
from file_ops import (
    rooted,
    file_sha,
    sha,
    stamp,
    backup_folder_part,
    payload_hash,
    atomic_payload,
    json_write,
)


def recovery_context(client, files, character=None):
    """Identify the destination of a recovery point, including older manifests."""
    client = Path(client).resolve()
    if character is None:
        candidates = set()
        for filename in files:
            parts = PurePosixPath(filename).parts
            if (
                len(parts) >= 6
                and parts[:2] == ("WTF", "Account")
                and parts[3] != "SavedVariables"
            ):
                candidates.add("/".join(parts[:5]))
        if len(candidates) == 1:
            character = rooted(client, candidates.pop())
    if character is None:
        return {"realm": "Unknown Realm", "character": "Unassigned"}
    character = Path(character).absolute()
    relative = character.relative_to(client).as_posix()
    rooted(client, relative)
    try:
        info = identity(character) or {}
    except (ValueError, OSError, KeyError, IndexError):
        info = {}
    realm = info.get("realm") or (
        ("Realm folder " + character.parent.name)
        if character.parent.name.isdigit()
        else character.parent.name
    )
    return {
        "realm": realm,
        "character": info.get("full") or character.name.replace("-", " ", 1),
        "character_path": relative,
    }


def apply_plan(
    client, plan, label, character=None, context=None, *, paths, writer=atomic_payload
):
    client = client.resolve()
    changes = {}
    for rel, value in plan.items():
        p = rooted(client, rel)
        if p.exists() and not p.is_file():
            raise ValueError("Destination is not a file: " + str(p))
        before = file_sha(p)
        after = payload_hash(value)
        if before != after:
            changes[rel] = (value, before, after)
    if not changes:
        print("No changes required.")
        return None
    context = context or recovery_context(client, changes, character)
    relative = (
        backup_folder_part(context["realm"])
        + "/"
        + backup_folder_part(context["character"])
        + "/"
        + stamp()
    )
    if paths.recovery.is_symlink():
        raise ValueError("Recovery storage must not be a symlink.")
    dest = rooted(paths.recovery, relative)
    dest.mkdir(parents=True)
    log = {
        "schema": 1,
        "client": str(client),
        "target": context,
        "label": label,
        "status": "preparing",
        "files": [],
    }
    with zipfile.ZipFile(dest / "before.zip", "w", zipfile.ZIP_DEFLATED) as z:
        for rel, (value, before, after) in changes.items():
            p = rooted(client, rel)
            if before is not None:
                z.write(p, rel)
                if file_sha(p) != before:
                    raise ValueError("Destination file changed concurrently: " + rel)
            log["files"].append({"path": rel, "before": before, "after": after})
    # Verify the rollback data before writing any destination files.
    with zipfile.ZipFile(dest / "before.zip") as z:
        for entry in log["files"]:
            if (
                entry["before"] is not None
                and sha(z.read(entry["path"])) != entry["before"]
            ):
                raise ValueError("Could not verify recovery data")
    log["status"] = "applying"
    json_write(dest / "manifest.json", log)
    done = []
    try:
        for rel, (value, before, after) in changes.items():
            p = rooted(client, rel)
            if file_sha(p) != before:
                raise ValueError("Destination file changed concurrently: " + rel)
            if value is None:
                p.unlink()
            else:
                writer(p, value)
            done.append(rel)
            if file_sha(p) != after:
                raise ValueError("Write verification failed: " + rel)
            if len(done) % 3000 == 0:
                print(f"{len(done)} files installed …", flush=True)
        log["status"] = "complete"
        json_write(dest / "manifest.json", log)
    except BaseException:
        with zipfile.ZipFile(dest / "before.zip") as z:
            for rel in reversed(done):
                p = rooted(client, rel)
                if changes[rel][1] is None:
                    p.unlink(missing_ok=True)
                else:
                    writer(p, z.read(rel))
        log["status"] = "rolled_back"
        json_write(dest / "manifest.json", log)
        raise
    print(f"{len(changes)} files written and verified. Recovery data: {dest}")
    return dest


def recovery_entries(*, paths):
    entries = []
    for root in (paths.recovery, paths.legacy_recovery):
        if root.is_symlink():
            continue
        for directory, folders, files in os.walk(root, followlinks=False):
            folders[:] = [
                name for name in folders if not (Path(directory) / name).is_symlink()
            ]
            if (
                "manifest.json" in files
                and not (Path(directory) / "manifest.json").is_symlink()
            ):
                entries.append(Path(directory))
                folders[:] = []
    return sorted(entries, key=lambda p: (p.name, str(p)), reverse=True)


def undo(recovery, *, paths, writer=atomic_payload):
    log = json.loads((recovery / "manifest.json").read_text())
    client = Path(log["client"])
    if log["status"] not in ["complete", "applying"]:
        raise ValueError("This operation cannot be undone: " + log["status"])
    plan = {}
    archive = recovery / "before.zip"
    if not archive.exists():
        archive = recovery / "vorher.zip"  # Legacy archive name.
    with zipfile.ZipFile(archive) as z:
        for e in log["files"]:
            p = rooted(client, e["path"])
            current = file_sha(p)
            if current not in [e["before"], e["after"]]:
                raise ValueError(
                    "File changed after this operation; undo would overwrite newer data: "
                    + e["path"]
                )
            data = z.read(e["path"]) if e["before"] is not None else None
            if data is not None and sha(data) != e["before"]:
                raise ValueError("Recovery data is corrupted")
            plan[e["path"]] = data
    context = log.get("target") or recovery_context(
        client, (e["path"] for e in log["files"])
    )
    result = apply_plan(
        client,
        plan,
        "Undo: " + english_legacy_text(log["label"]),
        context=context,
        paths=paths,
        writer=writer,
    )
    log["status"] = "undone"
    json_write(recovery / "manifest.json", log)
    return result


def delete_recovery_point(path, *, paths):
    path = Path(path).absolute()
    roots = [
        root
        for root in (paths.recovery, paths.legacy_recovery)
        if path != root.absolute() and path.is_relative_to(root.absolute())
    ]
    if not roots:
        raise ValueError("Selection is outside the recovery directories.")
    path = managed_entry(path, roots[0], nested=True, paths=paths)
    if not path.is_dir() or not (path / "manifest.json").is_file():
        raise ValueError("Select an existing recovery point.")
    # rmtree removes internal symlinks themselves without following their targets.
    shutil.rmtree(path)
    print("Recovery point deleted: " + path.name)
