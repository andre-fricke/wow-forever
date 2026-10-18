"""Discover characters, identities and installed addon metadata."""

import re
from saved_variables import decode, parse, plain

HELPER = "WoWUITransferIdentity"


def characters(client):
    base = client / "WTF/Account"
    return sorted(
        p
        for p in base.glob("*/*/*")
        if p.is_dir()
        and p.parent.name != "SavedVariables"
        and (
            (p / "SavedVariables").is_dir()
            or (p / "AddOns.txt").exists()
            or (p / "config-cache.wtf").exists()
        )
    )


def identity(char):
    helper = char / "SavedVariables" / f"{HELPER}.lua"
    if helper.exists():
        info = plain(parse(helper.read_bytes()).get(HELPER, {}))
        if all(info.get(k) for k in ["name", "full", "realm", "guid", "class"]):
            return info
    # Existing beta saves can identify the template without installing a helper.
    account = char.parent.parent
    full = char.name.replace("-", " ", 1)
    name = char.name.split("-", 1)[0]
    info = {
        "name": name,
        "full": full,
        "realm": None,
        "guid": None,
        "class": None,
        "realmKey": None,
        "regional": None,
    }
    p = account / "SavedVariables/EllesmereUI.lua"
    if p.exists():
        d = plain(parse(p.read_bytes())).get("EllesmereUIDB", {})
        entries = [
            v
            for v in d.get("goldLedger", {}).get("chars", {}).values()
            if isinstance(v, dict) and v.get("name") == name
        ]
        realms = {v.get("realm") for v in entries if v.get("realm")}
        if len(realms) == 1:
            info["realm"] = realms.pop()
            for v in entries:
                if v.get("realm") == info["realm"]:
                    info["class"] = v.get("class")
    p = account / "SavedVariables/Questie.lua"
    if p.exists():
        d = plain(parse(p.read_bytes())).get("QuestieConfig", {}).get("char", {})
        keys = [full, name + " - " + (info["realm"] or char.parent.name)]
        for key in keys:
            if key in d:
                info["guid"] = d[key].get("guid") or info["guid"]
    p = char / "SavedVariables/Pawn.lua"
    if p.exists():
        d = plain(parse(p.read_bytes()))
        info["class"] = (
            d.get("PawnClassicScaleProviderOptions", {}).get("LastClass")
            or info["class"]
        )
        info["full"] = (
            d.get("PawnOptions", {}).get("LastPlayerFullName") or info["full"]
        )
    if not info["realm"] and not char.parent.name.isdigit():
        info["realm"] = char.parent.name
    if not all(info.get(k) for k in ["realm", "guid", "class"]):
        return None
    return info


def inventory(addons):
    result = {}
    if not addons.is_dir():
        return result
    for folder in sorted(addons.iterdir()):
        if not folder.is_dir():
            continue
        tocs = list(folder.glob("*.toc"))
        if not tocs:
            continue
        meta = {}
        for toc in tocs:
            for k, v in re.findall(
                r"^##\s*([^:]+):\s*(.*)$", decode(toc.read_bytes()), re.M
            ):
                meta.setdefault(k.strip(), set()).add(v.strip())
        result[folder.name] = {
            k: sorted(v)
            for k, v in meta.items()
            if k
            in [
                "Version",
                "Interface",
                "Title",
                "SavedVariables",
                "SavedVariablesPerCharacter",
                "Dependencies",
                "RequiredDeps",
            ]
        }
    return result
