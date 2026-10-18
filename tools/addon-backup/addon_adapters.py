"""Reviewed addon transfer policies and character/profile transformations."""

import copy
from dataclasses import dataclass
import re
from characters import HELPER
from saved_variables import Atom, scalar, parse, dump, encode, decode


# One policy registry drives support checks and character-file routing.
@dataclass(frozen=True)
class AddonPolicy:
    account: bool = False
    character: str = None


POLICIES = {
    "Atlas": AddonPolicy(True, None),
    "AtlasBIStooltips": AddonPolicy(True, None),
    "AtlasLootClassic": AddonPolicy(True, None),
    "AtlasLootContinued": AddonPolicy(True, None),
    "Auctionator": AddonPolicy(True, "replace"),
    "Bagnon": AddonPolicy(True, None),
    "Bartender4": AddonPolicy(True, None),
    "Blizzard_AuctionHouseUI": AddonPolicy(False, "preserve"),
    "Blizzard_ClientSavedVariables": AddonPolicy(False, "preserve"),
    "Blizzard_Communities": AddonPolicy(False, "preserve"),
    "Blizzard_DamageMeter": AddonPolicy(False, "replace"),
    "Blizzard_LegacyChallengeTracker": AddonPolicy(False, "preserve"),
    "Blizzard_Professions": AddonPolicy(False, "preserve"),
    "Blizzard_RaidUI": AddonPolicy(False, "replace"),
    "Blizzard_TimeManager": AddonPolicy(False, "replace"),
    "Chatify": AddonPolicy(True, None),
    "DBM-Core": AddonPolicy(False, "replace"),
    "DandersFrames": AddonPolicy(True, "custom"),
    "DandersMover": AddonPolicy(True, None),
    "Decursive": AddonPolicy(True, None),
    "Details": AddonPolicy(True, "custom"),
    "Details_EncounterDetails": AddonPolicy(False, "custom"),
    "Details_Streamer": AddonPolicy(True, None),
    "Details_Vanguard": AddonPolicy(False, "custom"),
    "EllesmereUIChat": AddonPolicy(False, "custom"),
    "ForeverDualGathering": AddonPolicy(True, None),
    "Grid2": AddonPolicy(True, None),
    "MinimapButtonButton": AddonPolicy(True, None),
    "MoveAny": AddonPolicy(True, "replace"),
    "Pawn": AddonPolicy(True, "custom"),
    "Prat-3.0": AddonPolicy(True, "custom"),
    "Questie": AddonPolicy(True, "custom"),
    "RXPGuides": AddonPolicy(True, "custom"),
    "RareScanner": AddonPolicy(True, None),
    "ShadowedUnitFrames": AddonPolicy(True, None),
    "TipTac": AddonPolicy(True, None),
}
REVIEWED = {name for name, policy in POLICIES.items() if policy.account}
CHAR_CONFIG = {
    name for name, policy in POLICIES.items() if policy.character == "replace"
}
CHAR_SPECIAL = {
    name for name, policy in POLICIES.items() if policy.character == "custom"
}
CHAR_BLIZZARD_RUNTIME = {
    name for name, policy in POLICIES.items() if policy.character == "preserve"
}


def identity_map(source, target):
    pairs = {
        source["full"]: target["full"],
        source["name"]: target["name"],
        source["guid"]: target["guid"],
        source["realm"]: target["realm"],
    }
    for sep in [" - ", "-"]:
        pairs[source["name"] + sep + source["realm"]] = (
            target["name"] + sep + target["realm"]
        )
    if source.get("realmKey") and target.get("realmKey"):
        pairs[source["realmKey"]] = target["realmKey"]
    if source.get("faction") and target.get("faction"):
        for key in ["realm", "realmKey"]:
            if source.get(key) and target.get(key):
                pairs[source["faction"] + " - " + source[key]] = (
                    target["faction"] + " - " + target[key]
                )
    return {k: v for k, v in pairs.items() if k and v}


