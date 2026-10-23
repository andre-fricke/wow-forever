"""Prepare account-scoped, data-only templates for the in-game helper.

Offline adapters are not automatically runtime adapters. Only AceDB profiles and
reviewed character settings are applied in game. Shared settings are inherited;
missing account files can be seeded once during the explicit preparation step.
"""

import copy
import math
from collections import Counter
from pathlib import PurePosixPath
import re
import shlex
import zipfile

from addon_adapters import (
    CHAR_CONFIG, CHAR_SPECIAL, REVIEWED, account_config, character_config, profile_aliases,
)
from archives import verify_backup
from characters import HELPER, characters, identity
from file_ops import rooted, sha
from macro_placement import placement_snapshot
from macro_transform import compile_variants, POLICY_VERSION
from restore import install_plan, require_backup_kind
from saved_variables import decode, dump, parse, plain

STATE = "WoWUITransferAuto"


def state_path(client, character):
    client, character = client.resolve(), character.resolve()
    if character not in [p.resolve() for p in characters(client)]:
        raise ValueError("Choose an existing character in the destination account.")
    relative = (character.parent.parent / "SavedVariables" / (HELPER + ".lua")).relative_to(client).as_posix()
    rooted(client, relative)
    return relative


def read_state(client, character):
    path = rooted(client, state_path(client, character))
    roots = plain(parse(path.read_bytes())) if path.exists() else {}
    state = roots.get(STATE, {})
    # WoW writes declared but uninitialized SavedVariables as explicit nil.
    if state is None:
        state = {}
    if not isinstance(state, dict) or (state and state.get("schema") != 1):
        raise ValueError("Unsupported automatic setup state; no changes made.")
    return roots, state


def disable_plan(client, character):
    roots, state = read_state(client, character)
    if not state:
        return {}
    state["enabled"] = False
    roots[STATE] = state
    return {state_path(client, character): dump(roots)}


def capture_from(archive, manifest, clicks=False):
    member = "client/" + manifest["source_character"] + "/SavedVariables/" + HELPER + ".lua"
    with zipfile.ZipFile(archive) as z:
        snapshot = plain(parse(z.read(member))).get("WoWUITransferSetup") if member in manifest["files"] else None
    if not isinstance(snapshot, dict) or snapshot.get("schema") != 1 or snapshot.get("guid") != manifest["source_identity"]["guid"]:
        raise ValueError("This backup has no automatic setup capture. Install/update the helper (4.1), log in with the source, quit WoW, and create a new backup.")
    macros = snapshot.get("macros")
    if not isinstance(macros, dict):
        raise ValueError("Invalid captured macro catalog.")
    for index, macro in macros.items():
        if type(index) is not int or index < 1 or not isinstance(macro, dict) or macro.get("scope") not in ("account", "character") or any(not isinstance(macro.get(k), str) for k in ("name", "body")) or not isinstance(macro.get("icon"), (int, str)):
            raise ValueError("Invalid captured macro identity.")
    if clicks:
        bindings = snapshot.get("clicks")
        if not isinstance(bindings, dict) or set(bindings) != set(range(1, len(bindings) + 1)):
            raise ValueError("This backup has no native Click Casting API snapshot. Capture it with the updated helper first.")
        for binding in bindings.values():
            if not isinstance(binding, dict) or type(binding.get("type")) is not int or binding["type"] not in range(5) or type(binding.get("actionID")) is not int or type(binding.get("modifiers")) is not int or not isinstance(binding.get("button"), str):
                raise ValueError("Invalid native Click Casting entry.")
            if binding["type"] == 2 and binding["actionID"] not in macros:
                raise ValueError("Click Casting refers to an uncaptured macro.")
    return snapshot


