"""Validated macro slot snapshots; no game code is executed by Python."""
from saved_variables import parse, plain
from characters import HELPER
import zipfile


def placement_member(manifest):
    return "client/" + manifest["source_character"] + "/SavedVariables/" + HELPER + ".lua"


def has_placement(archive, manifest):
    member = placement_member(manifest)
    if member not in manifest["files"]:
        return False
    with zipfile.ZipFile(archive) as z:
        return "WoWUITransferBars" in parse(z.read(member))


def placement_snapshot(data):
    snapshot = plain(parse(data)).get("WoWUITransferBars")
    if not isinstance(snapshot, dict) or snapshot.get("schema") not in (1, 2):
        raise ValueError("Macro slot snapshot missing. Update the identity helper, log in with the source character and quit WoW before backing up.")
    slots = snapshot.get("slots")
    if not isinstance(slots, dict):
        raise ValueError("Invalid macro slot snapshot")
    if snapshot["schema"] == 1 and not slots:
        raise ValueError("This empty macro slot snapshot was captured by the old helper and is not reliable. Update the helper, log in with the source character, quit WoW and create a new macro backup.")
    if snapshot["schema"] == 2:
        if snapshot.get("unresolvedSlots"):
            raise ValueError("The helper could not identify all macro slots (possibly duplicate macro names). Give macros unique names, log in/out with the source character and create a new backup.")
        if type(snapshot.get("macroActions")) is not int or snapshot["macroActions"] != len(slots):
            raise ValueError("Incomplete macro slot capture. Log in/out with the updated helper and create a new backup.")
    for slot, entry in slots.items():
        if (
            type(slot) is not int or not 1 <= slot <= 180
            or not isinstance(entry, dict)
            or entry.get("scope") not in ("character", "account")
            or not isinstance(entry.get("name"), str)
            or not isinstance(entry.get("body"), str)
        ):
            raise ValueError("Invalid macro slot entry")
    return snapshot