def remap(value, mapping):
    if isinstance(value, dict):
        out = {}
        # A copied source entry takes precedence over a pre-existing target-name entry in the snapshot.
        for k, v in sorted(value.items(), key=lambda item: item[0] in mapping):
            nk = mapping.get(k, k)
            if nk in out and k not in mapping:
                raise ValueError("Ambiguous key mapping")
            out[nk] = remap(v, mapping)
        return out
    v = scalar(value)
    return (
        Atom(mapping[v])
        if isinstance(v, str) and v in mapping
        else copy.deepcopy(value)
    )


def retain(root, existing, keys):
    for k in keys:
        if k in existing:
            root[k] = copy.deepcopy(existing[k])
        else:
            root.pop(k, None)


def sanitize_account(name, roots, existing, source, target):
    out = copy.deepcopy(roots)
    # AceDB separates character/progress state from UI profiles.
    for key, root in out.items():
        if not isinstance(root, dict):
            continue
        old = existing.get(key, {})
        if not isinstance(old, dict):
            old = {}
        if "profileKeys" in root:
            retain(root, old, ["char", "realm", "factionrealm", "factionrealmregion"])
    if name == "Questie" and isinstance(out.get("QuestieConfig"), dict):
        g = out["QuestieConfig"].get("global", {})
        old = existing.get("QuestieConfig", {}).get("global", {})
        retain(
            g,
            old,
            [
                "lastKnownDailyReset",
                "unavailableDailyQuestsByNpc",
                "unavailableQuestsDeterminedByTalking",
            ],
        )
    if name == "RareScanner":
        g = out.get("RareScannerDB", {}).get("global", {})
        old = existing.get("RareScannerDB", {}).get("global", {})
        retain(
            g,
            old,
            [
                "containers_found",
                "dragon_glyphs_collected",
                "npc_counters",
                "container_counters",
                "rares_found",
                "recentlySeen",
                "events_found",
            ],
        )
    if name == "Auctionator":
        retain(
            out,
            existing,
            [
                "AUCTIONATOR_PRICE_DATABASE",
                "AUCTIONATOR_POSTING_HISTORY",
                "AUCTIONATOR_VENDOR_PRICE_CACHE",
                "AUCTIONATOR_SAVEDVARS",
            ],
        )
    if name == "RXPGuides":
        root = out.get("RXPData", {})
        if isinstance(root, dict):
            retain(
                root,
                existing.get("RXPData", {}),
                [
                    "cache",
                    "cacheVersion",
                    "questNames",
                    "realmData",
                    "gameVersion",
                    "maxLoadTime",
                ],
            )
    if name == "EllesmereUI":
        root = out.get("EllesmereUIDB", {})
        old = existing.get("EllesmereUIDB", {})
        retain(
            root,
            old,
            [
                "goldLedger",
                "dataBarsGold",
                "characterGold",
                "warbandGold",
                "qolUpgradeCalcChars",
                "xpBarChars",
                "restoreOnUninstall",
                "gfxBackup",
                "friendlyPlateVisSaved",
                "chatTellMuted",
                "bagCurrencyByChar",
                "cdmCachedBarSizes",
                "lastSpecByChar",
            ],
        )
        # Apply the captured visual profile; do not let a beta-spec switch select a different one.
        root["specProfiles"] = {}
        if source["class"] != target["class"]:
            retain(root, old, ["clickCast", "profileKeybinds"])
    if name.startswith("EllesmereUI"):

        def clean(node, old):
            if not isinstance(node, dict):
                return
            old = old if isinstance(old, dict) else {}
            retain(
                node,
                old,
                [
                    "goldLedger",
                    "characterGold",
                    "dataBarsGold",
                    "warbandGold",
                    "qolUpgradeCalcChars",
                    "xpBarChars",
                ],
            )
            for k, v in list(node.items()):
                clean(v, old.get(k, {}))

        for k, v in out.items():
            clean(v, existing.get(k, {}))
    if name == "DandersFrames":
        if source["class"] != target["class"]:
            retain(out, existing, ["DandersFramesClickCastingDB"])
        root = out.get("DandersFramesDB_v2", {})
        if isinstance(root, dict):
            retain(root, existing.get("DandersFramesDB_v2", {}), ["debugLog"])
        retain(out, existing, ["DandersFramesDebugDB"])
    if name == "Pawn" and source["class"] != target["class"]:
        scales = out.get("PawnCommon", {}).get("Scales", {})
        olds = existing.get("PawnCommon", {}).get("Scales", {})
        for key, scale in scales.items():
            if isinstance(scale, dict):
                retain(scale, olds.get(key, {}), ["PerCharacterOptions"])
    if name.startswith("DBM-"):
        for key in list(out):
            if "Stats" in key or key == "DBM_Keystones":
                retain(out, existing, [key])
    return out