def verify_macro_capture(archive, manifest, snapshot):
    """Reconcile regenerated bodies by unique scope/name; never guess indices."""
    snapshot = copy.deepcopy(snapshot)
    source = PurePosixPath("client") / manifest["source_character"]
    with zipfile.ZipFile(archive) as z:
        for scope, base in (("character", source), ("account", source.parent.parent)):
            member = str(base / "macros-cache.txt")
            entries = []
            lines = decode(z.read(member)).splitlines() if member in manifest["files"] else []
            index = 0
            while index < len(lines):
                line = lines[index]
                index += 1
                if not line.strip():
                    continue
                header = shlex.split(line)
                if len(header) < 5 or header[0] != "VER":
                    raise ValueError("Unsupported macro cache format; use manual restoration.")
                body = []
                while index < len(lines) and lines[index] != "END":
                    body.append(lines[index])
                    index += 1
                if index == len(lines):
                    raise ValueError("Incomplete macro cache entry.")
                index += 1
                entries.append((header[3], "\n".join(body).rstrip("\n"), header[4]))
            captured = [(m["name"], m["body"].replace("\r\n", "\n").rstrip("\n")) for m in snapshot["macros"].values() if m["scope"] == scope]
            names = Counter(name for name, _, _ in entries)
            if names != Counter(name for name, _ in captured) or any(count != 1 for count in names.values()):
                raise ValueError("Macro names are missing, changed or ambiguous between capture and files (" + scope + "). Log in with the updated helper, give macros unique names, quit WoW and create a fresh macro backup.")
            by_name = {name:(body, icon) for name, body, icon in entries}
            for macro in snapshot["macros"].values():
                if macro["scope"] == scope:
                    body, icon = by_name[macro["name"]]
                    macro["body"] = body
                    macro["icon"] = int(icon) if icon.isdigit() else icon
    return snapshot


def reconcile_references(entries, macros):
    """Keep captured slot/index keys, update the referenced macro contents."""
    catalog = {(m["scope"],m["name"]):m for m in macros.values()}
    result = copy.deepcopy(entries)
    for entry in result.values():
        match = catalog.get((entry["scope"],entry["name"]))
        if match is None:
            raise ValueError("Captured macro reference is missing from the macro backup: " + entry["name"])
        entry["body"] = match["body"]
    return result


def namespace_recipe(namespaces, selected):
    return {name: {"profile": node.get("profiles", {}).get(selected, {}),
                   "namespaces": namespace_recipe(node.get("namespaces", {}), selected)}
            for name, node in namespaces.items()}


