"""Support assessment and explicit opt-out for unknown configurations."""

import copy
import re
from pathlib import PurePosixPath
from characters import HELPER, inventory
from saved_variables import parse
from addon_adapters import REVIEWED, CHAR_CONFIG, CHAR_SPECIAL, CHAR_BLIZZARD_RUNTIME
from legacy import english_legacy_text


def active_saved_files(client, char):
    installed = inventory(client / "Interface/AddOns")
    account = char.parent.parent
    return installed, [
        p for p in (account / "SavedVariables").glob("*.lua") if p.stem in installed
    ]


def audit_support(client, char):
    installed, files = active_saved_files(client, char)
    unsupported = []
    for p in files:
        d = parse(p.read_bytes())
        if (
            p.stem not in REVIEWED
            and not p.stem.startswith(("EllesmereUI", "DBM-"))
            and not all(isinstance(v, dict) and "profileKeys" in v for v in d.values())
        ):
            unsupported.append("Account file: " + p.name)
    for p in (char / "SavedVariables").glob("*.lua"):
        if p.stem not in installed and not p.stem.startswith("Blizzard_"):
            continue
        if (
            p.stem not in CHAR_CONFIG | CHAR_SPECIAL | CHAR_BLIZZARD_RUNTIME
            and p.stem != HELPER
        ):
            unsupported.append("Character file: " + p.name)
    return unsupported


def pending_reviews(manifest):
    # A snapshot records support at creation time. Newly reviewed account
    # adapters also apply to existing archives without rewriting the backup.
    pending = []
    for item in manifest.get("unsupported", []):
        normalized = english_legacy_text(item)
        prefix = "Account file: "
        if normalized.startswith(prefix):
            filename = normalized[len(prefix) :]
            if filename.endswith(".lua") and filename[:-4] in REVIEWED:
                continue
        pending.append(normalized)
    return pending


def skip_unknown_addons(manifest):
    skipped = set()
    for item in pending_reviews(manifest):
        match = re.fullmatch(r"(?:Account|Character) file: ([^/\\]+)\.lua", item)
        if not match:
            raise ValueError("Cannot safely skip this review item: " + item)
        skipped.add(match.group(1))
    result = copy.deepcopy(manifest)
    result["skipped_addons"] = sorted(skipped)
    result["unsupported"] = []
    result["addons"] = {k: v for k, v in result["addons"].items() if k not in skipped}
    result["files"] = {
        k: v
        for k, v in result["files"].items()
        if not (
            PurePosixPath(k).parent.name == "SavedVariables"
            and PurePosixPath(k).stem in skipped
        )
    }
    return result