def profile_aliases(identity, addon):
    aliases = [identity["full"], identity["name"] + " - " + identity["realm"]]
    if addon == "RXPGuides":
        aliases.insert(
            0,
            identity["name"] + " - " + (identity.get("realmKey") or identity["realm"]),
        )
    return list(dict.fromkeys(aliases))


def destination_profile(profiles, keys, aliases, full_name):
    """Choose a private target profile without overwriting another character's profile."""
    other_profiles = {
        scalar(value) for key, value in keys.items() if key not in aliases
    }
    target_profiles = {scalar(keys[key]) for key in aliases if key in keys}
    number = 0
    while True:
        suffix = (
            ""
            if number == 0
            else " [UI Backup" + ("" if number == 1 else " " + str(number)) + "]"
        )
        candidate = full_name + suffix
        if candidate not in other_profiles and (
            candidate not in profiles or candidate in target_profiles
        ):
            return candidate
        number += 1


def account_config(name, data, target_data, source, target):
    roots = parse(data)
    existing = parse(target_data) if target_data else {}
    mapping = identity_map(source, target)
    source_aliases = profile_aliases(source, name)
    target_aliases = profile_aliases(target, name)
    if name == "RXPGuides":
        mapping[source_aliases[0]] = target_aliases[0]
    # Remap imported data first. Destination progress/caches are restored below
    # and must never pass through the source-to-target identity mapping.
    out = sanitize_account(name, remap(roots, mapping), existing, source, target)
    for rootkey, original in roots.items():
        if not isinstance(original, dict) or "profileKeys" not in original:
            continue
        keys = original["profileKeys"]
        profiles = original.get("profiles", {})
        chosen = next(
            (scalar(keys[key]) for key in source_aliases if key in keys), None
        )
        if chosen is None and "Default" in profiles:
            chosen = "Default"
        old = existing.get(rootkey, {})
        if not isinstance(old, dict):
            old = {}
        root = out[rootkey]
        root["profileKeys"] = copy.deepcopy(old.get("profileKeys", {}))
        root["profiles"] = copy.deepcopy(old.get("profiles", {}))
        if chosen is None:
            continue
        if chosen not in profiles:
            raise ValueError(
                "Selected addon profile is missing: " + name + " / " + str(chosen)
            )
        selected = destination_profile(
            root["profiles"], root["profileKeys"], target_aliases, target["full"]
        )
        root["profiles"][selected] = remap(profiles[chosen], mapping)
        for alias in target_aliases:
            root["profileKeys"][alias] = Atom(selected)
    return dump(out)


