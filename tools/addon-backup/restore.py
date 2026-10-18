"""Read-only plans for addon installation, settings and macro restoration."""

from pathlib import Path, PurePosixPath
import re
import zipfile
from characters import HELPER, identity, inventory, characters
from saved_variables import encode, decode
from models import CharacterIdentity
from file_ops import Archived, rooted, sha
from addon_support import pending_reviews
from addon_adapters import (
    CHAR_CONFIG,
    account_config,
    character_config,
    merge_cvars,
    merge_chat,
)


def helper_plan(client, manifest=None, character=None):
    interfaces = set()
    for meta in inventory(client / "Interface/AddOns").values():
        for line in meta.get("Interface", []):
            interfaces.update(re.findall(r"\d+", line))
    cfg = client / "WTF/Config.wtf"
    if cfg.exists():
        for key in ["engineSurveyPatch", "lastAddonVersion"]:
            m = re.search(r"^SET " + key + r' "(\d+)"', decode(cfg.read_bytes()), re.M)
            if m:
                interfaces.add(m[1])
    if manifest:
        for meta in manifest["addons"].values():
            for line in meta.get("Interface", []):
                interfaces.update(re.findall(r"\d+", line))
    if not interfaces:
        interfaces.add("16001")
    toc = (
        "## Interface: "
        + ", ".join(sorted(interfaces, key=int))
        + "\n## Title: WoW UI Transfer Identity\n## Notes: Records this character identity locally for UI backup restoration.\n## Version: 1.0\n## SavedVariablesPerCharacter: WoWUITransferIdentity\nidentity.lua\n"
    )
    prefix = "Interface/AddOns/" + HELPER + "/"
    plan = {
        prefix + HELPER + ".toc": encode(toc),
        prefix
        + "identity.lua": (
            Path(__file__).resolve().parent / "identity.lua"
        ).read_bytes(),
    }
    for char in [character] if character is not None else characters(client):
        p = char / "AddOns.txt"
        txt = decode(p.read_bytes()) if p.exists() else ""
        txt = re.sub(r"^" + HELPER + r":[^\r\n]*[\r\n]*", "", txt, flags=re.M)
        plan[p.relative_to(client).as_posix()] = encode(
            txt.rstrip() + "\n" + HELPER + ": enabled\n"
        )
    return plan


def require_backup_kind(manifest, kind):
    stored = manifest.get("kind", "combined")
    if stored not in ("combined", kind):
        raise ValueError(f"This is a {stored} backup. Select a {kind} backup instead.")


def install_plan(archive, manifest, client, replace=False, character=None):
    require_backup_kind(manifest, "addons")
    plan = {}
    existing = inventory(client / "Interface/AddOns")
    selected = (
        set(manifest["addons"]) if replace else set(manifest["addons"]) - set(existing)
    )
    for name, meta in manifest["files"].items():
        parts = PurePosixPath(name).parts
        if (
            len(parts) >= 5
            and parts[:3] == ("client", "Interface", "AddOns")
            and parts[3] in selected
        ):
            plan["/".join(parts[1:])] = Archived(archive, name, meta["sha256"])
    if replace:
        for addon in selected:
            folder = client / "Interface/AddOns" / addon
            if folder.exists():
                for p in folder.rglob("*"):
                    if p.is_file():
                        rel = p.relative_to(client).as_posix()
                        if rel not in plan:
                            plan[rel] = None
    plan.update(helper_plan(client, manifest, character))
    if character is not None:
        with zipfile.ZipFile(archive) as z:
            plan[(character / "AddOns.txt").relative_to(client).as_posix()] = (
                activation_data(
                    z,
                    manifest,
                    set(existing) | set(manifest["addons"]),
                    helper_enabled=True,
                    target_data=(
                        (character / "AddOns.txt").read_bytes()
                        if (character / "AddOns.txt").exists()
                        else None
                    ),
                )
            )
    return plan


def activation_data(z, manifest, installed, helper_enabled=False, target_data=None):
    states = {}
    member = "client/" + manifest["source_character"] + "/AddOns.txt"
    if member in manifest["files"]:
        for name, state in re.findall(
            r"^([^:\r\n]+):\s*(enabled|disabled)", decode(z.read(member)), re.M
        ):
            states[name] = state
    expected = set(manifest["addons"])
    for addon in installed:
        states[addon] = (
            states.get(addon, "enabled") if addon in expected else "disabled"
        )
    target_states = dict(
        re.findall(
            r"^([^:\r\n]+):\s*(enabled|disabled)", decode(target_data or b""), re.M
        )
    )
    for addon in manifest.get("skipped_addons", []):
        states.pop(addon, None)
        if addon in target_states:
            states[addon] = target_states[addon]
    states[HELPER] = "enabled" if helper_enabled else "disabled"
    return encode(
        "".join(name + ": " + state + "\n" for name, state in sorted(states.items()))
    )