def build_template(addons, macros=None, clicks=None):
    """Verify archives, extract only selected source data, report unsupported parts."""
    manifest = verify_backup(addons)
    require_backup_kind(manifest, "addons")
    source = manifest["source_identity"]
    template = {"source": source, "profiles": {}, "characters": {}, "flags": {},
                "macros": {}, "slots": {}, "hasMacros": False, "hasClicks": False}
    template["editModeLayout"] = "default"
    notes, shared = [], {}
    character_prefix = "client/" + manifest["source_character"] + "/SavedVariables/"
    account_prefix = "client/" + str(PurePosixPath(manifest["source_character"]).parent.parent) + "/SavedVariables/"
    with zipfile.ZipFile(addons) as z:
        helper_member = character_prefix + HELPER + ".lua"
        captured = plain(parse(z.read(helper_member))).get("WoWUITransferSetup", {}) if helper_member in manifest["files"] else {}
        chat = captured.get("chat") if isinstance(captured, dict) else None
        if chat is not None:
            # WoW can serialize sparse numeric tables as array constructors
            # with explicit nil holes. In Lua those entries do not exist.
            # Keep the original IDs: window 4 must not become window 3.
            if isinstance(chat, dict):
                chat = {index:entry for index,entry in chat.items() if entry is not None}
            if captured.get("guid") != source["guid"] or not isinstance(chat, dict) or not chat:
                raise ValueError("Invalid chat layout capture.")
            for index, entry in chat.items():
                if type(index) is not int or not 1 <= index <= 10 or not isinstance(entry, dict):
                    raise ValueError("Invalid chat window ID.")
                for key in ("x", "y", "width", "height"):
                    value = entry.get(key)
                    if type(value) not in (int, float) or not math.isfinite(value) or not -2 <= value <= 2 or (key in ("width", "height") and value <= 0):
                        raise ValueError("Invalid chat window geometry.")
                if type(entry.get("dock")) is not int or not 0 <= entry["dock"] <= 10 or type(entry.get("locked")) is not bool or not isinstance(entry.get("name"), str):
                    raise ValueError("Invalid chat window state.")
                if "alpha" in entry and (type(entry["alpha"]) not in (int, float) or not math.isfinite(entry["alpha"]) or not 0 <= entry["alpha"] <= 1):
                    raise ValueError("Invalid chat background opacity.")
                if "subscriptions" in entry:
                    subscriptions = entry["subscriptions"]
                    if not isinstance(subscriptions, dict) or set(subscriptions) != {"messages", "channels"} or not entry["name"].strip():
                        raise ValueError("Invalid chat subscriptions.")
                    for values in subscriptions.values():
                        if not isinstance(values, dict) or set(values) != set(range(1, len(values) + 1)) or any(not isinstance(v, str) or not v.strip() for v in values.values()):
                            raise ValueError("Invalid chat subscriptions.")
            template["chat"] = chat
            notes.append(f"Chat positions captured: {len(chat)} windows (including Combat Log when present).")
        else:
            notes.append("No chat positions in this older backup. Capture a new addon backup with the updated helper to include them.")
        for member in sorted(manifest["files"]):
            addon = PurePosixPath(member).stem
            if not member.endswith(".lua") or addon == HELPER:
                continue
            is_character = member.startswith(character_prefix) and "/" not in member[len(character_prefix):]
            is_account = member.startswith(account_prefix) and "/" not in member[len(account_prefix):]
            if (is_character or is_account) and addon not in manifest["addons"] and not addon.startswith("Blizzard_"):
                notes.append("Skipped leftover settings for an addon absent from the backup inventory: " + addon)
                continue
            if member.startswith(character_prefix) and "/" not in member[len(character_prefix):]:
                if addon not in CHAR_CONFIG | CHAR_SPECIAL:
                    notes.append("Not applied in game: character settings for " + addon)
                    continue
                # Source identity is retained here and remapped exactly at login.
                data = character_config(addon, z.read(member), None, source, source)
                if data:
                    template["characters"][addon] = plain(parse(data))
            elif member.startswith(account_prefix) and "/" not in member[len(account_prefix):]:
                # Account-wide data must pass the same review as manual restores.
                raw = parse(z.read(member))
                if addon not in REVIEWED and not addon.startswith(("EllesmereUI", "DBM-")) and not (raw and all(isinstance(root, dict) and "profileKeys" in root for root in raw.values())):
                    notes.append("Not applied: unreviewed account settings for " + addon)
                    continue
                sanitized = plain(parse(account_config(addon, z.read(member), None, source, source)))
                shared[addon] = sanitized
                for root_name, root in sanitized.items():
                    if not isinstance(root, dict) or "profileKeys" not in root:
                        continue
                    selected = next((root["profileKeys"][alias] for alias in profile_aliases(source, addon) if alias in root["profileKeys"]), None)
                    if selected is None or selected not in root.get("profiles", {}):
                        notes.append("No selected profile: " + addon + " / " + root_name)
                        continue
                    template["profiles"][root_name] = {
                        "addon": addon, "profile": root["profiles"][selected],
                        "namespaces": namespace_recipe(root.get("namespaces", {}), selected),
                    }
        flags = "client/" + manifest["source_character"] + "/AddOns.txt"
        if flags in manifest["files"]:
            for name, enabled in re.findall(r"^([^:\r\n]+):\s*(enabled|disabled)\s*$", decode(z.read(flags)), re.M):
                if name in manifest["addons"] and name != HELPER:
                    template["flags"][name] = enabled == "enabled"
    for kind, archive in (("macros", macros), ("click-casting", clicks)):
        if archive is None:
            continue
        other = verify_backup(archive)
        require_backup_kind(other, kind)
        if other["source_identity"]["guid"] != source["guid"]:
            raise ValueError("All selected backups must belong to the same source character.")
        snapshot = capture_from(archive, other, clicks=kind == "click-casting")
        if kind == "macros":
            original = snapshot
            snapshot = verify_macro_capture(archive, other, snapshot)
            changed = sum(original["macros"][index]["body"].rstrip("\n") != macro["body"] for index,macro in snapshot["macros"].items())
            if changed:
                notes.append(f"Reconciled {changed} changed macro bodies by unique scope/name using archived macro files (including addon-generated macros).")
            template["hasMacros"] = True
            template["macros"] = snapshot["macros"]
            member = "client/" + other["source_character"] + "/SavedVariables/" + HELPER + ".lua"
            with zipfile.ZipFile(archive) as z:
                template["slots"] = reconcile_references(placement_snapshot(z.read(member))["slots"], template["macros"])
        else:
            template["hasClicks"] = True
            template["clicks"] = snapshot["clicks"]
            # Click macro IDs belong to this particular capture, not to another
            # backup's macro ordering. Store the identities alongside the binds.
            template["clickMacros"] = snapshot["macros"]
    if clicks and not macros and any(b["type"] == 2 for b in template["clicks"].values()):
        raise ValueError("Click Casting contains macros; also select a macro backup.")
    if clicks and macros:
        referenced = {}
        click_names = Counter((entry["scope"],entry["name"]) for entry in template["clickMacros"].values())
        for binding in template["clicks"].values():
            if binding["type"] == 2:
                entry = template["clickMacros"][binding["actionID"]]
                if click_names[(entry["scope"],entry["name"])] != 1:
                    raise ValueError("Click Casting macro name is ambiguous: " + entry["name"])
                referenced[binding["actionID"]] = template["clickMacros"][binding["actionID"]]
        template["clickMacros"] = reconcile_references(referenced, template["macros"])
    compile_variants(template)
    template["id"] = sha(dump({"template": template}))
    return manifest, template, shared, notes