def character_config(name, data, target_data, source, target):
    # Identity belongs to the destination and must never be restored from a template.
    if name == HELPER:
        return target_data
    mapping = identity_map(source, target)
    src = remap(parse(data), mapping)
    dst = parse(target_data) if target_data else {}
    out = copy.deepcopy(dst)
    if name in CHAR_CONFIG:
        return dump(src)
    if name in CHAR_BLIZZARD_RUNTIME or name in [
        "Questie",
        "Prat-3.0",
        "EllesmereUIChat",
        "Details_EncounterDetails",
        "Details_Vanguard",
    ]:
        return target_data
    if name == "DandersFrames":
        root = out.setdefault("DandersFramesCharDB", {})
        for key in ["currentProfile", "languageOverride"]:
            if key in src.get("DandersFramesCharDB", {}):
                root[key] = copy.deepcopy(src["DandersFramesCharDB"][key])
        # Keep the captured layout active while retaining target assignments for later use.
        root["enableSpecSwitch"] = Atom(False)
        root.setdefault("specProfiles", {})
    elif name == "RXPGuides":
        local = src.get("RXPCData", {}).get("localDB")
        if local is not None:
            out.setdefault("RXPCData", {})["localDB"] = copy.deepcopy(local)
        if isinstance(src.get("RXPCSettings"), dict):
            out["RXPCSettings"] = copy.deepcopy(src["RXPCSettings"])
    elif name == "Pawn":
        root = out.setdefault("PawnOptions", {})
        for k, v in src.get("PawnOptions", {}).items():
            if k not in [
                "ItemLevels",
                "LastPlayerFullName",
                "LastVersion",
                "AutoSelectScales",
            ]:
                root[k] = copy.deepcopy(v)
        root["LastPlayerFullName"] = Atom(target["full"])
        if source["class"] == target["class"] and "AutoSelectScales" in src.get(
            "PawnOptions", {}
        ):
            root["AutoSelectScales"] = copy.deepcopy(
                src["PawnOptions"]["AutoSelectScales"]
            )
    elif name == "Details":
        root = out.setdefault("_detalhes_database", {})
        for k in ["active_profile", "local_instances_config", "window_scale"]:
            if k in src.get("_detalhes_database", {}):
                root[k] = copy.deepcopy(src["_detalhes_database"][k])
    else:
        raise ValueError("Character file requires an adapter: " + name)
    return dump(out)


UI_CVAR = re.compile(
    r"^(?:uiScale$|useUiScale$|Brightness$|Contrast$|Gamma$|nameplate|raidFrames|damageMeter|showQuestLevel$|chat|floatingCombatText|UnitName|unitName|showTarget|showParty|showArena|colorblind|colorBlind|profanityFilter|buffDurations$|showCastableBuffs$|showDispelDebuffs$|statusText|displaySpellActivationOverlays$)",
    re.I,
)


def merge_cvars(source, target):
    values = {
        k: v
        for k, v in re.findall(r"^SET (\S+) (.*)$", decode(source), re.M)
        if UI_CVAR.match(k)
    }
    lines = decode(target or b"").splitlines()
    seen = set()
    out = []
    for line in lines:
        m = re.match(r"^SET (\S+) (.*)$", line)
        if m and m[1] in values:
            out.append("SET " + m[1] + " " + values[m[1]])
            seen.add(m[1])
        else:
            out.append(line)
    out.extend("SET " + k + " " + v for k, v in values.items() if k not in seen)
    return encode("\n".join(out) + "\n")


def merge_chat(source, target):
    if not target:
        return source
    sa = decode(source).split("WINDOW ")
    sb = decode(target).split("WINDOW ")
    fields = (
        r"(?:NAME|SIZE|COLOR|LOCKED|UNINTERACTABLE|DOCKED|SHOWN|POSITION|DIMENSIONS)"
    )
    source_windows = {part.splitlines()[0].strip(): part for part in sa[1:]}
    for i in range(1, len(sb)):
        key = sb[i].splitlines()[0].strip()
        if key not in source_windows:
            continue
        geometry = re.findall(r"^" + fields + r" [^\r\n]+", source_windows[key], re.M)
        sb[i] = re.sub(r"^" + fields + r" [^\r\n]+[\r\n]*", "", sb[i], flags=re.M)
        first, _, tail = sb[i].partition("\n")
        sb[i] = first + "\n" + "\n".join(geometry) + "\n" + tail
    return encode("WINDOW ".join(sb))