def restore_plan(archive, manifest, client, char, allow_missing=False):
    require_backup_kind(manifest, "addons")
    target = identity(char)
    if not target:
        raise ValueError(
            "Target identity is unknown. Complete preparation and log in for character detection first."
        )
    CharacterIdentity.from_mapping(target)
    source = manifest["source_identity"]
    account = char.parent.parent
    if pending_reviews(manifest):
        raise ValueError(
            "Backup contains configurations that still need review: "
            + ", ".join(pending_reviews(manifest))
        )
    expected = set(manifest["addons"])
    actual = inventory(client / "Interface/AddOns")
    missing = expected - set(actual)
    if missing and not allow_missing:
        raise ValueError(
            "Addon files are missing; run preparation first: "
            + ", ".join(sorted(missing))
        )
    plan = {}
    notes = ["Skipped addon: " + addon for addon in manifest.get("skipped_addons", [])]
    for addon in expected & set(actual):
        if manifest["addons"][addon].get("Version") != actual[addon].get("Version"):
            notes.append("Keeping a different installed addon version: " + addon)
    if source["class"] != target["class"]:
        notes.append(
            "Different class: "
            + source["class"]
            + " → "
            + target["class"]
            + ". Spells and click-casting may need adjustment in the game."
        )
    srcchar = "client/" + manifest["source_character"]
    srcacc = str(PurePosixPath(srcchar).parent.parent)

    def put(path, data):
        if data is not None and (not path.exists() or path.read_bytes() != data):
            plan[path.relative_to(client).as_posix()] = data

    def existing(path):
        return path.read_bytes() if path.exists() else None

    with zipfile.ZipFile(archive) as z:
        for member in manifest["files"]:
            p = PurePosixPath(member)
            if (
                str(p.parent) == srcacc + "/SavedVariables"
                and p.suffix == ".lua"
                and p.stem in expected
            ):
                dst = account / "SavedVariables" / p.name
                put(
                    dst,
                    account_config(
                        p.stem, z.read(member), existing(dst), source, target
                    ),
                )
            elif (
                str(p.parent) == srcchar + "/SavedVariables"
                and p.suffix == ".lua"
                and (p.stem in expected or p.stem in CHAR_CONFIG)
            ):
                dst = char / "SavedVariables" / p.name
                put(
                    dst,
                    character_config(
                        p.stem, z.read(member), existing(dst), source, target
                    ),
                )
        for source_dir, dest_dir, names in [
            (srcacc, account, ["edit-mode-cache-account.txt", "bindings-cache.wtf"]),
            (
                srcchar,
                char,
                [
                    "layout-local.txt",
                    "edit-mode-cache-character.txt",
                    "bindings-cache.wtf",
                ],
            ),
        ]:
            for name in names:
                member = source_dir + "/" + name
                if member in manifest["files"]:
                    put(dest_dir / name, z.read(member))
        for source_dir, dest_dir, name in [
            ("client/WTF", client / "WTF", "Config.wtf"),
            (srcacc, account, "config-cache.wtf"),
            (srcchar, char, "config-cache.wtf"),
        ]:
            member = source_dir + "/" + name
            if member in manifest["files"]:
                put(
                    dest_dir / name,
                    merge_cvars(z.read(member), existing(dest_dir / name)),
                )
        member = srcchar + "/chat-cache.txt"
        if member in manifest["files"]:
            put(
                char / "chat-cache.txt",
                merge_chat(z.read(member), existing(char / "chat-cache.txt")),
            )
        put(
            char / "AddOns.txt",
            activation_data(
                z,
                manifest,
                set(actual) | expected,
                helper_enabled=False,
                target_data=existing(char / "AddOns.txt"),
            ),
        )
    return plan, notes, target


def macro_plan(archive, manifest, client, char, scope="character"):
    """Restore complete macro files without changing macro bodies or identifiers."""
    require_backup_kind(manifest, "macros")
    client = client.resolve()
    char = char.resolve()
    if char not in [p.resolve() for p in characters(client)]:
        raise ValueError("Target character does not belong to the destination client")
    if scope not in ("character", "account", "both"):
        raise ValueError("Unknown macro scope: " + scope)
    source = PurePosixPath("client") / manifest["source_character"]
    locations = {
        "character": (source, char),
        "account": (source.parent.parent, char.parent.parent),
    }
    plan = {}
    notes = []
    with zipfile.ZipFile(archive) as z:
        for kind in ("character", "account") if scope == "both" else (scope,):
            src, dst = locations[kind]
            member = str(src / "macros-cache.txt")
            if member not in manifest["files"]:
                notes.append(
                    kind.capitalize()
                    + ": no macro file in this backup; destination unchanged."
                )
                continue
            data = z.read(member)
            # Validate the selected payload even when called outside the CLI/menu.
            if sha(data) != manifest["files"][member]["sha256"]:
                raise ValueError("Corrupted backup file: " + member)
            rel = (dst / "macros-cache.txt").relative_to(client).as_posix()
            target = rooted(client, rel)
            count = sum(line.startswith(b"VER ") for line in data.splitlines())
            notes.append(
                f"{kind.capitalize()}: {count} saved macros; replace the complete destination macro file: {rel}"
            )
            if not target.exists() or target.read_bytes() != data:
                plan[rel] = data
    return plan, notes


def show_macro_notes(notes):
    for note in notes:
        print(note)
    print(
        "Macro bodies are copied unchanged. Check class-specific spells and explicit character names in the game."
    )
    print(
        "Action bar placement is not restored. Check the macros after login; live client/server synchronization has not been validated."
    )