def configure_plan(client, character, addons, macros=None, clicks=None):
    client, character = client.resolve(), character.resolve()
    roots, state = read_state(client, character)
    manifest, template, shared, notes = build_template(addons, macros, clicks)
    # Installing packages is offline; never replace existing addon versions.
    files = install_plan(addons, manifest, client)
    # helper_plan may enable detection for other accounts; keep this account only.
    for key in list(files):
        if key.startswith("WTF/") and not key.startswith(character.parent.parent.relative_to(client).as_posix() + "/"):
            del files[key]
    state = copy.deepcopy(state) or {"schema": 1, "excluded": {}, "characters": {}}
    state.setdefault("excludedNames", {})
    for char in characters(client):
        if char.parent.parent != character.parent.parent:
            continue
        info = identity(char)
        if info:
            state["excluded"][info["guid"]] = True
        else:
            # Fail closed for names without a GUID. This intentionally also
            # excludes a future same-name character on another realm.
            state["excludedNames"][char.name.replace("-", " ")] = True
            notes.append("Existing character excluded by name (all realms): " + char.name)
    # Keep each pending import's original content and completed stages. Compile
    # the new policy from that original content, not from a newly chosen backup.
    for record in state.get("characters", {}).values():
        pending = record.get("template")
        if record.get("done") or not isinstance(pending, dict) or pending.get("macroPolicy") == POLICY_VERSION:
            continue
        if any(record.get(key) for key in ("macros", "clicks", "slots", "slotsQueued", "macroPolicyApplied")):
            notes.append("Pending macro policy not upgraded: bindings were already applied for " + record.get("full", "unknown character") + ". Use manual macro restore to change them.")
            continue
        compile_variants(pending)
        pending["id"] = sha(dump({"template": {k:v for k,v in pending.items() if k != "id"}}))
        notes.append("Updated macro policy for pending character: " + record.get("full", "unknown character") + ". Original settings and progress are retained.")
    state.update(enabled=True, template=template)
    roots[STATE] = state
    files[state_path(client, character)] = dump(roots)
    account = character.parent.parent.relative_to(client).as_posix()
    for addon, data in shared.items():
        relative = account + "/SavedVariables/" + addon + ".lua"
        if rooted(client, relative).exists():
            notes.append("Shared settings kept and inherited: " + addon)
        else:
            files[relative] = dump(data)
            notes.append("Shared account settings seeded once (affects this account): " + addon)
    notes += [
        f"Automatic private profiles: {len(template['profiles'])}; character setting files: {len(template['characters'])}.",
        "Existing characters are excluded. Only unseen level-1 characters are initialized.",
        "Edit Mode: select the existing custom layout named 'default' once. If missing, setup waits until it is created/imported. Shared layout contents are not changed.",
        "Macros and Click Casting apply across classes. For a different class, named spells in explicit macro spell commands become null. Native Click Casting spell IDs are unchanged.",
        "Shared settings are inherited, not reset at each login. Captured chat geometry is applied once; key bindings and full Edit Mode layouts are not imported.",
        "The helper must stay enabled. Initial setup may reload the UI up to three times, including a final reload for restored chat windows; blocked operations remain pending (/wuisetup to retry).",
    ]
    return files, notes
